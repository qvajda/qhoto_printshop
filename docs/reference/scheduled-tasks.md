# Scheduled tasks and the two locks

What runs unattended on the owner's Windows machine, and which lock each one takes.
Registered by hand; there is no installer.

## The tasks

| Task | Trigger | Command | Takes |
|---|---|---|---|
| `qhoto-hourly` | Every 1 hour | `python run_hourly.py` | pipeline lock; cursor lock only to poll |
| `qhoto-batch-morning` | Daily 09:00 | `python run_batch.py` | pipeline lock |
| `qhoto-batch-evening` | Daily 21:00 | `python run_batch.py` | pipeline lock |

All three run with `WorkingDirectory` set to the repo root. Each tees stdout and stderr
into `logs/<job>.log` (`pipeline/runlog.py`), with credentials redacted.

## There is deliberately no listener task

`telegram_listener.py` is a resident process, but it gets no scheduled task of its own.
Both jobs above already call `telegram_listener.ensure_alive` — the hourly at the end of
its run, the batch immediately before each digest — and start one if no heartbeat is
breathing. Whichever runs first restarts a dead listener, so a fourth task would be a
second mechanism for a job already covered.

What that costs, stated plainly: worst-case restart latency is one hourly cycle rather
than the 15 minutes a dedicated supervisor trigger would give. If that ever matters, the
answer is the hourly's cadence, not a new task. After a reboot nothing starts the
listener until the next hourly run — within the hour, since the task is
`-StartWhenAvailable`.

Two ordering constraints keep this working, and both are load-bearing:

- The hourly ensures the listener **after** its own poll, because the poll may still be
  holding the cursor lock, and a listener spawned into that exits 2 immediately — a
  restart that silently never happens.
- A stale heartbeat with the cursor lock still held reads as **wedged**, not absent. A
  second listener would only exit 2 while the report claimed "started", so that case is
  reported and never spawned over.

## The two locks

Both live in the system temp directory, named by a hash so nothing credential-shaped or
path-shaped is written to a world-readable file.

- **Cursor lock** — `lock.token_lock_path(bot_token)`, `qhoto-telegram-<hash>.lock`.
  Guards the single server-side `getUpdates` cursor: Telegram hands an update to exactly
  one reader, so a second poller silently eats the first one's decisions. Held by the
  listener for its whole life; taken by `run_hourly` only around its poll.
- **Pipeline lock** — `lock.pipeline_lock_path(db_path)`, `qhoto-pipeline-<hash>.lock`.
  Guards the database against two cron jobs interleaving stages. Held by `run_hourly`
  and `run_batch` for their runs. **The listener never takes it** — that is what lets a
  batch run while the listener is up (#142).

A holder is considered dead if its PID is gone *or* its lock file is older than an hour.
The listener touches its file each loop (`lock.refresh`) so it is never declared stale
while it is merely blocked on a 25-second long poll.

## Exit codes (all entrypoints)

`0` success · `1` missing config · `2` a lock is held by a live process · `3` stale schema

Exit 2 is normal, not an error: it is how a duplicate invocation declines to run.

## Changing a cadence

Windows PowerShell 5.1 trap, hit while doing exactly this: build a fresh trigger with
`New-ScheduledTaskTrigger` and `Set-ScheduledTask` rejects it (`[TimeSpan]::MaxValue`
becomes `P99999999DT23H59M59S`, which is out of range). Mutate the trigger the task
already has instead:

```powershell
$t = Get-ScheduledTask -TaskName 'qhoto-hourly'
$t.Triggers[0].Repetition.Interval = 'PT1H'
Set-ScheduledTask -TaskName 'qhoto-hourly' -Trigger $t.Triggers
```

## Cadence is written in two places

`qhoto-hourly`'s trigger and `run_hourly.EXPECTED_CADENCE_MINUTES` are one decision.
The job compares its own interval against that constant and reports `cadence-degraded`
when they disagree — which is how GL-130's silent PT5M → PT1H reversion would have been
caught in an hour instead of five days. **Change the trigger and the constant together**,
or the job either cries wolf on every run or stops noticing a real reversion.

Current value: PT1H / 60. It was PT5M / 5 between E10a and #142, when the cron poll was
the owner's button; the listener owns that latency now.
