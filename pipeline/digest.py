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
