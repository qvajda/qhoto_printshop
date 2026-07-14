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
        f"{listing_text['disclosure_text']}\n\n"
        f"Price: €{price_eur}"
    )
