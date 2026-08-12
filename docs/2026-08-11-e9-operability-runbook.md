# E9 operability: the GL-61 knobs and the GL-62 run logs

Companion to `docs/2026-08-10-e9-small-items-kickoff.md` §5 and §6. Every knob
below defaults to today's behaviour — an unconfigured `.env` is not a behaviour
change.

## The knobs (`.env`, resolved in `pipeline/config.py`)

| Variable | Default | Effect |
|---|---|---|
| `RESEARCH_MODE` | `always` | `always` = today's behaviour. `consume-pending-only` = the research stage proposes nothing (including no safe-evergreen fallback) — the mode for draining the good-design/bad-copy backlog through GL-56 without piling new candidates on top. `if-nothing-pending` = propose only when no candidate is still in flight (`status NOT IN ('failed','abandoned','completed')`). An explicitly-requested on-demand topic is always honoured, and in a non-`always` mode it runs *alone*, without the automatic sources. An unknown value raises `MissingConfigError` at the start of the cycle rather than being silently ignored. |
| `CANDIDATES_PER_BATCH` | unset = uncapped | Cap on how many candidates one `generate` cycle processes. The overflow is deferred, never dropped — the rows stay `pending` and the next cycle takes them in the same id order. Also GL-59's cheap mitigation: fewer generate calls per cycle is less queue depth against Replicate's 6/min granted-credit cap. |
| `TELEGRAM_ERROR_VERBOSITY` | `full` | `full` = today's behaviour (the exception text goes to Telegram). `brief` = stage name only, pointing at the log; the exception is still written to the log in full. |

Backlog-recovery recipe (the reason knob 3 exists):
`RESEARCH_MODE=consume-pending-only` for the batch runs that drain the backlog,
then unset it.

## The run logs (GL-62)

`run_batch.py` and `run_hourly.py` tee stdout **and** stderr into
`logs/<job>.log` (`logs/batch.log`, `logs/hourly.log`) — only when invoked as a
scheduled task/script, never when `main()` is imported by a test.

- Console output is unchanged; the file is a copy, not a diversion.
- Size-bounded: 5 MB, one rotation kept (`logs/batch.log.1`) — a 10 MB ceiling.
- Secrets are scrubbed before writing (`pipeline/runlog.redact`):
  `TELEGRAM_ADMIN_CHAT_ID` (treated as a credential, CLAUDE.md), the bot token,
  and the Replicate/Anthropic/Gelato/Etsy keys are replaced with
  `<VAR_NAME>`. **Adding a new credential env var means adding it to
  `_SECRET_ENV_VARS`.**
- `logs/` is already git-ignored.

No change is needed in the Windows Task Scheduler actions; a redirect there
would be lost on re-registration, which is why this lives in the repo.

---

## Poll cadence: the "hourly" job runs every 5 minutes (E10a, 2026-08-11)

**`JOB_NAME` stays `"hourly"`. It is a deliberate misnomer, do not rename it** —
the name is load-bearing in `heartbeats.job_name`, `heartbeat_status.JOB_NAMES`,
the `logs/hourly.log` filename and the Task Scheduler task name, and renaming
buys nothing functional.

Why the cadence and not the ack: `process_update` has acknowledged the tap
*before* dispatching `handle_decision` since GL-45 (`publish_primary_group.py`,
the `_ack` call above the dispatch). The dispatch was never the latency — the
**cadence** is. Telegram expires a `callback_query_id` in minutes, so on an
hourly poll the ack we already ship was usually answering a dead query: the
owner's tap landed and looked dropped. At 5 minutes the ack lands inside the
window.

Checked before changing it:

- `getUpdates` is free and unmetered; 12 calls/hour is nothing. **No Replicate,
  Anthropic, Gelato or Etsy call is added** — `run_hourly` only polls and retries
  `publish_failed` groups.
- A run colliding with a batch or a long `handle_decision` raises
  `lock.LockHeldError`, prints, exits 2 — **no Telegram alert, no heartbeat
  row** — so 12× the cadence produces no new noise, and the skipped poll retries
  in 5 minutes instead of an hour.
- `heartbeat_status.py` has no hardcoded staleness window (it prints the last row
  and judges nothing), so a faster cadence cannot make it lie.

**The trigger edit is manual, on the owner's machine** (Task Scheduler → the
hourly task → Triggers → repeat every 5 minutes). Nothing in the repo sets it.

### Not done, deliberately

Early dispatch, webhook migration, cursor changes, retrospective log-diffing. If
taps still vanish after this, the next decision is a different confirmation
channel — record it, do not iterate (E10 kickoff §1).
