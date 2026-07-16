import json
from datetime import datetime, timezone

import pipeline.config as config
import pipeline.telegram_client as telegram_client


def get_primary_group(conn, candidate_id: int) -> dict:
    row = conn.execute(
        """
        SELECT g.id AS group_id, gp.id AS group_product_id
        FROM groups g
        JOIN group_products gp ON gp.group_id = g.id AND gp.status = 'created'
        WHERE g.candidate_id = ? AND g.group_type = 'primary'
        """,
        (candidate_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"No live primary group_product for candidate {candidate_id}")
    variant_rows = conn.execute(
        "SELECT size, price_eur FROM group_product_variants WHERE group_product_id = ? ORDER BY size",
        (row["group_product_id"],),
    ).fetchall()
    return {
        "group_id": row["group_id"],
        "variants": [{"size": r["size"], "price_eur": r["price_eur"]} for r in variant_rows],
    }


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


def build_digest_message_text(candidate_id: int, group_id: int, listing_text: dict, variants: list) -> str:
    tags = ", ".join(json.loads(listing_text["tags"]))
    price_lines = " · ".join(f"{v['size']} €{v['price_eur']}" for v in variants)
    return (
        f"Candidate #{candidate_id} — Primary group (#{group_id})\n\n"
        f"{listing_text['title']}\n\n"
        f"{listing_text['description']}\n\n"
        f"Tags: {tags}\n\n"
        f"Sizes: {price_lines}"
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

    text = build_digest_message_text(candidate_id, group["group_id"], listing_text, group["variants"])
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


def run_digest_cycle(conn, *, static_config: dict = None, bot_token: str = None,
                      chat_id: str = None, now=None) -> list:
    candidate_ids = [
        row["id"] for row in conn.execute(
            """
            SELECT DISTINCT c.id FROM candidates c
            JOIN groups g ON g.candidate_id = c.id AND g.group_type = 'primary'
            WHERE c.status = 'primary_review'
              AND g.id NOT IN (SELECT group_id FROM group_messages)
            ORDER BY c.id
            """
        ).fetchall()
    ]
    processed_ids = []
    for candidate_id in candidate_ids:
        try:
            send_primary_digest(
                conn, candidate_id, static_config=static_config,
                bot_token=bot_token, chat_id=chat_id, now=now,
            )
        except Exception as exc:
            print(f"send_primary_digest failed for candidate {candidate_id}: {exc}")
            continue
        processed_ids.append(candidate_id)
    return processed_ids
