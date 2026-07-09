import json
from datetime import datetime, timezone

import pipeline.anthropic_client as anthropic_client
import pipeline.config as config


DISCLOSURE_TEXT = (
    "This design was created using AI image generation from the seller's own prompts, "
    "then selected, edited, and prepared for print by the seller. Printed and shipped "
    "by our production partner, Gelato."
)

MAX_TAGS = 13
MAX_TAG_LENGTH = 20
MAX_TITLE_LENGTH = 140


def resolve_compliance_metadata(static_config: dict) -> dict:
    return {
        "who_made": static_config["etsy_who_made"],
        "production_partner_ids": static_config["etsy_production_partner_ids"],
        "taxonomy_id": static_config["etsy_taxonomy_id"],
        "shipping_profile_id": static_config["etsy_shipping_profile_id"],
    }


def validate_listing_text(title: str, tags: list) -> None:
    if len(title) > MAX_TITLE_LENGTH:
        raise ValueError(
            f"title is {len(title)} chars, exceeds Etsy's {MAX_TITLE_LENGTH}-char limit: {title!r}"
        )
    if len(tags) > MAX_TAGS:
        raise ValueError(f"{len(tags)} tags exceeds Etsy's {MAX_TAGS}-tag limit: {tags!r}")
    for tag in tags:
        if len(tag) > MAX_TAG_LENGTH:
            raise ValueError(
                f"tag {tag!r} is {len(tag)} chars, exceeds Etsy's {MAX_TAG_LENGTH}-char limit"
            )


def get_primary_gallery(conn, candidate_id: int) -> list:
    rows = conn.execute(
        """
        SELECT pi.id, pi.gallery_order, pi.image_type
        FROM product_images pi
        JOIN group_products gp ON gp.id = pi.group_product_id
        JOIN groups g ON g.id = gp.group_id
        WHERE g.candidate_id = ? AND g.group_type = 'primary'
        ORDER BY pi.gallery_order
        """,
        (candidate_id,),
    ).fetchall()
    return [dict(row) for row in rows]
