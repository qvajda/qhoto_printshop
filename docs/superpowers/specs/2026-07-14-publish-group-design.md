# publish_group.py — design (pipeline stage 11/12)

Date: 2026-07-14
Spec basis: SPEC_v4.10.md section 3 step 7's 5x7/10x24 sub-bullet ("You approve/edit/reject
each of these two groups independently... Approving one publishes that group's single
listing the same way as the primary group... rejecting or editing behaves the same as it
does for the primary group, scoped to that one group"); CLAUDE.md hard constraints
(aspect-ratio-group rule, critic-pass/abandon rule).
Prior art: pipeline/publish_primary_group.py (stage 7, owns the poll loop and reusable
building blocks); pipeline/group_mockup.py (stage 8); pipeline/group_critic_pass.py (stage
9); pipeline/group_digest.py (stage 10, sends the follow-up digest this stage reacts to).

## 1. Purpose

`pipeline/publish_group.py` handles the Approve/Edit/Reject decision for a single 5x7 or
10x24 group, once `group_digest.py` (stage 10) has sent that group's follow-up digest entry
and the admin has tapped a button.

## 2. Scope

**Owns:** `handle_decision(conn, candidate_id, group_id, action, decision_notes=None, ...)`
for a non-primary group — the group-scoped analog of
`publish_primary_group.handle_decision`. On approve, publishes that one group's single Etsy
listing. On reject, abandons only that group. On edit, discards the group's current
render/review state so the next cron passes reprocess it.

**Does not own:** the poll loop, `telegram_offset` cursor, `resolve_callback`, `is_admin`,
or `log_telegram_event` — all stay owned by `publish_primary_group.py`. `process_update`
(in `publish_primary_group.py`) gets one extra `SELECT group_type FROM groups` after
resolving the callback, and routes to `publish_group.handle_decision` when `group_type !=
'primary'`. No second poll loop, no second `telegram_offset` row.

**Reused as-is (not reimplemented):**
- `publish_primary_group.record_decision` — already generic on `group_id`.
- `publish_primary_group.build_size_listing_data` / `publish_group_product` — already
  generic on `group_product_id`/size; `SIZE_TITLE_SUFFIXES` gets two new entries (`5x7`,
  `10x24`).
- `critic_pass.discard_superseded_attempt` — same DELETE-Gelato-product-and-rows helper
  stage 9 already uses for both retry and abandon.

## 3. Decision handling

### Approve

1. `record_decision(conn, group_id, "approved", decision_notes)`.
2. Look up the group's single live `group_products` row (`status IN ('created',
   'published')`, mirrors the primary group's `existing_8x12` guard so a retry after a
   crash still passes).
3. `publish_primary_group.publish_group_product(...)` for that one row (Gelato-create-if-
   needed, then Etsy draft → upload images → activate). Same retry-once-then-
   `publish_failed` behavior as the primary group — this stage adds no second retry layer.
4. On success: `groups.status = 'approved_published'`. No `candidates` row touched — this is
   the whole point of the narrow blast radius (a design already sells at its published
   sizes regardless of this group's outcome).
5. On failure after the retry: `group_products.status = 'publish_failed'` (set inside
   `publish_group_product` itself), `groups.status` left as `'pending_review'` — a future
   digest surfaces this the same way an unresolved primary-group publish failure would;
   authoring that surfacing is explicitly out of scope here (per the task brief).

### Reject

1. `record_decision(conn, group_id, "rejected", decision_notes)`.
2. The group has a live `created` group_product at reject time (that's what the digest was
   built from) — clean it up via `critic_pass.discard_superseded_attempt(conn,
   group_product_id, ...)`, same DELETE-the-Gelato-product helper `abandon_group` uses for
   a 3rd critic-pass failure. A rejected group shouldn't leave an unpublished Gelato
   product dangling any more than an abandoned one should.
3. `groups.status = 'rejected'`.
4. Nothing else — no candidate-level change, sibling groups (primary, the other of
   5x7/10x24) untouched. Same narrow blast radius as `group_critic_pass.abandon_group`,
   just triggered by a human reject instead of a 3rd critic-pass failure.

### Edit

1. `record_decision(conn, group_id, "edited", decision_notes)` — `decision_notes` is stored
   for the record but not consumed by any regeneration call (confirmed with user: there's
   no correction-note lever for a re-crop).
2. Discard the group's current render: `critic_pass.discard_superseded_attempt(conn,
   group_product_id, ...)` (DELETEs the Gelato product + `product_images`/`group_products`
   rows for that group's live `group_products` row, if any).
3. `DELETE FROM critic_pass_attempts WHERE group_id = ?` — fresh 3-attempt budget.
4. `DELETE FROM group_messages WHERE group_id = ?` — so `group_digest.py`'s selection query
   (`... AND g.id NOT IN (SELECT group_id FROM group_messages)`) picks the group back up
   once it re-passes critic pass.
5. `groups.status` is left untouched (stays `'pending_review'`) — confirmed with user.
   Neither `group_mockup.create_group_mockup`'s guard (blocks only `'failed_abandoned'`/
   `'rejected'`) nor its existing-row check (looks at `group_products`, now empty) cares
   about `'pending_review'` specifically, so the next `run_group_mockup_cycle` /
   `run_group_critic_pass_cycle` pass naturally reprocesses this group from scratch.

## 4. Function signatures

```python
# pipeline/publish_group.py

def handle_decision(conn, candidate_id: int, group_id: int, action: str,
                     decision_notes: str = None, *, static_config=None, store_id=None,
                     gelato_api_key=None, shop_id=None, etsy_api_key=None,
                     etsy_api_secret=None, etsy_access_token=None, dry_run=None,
                     now=None) -> dict:
    """Group-scoped analog of publish_primary_group.handle_decision, for group_type in
    ('5x7', '10x24'). approve -> publish that group's single listing via
    publish_primary_group.publish_group_product, groups.status='approved_published'.
    reject -> discard the group's product, groups.status='rejected'. edit -> discard the
    group's product/critic_pass_attempts/group_messages, groups.status left as-is so the
    next group_mockup/group_critic_pass cron pass reprocesses it. No candidate-level state
    is ever touched by this function."""
```

`publish_primary_group.SIZE_TITLE_SUFFIXES` gains:

```python
SIZE_TITLE_SUFFIXES = {
    "8x12": "",
    "A3": " - A3 Print",
    "A2": " - A2 Print",
    "A1": " - A1 Print",
    "5x7": " - 5x7 Print",
    "10x24": " - 10x24 Panoramic Print",
}
```

## 5. Dispatch change in publish_primary_group.py

`process_update` currently always calls its own `handle_decision`. New behavior, right
after the existing `group_messages` match check (which already establishes the callback is
real and matches a known digest message for this `group_id`):

```python
group_row = conn.execute(
    "SELECT candidate_id, group_type FROM groups WHERE id = ?", (parsed["group_id"],)
).fetchone()
candidate_id = group_row["candidate_id"]

...

if group_row["group_type"] == "primary":
    result = handle_decision(conn, candidate_id, parsed["group_id"], parsed["action"], ...)
else:
    import pipeline.publish_group as publish_group
    result = publish_group.handle_decision(conn, candidate_id, parsed["group_id"], parsed["action"], ...)
```

(Actual import goes at module top-level, not inline — written inline above only to show the
diff shape.) No changes to `resolve_callback`, `is_admin`, `log_telegram_event`,
`get_telegram_offset`, `set_telegram_offset`, or `run_publish_primary_group_cycle` — they
stay generic on `group_id` already.

## 6. Error handling summary

- Approve, Gelato/Etsy operational failure: retry once (inside `publish_group_product`,
  unchanged), then `group_products.status = 'publish_failed'`, exception propagates to
  `run_publish_primary_group_cycle`'s per-update catch (logs to `telegram_events_log`,
  continues past this update) — matches the primary group's existing failure path exactly.
- Reject: no retryable operation other than the Gelato DELETE inside
  `discard_superseded_attempt`; if that raises, it propagates the same way.
- Edit: same — `discard_superseded_attempt`'s DELETE is the only external call; if it
  raises, propagates and this update is logged/skipped, leaving the group's rows as they
  were (retry-safe: next callback replay would re-attempt the same discard).

## 7. Testing approach

TDD, mocking `gelato_client`/`etsy_client`/`telegram_client` at their existing seams (same
style as `publish_primary_group.py`'s and `group_critic_pass.py`'s suites):
- `handle_decision` approve: publishes the group's one listing, `groups.status` updated,
  `candidates` row untouched, decision recorded.
- `handle_decision` approve with operational failure: `group_products.status =
  'publish_failed'`, exception propagates, `groups.status` unchanged.
- `handle_decision` reject: Gelato product deleted, `groups.status = 'rejected'`,
  candidate/sibling-group rows untouched.
- `handle_decision` edit: group_product/critic_pass_attempts/group_messages rows gone,
  `groups.status` unchanged, decision recorded with notes.
- `process_update` dispatch: a primary-group callback still routes to
  `publish_primary_group.handle_decision`; a 5x7/10x24-group callback routes to
  `publish_group.handle_decision`; asserted via call tracking/mocks, not by duplicating the
  full decision-flow tests.
- Full whole-branch regression run at the end (existing test suite must stay green).
