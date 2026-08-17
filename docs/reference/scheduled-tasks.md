# Scheduled tasks and the two locks

What runs unattended on the owner's Windows machine, and which lock each one takes.
Registered by hand (there is no installer); the commands below are the record.

## The tasks

| Task | Trigger | Command | Takes |
|---|---|---|---|
| `qhoto-listener` | At log on, then every 15 min | `python telegram_listener.py` | cursor lock, for its lifetime |
| `qhoto-hourly` | Every 1 hour | `python run_hourly.py` | pipeline lock; cursor lock only to poll |
| `qhoto-batch-morning` | Daily 09:00 | `python run_batch.py` | pipeline lock |
| `qhoto-batch-evening` | Daily 21:00 | `python run_batch.py` | pipeline lock |

All four run with `WorkingDirectory` set to the repo root. Each tees stdout and stderr
into `logs/<job>.log` (`pipeline/runlog.py`), with credentials redacted.

`qhoto-listener` repeats every 15 minutes on purpose: a second copy takes the cursor
lock, finds it held, prints and exits 2 in milliseconds. The repetition is therefore a
supervisor — it restarts a listener that died, and costs nothing when one is alive.

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

## Registering them

```powershell
$repo   = "C:\Users\QVajd\Documents\claude\qhoto_printshop"
$python = "C:\Users\QVajd\AppData\Local\Programs\Python\Python312\python.exe"

# Listener: at log on, plus a 15-minute supervisor sweep, running indefinitely.
$action  = New-ScheduledTaskAction -Execute $python -Argument "telegram_listener.py" -WorkingDirectory $repo
$logon   = New-ScheduledTaskTrigger -AtLogOn
$sweep   = New-ScheduledTaskTrigger -Once -At (Get-Date).Date `
             -RepetitionInterval (New-TimeSpan -Minutes 15) `
             -RepetitionDuration (New-TimeSpan -Days 3650)
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew `
             -ExecutionTimeLimit ([TimeSpan]::Zero) -StartWhenAvailable
Register-ScheduledTask -TaskName 'qhoto-listener' -Action $action `
  -Trigger @($logon, $sweep) -Settings $settings
```

`-ExecutionTimeLimit 0` matters: the default kills a task after three days, and this one
is meant to run forever. `-MultipleInstances IgnoreNew` keeps Task Scheduler from
stacking copies, though the cursor lock would refuse them anyway.

Two Windows PowerShell 5.1 traps, both hit while writing this: `[TimeSpan]::MaxValue`
as a repetition duration is rejected (`P99999999DT23H59M59S` is out of range) — hence
the 3650-day duration above; and to change an existing task's cadence, mutate the
trigger you already have rather than building a fresh one:

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
