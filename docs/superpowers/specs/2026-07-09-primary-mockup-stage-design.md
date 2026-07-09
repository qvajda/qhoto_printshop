# Primary Mockup Stage (`primary_mockup.py`) — Design

**Status:** approved by Quentin 2026-07-09
**Scope:** `pipeline/primary_mockup.py`, the third of 12 M1 pipeline stage modules. Renders
the design onto **one** Gelato poster product at the candidate's primary size (21x29.7cm /
8x12″, portrait only for M1), per SPEC_v4.10.md section 3 step 3. Consumes `generate.py`'s
output (`status='generating' AND base_image_url IS NOT NULL` rows); is itself consumed by
the not-yet-built `compliance_draft.py`.

## Non-goals

- No other size and no other group (5x7/10x24) — those only happen after human approval
  (SPEC section 3 step 7), a much later stage.
- No compliance-draft text generation, no alt text generation (`compliance_draft.py`'s job
  — this stage writes a `''` placeholder for `product_images.alt_text`, see section 4).
- No critic-pass evaluation or regenerate-retry orchestration (`critic_pass.py`'s job,
  future stage) — `create_primary_mockup` is a single, one-shot attempt; retry policy
  (calling `generate_for_candidate` again with a `correction_note`, then this stage again)
  lives entirely in the future `critic_pass.py`.
- No orientation selection — hardcoded portrait, per `generate.py`'s existing deferred-
  feature note (no `candidates.orientation` column exists).

## 1. Function signatures

```python
def build_mockup_title(candidate: dict) -> str:
    """Pure, no I/O. Gelato's *internal* product title only — not the eventual Etsy
    listing title (compliance_draft.py generates that later, SPEC section 3 step 4)."""

def get_or_create_primary_group(conn, candidate_id: int, *, now=None) -> int:
    """Finds the existing groups row (candidate_id, group_type='primary') or inserts one
    (status='pending_generation'). Returns group_id. Idempotent — safe to call again."""

def poll_until_ready(product_id: str, *, store_id: str = None, api_key: str = None,
                      poll_interval: float = 3.0, timeout: float = 90.0,
                      sleep_fn=time.sleep, now_fn=time.monotonic) -> dict:
    """Calls gelato_client.get_product() repeatedly until isReadyToPublish is True.
    Raises GelatoMockupTimeoutError after timeout seconds elapsed without success.
    sleep_fn/now_fn are injectable so tests don't actually sleep."""

def create_primary_mockup(conn, candidate_id: int, *, static_config: dict = None,
                           store_id: str = None, api_key: str = None,
                           poll_interval: float = 3.0, poll_timeout: float = 90.0,
                           now=None) -> dict:
    """One ready candidate -> one Gelato product at 8x12 portrait. See section 3 for the
    full step-by-step flow. Returns {"group_id", "group_product_id", "gelato_product_id"}.
    Does not touch candidates.status (see section 5)."""

def run_primary_mockup_cycle(conn, *, static_config: dict = None, store_id: str = None,
                              api_key: str = None, poll_interval: float = 3.0,
                              poll_timeout: float = 90.0, now=None) -> list[int]:
    """Batch entry point (morning run). Selects every ready-and-not-yet-mocked-up
    candidate (section 2's predicate) and calls create_primary_mockup on each, isolating
    per-candidate failures with the same try/except-and-continue pattern as
    generate.run_generate_cycle, so one candidate's Gelato outage doesn't abort the batch."""
```

**Reads from the candidate row:** `id`, `niche`, `base_image_url`.
**Writes:** a `groups` row (`group_type='primary'`), a `group_products` row (one per call —
see section 6), N `product_images` rows. Does not modify the `candidates` row at all.

## 2. Selection predicate (`run_primary_mockup_cycle`)

Continuing the combined-check convention `generate.py` established (no new `candidates`
status value):

```sql
SELECT id FROM candidates
WHERE status = 'generating'
  AND base_image_url IS NOT NULL
  AND id NOT IN (
    SELECT g.candidate_id FROM groups g
    JOIN group_products gp ON gp.group_id = g.id
    WHERE g.group_type = 'primary'
  )
```

This means a candidate whose only `group_products` row is `'mockup_failed'` (section 4)
will **not** be picked up again automatically — a stalled/failed mockup needs deliberate
retry (future `critic_pass.py` machinery, or a manual re-run of `create_primary_mockup`
directly), not silent reprocessing by the batch cycle. This mirrors how `generate.py`
leaves failed candidates at `status='pending'` rather than auto-retrying them within the
same cycle.

## 3. `create_primary_mockup` step-by-step

1. Read the candidate row; raise `ValueError` if missing (same style as
   `generate_for_candidate`).
2. `get_or_create_primary_group(conn, candidate_id)` → `group_id`.
3. Resolve the 8x12/portrait template via `config.get_template_variant(static_config,
   "8x12", "portrait")`.
4. `INSERT INTO group_products` — `status='pending'`, `size='8x12'`,
   `orientation='portrait'`, `gelato_template_id=<resolved template_id>`,
   `price_eur=static_config["prices_eur"]["8x12"]`.
5. Call `gelato_client.create_product_from_template(template_id, template_variant_id,
   image_placeholder_name, candidate['base_image_url'], build_mockup_title(candidate),
   store_id=store_id, api_key=api_key)`.
6. `UPDATE group_products SET gelato_product_id = <response id>`.
7. **Branch on dry-run** (section 4): if the response carries `_dry_run: True`, skip
   polling and synthesize one placeholder gallery entry. Otherwise call
   `poll_until_ready(gelato_product_id, ...)`.
8. On success: sort the polled product's `productImages` (`isPrimary=True` first, then
   response order) and `INSERT INTO product_images` one row per image —
   `gallery_order=0,1,2,...`, `image_type='flat_mockup'` for the primary image and
   `'lifestyle'` for the rest, `alt_text=''` (placeholder — see section 4).
9. `UPDATE group_products SET status='created'`.
10. `UPDATE groups SET status='pending_review'`.
11. Return `{"group_id", "group_product_id", "gelato_product_id"}`.

**On failure at step 5, 7, or `poll_until_ready` timing out:** `UPDATE group_products SET
status='mockup_failed', updated_at=...` before re-raising. `groups.status` stays
`'pending_generation'` (still true — no product exists yet). The exception propagates to
the caller; `run_primary_mockup_cycle` catches and isolates it per candidate (section 2's
predicate already excludes rows with *any* `group_products` row, so a `'mockup_failed'`
row correctly prevents the batch cycle from silently re-attempting it).

## 4. Schema change: `group_products.status` gains `'mockup_failed'`

```sql
status TEXT NOT NULL CHECK(status IN (
  'pending','created','mockup_failed','publish_failed','published','deleted'
)),
```

Distinguishes a Gelato product-creation/render failure (this stage) from an Etsy publish
failure (`publish_failed`, a later stage's concern) — same row, two different failure
modes at two different points in its lifecycle, so they need distinct terminal-ish states
rather than overloading one.

## 5. Status semantics summary

- **`candidates.status`** — unchanged by this stage, stays `'generating'` throughout
  mockup + compliance-draft + critic-pass. Per your confirmation, `'primary_review'` gets
  set later, by `critic_pass.py`, once the primary group actually passes and is about to
  reach the Telegram digest — matching the enum value's name ("in primary review," i.e.
  under human review) rather than "mockup exists." `compliance_draft.py`'s selection
  predicate (next stage) will need its own combined check (e.g. `status='generating' AND`
  a `'created'` `group_products` row exists for the primary group), same pattern as
  section 2 here.
- **`groups.status`** — `'pending_generation'` (on insert, before any product exists) →
  `'pending_review'` (once the mockup's `product_images` are written — covers the
  compliance-draft + critic-pass span, not just literal human review, since there's no
  finer-grained enum value between "needs a product" and "needs a decision").
- **`group_products.status`** — `'pending'` (row inserted, no Gelato product yet) →
  `'created'` (poll succeeded, images written) OR `'mockup_failed'` (create/poll failed —
  new value, section 4). `'publish_failed'`/`'published'`/`'deleted'` remain untouched by
  this stage (Etsy-publish and cleanup stages' concern).

## 6. Retry-safety: always insert cleanly

`create_primary_mockup` always inserts a **fresh** `group_products` row — it does not
look for or reuse an existing one for the group, even on a second call. If a future
`critic_pass.py` retry calls `generate_for_candidate` again (fresh base image) and then
`create_primary_mockup` again for the same candidate, a second `group_products` row is
created; cleaning up the superseded Gelato product (via `gelato_client.delete_product`) is
`critic_pass.py`'s job at that point, not this stage's. `get_or_create_primary_group` is
the only find-or-create in this module — the `groups` row itself is genuinely one-per-
candidate-per-group-type (schema `UNIQUE(candidate_id, group_type)`), but `group_products`
rows are attempt-scoped.

## 7. Dry-run polling short-circuit

`gelato_client.get_product()` has no `dry_run` parameter, and
`create_product_from_template`'s dry-run mock response (`_dry_run: True`,
`isReadyToPublish: False`, `productImages: []`) never becomes "ready." Rather than
changing `gelato_client.py` (out of scope — it's already-merged, tested code from a prior
stage), `create_primary_mockup` checks the create response for `_dry_run` and, if present,
skips `poll_until_ready` entirely: it synthesizes a single placeholder `product_images` row
(`image_type='flat_mockup'`, `gallery_order=0`, `image_url` = the dry-run response's
`previewUrl` — `None` in the current mock shape, so literally `None`/a fixed placeholder
string) instead of calling `get_product`. This keeps the whole flow runnable end-to-end
against placeholders without a live Gelato call, consistent with CLAUDE.md's placeholder-
testing policy.

## 8. `alt_text` placeholder

`product_images.alt_text` is `NOT NULL`, but alt text is `compliance_draft.py`'s job (SPEC
section 3 step 4, a later stage). This stage inserts `alt_text=''` for every row;
`compliance_draft.py` is expected to `UPDATE product_images SET alt_text = ... WHERE id =
...` once it runs, for every image in the gallery this stage just created.

## 9. Poll interval / timeout defaults

Defaults: `poll_interval=3.0` seconds, `timeout=90.0` seconds. Calibrated against the one
real observed Gelato render (`docs/gelato_call_response_example_from_manual_tests.txt`):
product `createdAt` `12:41:50` → `isReadyToPublish: true` at `updatedAt` `12:41:59`, ~9
seconds for a 4-image gallery — a 90s timeout is a ~10x margin over that single sample.
`GelatoMockupTimeoutError` message follows `ReplicatePredictionTimeoutError`'s precedent:
states the product ID, elapsed time, and that this likely indicates a Gelato-side delay or
outage rather than a pipeline bug.

## 10. File / module layout

```
pipeline/
  primary_mockup.py
tests/
  test_primary_mockup.py
```

Depends on already-merged `pipeline/gelato_client.py` (`create_product_from_template`,
`get_product`), `pipeline/config.py` (`get_template_variant`), `pipeline/db.py`. Touches
`db/schema.sql` (section 4's `group_products.status` addition — the only schema change).
No changes to `config/static_config.json`, `.env.example`, or already-merged
`gelato_client.py`/`config.py` beyond that one CHECK-constraint edit.
