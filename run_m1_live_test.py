"""Manual M1 live test: run each pipeline stage once, in order, against real APIs.

Not wired to cron yet (that's the next step, after this passes). Run this,
watch Telegram for the digest, approve/reject, then re-run this script (or
just the publish stage below) to pick up the decision.

Usage: python run_m1_live_test.py
"""
from pathlib import Path

from pipeline import config, db
from pipeline import research, generate, primary_mockup, compliance_draft
from pipeline import critic_pass, digest, publish_primary_group
from pipeline import group_mockup, group_critic_pass, group_digest

DB_PATH = Path(__file__).resolve().parent / "db" / "qhoto.sqlite3"


def main():
    config.load_env()
    static_config = config.load_static_config()

    replicate_api_token = config.require_env("REPLICATE_API_TOKEN")
    anthropic_api_key = config.require_env("ANTHROPIC_API_KEY")
    gelato_api_key = config.require_env("GELATO_API_KEY")
    gelato_store_id = config.require_env("GELATO_STORE_ID")
    etsy_api_key = config.require_env("ETSY_API_KEY")
    etsy_api_secret = config.require_env("ETSY_API_SECRET")
    etsy_access_token = config.require_env("ETSY_ACCESS_TOKEN")
    etsy_shop_id = config.require_env("ETSY_SHOP_ID")
    telegram_bot_token = config.require_env("TELEGRAM_BOT_TOKEN")
    telegram_admin_chat_id = config.require_env("TELEGRAM_ADMIN_CHAT_ID")

    print(f"GELATO_LIVE_MODE={config.is_live_mode('GELATO')} ETSY_LIVE_MODE={config.is_live_mode('ETSY')}")

    conn = db.get_connection(DB_PATH)
    db.init_db(conn)

    existing = conn.execute("SELECT id FROM candidates").fetchone()
    if existing:
        print(f"== research (skipped, candidate {existing['id']} already seeded) ==")
    else:
        print("== research (skipped, seeding 1 candidate for smoke test) ==")
        raw = {
            "niche": "botanical minimalist wall art - smoke test",
            "trend_source": "manual_smoke_test",
            "rationale": "M1 live smoke test - single candidate to bound API cost.",
            "window_start": None,
            "window_end": None,
            "demand_ratio": None,
            "listing_count": None,
        }
        classification = research.classify(raw)
        candidate_id = research._insert_candidate(conn, raw, classification)
        print(f"seeded candidate {candidate_id} ({classification['go_hold_kill']})")

    print("== generate ==")
    print(generate.run_generate_cycle(conn, api_token=replicate_api_token))

    print("== primary_mockup ==")
    print(primary_mockup.run_primary_mockup_cycle(
        conn, static_config=static_config, store_id=gelato_store_id, api_key=gelato_api_key,
    ))

    print("== compliance_draft ==")
    print(compliance_draft.run_compliance_draft_cycle(
        conn, static_config=static_config, anthropic_api_key=anthropic_api_key,
    ))

    print("== critic_pass ==")
    print(critic_pass.run_critic_pass_cycle(
        conn, static_config=static_config, anthropic_api_key=anthropic_api_key,
        store_id=gelato_store_id, gelato_api_key=gelato_api_key,
        replicate_api_token=replicate_api_token,
    ))

    print("== digest ==")
    print(digest.run_digest_cycle(
        conn, static_config=static_config, bot_token=telegram_bot_token, chat_id=telegram_admin_chat_id,
    ))

    print("== publish_primary_group (polls Telegram for your decision) ==")
    print(publish_primary_group.run_publish_primary_group_cycle(
        conn, admin_chat_id=telegram_admin_chat_id, bot_token=telegram_bot_token, static_config=static_config,
        store_id=gelato_store_id, gelato_api_key=gelato_api_key, shop_id=etsy_shop_id,
        etsy_api_key=etsy_api_key, etsy_api_secret=etsy_api_secret, etsy_access_token=etsy_access_token,
        replicate_api_token=replicate_api_token, anthropic_api_key=anthropic_api_key,
    ))

    print("== group_mockup (5x7/10x24 re-crop) ==")
    print(group_mockup.run_group_mockup_cycle(
        conn, static_config=static_config, store_id=gelato_store_id, api_key=gelato_api_key,
    ))

    print("== group_critic_pass ==")
    print(group_critic_pass.run_group_critic_pass_cycle(
        conn, static_config=static_config, anthropic_api_key=anthropic_api_key,
        store_id=gelato_store_id, gelato_api_key=gelato_api_key,
    ))

    print("== group_digest ==")
    print(group_digest.run_group_digest_cycle(
        conn, static_config=static_config, bot_token=telegram_bot_token, chat_id=telegram_admin_chat_id,
    ))

    print("== publish_primary_group (also polls/dispatches 5x7/10x24 group decisions) ==")
    print(publish_primary_group.run_publish_primary_group_cycle(
        conn, admin_chat_id=telegram_admin_chat_id, bot_token=telegram_bot_token, static_config=static_config,
        store_id=gelato_store_id, gelato_api_key=gelato_api_key, shop_id=etsy_shop_id,
        etsy_api_key=etsy_api_key, etsy_api_secret=etsy_api_secret, etsy_access_token=etsy_access_token,
        replicate_api_token=replicate_api_token, anthropic_api_key=anthropic_api_key,
    ))

    print(f"\nDone. DB at {DB_PATH}. If a digest was just sent, approve/reject in Telegram then re-run this "
          f"script to process the decision and publish.")


if __name__ == "__main__":
    main()
