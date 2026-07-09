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

DRAFT_TEXT_PROMPT_TEMPLATE = (
    "You are writing an Etsy listing draft for an AI-generated botanical/minimalist wall "
    "art poster print, niche: {niche}. This listing must comply with Etsy's format limits: "
    "the title must be at most 140 characters, there must be at most 13 tags and each tag "
    "at most 20 characters, and the description must mention the following AI disclosure: "
    "\"{disclosure}\"\n\n"
    "The product gallery has {image_count} images in this order: {image_types}. Write one "
    "short, descriptive alt text per image, in the same order, distinguishing a flat print "
    "mockup shot from a lifestyle/room-context shot.\n\n"
    "Reply with ONLY a JSON object with keys 'title' (string), 'tags' (list of strings), "
    "'description' (string), and 'alt_texts' (list of strings, same length and order as the "
    "gallery), no other text."
)


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


def build_draft_prompt(candidate: dict, image_types: list) -> str:
    return DRAFT_TEXT_PROMPT_TEMPLATE.format(
        niche=candidate["niche"],
        disclosure=DISCLOSURE_TEXT,
        image_count=len(image_types),
        image_types=", ".join(image_types),
    )


def generate_draft_text(candidate: dict, image_types: list, *, api_key: str = None) -> dict:
    result = anthropic_client.complete(build_draft_prompt(candidate, image_types), api_key=api_key)
    draft = json.loads(result["text"])
    for key in ("title", "tags", "description", "alt_texts"):
        if key not in draft:
            raise ValueError(f"Claude draft response missing required key {key!r}: {draft!r}")
    if len(draft["alt_texts"]) != len(image_types):
        raise ValueError(
            f"Claude draft response has {len(draft['alt_texts'])} alt_texts, "
            f"expected {len(image_types)} to match the gallery: {draft!r}"
        )
    return draft


def write_listing_texts(conn, candidate_id: int, draft: dict, metadata: dict, *, now=None) -> int:
    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()
    cursor = conn.execute(
        """
        INSERT INTO listing_texts (
            candidate_id, title, tags, description, disclosure_text,
            who_made, production_partner_ids, taxonomy_id, shipping_profile_id, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            candidate_id, draft["title"], json.dumps(draft["tags"]), draft["description"], DISCLOSURE_TEXT,
            metadata["who_made"], json.dumps(metadata["production_partner_ids"]),
            metadata["taxonomy_id"], metadata["shipping_profile_id"], timestamp,
        ),
    )
    conn.commit()
    return cursor.lastrowid


def update_gallery_alt_text(conn, candidate_id: int, alt_texts: list) -> None:
    gallery = get_primary_gallery(conn, candidate_id)
    if len(alt_texts) != len(gallery):
        raise ValueError(
            f"{len(alt_texts)} alt_texts provided but candidate {candidate_id}'s primary "
            f"gallery has {len(gallery)} images"
        )
    for image, alt_text in zip(gallery, alt_texts):
        conn.execute(
            "UPDATE product_images SET alt_text = ? WHERE id = ?",
            (alt_text, image["id"]),
        )
    conn.commit()
