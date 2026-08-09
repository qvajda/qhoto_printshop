"""GL-7 hourly entrypoint. Sequences exactly what run_m1_live_test.py already
proves: publish_primary_group.run_publish_primary_group_cycle polls Telegram,
checks the admin ID, dispatches decisions, advances the offset, retries
publish_failed groups. This script adds only what unattended operation needs:
a schema guard, a single-instance lock, and Telegram-visible failure
reporting - it does not touch that function's internals (CLAUDE.md: one
function per stage, the runner sequences, it does not absorb).

Windows Task Scheduler invokes this hourly; exit code is the signal it acts
on (see docs/2026-08-05-gl7-cron-prd-and-kickoff.md §2 item 1 and item 7).
"""
import sys
from pathlib import Path

import migrate
import pipeline.config as config
import pipeline.db as db
import pipeline.heartbeat as heartbeat
import pipeline.lock as lock
import pipeline.publish_primary_group as publish_primary_group
import pipeline.telegram_client as telegram_client

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "db" / "qhoto.sqlite3"
JOB_NAME = "hourly"


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
                _notify_admin(admin_chat_id, bot_token, f"[{JOB_NAME}] stage failed: {exc}")
                return 1
            heartbeat.record(conn, JOB_NAME, ok=True)
            return 0
    except lock.LockHeldError as exc:
        print(f"{JOB_NAME}: {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
