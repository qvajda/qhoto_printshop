import json
from datetime import datetime, timezone

import pipeline.compliance_draft as compliance_draft
import pipeline.config as config
import pipeline.critic_pass as critic_pass
import pipeline.etsy_client as etsy_client
import pipeline.gelato_client as gelato_client
import pipeline.generate as generate
import pipeline.http as http
import pipeline.primary_mockup as primary_mockup
import pipeline.telegram_client as telegram_client


# Etsy has no "unlimited stock" flag for made-to-order POD items; 999 is the
# conventional large-placeholder quantity for this listing style.
LISTING_QUANTITY = 999

SIZE_TITLE_SUFFIXES = {
    "8x12": "",
    "A3": " - A3 Print",
    "A2": " - A2 Print",
    "A1": " - A1 Print",
}


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
    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()
    conn.execute(
        "UPDATE groups SET decision = ?, decision_notes = ?, decided_at = ?, updated_at = ? WHERE id = ?",
        (decision, decision_notes, timestamp, timestamp, group_id),
    )
    conn.commit()


def build_size_listing_data(listing_text: dict, size: str, price_eur: float) -> dict:
    tags = json.loads(listing_text["tags"])
    title = f"{listing_text['title']}{SIZE_TITLE_SUFFIXES[size]}"
    compliance_draft.validate_listing_text(title, tags)
    return {
        "title": title,
        "description": listing_text["description"],
        "price": price_eur,
        "quantity": LISTING_QUANTITY,
        "who_made": listing_text["who_made"],
        "when_made": "made_to_order",
        "is_supply": False,
        "taxonomy_id": listing_text["taxonomy_id"],
        "shipping_profile_id": listing_text["shipping_profile_id"],
        "production_partner_ids": json.loads(listing_text["production_partner_ids"]),
        "tags": tags,
    }
