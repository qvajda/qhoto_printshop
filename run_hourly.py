"""GL-7 hourly entrypoint. Sequences exactly what run_m1_live_test.py already
proves: publish_primary_group.run_publish_primary_group_cycle polls Telegram,
checks the admin ID, dispatches decisions, advances the offset, retries
publish_failed groups. This script adds only what unattended operation needs:
a schema guard, a single-instance lock, and Telegram-visible failure
reporting - it does not touch that function's internals (CLAUDE.md: one
function per stage, the runner sequences, it does not absorb).

Windows Task Scheduler invokes this hourly; exit code is the signal it acts
on (see docs/2026-08-05-gl7-cron-prd-and-kickoff.md §2 item 1 and item 7).

E10a: the trigger is now every 5 minutes, and JOB_NAME stays "hourly" as a
deliberate misnomer - renaming it churns heartbeats.job_name, the log filename
and the Task Scheduler task name for zero functional gain. The cadence is the
dominant term in tap-to-toast latency (the ack in process_update has been
pre-dispatch since GL-45, so it was never the dispatch), and Telegram expires a
callback_query_id in minutes, not an hour. A run that collides with a batch
raises lock.LockHeldError, prints, and exits 2 with no alert and no heartbeat
row, so 12x the cadence adds no noise. See docs/2026-08-11-e10-kickoff.md §1.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import migrate
import pipeline.config as config
import pipeline.db as db
import pipeline.heartbeat as heartbeat
import pipeline.lock as lock
import pipeline.publish_primary_group as publish_primary_group
import pipeline.runlog as runlog
import pipeline.telegram_client as telegram_client

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "db" / "qhoto.sqlite3"
JOB_NAME = "hourly"

# GL-130: the cadence is a fact about the host (a Task Scheduler trigger), and on
# 2026-08-12T13:06 it silently went from PT5M back to PT1H - the task file's mtime and
# the moment logs/telegram_getupdates.log drops from 12 polls an hour to 1 agree to the
# minute. Nothing in the pipeline noticed for five days, because a slow poll looks
# exactly like a quiet one. The job now measures its own interval against the cadence
# E10a set, from the heartbeat it already writes, and says so once per episode.
EXPECTED_CADENCE_MINUTES = 5
CADENCE_STALE_MULTIPLIER = 3
CADENCE_DEGRADED_PREFIX = "cadence-degraded"

# GL-131 (#139): the listener is the thing that answers the owner's button in under a
# second, so a listener that dies silently is the same five-day outage GL-130 was. It
# writes a heartbeat every completed long poll (~25s), so a gap this wide is not a slow
# poll, it is a dead process. Never having run at all is NOT reported - before the
# listener is installed on the machine there is nothing to be down.
LISTENER_JOB_NAME = "listener"
LISTENER_STALE_MINUTES = 5
LISTENER_DOWN_PREFIX = "listener-down"


def _admin_error_text(exc):
    """GL-61 knob 2: 'brief' keeps the exception text out of Telegram (it is still in
    the log). Default 'full' is today's behaviour."""
    if config.telegram_error_verbosity() == "brief":
        return f"[{JOB_NAME}] stage failed - see logs/{JOB_NAME}.log"
    return f"[{JOB_NAME}] stage failed: {exc}"


def _cadence_detail(conn, *, now=None) -> str | None:
    """Return a detail string if this run came too long after the last one, else None.
    Reads the heartbeat this job already writes - no new state, no new table."""
    previous = heartbeat.last(conn, JOB_NAME)
    if previous is None:
        return None
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    try:
        gap_minutes = (now - datetime.fromisoformat(previous["ran_at"])).total_seconds() / 60
    except (TypeError, ValueError):
        return None
    if gap_minutes <= EXPECTED_CADENCE_MINUTES * CADENCE_STALE_MULTIPLIER:
        return None
    return (f"{CADENCE_DEGRADED_PREFIX}: last run was {gap_minutes:.0f} min ago, "
            f"expected every {EXPECTED_CADENCE_MINUTES} min (E10a)")


def _listener_detail(conn, *, now=None) -> str | None:
    """Return a detail string if the always-on listener looks dead, else None."""
    row = heartbeat.last(conn, LISTENER_JOB_NAME)
    if row is None:
        return None
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    try:
        gap_minutes = (now - datetime.fromisoformat(row["ran_at"])).total_seconds() / 60
    except (TypeError, ValueError):
        return None
    if not row["ok"]:
        return f"{LISTENER_DOWN_PREFIX}: last poll failed - {row['detail']}"
    if gap_minutes <= LISTENER_STALE_MINUTES:
        return None
    return (f"{LISTENER_DOWN_PREFIX}: no poll for {gap_minutes:.0f} min - taps are only "
            f"collected by this job now (#139)")


def _findings(conn, *, now=None) -> list:
    return [d for d in (_cadence_detail(conn, now=now), _listener_detail(conn, now=now)) if d]


def _notify_admin(admin_chat_id, bot_token, message):
    try:
        telegram_client.send_message(admin_chat_id, message, bot_token=bot_token)
    except Exception as exc:
        print(f"failed to notify admin of {JOB_NAME} failure: {exc}")


def main(*, db_path=None, lock_path=None, load_dotenv=True) -> int:
    if load_dotenv:
        config.load_env()

    db_path = db_path or DEFAULT_DB_PATH

    # I2: TELEGRAM_ADMIN_CHAT_ID/TELEGRAM_BOT_TOKEN are resolved first and on
    # their own - if either is missing, no Telegram notification is possible,
    # so this path is print-and-return only. Any later missing var CAN still
    # be notified, since Telegram creds are already in hand.
    try:
        admin_chat_id = config.require_env("TELEGRAM_ADMIN_CHAT_ID")
        bot_token = config.require_env("TELEGRAM_BOT_TOKEN")
    except config.MissingConfigError as exc:
        print(f"{JOB_NAME}: {exc}")
        return 1

    # GL-45: shared with run_batch.py, and now keyed on the bot token rather than on
    # this file's directory - the cursor being protected is per-token and global, so a
    # per-tree lock let a second checkout poll straight past it.
    lock_path = lock_path or lock.token_lock_path(bot_token)

    try:
        replicate_api_token = config.require_env("REPLICATE_API_TOKEN")
        anthropic_api_key = config.require_env("ANTHROPIC_API_KEY")
        gelato_api_key = config.require_env("GELATO_API_KEY")
        gelato_store_id = config.require_env("GELATO_STORE_ID")
        etsy_api_key = config.require_env("ETSY_API_KEY")
        etsy_api_secret = config.require_env("ETSY_API_SECRET")
        etsy_access_token = config.require_env("ETSY_ACCESS_TOKEN")
        etsy_shop_id = config.require_env("ETSY_SHOP_ID")
    except config.MissingConfigError as exc:
        print(f"{JOB_NAME}: {exc}")
        _notify_admin(admin_chat_id, bot_token, f"[{JOB_NAME}] {exc}")
        return 1

    try:
        migrate.check(db_path)
    except migrate.StaleSchemaError as exc:
        print(f"{JOB_NAME}: refusing to run on stale schema: {exc}")
        _notify_admin(admin_chat_id, bot_token, f"[{JOB_NAME}] refusing to run on stale schema: {exc}")
        return 3

    try:
        with lock.acquire(lock_path):
            conn = db.get_connection(db_path)
            # Measured before the cycle runs, so a cycle that then fails still leaves the
            # findings on its heartbeat. Each is notified at most once per episode: the
            # previous heartbeat's detail carries the prefixes already reported, so a poll
            # stuck at hourly (or a listener down all night) says so once, not 24 times
            # a day (ADR-0018).
            findings = _findings(conn)
            previous_detail = str((heartbeat.last(conn, JOB_NAME) or {}).get("detail") or "")
            for finding in findings:
                if finding.split(":")[0] in previous_detail:
                    continue
                print(f"{JOB_NAME}: {finding}")
                _notify_admin(admin_chat_id, bot_token, f"[{JOB_NAME}] {finding}")
            detail = "; ".join(findings) or None
            try:
                publish_primary_group.run_publish_primary_group_cycle(
                    conn, admin_chat_id=admin_chat_id, bot_token=bot_token,
                    static_config=config.load_static_config(),
                    store_id=gelato_store_id, gelato_api_key=gelato_api_key, shop_id=etsy_shop_id,
                    etsy_api_key=etsy_api_key, etsy_api_secret=etsy_api_secret,
                    etsy_access_token=etsy_access_token,
                    replicate_api_token=replicate_api_token, anthropic_api_key=anthropic_api_key,
                )
            except Exception as exc:
                heartbeat.record(conn, JOB_NAME, ok=False, detail=str(exc))
                _notify_admin(admin_chat_id, bot_token, _admin_error_text(exc))
                return 1
            heartbeat.record(conn, JOB_NAME, ok=True, detail=detail)
            return 0
    except lock.LockHeldError as exc:
        print(f"{JOB_NAME}: {exc}")
        return 2


if __name__ == "__main__":
    # GL-62: only the scheduled invocation tees to a file - see run_batch.py.
    _stop_log = runlog.start(JOB_NAME)
    try:
        sys.exit(main())
    finally:
        _stop_log()
