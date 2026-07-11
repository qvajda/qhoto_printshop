import json
from datetime import datetime, timezone

import pipeline.config as config
import pipeline.telegram_client as telegram_client


def get_primary_group(conn, candidate_id: int) -> dict:
    row = conn.execute(
        """
        SELECT g.id AS group_id, gp.price_eur AS price_eur
        FROM groups g
        JOIN group_products gp ON gp.group_id = g.id AND gp.status = 'created'
        WHERE g.candidate_id = ? AND g.group_type = 'primary'
        """,
        (candidate_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"No live primary group_product for candidate {candidate_id}")
    return {"group_id": row["group_id"], "price_eur": row["price_eur"]}


def get_primary_gallery_urls(conn, candidate_id: int) -> list:
    rows = conn.execute(
        """
        SELECT pi.image_url
        FROM product_images pi
        JOIN group_products gp ON gp.id = pi.group_product_id AND gp.status = 'created'
        JOIN groups g ON g.id = gp.group_id
        WHERE g.candidate_id = ? AND g.group_type = 'primary'
        ORDER BY pi.gallery_order
        """,
        (candidate_id,),
    ).fetchall()
    return [row["image_url"] for row in rows]


def get_listing_text(conn, candidate_id: int) -> dict:
    row = conn.execute(
        "SELECT title, tags, description, disclosure_text FROM listing_texts WHERE candidate_id = ?",
        (candidate_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"No listing_texts row for candidate {candidate_id}")
    return dict(row)


def build_digest_message_text(candidate_id: int, group_id: int, listing_text: dict, price_eur: float) -> str:
    tags = ", ".join(json.loads(listing_text["tags"]))
    return (
        f"Candidate #{candidate_id} — Primary group (#{group_id})\n\n"
        f"{listing_text['title']}\n\n"
        f"{listing_text['description']}\n\n"
        f"Tags: {tags}\n\n"
        f"{listing_text['disclosure_text']}\n\n"
        f"Price: €{price_eur}"
    )


def build_digest_keyboard(group_id: int) -> dict:
    return {
        "inline_keyboard": [[
            {"text": "✅ Approve", "callback_data": f"approve:{group_id}"},
            {"text": "✏️ Edit", "callback_data": f"edit:{group_id}"},
            {"text": "❌ Reject", "callback_data": f"reject:{group_id}"},
        ]]
    }


def send_primary_digest(conn, candidate_id: int, *, static_config: dict = None,
                         bot_token: str = None, chat_id: str = None, now=None) -> dict:
    group = get_primary_group(conn, candidate_id)
    photo_urls = get_primary_gallery_urls(conn, candidate_id)
    listing_text = get_listing_text(conn, candidate_id)
    chat_id = chat_id or config.require_env("TELEGRAM_ADMIN_CHAT_ID")

    telegram_client.send_media_group(chat_id, photo_urls, bot_token=bot_token)

    text = build_digest_message_text(candidate_id, group["group_id"], listing_text, group["price_eur"])
    reply_markup = build_digest_keyboard(group["group_id"])
    response = telegram_client.send_message(chat_id, text, reply_markup, bot_token=bot_token)
    telegram_message_id = response["result"]["message_id"]

    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()
    conn.execute(
        "INSERT INTO group_messages (group_id, telegram_message_id, chat_id, sent_at) VALUES (?, ?, ?, ?)",
        (group["group_id"], telegram_message_id, chat_id, timestamp),
    )
    conn.commit()

    return {"candidate_id": candidate_id, "group_id": group["group_id"],
            "telegram_message_id": telegram_message_id}
