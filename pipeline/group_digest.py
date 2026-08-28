import json
from datetime import datetime, timezone

import pipeline.config as config
import pipeline.digest as digest
import pipeline.publish_primary_group as publish_primary_group
import pipeline.telegram_client as telegram_client


class GroupDigestCycleError(RuntimeError):
    """Raised once at the end of run_group_digest_cycle if any send failed.
    Same (b)-only reasoning as digest.DigestCycleError - see there."""


def get_review_group(conn, group_id: int) -> dict:
    # v4.12: the digest entry is still per group, but the variant rows it prices live on
    # the candidate's shared listing record - so they're read by group_id, not by
    # group_product_id alone.
    row = conn.execute(
        """
        SELECT g.candidate_id AS candidate_id, g.group_type AS group_type,
               (SELECT gp.id FROM group_products gp
                 WHERE gp.candidate_id = g.candidate_id AND gp.status != 'deleted'
                 ORDER BY gp.id LIMIT 1) AS group_product_id
        FROM groups g WHERE g.id = ?
        """,
        (group_id,),
    ).fetchone()
    if row is None or row["group_product_id"] is None:
        raise ValueError(f"No live group_product for group {group_id}")
    variant_rows = conn.execute(
        "SELECT size, price_eur FROM group_product_variants WHERE group_product_id = ? "
        "AND group_id = ? ORDER BY size",
        (row["group_product_id"], group_id),
    ).fetchall()
    return {
        "candidate_id": row["candidate_id"],
        "group_type": row["group_type"],
        "variants": [{"size": r["size"], "price_eur": r["price_eur"]} for r in variant_rows],
    }


def get_group_gallery_urls(conn, group_id: int) -> list:
    rows = conn.execute(
        """
        SELECT pi.image_url
        FROM product_images pi
        JOIN group_products gp ON gp.id = pi.group_product_id AND gp.status != 'deleted'
        WHERE pi.group_id = ?
        ORDER BY pi.gallery_order
        """,
        (group_id,),
    ).fetchall()
    return [row["image_url"] for row in rows]


def build_group_digest_message_text(candidate_id: int, group_id: int, group_type: str,
                                     listing_text: dict, variants: list) -> str:
    tags = ", ".join(json.loads(listing_text["tags"]))
    price_lines = " · ".join(f"{v['size']} €{v['price_eur']}" for v in variants)
    return (
        f"Candidate #{candidate_id} — {group_type} group (#{group_id})\n\n"
        f"{listing_text['title']}\n\n"
        f"{listing_text['description']}\n\n"
        f"Tags: {tags}\n\n"
        f"Sizes: {price_lines}"
    )


def send_group_digest(conn, group_id: int, *, static_config: dict = None,
                       bot_token: str = None, chat_id: str = None, now=None,
                       reminder: bool = False) -> dict:
    # Duplicate-send guard (M1): if this group already has a group_messages row, the
    # digest went out before - don't re-send the gallery. The two-call send isn't
    # atomic (sendMediaGroup then sendMessage+row-insert), so a re-run must not
    # re-fire the gallery for a group already surfaced. GL-31: the reminder path
    # deliberately bypasses this - it exists BECAUSE a group_messages row already
    # exists (that is the whole point of a re-send).
    if not reminder:
        existing = conn.execute(
            "SELECT 1 FROM group_messages WHERE group_id = ? LIMIT 1", (group_id,)
        ).fetchone()
        if existing is not None:
            return {"candidate_id": None, "group_id": group_id, "telegram_message_id": None, "skipped": True}

    review_group = get_review_group(conn, group_id)
    candidate_id = review_group["candidate_id"]
    group_type = review_group["group_type"]
    variants = review_group["variants"]

    photo_urls = get_group_gallery_urls(conn, group_id)
    listing_text = digest.get_listing_text(conn, candidate_id)
    chat_id = chat_id or config.require_env("TELEGRAM_ADMIN_CHAT_ID")

    telegram_client.send_media_group(chat_id, photo_urls, bot_token=bot_token)

    text = build_group_digest_message_text(candidate_id, group_id, group_type, listing_text, variants)
    reply_markup = digest.build_digest_keyboard(group_id)
    response = telegram_client.send_message(chat_id, text, reply_markup, bot_token=bot_token)
    telegram_message_id = response["result"]["message_id"]

    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()
    conn.execute(
        "INSERT INTO group_messages (group_id, telegram_message_id, chat_id, sent_at) VALUES (?, ?, ?, ?)",
        (group_id, telegram_message_id, chat_id, timestamp),
    )
    if reminder:
        # Same commit as the send it belongs to (GL-31): read before any further send,
        # so a group cannot be reminded twice.
        conn.execute("UPDATE groups SET reminder_sent_at = ? WHERE id = ?", (timestamp, group_id))
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
            WHERE g.group_type IN ('5x7', '10x24')
              AND EXISTS (SELECT 1 FROM product_images pi WHERE pi.group_id = g.id)
              AND g.status = 'pending_review'
              AND g.id IN (SELECT group_id FROM critic_pass_attempts WHERE passed = 1)
              AND g.id NOT IN (SELECT group_id FROM group_messages)
            ORDER BY g.id
            """
        ).fetchall()
    ]
    processed_ids = []
    failures = []
    for group_id in group_ids:
        try:
            send_group_digest(
                conn, group_id, static_config=static_config,
                bot_token=bot_token, chat_id=chat_id, now=now,
            )
        except Exception as exc:
            print(f"send_group_digest failed for group {group_id}: {exc}")
            failures.append(f"group {group_id}: {exc}")
            continue
        processed_ids.append(group_id)

    # GL-31: the stall reminder sweep runs after the normal pass, in the same
    # per-group-failure shape (GL-46) - a failed reminder leaves reminder_sent_at
    # NULL so the next cycle retries it, and the cycle still raises once at the end.
    resolved_static_config = static_config if static_config is not None else config.load_static_config()
    reminder_group_ids = publish_primary_group.groups_due_for_reminder(
        conn, resolved_static_config, now=now,
    )
    for group_id in reminder_group_ids:
        try:
            send_group_digest(
                conn, group_id, static_config=static_config,
                bot_token=bot_token, chat_id=chat_id, now=now, reminder=True,
            )
        except Exception as exc:
            print(f"reminder send_group_digest failed for group {group_id}: {exc}")
            failures.append(f"group {group_id} (reminder): {exc}")
            continue
        processed_ids.append(group_id)

    if failures:
        raise GroupDigestCycleError(
            f"{len(failures)} group digest send(s) failed - " + "; ".join(failures)
        )
    return processed_ids
