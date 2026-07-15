import json
from datetime import datetime, timezone

import pipeline.config as config
import pipeline.digest as digest
import pipeline.telegram_client as telegram_client


def get_review_group(conn, group_id: int) -> dict:
    row = conn.execute(
        """
        SELECT g.candidate_id AS candidate_id, g.group_type AS group_type, gp.price_eur AS price_eur
        FROM groups g
        JOIN group_products gp ON gp.group_id = g.id AND gp.status = 'created'
        WHERE g.id = ?
        """,
        (group_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"No live group_product for group {group_id}")
    return dict(row)


def get_group_gallery_urls(conn, group_id: int) -> list:
    rows = conn.execute(
        """
        SELECT pi.image_url
        FROM product_images pi
        JOIN group_products gp ON gp.id = pi.group_product_id AND gp.status = 'created'
        WHERE gp.group_id = ?
        ORDER BY pi.gallery_order
        """,
        (group_id,),
    ).fetchall()
    return [row["image_url"] for row in rows]


def build_group_digest_message_text(candidate_id: int, group_id: int, group_type: str,
                                     listing_text: dict, price_eur: float) -> str:
    tags = ", ".join(json.loads(listing_text["tags"]))
    return (
        f"Candidate #{candidate_id} — {group_type} group (#{group_id})\n\n"
        f"{listing_text['title']}\n\n"
        f"{listing_text['description']}\n\n"
        f"Tags: {tags}\n\n"
        f"Price: €{price_eur}"
    )


def send_group_digest(conn, group_id: int, *, static_config: dict = None,
                       bot_token: str = None, chat_id: str = None, now=None) -> dict:
    review_group = get_review_group(conn, group_id)
    candidate_id = review_group["candidate_id"]
    group_type = review_group["group_type"]
    price_eur = review_group["price_eur"]

    photo_urls = get_group_gallery_urls(conn, group_id)
    listing_text = digest.get_listing_text(conn, candidate_id)
    chat_id = chat_id or config.require_env("TELEGRAM_ADMIN_CHAT_ID")

    telegram_client.send_media_group(chat_id, photo_urls, bot_token=bot_token)

    text = build_group_digest_message_text(candidate_id, group_id, group_type, listing_text, price_eur)
    reply_markup = digest.build_digest_keyboard(group_id)
    response = telegram_client.send_message(chat_id, text, reply_markup, bot_token=bot_token)
    telegram_message_id = response["result"]["message_id"]

    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()
    conn.execute(
        "INSERT INTO group_messages (group_id, telegram_message_id, chat_id, sent_at) VALUES (?, ?, ?, ?)",
        (group_id, telegram_message_id, chat_id, timestamp),
    )
    conn.commit()

    return {"candidate_id": candidate_id, "group_id": group_id,
            "telegram_message_id": telegram_message_id}


def run_group_digest_cycle(conn, *, static_config: dict = None, bot_token: str = None,
                            chat_id: str = None, now=None) -> list:
    group_ids = [
        row["id"] for row in conn.execute(
            """
            SELECT DISTINCT g.id
            FROM groups g
            JOIN group_products gp ON gp.group_id = g.id AND gp.status = 'created'
            WHERE g.group_type IN ('5x7', '10x24')
              AND g.status = 'pending_review'
              AND g.id IN (SELECT group_id FROM critic_pass_attempts WHERE passed = 1)
              AND g.id NOT IN (SELECT group_id FROM group_messages)
            ORDER BY g.id
            """
        ).fetchall()
    ]
    processed_ids = []
    for group_id in group_ids:
        try:
            send_group_digest(
                conn, group_id, static_config=static_config,
                bot_token=bot_token, chat_id=chat_id, now=now,
            )
        except Exception as exc:
            print(f"send_group_digest failed for group {group_id}: {exc}")
            continue
        processed_ids.append(group_id)
    return processed_ids
