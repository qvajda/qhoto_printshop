# Group critic pass — design (pipeline stage 9/12)

Date: 2026-07-13
Spec basis: SPEC_v4.10.md section 3 step 7 (5x7/10x24 review flow); CLAUDE.md hard
constraints (critic-pass retry cap / DELETE-on-abandon rule, aspect-ratio-group rule).
Prior art: pipeline/critic_pass.py (stage 5, same rubric/retry-cap pattern at the
primary-group level); docs/superpowers/specs/2026-07-12-group-mockup-design.md (stage 8,
what this stage consumes).

## 1. Purpose

`pipeline/group_critic_pass.py` runs the same critic-pass rubric `critic_pass.py` already
uses against the gallery of a candidate's 5x7 group or 10x24 group, once
`group_mockup.create_group_mockup` (stage 8) has produced it
(`groups.status='pending_review'`, that group's `group_products.status='created'`).

Pass: leave the group as-is for `group_digest.py` (stage 10) to send its own follow-up
Telegram entry. Fail: retry up to 3 attempts total (same cap/logging pattern as stage 5),
recreating that group's Gelato product between attempts. On the 3rd failure, abandon
**only that group** — DELETE its Gelato product, `groups.status='failed_abandoned'` — the
candidate itself and its other groups (primary, and the other of 5x7/10x24) are untouched.

## 2. Scope

**Owns:** critic-passing one group's gallery; the 3-attempt retry loop and its
`critic_pass_attempts` logging; recreating the group's Gelato product between failed
attempts (via stage 8's `create_group_mockup`); abandoning just that group on the 3rd
failure (DELETE Gelato product, terminal `groups.status`).

**Does not own:** creating the group's first Gelato product (stage 8, already done before
this stage runs), sending the follow-up digest (stage 10), reading the admin's decision
(stage 11), or anything about the primary group / Go-Hold-Kill fallback — a failed 5x7 or
10x24 group never touches `candidates.status` or the other group's rows.

**Also fixes (carried over from stage 8's review):** `group_mockup.create_group_mockup`'s
idempotency guard currently only checks `group_products.status`, not `groups.status`. Once
this stage introduces `groups.status='failed_abandoned'` as a real terminal state, a later
`run_group_mockup_cycle` run would resurrect an abandoned group — its `group_products` row
was deleted by the abandon step, so the existing `group_products`-only check finds nothing
and happily recreates the Gelato product, flipping `groups.status` back to
`pending_review`. Fixed as part of this stage: `create_group_mockup` fetches the group's
current status right after `get_or_create_group` and returns `None` early if it's
`failed_abandoned` or `rejected`.

## 3. Retry mechanics (confirmed with user)

Unlike the primary group's retry (`critic_pass.run_critic_pass`), which has a real lever
between attempts — `generate.generate_for_candidate(correction_note=...)` produces a
genuinely different FLUX image — a group's crop has no such lever: `create_group_mockup`
re-composes the same already-approved `base_image_url` into the same fixed Gelato template
every time, with no correction-note parameter. There is no prompt to vary.

Decision: retry anyway, by recreating the Gelato product between attempts (discard old
product + product_images rows via `critic_pass.discard_superseded_attempt`, then call
`group_mockup.create_group_mockup` again). This matches spec wording ("up to 3 crop/
composition retry attempts") literally and keeps the retry loop structurally identical to
stage 5's, even though in practice a retry is more of a re-roll (fresh Gelato render +
independent LLM critic judgment on a freshly fetched gallery) than a true correction.

## 4. Data model

No new tables/columns. Reuses `critic_pass_attempts` (already keyed by generic `group_id`,
not primary-specific), `groups.status` (already includes `'failed_abandoned'` in its CHECK
constraint), `group_products.status` (deletion via existing `discard_superseded_attempt`,
same as the primary-group Edit path in `publish_primary_group.py`).

## 5. Function signatures

```python
# pipeline/group_critic_pass.py

def get_group_critic_state(conn, group_id: int) -> dict:
    """Loads what evaluate_critic_pass needs for one group: group_product_id,
    ordered image_urls (from product_images, for the group_products row with
    status='created'), and the candidate's listing_text (title/description) — same
    shared draft the primary group used, per spec step 7 ('reusing the already-approved
    title/description as the base text'). Also returns candidate_id and group_type so the
    retry path can call create_group_mockup. Raises ValueError if no live group_products
    row exists (mirrors critic_pass.get_primary_group_state)."""

def abandon_group(conn, group_id: int, reason: str, *, now=None) -> None:
    """Sets groups.status='failed_abandoned', failed_reason=reason. Does NOT touch
    candidates or any other group's rows — this is the group-scoped analog of
    critic_pass.abandon_candidate, deliberately narrower."""

def run_group_critic_pass(conn, candidate_id: int, group_type: str, *, static_config=None,
                           anthropic_api_key=None, store_id=None, gelato_api_key=None,
                           now=None) -> dict:
    """One group, end to end — same shape as critic_pass.run_critic_pass:
    - look up groups row for (candidate_id, group_type), attempt_number = existing
      max(critic_pass_attempts.attempt_number) + 1
    - loop: get_group_critic_state -> critic_pass.evaluate_critic_pass (reused as-is,
      same rubric/prompt) -> critic_pass.record_critic_attempt (reused as-is)
    - pass: return {"passed": True, "attempts": attempt_number} (groups.status stays
      'pending_review' — nothing else to flip; stage 10 sends the digest from that state)
    - fail: critic_pass.discard_superseded_attempt(group_product_id) (reused as-is —
      DELETEs the Gelato product + product_images/group_products rows)
      - attempt_number >= 3: abandon_group(...), return {"passed": False, ...}
      - else: group_mockup.create_group_mockup(conn, candidate_id, group_type, ...)
        to recreate the product/gallery, attempt_number += 1, loop"""

def run_group_critic_pass_cycle(conn, *, static_config=None, anthropic_api_key=None,
                                 store_id=None, gelato_api_key=None, now=None) -> list:
    """Selects (candidate_id, group_type) pairs where group_type IN ('5x7', '10x24'),
    groups.status='pending_review', that group's live group_products.status='created',
    and the group hasn't already passed (group_id NOT IN critic_pass_attempts WHERE
    passed=1) — same NOT IN convention as critic_pass.run_critic_pass_cycle. Calls
    run_group_critic_pass per pair, catches+logs exceptions, continues past one
    group's failure to still process the others."""
```

Also, in `pipeline/group_mockup.py`:

```python
def create_group_mockup(...):
    ...
    group_id = get_or_create_group(conn, candidate_id, group_type, now=now)
    group_status = conn.execute(
        "SELECT status FROM groups WHERE id = ?", (group_id,)
    ).fetchone()["status"]
    if group_status in ("failed_abandoned", "rejected"):
        return None
    ...
```

## 6. Selection query

```sql
SELECT DISTINCT g.candidate_id, g.group_type
FROM groups g
JOIN group_products gp ON gp.group_id = g.id
WHERE g.group_type IN ('5x7', '10x24')
  AND g.status = 'pending_review'
  AND gp.status = 'created'
  AND g.id NOT IN (SELECT group_id FROM critic_pass_attempts WHERE passed = 1)
```

## 7. Error handling summary

- Critic-pass fail, attempts 1-2: discard the Gelato product (real DELETE call via
  `gelato_client.delete_product`, same as stage 5), recreate via `create_group_mockup`,
  retry.
- Critic-pass fail, attempt 3: discard the Gelato product, `groups.status =
  'failed_abandoned'`. No Go/Hold/Kill, no candidate-level change, no effect on the
  candidate's other groups (primary already published; the other of 5x7/10x24 is
  independent).
- Operational failure (not critic-pass fail) inside the recreate step: already
  `create_group_mockup`'s job (retry-once-then-`mockup_failed`, per stage 8's contract) —
  this stage doesn't add a second layer of operational retry, it just calls
  `create_group_mockup` and lets an exception propagate up to
  `run_group_critic_pass_cycle`'s per-pair catch, same as stage 8's own cycle function.
- `create_group_mockup`'s new terminal-status guard prevents `run_group_mockup_cycle` from
  ever resurrecting a group this stage abandoned.

## 8. Testing approach

TDD, mocking `anthropic_client`/`gelato_client` at their existing seams (same style as
`critic_pass.py`'s suite): `get_group_critic_state` happy path + missing-row error,
`abandon_group`'s narrow blast radius (asserting candidate/other-group rows are
untouched), full pass-on-first-attempt, fail-then-retry-then-pass, fail-3-times-then-abandon
(asserting the real DELETE call fires), `run_group_critic_pass_cycle`'s selection query
(only picks up `pending_review` groups with a `created` product, skips already-passed
groups, continues past one group's exception), and `create_group_mockup`'s new
terminal-guard regression test (a `failed_abandoned` group must not be resurrected by
`run_group_mockup_cycle`).
