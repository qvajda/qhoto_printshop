# Group mockup — design (pipeline stage 8/12)

Date: 2026-07-12
Spec basis: SPEC_v4.10.md section 3 step 7; CLAUDE.md hard constraints (aspect-ratio-group
rule, single-image-generation-per-design rule, discrete-scheduled-function rule).

## 1. Purpose

`pipeline/group_mockup.py` creates the Gelato products for the 5x7 group and the 10x24
group once a candidate's primary group has published (`groups.status = 'approved_published'`
on its `group_type='primary'` row). Each group is its own aspect ratio, genuinely different
from the primary, re-cropped/composed from the same already-approved
`candidates.base_image_url` — no new Replicate/FLUX call, per CLAUDE.md's "a design is only
ever image-generated once" constraint.

## 2. Scope

**Owns:** finding candidates whose primary group just published and don't yet have a
completed 5x7/10x24 `group_products` row; creating/reusing the `groups` row for each of those
two group_types; calling Gelato `create_product_from_template` against that group_type's own
template; polling until ready; writing the ordered `product_images` gallery; retry-once on
operational failure.

**Does not own:** critic-passing the resulting gallery (`group_critic_pass.py`, stage 9),
sending the follow-up Telegram digest entry (`group_digest.py`, stage 10), reading the
admin's approve/edit/reject on it (`publish_group.py`, stage 11), or the 3-attempt
critic-pass retry cap / DELETE-on-abandon rule (that's stage 9's contract, scoped to
`critic_pass_attempts` and the critic-pass rubric — this stage never critic-passes anything).
This stage's job ends once each group's Gelato product + `group_products`/`product_images`
rows exist and `groups.status = 'pending_review'`.

**Trigger pattern:** discrete scheduled batch-scan function (`run_group_mockup_cycle`), same
shape as `primary_mockup.run_primary_mockup_cycle` — not called inline from
`publish_primary_group.py`. Matches CLAUDE.md's "one function per pipeline stage... discrete
scheduled functions" constraint; the orchestrating twice-daily-batch cron calls each stage
function in sequence, which is what satisfies the spec's "same evening run" wording without
coupling stages in-process.

## 3. Data model

No new tables/columns. `groups.group_type` already includes `'5x7'`/`'10x24'` in its CHECK
constraint (schema.sql), and `group_products.size` already includes `'5x7'`/`'10x24'`. One
`groups` row per (candidate_id, group_type) as usual (`UNIQUE(candidate_id, group_type)`),
one `group_products` row per group (each of these two group_types maps to exactly one size,
per `static_config["aspect_ratio_groups"]`: `"5x7": ["5x7"]`, `"10x24": ["10x24"]` — unlike
`primary`'s four sizes).

Orientation is hardcoded `'portrait'`, matching every existing stage — `candidates` carries
no orientation field, and this is consistent with `primary_mockup.py`/
`publish_primary_group.py`'s existing assumption.

## 4. Function signatures

```python
# pipeline/group_mockup.py

def get_or_create_group(conn, candidate_id: int, group_type: str, *, now=None) -> int:
    """Generalizes primary_mockup.get_or_create_primary_group to any group_type.
    Returns existing groups.id for (candidate_id, group_type) or inserts a new row with
    status='pending_generation'."""

def create_group_mockup(conn, candidate_id: int, group_type: str, *, static_config=None,
                         store_id=None, api_key=None, poll_interval=3.0, poll_timeout=90.0,
                         now=None) -> dict:
    """One group_type for one candidate, end to end:
    - get_or_create_group
    - skip (return early) if a group_products row for this group already has
      status in ('created', 'published') — idempotent re-run guard, same convention as
      publish_primary_group.py's existing_row checks
    - else create/reuse a 'pending' group_products row (size = the group_type's single size,
      orientation='portrait', template + price from config.get_template_variant/prices_eur)
    - create_product_from_template(candidate['base_image_url'], ...) -> poll_until_ready
      (reusing primary_mockup.poll_until_ready) -> isPrimary-first gallery ordering
      (same pattern as create_gelato_product in publish_primary_group.py)
    - retry the create-then-poll sequence once on any exception (same attempt()/attempt()
      shape as publish_primary_group.publish_group_product)
    - success: group_products.status='created', product_images rows inserted,
      groups.status='pending_review'
    - failure after retry: group_products.status='mockup_failed', groups.status left at
      'pending_generation' (not a terminal state) so the next cycle retries it; re-raises
      to the caller, which is caught per-group_type so one failing group never blocks
      the other."""

def run_group_mockup_cycle(conn, *, static_config=None, store_id=None, api_key=None,
                            poll_interval=3.0, poll_timeout=90.0, now=None) -> list:
    """Selects candidates whose primary group has status='approved_published', for each of
    the two group_types ('5x7', '10x24') where that candidate doesn't yet have a
    group_products row with status in ('created', 'published') for that group_type's size,
    calls create_group_mockup, catches+logs exceptions per group_type/candidate (continues
    past failures, same convention as run_primary_mockup_cycle), returns processed results."""
```

## 5. Selection query

```sql
SELECT DISTINCT c.id
FROM candidates c
JOIN groups g ON g.candidate_id = c.id AND g.group_type = 'primary' AND g.status = 'approved_published'
```

then, per candidate, per group_type in `('5x7', '10x24')`:

```sql
SELECT gp.id FROM group_products gp
JOIN groups g ON g.id = gp.group_id
WHERE g.candidate_id = ? AND g.group_type = ? AND gp.status IN ('created', 'published')
```

— if this returns a row, skip; otherwise call `create_group_mockup`. This mirrors
`publish_primary_group.py`'s per-size `existing_row` check and `run_primary_mockup_cycle`'s
`NOT IN` guard, adapted to two independent group_types instead of one candidate-status gate.

## 6. Error handling summary

- Gelato create/poll operational failure: retry the whole create-then-poll sequence once
  (per SPEC_v4.10.md section 3 step 7: "retry once automatically"); if it still fails,
  `group_products.status='mockup_failed'`, `groups.status` stays `'pending_generation'` so
  the next `run_group_mockup_cycle` run retries it, and processing continues with the other
  group_type/candidate.
- No critic-pass logic, no 3-attempt cap, no DELETE-on-abandon here — those are
  `group_critic_pass.py`'s contract once a gallery exists and is critic-passed.
- `dry_run` threads through `gelato_client.create_product_from_template` exactly as it does
  in `primary_mockup.py`/`publish_primary_group.py` — synthesizes a single placeholder image
  when `response.get("_dry_run")` is truthy, so the full cycle is testable without live Gelato
  calls.

## 7. Testing approach

TDD per project convention, mocking `gelato_client` at its existing seam (same style as
`primary_mockup.py`'s test suite): `get_or_create_group` reuse-vs-create, the idempotent
skip-if-already-created guard, successful create+poll+gallery-ordering for both group_types
independently, retry-once-then-mockup_failed on repeated exceptions, and
`run_group_mockup_cycle`'s selection query (only picks up `approved_published` primary
groups, skips candidates that already have both 5x7/10x24 created, continues past one
group_type's failure to still process the other).
