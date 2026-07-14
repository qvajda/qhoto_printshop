# cleanup.py design — stage 12/12

## Scope

Final pipeline stage. Two responsibilities, decided after brainstorming:

1. **Orphaned Gelato product cleanup** — absorbs two known gaps left by
   `publish_primary_group.py` and `publish_group.py`'s reject/edit paths:
   - `publish_primary_group.py`'s reject path never deletes its Gelato
     product at all.
   - Both files' cleanup queries filter `status IN ('created','published')`,
     which misses `group_products` rows stuck at `status='publish_failed'` —
     those rows are invisible to reject/edit cleanup, and a later edit can
     spawn a second Gelato product alongside the orphaned one.
2. **Stale local row pruning** — `telegram_events_log` (grows on every
   inbound message/callback, accepted or not) and terminal-status
   `candidates` (with full cascade of their children), both past a 30-day
   retention window.

**Explicitly out of scope**: reconciliation against live Gelato/Etsy state
(cross-checking local `status` against what actually exists via the APIs).
Flagged as a future nice-to-have, likely its own monthly cadence — not
built now.

**Not touching stages 7/11 directly.** Rather than patch
`publish_primary_group.py`'s reject and widen `publish_group.py`'s
`status IN (...)` filters in place, both gaps are covered by one unified
query in the new stage: broader condition, no duplicate logic in three
places, and it naturally also catches any future gap where a group_product
gets orphaned without deletion.

## Cron placement

No scheduler/orchestrator file exists yet for any of the 11 shipped
stages — each is a standalone, independently callable function per
CLAUDE.md's hard constraint ("one function per pipeline stage"). Wiring
into an actual cron entrypoint is out of scope here, same as it was for
stages 1-11. `run_cleanup` is designed to run once per day, at the end of
the evening batch (after `publish_group`/`publish_primary_group` have
processed that day's decisions — freshest orphans to catch), whenever that
wiring is built.

## Functions

### `cleanup_orphaned_gelato_products(conn, *, store_id=None, api_key=None, now=None) -> list`

Unifies both known gaps into one query — any `group_products` row that:
- has `gelato_product_id IS NOT NULL AND status != 'deleted'`, AND
- either `group_products.status = 'publish_failed'`, OR its parent
  `groups.status IN ('rejected', 'failed_abandoned')`

For each match: call `gelato_client.delete_product(gelato_product_id,
store_id=store_id, api_key=api_key)`.
- On success: `UPDATE group_products SET status = 'deleted', updated_at = ?`.
- On exception: `print` a log line and continue to the next row, leaving
  its status untouched so the next run retries it. Matches the existing
  `except Exception as exc: print(...); continue` pattern in
  `critic_pass.run_critic_pass_cycle` / `group_critic_pass.run_group_critic_pass_cycle`.

Returns the list of `group_products.id` successfully marked deleted.

### `prune_telegram_events_log(conn, *, retention_days=30, now=None) -> int`

`DELETE FROM telegram_events_log WHERE received_at < cutoff`, where
`cutoff = now - retention_days`. Returns rows-deleted count
(`cursor.rowcount`).

### `prune_stale_candidates(conn, *, retention_days=30, now=None) -> list`

Selects candidates where `status IN ('failed','abandoned','completed')
AND updated_at < cutoff`, **excluding** any candidate that still has a
`group_products` row (via its `groups`) with `gelato_product_id IS NOT NULL
AND status != 'deleted'` — safety guard so a candidate is never pruned
while a live Gelato product still points at it, independent of call order.

For each eligible candidate, cascade-delete children in FK-safe order
(schema has no `ON DELETE CASCADE`, `PRAGMA foreign_keys = ON` is set):

```
product_images      (WHERE group_product_id IN (SELECT id FROM group_products WHERE group_id IN (SELECT id FROM groups WHERE candidate_id = ?)))
group_products       (WHERE group_id IN (SELECT id FROM groups WHERE candidate_id = ?))
critic_pass_attempts (WHERE group_id IN (SELECT id FROM groups WHERE candidate_id = ?))
group_messages       (WHERE group_id IN (SELECT id FROM groups WHERE candidate_id = ?))
groups               (WHERE candidate_id = ?)
listing_texts        (WHERE candidate_id = ?)
candidates           (WHERE id = ?)
```

Returns the list of pruned `candidate_id`s.

`listing_metrics_snapshots` reference `group_products`, which by this point
in a pruned candidate's tree has already been deleted — no separate
`listing_metrics_snapshots` delete needed beyond what cascades logically
imply (there's no FK enforcing it, but any row would already be orphaned
data left from a deleted `group_product_id`; out of scope per the
brainstorm answer — only `telegram_events_log` and `candidates` were
selected for pruning).

Wait — `listing_metrics_snapshots` has `group_product_id NOT NULL
REFERENCES group_products(id)`, and FK enforcement is ON. Deleting a
`group_products` row that still has snapshot children would violate the FK
and raise. So `prune_stale_candidates` must also delete
`listing_metrics_snapshots` rows for the group_products being removed, as
a mechanical FK-satisfying step (not a "pruning old metrics" feature —
just required to let the cascade complete):

```
DELETE FROM listing_metrics_snapshots WHERE group_product_id IN (SELECT id FROM group_products WHERE group_id IN (SELECT id FROM groups WHERE candidate_id = ?))
```
— inserted before the `group_products` delete step above.

### `run_cleanup(conn, *, store_id=None, gelato_api_key=None, retention_days=30, now=None) -> dict`

Orchestrator. Runs in this order:
1. `cleanup_orphaned_gelato_products` — first, so step 3's safety guard
   sees post-cleanup state.
2. `prune_stale_candidates`
3. `prune_telegram_events_log`

Returns `{"gelato_products_deleted": [...], "candidates_pruned": [...],
"telegram_events_pruned": <int>}`.

No Telegram notification — this is routine housekeeping, not a decision
point requiring admin review, and nothing in SPEC_v4.10 calls for one.

## Testing

Follows existing test conventions (`tests/test_cleanup.py`, sqlite
`tmp_path` fixture per `tests/test_publish_group.py`). Cases per function:
- orphan cleanup: matches both gap shapes (publish_failed status;
  rejected/failed_abandoned parent group), skips already-deleted rows,
  continues past a delete exception, leaves failed rows' status untouched.
- log pruning: deletes rows older than cutoff, keeps newer rows.
- candidate pruning: prunes eligible candidates with full cascade
  (including the `listing_metrics_snapshots` FK-satisfying delete),
  skips candidates with a live Gelato product still attached, skips
  non-terminal-status candidates, skips candidates newer than cutoff.
- `run_cleanup`: calls all three in the documented order, returns the
  combined summary dict.
