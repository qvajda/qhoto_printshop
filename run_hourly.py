"""GL-7 hourly entrypoint. Sequences exactly what run_m1_live_test.py already
proves: publish_primary_group.run_publish_primary_group_cycle polls Telegram,
checks the admin ID, dispatches decisions, advances the offset, retries
publish_failed groups. This script adds only what unattended operation needs:
a schema guard, a single-instance lock, and Telegram-visible failure
reporting - it does not touch that function's internals (CLAUDE.md: one
function per stage, the runner sequences, it does not absorb).

Windows Task Scheduler invokes this hourly; exit code is the signal it acts
on (see docs/2026-08-05-gl7-cron-prd-and-kickoff.md §2 item 1 and item 7).

GL-132 (#142): the name is honest again. E10a had moved the trigger to PT5M for
exactly one reason - the cron poll WAS the owner's button, and a callback_query_id
expires in minutes. The listener owns that latency now (#139), so the trigger is back
to PT1H and this job is what it is named after.

What it still is, and what nothing else covers between the 09:00 and 21:00 batches:
drain the decisions the listener recorded, retry publish_failed candidates, and notice
a listener that has stopped breathing.

Two locks, and which one it takes when is the whole design (see pipeline/lock.py):
it holds the PIPELINE lock for its run, so it and the batch never interleave stages;
it takes the TOKEN lock on top only to poll, and if a live listener already owns the
cursor it skips polling and does the rest anyway. A poll it cannot do is not a reason
to leave a recorded decision undispatched.
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
import telegram_listener

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "db" / "qhoto.sqlite3"
JOB_NAME = "hourly"

# GL-130: the cadence is a fact about the host (a Task Scheduler trigger), and on
# 2026-08-12T13:06 it silently went from PT5M back to PT1H - the task file's mtime and
# the moment logs/telegram_getupdates.log drops from 12 polls an hour to 1 agree to the
# minute. Nothing in the pipeline noticed for five days, because a slow poll looks
# exactly like a quiet one. The job now measures its own interval against the cadence
# it expects, from the heartbeat it already writes, and says so once per episode.
# GL-132: PT5M -> PT1H, so this moved 5 -> 60 with the Task Scheduler trigger. These
# two are one decision written in two places; changing either alone means the job
# either cries wolf every run or never notices a real reversion.
EXPECTED_CADENCE_MINUTES = 60
CADENCE_STALE_MULTIPLIER = 3
CADENCE_DEGRADED_PREFIX = "cadence-degraded"

# GL-131 (#139): the listener answers the owner's button in under a second, so a
# listener that dies silently is the same five-day outage GL-130 was. The threshold and
# the wording live in telegram_listener.stale_detail - one definition, read here (which
# reports it) and by run_batch (which restarts it).


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


def _findings(conn, *, now=None) -> list:
    # GL-132b: the listener is NOT reported here. It is ensured after the cycle, and
    # what gets reported is the outcome of that - "started one" rather than "one is
    # missing". Reporting both would send two messages about one episode.
    return [d for d in (_cadence_detail(conn, now=now),) if d]


def _ensure_listener(conn, admin_chat_id, bot_token, *, token_lock_path=None,
                      previous_detail="") -> str | None:
    """Start a listener if none is breathing, and report what happened - once per
    episode, like every other finding this job reports (ADR-0018)."""
    result = telegram_listener.ensure_alive(conn, bot_token=bot_token,
                                            token_lock_path=token_lock_path)
    if result["status"] == "alive":
        return None
    detail = result["detail"]
    print(f"{JOB_NAME}: {detail}")
    if detail.split(":")[0] not in previous_detail:
        _notify_admin(admin_chat_id, bot_token, f"[{JOB_NAME}] {detail}")
    return detail


def _notify_admin(admin_chat_id, bot_token, message):
    try:
        telegram_client.send_message(admin_chat_id, message, bot_token=bot_token)
    except Exception as exc:
        print(f"failed to notify admin of {JOB_NAME} failure: {exc}")


def main(*, db_path=None, lock_path=None, token_lock_path=None, load_dotenv=True) -> int:
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

    # GL-132: two locks, two properties. `lock_path` is the pipeline lock, shared with
    # run_batch.py so the two cron jobs never interleave stages. `token_lock` is the
    # Telegram cursor, shared with the listener - keyed on the bot token since GL-45,
    # because the cursor is per-token and global and a per-tree lock let a second
    # checkout poll straight past it.
    lock_path = lock_path or lock.pipeline_lock_path(db_path)
    token_lock = token_lock_path or lock.token_lock_path(bot_token)

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
            def _cycle(poll):
                publish_primary_group.run_publish_primary_group_cycle(
                    conn, admin_chat_id=admin_chat_id, bot_token=bot_token,
                    static_config=config.load_static_config(),
                    store_id=gelato_store_id, gelato_api_key=gelato_api_key, shop_id=etsy_shop_id,
                    etsy_api_key=etsy_api_key, etsy_api_secret=etsy_api_secret,
                    etsy_access_token=etsy_access_token,
                    replicate_api_token=replicate_api_token, anthropic_api_key=anthropic_api_key,
                    poll=poll,
                )

            try:
                # GL-132: losing the cursor to a live listener is the normal, designed
                # case - not a failure and not a reason to skip the work. The probe is
                # racy by nature, so the LockHeldError below is the real guard; the
                # probe only keeps the common path from writing a lock file it would
                # immediately have to give back.
                if lock.is_held(token_lock):
                    print(f"{JOB_NAME}: a live listener holds the cursor - not polling, "
                          f"dispatching what it recorded")
                    _cycle(poll=False)
                else:
                    try:
                        with lock.acquire(token_lock):
                            _cycle(poll=True)
                    except lock.LockHeldError:
                        print(f"{JOB_NAME}: a listener took the cursor mid-run - not polling")
                        _cycle(poll=False)
            except Exception as exc:
                heartbeat.record(conn, JOB_NAME, ok=False, detail=str(exc))
                _notify_admin(admin_chat_id, bot_token, _admin_error_text(exc))
                return 1
            # GL-132b (#142): AFTER the cycle, deliberately - the poll above may still
            # have been holding the cursor lock, and a listener spawned into that would
            # find the lock held and exit 2 immediately. This is also why there is no
            # separate supervisor task: this job and the batch already run on a cadence,
            # and a listener that dies is restarted by whichever comes first.
            listener_detail = _ensure_listener(conn, admin_chat_id, bot_token,
                                               token_lock_path=token_lock,
                                               previous_detail=previous_detail)
            if listener_detail:
                detail = "; ".join(d for d in (detail, listener_detail) if d)

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
