import json
from datetime import datetime, timezone

import pipeline.compliance_draft as compliance_draft
import pipeline.config as config
import pipeline.critic_pass as critic_pass
import pipeline.generate as generate
import pipeline.group_product as group_product
import pipeline.primary_mockup as primary_mockup
import pipeline.publish_group as publish_group
import pipeline.telegram_client as telegram_client


def resolve_callback(update: dict) -> dict | None:
    callback_query = update.get("callback_query")
    if callback_query is None:
        return None

    action, _, group_id = callback_query["data"].partition(":")
    return {
        "telegram_user_id": callback_query["from"]["id"],
        "callback_query_id": callback_query["id"],
        "action": action,
        "group_id": int(group_id),
        "message_id": callback_query["message"]["message_id"],
        "chat_id": callback_query["message"]["chat"]["id"],
    }


def is_admin(telegram_user_id, admin_chat_id) -> bool:
    return str(telegram_user_id) == str(admin_chat_id)


def log_telegram_event(conn, telegram_user_id, raw_payload, accepted, action_taken=None, *, now=None) -> int:
    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()
    cursor = conn.execute(
        """
        INSERT INTO telegram_events_log (received_at, telegram_user_id, raw_payload, accepted, action_taken)
        VALUES (?, ?, ?, ?, ?)
        """,
        (timestamp, str(telegram_user_id), json.dumps(raw_payload), 1 if accepted else 0, action_taken),
    )
    conn.commit()
    return cursor.lastrowid


def record_decision(conn, group_id, decision, decision_notes=None, *, now=None) -> None:
    timestamp = now if isinstance(now, str) else (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()
    conn.execute(
        "UPDATE groups SET decision = ?, decision_notes = ?, decided_at = ?, updated_at = ? WHERE id = ?",
        (decision, decision_notes, timestamp, timestamp, group_id),
    )
    conn.commit()


def publish_primary_group(conn, candidate_id, *, static_config=None, store_id=None,
                           gelato_api_key=None, shop_id=None, etsy_api_key=None,
                           etsy_api_secret=None, etsy_access_token=None, dry_run=None, now=None) -> dict:
    static_config = static_config if static_config is not None else config.load_static_config()
    timestamp = now if isinstance(now, str) else (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()

    candidate_row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    if candidate_row is None:
        raise ValueError(f"No candidate with id {candidate_id}")
    candidate = dict(candidate_row)

    group_row = conn.execute(
        "SELECT id FROM groups WHERE candidate_id = ? AND group_type = 'primary'", (candidate_id,)
    ).fetchone()
    if group_row is None:
        raise ValueError(f"No primary group for candidate {candidate_id}")
    group_id = group_row["id"]

    listing_text_row = conn.execute(
        "SELECT * FROM listing_texts WHERE candidate_id = ?", (candidate_id,)
    ).fetchone()
    if listing_text_row is None:
        raise ValueError(f"No listing_texts row for candidate {candidate_id}")
    listing_text = dict(listing_text_row)

    sizes = static_config["aspect_ratio_groups"]["primary"]

    def attempt():
        result = group_product.create_or_reuse_group_product(
            conn, group_id, sizes, candidate, static_config, listing_text["title"],
            store_id=store_id, api_key=gelato_api_key, now=now,
        )
        return group_product.patch_etsy_listing(
            conn, result["group_product_id"], "primary", listing_text, static_config,
            shop_id=shop_id, etsy_api_key=etsy_api_key, etsy_api_secret=etsy_api_secret,
            etsy_access_token=etsy_access_token, dry_run=dry_run, now=now,
        )

    try:
        try:
            etsy_listing_id = attempt()
        except Exception:
            etsy_listing_id = attempt()
    except Exception:
        conn.execute(
            "UPDATE groups SET status = 'publish_failed', updated_at = ? WHERE id = ?",
            (timestamp, group_id),
        )
        conn.commit()
        raise

    conn.execute(
        "UPDATE groups SET status = 'approved_published', updated_at = ? WHERE id = ?",
        (timestamp, group_id),
    )
    conn.execute(
        "UPDATE candidates SET status = 'completed', updated_at = ? WHERE id = ?",
        (timestamp, candidate_id),
    )
    conn.commit()

    return {"etsy_listing_id": etsy_listing_id}


def handle_decision(conn, candidate_id, group_id, action, decision_notes=None, *,
                     static_config=None, store_id=None, gelato_api_key=None, shop_id=None,
                     etsy_api_key=None, etsy_api_secret=None, etsy_access_token=None,
                     replicate_api_token=None, anthropic_api_key=None, dry_run=None, now=None) -> dict:
    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()

    if action == "approve":
        record_decision(conn, group_id, "approved", decision_notes, now=now)
        result = publish_primary_group(
            conn, candidate_id, static_config=static_config, store_id=store_id,
            gelato_api_key=gelato_api_key, shop_id=shop_id, etsy_api_key=etsy_api_key,
            etsy_api_secret=etsy_api_secret, etsy_access_token=etsy_access_token,
            dry_run=dry_run, now=now,
        )
        return {"action": "approve", **result}

    if action == "edit":
        record_decision(conn, group_id, "edited", decision_notes, now=now)
        resolved_static_config = static_config if static_config is not None else config.load_static_config()

        old_gp_row = conn.execute(
            "SELECT id FROM group_products WHERE group_id = ? AND status = 'created'",
            (group_id,),
        ).fetchone()
        if old_gp_row is not None:
            critic_pass.discard_superseded_attempt(
                conn, old_gp_row["id"], store_id=store_id, api_key=gelato_api_key,
            )
        conn.execute("DELETE FROM critic_pass_attempts WHERE group_id = ?", (group_id,))
        conn.execute("DELETE FROM listing_texts WHERE candidate_id = ?", (candidate_id,))
        conn.execute("DELETE FROM group_messages WHERE group_id = ?", (group_id,))
        conn.commit()

        generate.generate_for_candidate(
            conn, candidate_id, correction_note=decision_notes, api_token=replicate_api_token, now=now,
        )
        primary_mockup.create_primary_mockup(
            conn, candidate_id, static_config=resolved_static_config, store_id=store_id,
            api_key=gelato_api_key, now=now,
        )
        compliance_draft.build_compliance_draft(
            conn, candidate_id, static_config=resolved_static_config,
            anthropic_api_key=anthropic_api_key, now=now,
        )
        return {"action": "edit"}

    if action == "reject":
        record_decision(conn, group_id, "rejected", decision_notes, now=now)
        conn.execute(
            "UPDATE groups SET status = 'rejected', updated_at = ? WHERE id = ?",
            (timestamp, group_id),
        )
        conn.execute(
            "UPDATE candidates SET status = 'failed', failed_reason = 'primary group rejected', "
            "updated_at = ? WHERE id = ?",
            (timestamp, candidate_id),
        )
        conn.commit()
        return {"action": "reject"}

    raise ValueError(f"Unknown action {action!r}")


def get_telegram_offset(conn) -> int | None:
    row = conn.execute("SELECT last_update_id FROM telegram_offset WHERE id = 1").fetchone()
    return row["last_update_id"] if row is not None else None


def set_telegram_offset(conn, last_update_id: int) -> None:
    conn.execute(
        "INSERT INTO telegram_offset (id, last_update_id) VALUES (1, ?) "
        "ON CONFLICT(id) DO UPDATE SET last_update_id = excluded.last_update_id",
        (last_update_id,),
    )
    conn.commit()


def process_update(conn, update, *, admin_chat_id=None, bot_token=None, static_config=None,
                    store_id=None, gelato_api_key=None, shop_id=None, etsy_api_key=None,
                    etsy_api_secret=None, etsy_access_token=None, replicate_api_token=None,
                    anthropic_api_key=None, dry_run=None, now=None) -> dict | None:
    admin_chat_id = admin_chat_id or config.require_env("TELEGRAM_ADMIN_CHAT_ID")
    parsed = resolve_callback(update)
    if parsed is None:
        return None

    if not is_admin(parsed["telegram_user_id"], admin_chat_id):
        log_telegram_event(conn, parsed["telegram_user_id"], update, False,
                            "discarded: not admin", now=now)
        return None

    message_row = conn.execute(
        "SELECT chat_id, telegram_message_id FROM group_messages WHERE group_id = ?",
        (parsed["group_id"],),
    ).fetchone()
    if message_row is None or str(message_row["chat_id"]) != str(parsed["chat_id"]) \
            or message_row["telegram_message_id"] != parsed["message_id"]:
        log_telegram_event(conn, parsed["telegram_user_id"], update, False,
                            "discarded: callback does not match a known group_messages row", now=now)
        return None

    group_row = conn.execute(
        "SELECT candidate_id, group_type FROM groups WHERE id = ?", (parsed["group_id"],)
    ).fetchone()
    candidate_id = group_row["candidate_id"]

    log_telegram_event(conn, parsed["telegram_user_id"], update, True, parsed["action"], now=now)

    if group_row["group_type"] == "primary":
        result = handle_decision(
            conn, candidate_id, parsed["group_id"], parsed["action"], static_config=static_config,
            store_id=store_id, gelato_api_key=gelato_api_key, shop_id=shop_id, etsy_api_key=etsy_api_key,
            etsy_api_secret=etsy_api_secret, etsy_access_token=etsy_access_token,
            replicate_api_token=replicate_api_token, anthropic_api_key=anthropic_api_key,
            dry_run=dry_run, now=now,
        )
    else:
        result = publish_group.handle_decision(
            conn, candidate_id, parsed["group_id"], parsed["action"], static_config=static_config,
            store_id=store_id, gelato_api_key=gelato_api_key, shop_id=shop_id, etsy_api_key=etsy_api_key,
            etsy_api_secret=etsy_api_secret, etsy_access_token=etsy_access_token,
            dry_run=dry_run, now=now,
        )

    # The decision is already durably recorded above - a failure here (e.g. a stale/expired
    # callback query) is just a lost "loading spinner" on the admin's tap, not a lost decision,
    # so it must not raise past this point and roll back the offset advance.
    try:
        telegram_client.answer_callback_query(parsed["callback_query_id"], bot_token=bot_token)
    except Exception as exc:
        print(f"answer_callback_query failed for {parsed['callback_query_id']}: {exc}")

    return {"candidate_id": candidate_id, "group_id": parsed["group_id"], **result}


def run_publish_primary_group_cycle(conn, *, admin_chat_id=None, bot_token=None, static_config=None,
                                     store_id=None, gelato_api_key=None, shop_id=None,
                                     etsy_api_key=None, etsy_api_secret=None, etsy_access_token=None,
                                     replicate_api_token=None, anthropic_api_key=None,
                                     dry_run=None, now=None) -> list:
    last_offset = get_telegram_offset(conn)
    offset = last_offset + 1 if last_offset is not None else None
    updates = telegram_client.get_updates(offset=offset, bot_token=bot_token)

    processed = []
    max_update_id = last_offset
    for update in updates:
        update_id = update["update_id"]
        max_update_id = update_id if max_update_id is None else max(max_update_id, update_id)
        try:
            result = process_update(
                conn, update, admin_chat_id=admin_chat_id, bot_token=bot_token, static_config=static_config,
                store_id=store_id, gelato_api_key=gelato_api_key, shop_id=shop_id, etsy_api_key=etsy_api_key,
                etsy_api_secret=etsy_api_secret, etsy_access_token=etsy_access_token,
                replicate_api_token=replicate_api_token, anthropic_api_key=anthropic_api_key,
                dry_run=dry_run, now=now,
            )
        except Exception as exc:
            # process_update can raise after resolve_callback succeeds but before/during
            # handle_decision — this cron has no console to watch, so a print() alone leaves
            # no durable trace that the admin's tap was dropped. accepted=True distinguishes
            # "this was a real event that failed" from the accepted=False discard-path rows
            # log_telegram_event already writes for non-admin/unknown-group callbacks.
            telegram_user_id = update.get("callback_query", {}).get("from", {}).get("id")
            log_telegram_event(conn, telegram_user_id, update, True, f"error: {exc}", now=now)
            print(f"process_update failed for update {update_id}: {exc}")
            continue
        if result is not None:
            processed.append(result)

    if max_update_id is not None:
        set_telegram_offset(conn, max_update_id)

    return processed
