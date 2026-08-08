# GL-7 soak findings (2026-08-06 to 2026-08-08)

Running log of defects found during the owner's two-night dry-run soak of
PR #7 (`run_hourly.py`/`run_batch.py`), ahead of merge. Two are fixed on the
branch already; one is open, deliberately left for later.

## Fixed during the soak

1. **`research` stage was never wired into `run_batch.py`** (found 2026-08-06).
   `generate.run_generate_cycle` only consumes candidates already in status
   `pending`; `research.run_research_cycle` is what inserts them, and it was
   listed in CLAUDE.md's 12-stage sequence and this file's own docstring but
   never actually called. Batch ran clean every cycle and never produced a
   new candidate. Fixed: added the `research` stage call ahead of `generate`,
   updated the docstring, added `test_main_calls_research_before_generate`.

2. **Two live bugs inside `research`, surfaced once stage 1 was wired in**
   (found 2026-08-07):
   - `pipeline/research.py:158` passed `sort_on="favorites"` to Etsy's
     `findAllListingsActive` - not a real enum value (`created`/`price`/
     `updated`/`score` only), every demand-check call failed
     `HTTP 400`. Fixed: changed to `sort_on="score"`.
   - `pipeline/anthropic_client.py:128` `research_web_search`'s
     `max_tokens=2048` default was too low once the `web_search` tool's own
     result content is counted against the budget - the model's final JSON
     got truncated mid-string before it could close. Same failure class as
     the earlier GL-13 `critic_pass` fix (2048->4096). Fixed: raised default
     to `4096`.
   - Both have regression tests (`test_research.py`,
     `test_anthropic_client.py`).

## Open - not fixed yet, flagged for later

3. **Per-candidate `generate` failures are silently swallowed** (found
   2026-08-08). `pipeline/generate.py:262-264`, inside
   `run_generate_cycle`: any exception from `generate_for_candidate` is
   caught with a bare `except Exception: ... continue` - the candidate's
   status is never set to `failed`, and because the exception dies here it
   never reaches `run_batch.py`'s `_run_stage` outer catch either, so no
   Telegram notification fires. A *transient* failure self-heals for free
   (the next run re-queries `WHERE status = 'pending'` and retries
   automatically - confirmed live: candidate 45 got stuck `pending` this
   morning, then generated cleanly on a manual retry with no code change),
   but a *persistent* failure (bad prompt, expired token, real outage) would
   leave a candidate silently stuck forever, indistinguishable from "hasn't
   run yet" without inspecting the DB directly. Owner decision 2026-08-08:
   leave as a known gap, let the soak continue - not fixing before merge.

   Related, same discovery session: `research.collect_event_lookahead()`
   returns the same fixed set of 2026 event-window niches on every call with
   no check against already-active candidates for the same niche - two
   batch runs close together (one from a manual verification call that
   skipped the process lock, one from the real scheduled 09:00 run) produced
   near-duplicate candidates for the same 6 event niches. Not soak-breaking,
   but worth a dedup pass before this is trusted to run unattended for
   longer stretches.

4. **Telegram button taps silently dropped, root cause unknown** (found
   2026-08-08, unresolved). Owner reported tapping approve/reject on 7
   `pending_review` primary groups (candidates 48, 49, 55, 57, 58, 59, 60);
   only 3 (48, 49, 55) ever produced a `telegram_events_log` row. The owner
   re-tapped the remaining 4 explicitly to test - this was their **third**
   attempt on those specific buttons, not their first - and only that third
   attempt was captured (one via a manual `run_hourly.py` invocation, three
   more via a second manual invocation). The first two rounds of taps left
   **zero trace** in `telegram_events_log`, not even a "discarded" row.

   Code review found no logic path that explains this: `set_telegram_offset`
   only advances past `update_id`s the loop actually iterated;
   `resolve_callback` only returns `None` (silent, unlogged skip) for
   updates with no `callback_query` at all, which a real button tap always
   has; every other path (wrong admin, stale message match, processing
   exception) logs an explicit row. So either Telegram never delivered
   those two earlier rounds of `callback_query` updates to `getUpdates` at
   all, or something outside the reviewed code path is consuming/discarding
   them before `resolve_callback` ever sees them. **Do not repeat the
   "they probably weren't actually tapped" explanation - the owner has
   directly contradicted it.** Also worth noting: Telegram's inline buttons
   never visually change after a tap (no greyed-out/disabled/spinner
   state), which is a separate, real UX gap - it made it hard for the owner
   to tell whether an earlier tap had registered at all, but it is not
   itself the cause of the drop (the DB evidence shows the tap truly never
   arrived, not just that it looked unconfirmed).

   Not investigated further yet: whether this correlates with manual
   `run_hourly.py` invocations racing real Task-Scheduler-fired runs
   during today's testing (several manual runs happened outside the
   normal cadence while debugging other findings in this same session).
   Needs reproduction with instrumentation on the raw `getUpdates` response
   before a real fix can be attempted - owner decision 2026-08-08: log and
   continue the soak, revisit if it recurs.
