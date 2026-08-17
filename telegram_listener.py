"""GL-131 (#139): the always-on Telegram ack listener.

ADR-0005 keeps every stage a discrete scheduled function; its 2026-08-17
amendment carves out exactly one seam, and this file is that seam. A
`callback_query_id` expires in seconds and a cron poll answers in minutes, so
every `answerCallbackQuery` this pipeline sent for a real tap has been rejected
as "query is too old". A long-poll listener answers in under a second.

**The boundary is the deliverable.** This process owns four things:
`getUpdates`, the admin check, recording the decision, and the acknowledgement
(`answerCallbackQuery` + the keyboard edit). It never calls Gelato or Etsy,
never generates, never publishes - `process_update(dispatch=False)` records the
decision and queues one `pending_decisions` row, and
`publish_primary_group.dispatch_pending_decisions`, running inside the ordinary
scheduled cycle, does the slow work on its own cadence.

It holds `lock.token_lock_path` for its whole lifetime, because `getUpdates`
hands an update to exactly one reader. The scheduled poll (`run_hourly.py`) is
KEPT as a backstop and loses to a live listener with `LockHeldError`/exit 2, so
a listener that is down means taps arrive late, never that they are lost.

Exit codes match run_hourly.py: 0 clean stop, 1 missing config, 2 lock held,
3 stale schema.
"""
import sys
import time
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
JOB_NAME = "listener"

# Telegram holds the request open this long when there is nothing to send. Well
# under the 30s HTTP timeout in pipeline/http.py, so an idle poll returns [] rather
# than raising.
LONG_POLL_TIMEOUT = 25
# ponytail: a flat backoff, not exponential - the loop's only job is to not spin
# hot against a network outage, and a dead listener is already visible through the
# failed heartbeat run_hourly checks.
POLL_ERROR_BACKOFF_SECONDS = 5


def poll_once(conn, *, admin_chat_id, bot_token, timeout=LONG_POLL_TIMEOUT, now=None) -> int:
    """One long poll. Records and acks every decision it sees; dispatches none."""
    last_offset = publish_primary_group.get_telegram_offset(conn)
    updates = telegram_client.get_updates(
        offset=last_offset + 1 if last_offset is not None else None,
        timeout=timeout, bot_token=bot_token,
    )

    for update in updates:
        update_id = update["update_id"]
        try:
            publish_primary_group.process_update(
                conn, update, admin_chat_id=admin_chat_id, bot_token=bot_token,
                dispatch=False, now=now,
            )
        except Exception as exc:
            # Same durable-trace rule the scheduled cycle follows: an update that
            # raised must leave a row saying so, never just a print.
            telegram_user_id = update.get("callback_query", {}).get("from", {}).get("id")
            publish_primary_group.log_telegram_event(
                conn, telegram_user_id, update, True, f"error: {exc}", now=now,
            )
            print(f"process_update failed for update {update_id}: {exc}")
        # GL-45: per update, not once after the loop - either the decision is
        # recorded or its failure is logged, and both mean it must not come back.
        publish_primary_group.set_telegram_offset(conn, update_id)

    return len(updates)


def run(conn, *, admin_chat_id, bot_token, stop=None, sleep=time.sleep, timeout=LONG_POLL_TIMEOUT) -> None:
    # GL-45: one cursor per bot token. A poll from a copy of the database deletes
    # updates the canonical one will never see.
    db.assert_canonical(conn)

    while not (stop is not None and stop()):
        try:
            poll_once(conn, admin_chat_id=admin_chat_id, bot_token=bot_token, timeout=timeout)
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            print(f"{JOB_NAME}: poll failed: {exc}")
            heartbeat.record(conn, JOB_NAME, ok=False, detail=str(exc))
            sleep(POLL_ERROR_BACKOFF_SECONDS)
            continue
        # Every completed poll, so "when did the listener last breathe" is at most
        # LONG_POLL_TIMEOUT old. run_hourly reads this to notice a dead listener.
        heartbeat.record(conn, JOB_NAME, ok=True)


def main(*, db_path=None, lock_path=None, load_dotenv=True, stop=None) -> int:
    if load_dotenv:
        config.load_env()

    db_path = db_path or DEFAULT_DB_PATH

    try:
        admin_chat_id = config.require_env("TELEGRAM_ADMIN_CHAT_ID")
        bot_token = config.require_env("TELEGRAM_BOT_TOKEN")
    except config.MissingConfigError as exc:
        print(f"{JOB_NAME}: {exc}")
        return 1

    # Deliberately the ONLY credentials this process resolves. No Gelato key, no
    # Etsy token, no Replicate token: the boundary is enforced by what it holds,
    # not only by what it calls.
    lock_path = lock_path or lock.token_lock_path(bot_token)

    try:
        migrate.check(db_path)
    except migrate.StaleSchemaError as exc:
        print(f"{JOB_NAME}: refusing to run on stale schema: {exc}")
        return 3

    try:
        with lock.acquire(lock_path):
            conn = db.get_connection(db_path)
            print(f"{JOB_NAME}: polling (long poll {LONG_POLL_TIMEOUT}s, lock {lock_path})")
            try:
                run(conn, admin_chat_id=admin_chat_id, bot_token=bot_token, stop=stop)
            except KeyboardInterrupt:
                print(f"{JOB_NAME}: stopped")
            return 0
    except lock.LockHeldError as exc:
        print(f"{JOB_NAME}: {exc}")
        return 2


if __name__ == "__main__":
    _stop_log = runlog.start(JOB_NAME)
    try:
        sys.exit(main())
    finally:
        _stop_log()
