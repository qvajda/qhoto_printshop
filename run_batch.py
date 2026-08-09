"""GL-7 twice-daily batch entrypoint. Sequences the same stage order
run_m1_live_test.py already proves works end to end (research -> generate ->
primary mockup -> compliance draft -> critic pass -> digest -> publish (1st
tap window) -> group mockup -> group critic pass -> group digest -> publish
(2nd tap window)), then GL-36's reconcile pass and cleanup. Each stage is isolated
in its own try/except: a broken stage is reported and skipped, it does not
abort stages after it - a research API outage must not also block publish,
reconcile, or cleanup running for everything already in flight.

Note: run_m1_live_test.py's own docstring is the reference for "in order";
this script does not replace it, it is the unattended sibling.
"""
import sys
from pathlib import Path

import migrate
import pipeline.cleanup as cleanup
import pipeline.compliance_draft as compliance_draft
import pipeline.config as config
import pipeline.critic_pass as critic_pass
import pipeline.db as db
import pipeline.digest as digest
import pipeline.generate as generate
import pipeline.group_critic_pass as group_critic_pass
import pipeline.group_digest as group_digest
import pipeline.group_mockup as group_mockup
import pipeline.heartbeat as heartbeat
import pipeline.lock as lock
import pipeline.primary_mockup as primary_mockup
import pipeline.publish_primary_group as publish_primary_group
import pipeline.reconcile as reconcile
import pipeline.research as research
import pipeline.telegram_client as telegram_client

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "db" / "qhoto.sqlite3"
JOB_NAME = "batch"


def _notify_admin(admin_chat_id, bot_token, message):
    try:
        telegram_client.send_message(admin_chat_id, message, bot_token=bot_token)
    except Exception as exc:
        print(f"failed to notify admin of {JOB_NAME} failure: {exc}")


def _run_stage(name, fn, admin_chat_id, bot_token, failures):
    # I4: return fn()'s result - reconcile's summary dict was being computed
    # and discarded even when it found real drift (aged-out candidates, a 404'd
    # Etsy listing). Every other stage still ignores this return value; only
    # the reconcile call site below reads it.
    try:
        return fn()
    except Exception as exc:
        print(f"{JOB_NAME}: stage {name} failed: {exc}")
        _notify_admin(admin_chat_id, bot_token, f"[{JOB_NAME}] stage '{name}' failed: {exc}")
        failures.append(name)
        return None


def _reconcile_detail(result: dict | None) -> str | None:
    """I4: one-line summary of reconcile drift for the batch heartbeat's
    detail field - not a Telegram send (that would be noisy on every run with
    drift), just enough for an operator checking heartbeat_status.py."""
    if not result:
        return None
    aged_out = result.get("aged_out_candidates") or []
    marked_missing = (result.get("etsy_reconcile") or {}).get("marked_missing") or []
    if not aged_out and not marked_missing:
        return None
    parts = []
    if aged_out:
        parts.append(f"{len(aged_out)} candidates aged out")
    if marked_missing:
        noun = "listing" if len(marked_missing) == 1 else "listings"
        parts.append(f"{len(marked_missing)} {noun} marked missing")
    return "reconcile: " + ", ".join(parts)


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

    # GL-45: shared with run_hourly.py, keyed on the bot token - see that file.
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
            static_config = config.load_static_config()
            failures = []

            _run_stage(
                "research",
                lambda: research.run_research_cycle(conn, static_config),
                admin_chat_id, bot_token, failures,
            )
            _run_stage(
                "generate",
                lambda: generate.run_generate_cycle(conn, api_token=replicate_api_token),
                admin_chat_id, bot_token, failures,
            )
            _run_stage(
                "primary_mockup",
                lambda: primary_mockup.run_primary_mockup_cycle(
                    conn, static_config=static_config, store_id=gelato_store_id, api_key=gelato_api_key,
                ),
                admin_chat_id, bot_token, failures,
            )
            _run_stage(
                "compliance_draft",
                lambda: compliance_draft.run_compliance_draft_cycle(
                    conn, static_config=static_config, anthropic_api_key=anthropic_api_key,
                ),
                admin_chat_id, bot_token, failures,
            )
            _run_stage(
                "critic_pass",
                lambda: critic_pass.run_critic_pass_cycle(
                    conn, static_config=static_config, anthropic_api_key=anthropic_api_key,
                    store_id=gelato_store_id, gelato_api_key=gelato_api_key,
                    replicate_api_token=replicate_api_token,
                ),
                admin_chat_id, bot_token, failures,
            )
            _run_stage(
                "digest",
                lambda: digest.run_digest_cycle(
                    conn, static_config=static_config, bot_token=bot_token, chat_id=admin_chat_id
                ),
                admin_chat_id, bot_token, failures,
            )
            _run_stage(
                "publish_primary_group_1",
                lambda: publish_primary_group.run_publish_primary_group_cycle(
                    conn, admin_chat_id=admin_chat_id, bot_token=bot_token, static_config=static_config,
                    store_id=gelato_store_id, gelato_api_key=gelato_api_key, shop_id=etsy_shop_id,
                    etsy_api_key=etsy_api_key, etsy_api_secret=etsy_api_secret,
                    etsy_access_token=etsy_access_token,
                    replicate_api_token=replicate_api_token, anthropic_api_key=anthropic_api_key,
                ),
                admin_chat_id, bot_token, failures,
            )
            _run_stage(
                "group_mockup",
                lambda: group_mockup.run_group_mockup_cycle(
                    conn, static_config=static_config, store_id=gelato_store_id, api_key=gelato_api_key,
                ),
                admin_chat_id, bot_token, failures,
            )
            _run_stage(
                "group_critic_pass",
                lambda: group_critic_pass.run_group_critic_pass_cycle(
                    conn, static_config=static_config, anthropic_api_key=anthropic_api_key,
                    store_id=gelato_store_id, gelato_api_key=gelato_api_key,
                ),
                admin_chat_id, bot_token, failures,
            )
            _run_stage(
                "group_digest",
                lambda: group_digest.run_group_digest_cycle(
                    conn, static_config=static_config, bot_token=bot_token, chat_id=admin_chat_id
                ),
                admin_chat_id, bot_token, failures,
            )
            _run_stage(
                "publish_primary_group_2",
                lambda: publish_primary_group.run_publish_primary_group_cycle(
                    conn, admin_chat_id=admin_chat_id, bot_token=bot_token, static_config=static_config,
                    store_id=gelato_store_id, gelato_api_key=gelato_api_key, shop_id=etsy_shop_id,
                    etsy_api_key=etsy_api_key, etsy_api_secret=etsy_api_secret,
                    etsy_access_token=etsy_access_token,
                    replicate_api_token=replicate_api_token, anthropic_api_key=anthropic_api_key,
                ),
                admin_chat_id, bot_token, failures,
            )
            reconcile_result = _run_stage(
                "reconcile",
                lambda: reconcile.run_reconcile(
                    conn, shop_id=etsy_shop_id, api_key=etsy_api_key,
                    api_secret=etsy_api_secret, access_token=etsy_access_token,
                ),
                admin_chat_id, bot_token, failures,
            )
            _run_stage(
                "cleanup",
                lambda: cleanup.run_cleanup(conn, store_id=gelato_store_id, gelato_api_key=gelato_api_key),
                admin_chat_id, bot_token, failures,
            )

            if failures:
                heartbeat.record(conn, JOB_NAME, ok=False, detail=f"failed stages: {', '.join(failures)}")
                return 1
            heartbeat.record(conn, JOB_NAME, ok=True, detail=_reconcile_detail(reconcile_result))
            return 0
    except lock.LockHeldError as exc:
        print(f"{JOB_NAME}: {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
