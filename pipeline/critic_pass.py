import json
from datetime import datetime, timezone

import pipeline.anthropic_client as anthropic_client
import pipeline.compliance_draft as compliance_draft
import pipeline.config as config
import pipeline.gelato_client as gelato_client
import pipeline.generate as generate
import pipeline.primary_mockup as primary_mockup
import pipeline.research as research


CRITIC_RUBRIC_PROMPT_TEMPLATE = (
    "You are the compliance and quality critic for an Etsy AI-generated wall art listing. "
    "Review the {image_count} gallery images above against this rubric:\n"
    "1. Hard no-go list: no named artist's style, no recognizable characters, franchises, or "
    "logos, no implied celebrity likeness, no claims of hand-painted or one-of-a-kind original "
    "artwork - this is a print reproduction.\n"
    "2. Image quality: no obvious artifacts, no garbled or watermark-like elements, no "
    "off-center or cut-off composition, in any image.\n"
    "3. Text match: does this draft title and description actually match what's shown in the "
    "images and fit the niche?\n\n"
    "Title: {title}\n"
    "Description: {description}\n\n"
    "Reply with ONLY a JSON object with keys 'passed' (boolean) and 'reason' (string explaining "
    "the verdict - cite the specific rubric point if failing), no other text."
)


def build_critic_prompt(listing_text: dict, image_count: int) -> str:
    return CRITIC_RUBRIC_PROMPT_TEMPLATE.format(
        image_count=image_count,
        title=listing_text["title"],
        description=listing_text["description"],
    )


def evaluate_critic_pass(gallery_image_urls: list, listing_text: dict, *, api_key: str = None) -> dict:
    prompt = build_critic_prompt(listing_text, len(gallery_image_urls))
    result = anthropic_client.complete_with_images(prompt, gallery_image_urls, api_key=api_key)
    parsed = json.loads(result["text"])
    for key in ("passed", "reason"):
        if key not in parsed:
            raise ValueError(f"Claude critic response missing required key {key!r}: {parsed!r}")
    return {"passed": parsed["passed"], "reason": parsed["reason"]}


def get_primary_group_state(conn, candidate_id: int) -> dict:
    group_row = conn.execute(
        "SELECT id FROM groups WHERE candidate_id = ? AND group_type = 'primary'",
        (candidate_id,),
    ).fetchone()
    if group_row is None:
        raise ValueError(f"No primary group for candidate {candidate_id}")
    group_id = group_row["id"]

    group_product_row = conn.execute(
        "SELECT id FROM group_products WHERE group_id = ? AND status = 'created'",
        (group_id,),
    ).fetchone()
    if group_product_row is None:
        raise ValueError(f"No live group_products row for candidate {candidate_id}'s primary group")
    group_product_id = group_product_row["id"]

    image_rows = conn.execute(
        "SELECT image_url FROM product_images WHERE group_product_id = ? ORDER BY gallery_order",
        (group_product_id,),
    ).fetchall()
    image_urls = [row["image_url"] for row in image_rows]

    listing_row = conn.execute(
        "SELECT title, tags, description FROM listing_texts WHERE candidate_id = ?",
        (candidate_id,),
    ).fetchone()
    if listing_row is None:
        raise ValueError(f"No listing_texts row for candidate {candidate_id}")

    return {
        "group_id": group_id,
        "group_product_id": group_product_id,
        "image_urls": image_urls,
        "listing_text": dict(listing_row),
    }


def record_critic_attempt(conn, group_id: int, attempt_number: int, result: dict,
                           correction_notes: str = None, *, now=None) -> int:
    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()
    cursor = conn.execute(
        """
        INSERT INTO critic_pass_attempts (
            group_id, attempt_number, passed, failure_reason, correction_notes, created_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            group_id, attempt_number, 1 if result["passed"] else 0,
            None if result["passed"] else result["reason"],
            correction_notes, timestamp,
        ),
    )
    conn.commit()
    return cursor.lastrowid


def discard_superseded_attempt(conn, group_product_id: int, *, store_id: str = None, api_key: str = None) -> None:
    row = conn.execute(
        "SELECT gelato_product_id FROM group_products WHERE id = ?", (group_product_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"No group_products row with id {group_product_id}")
    if row["gelato_product_id"]:
        gelato_client.delete_product(row["gelato_product_id"], store_id=store_id, api_key=api_key)
    conn.execute("DELETE FROM product_images WHERE group_product_id = ?", (group_product_id,))
    conn.execute("DELETE FROM group_products WHERE id = ?", (group_product_id,))
    conn.commit()


def abandon_candidate(conn, candidate_id: int, group_id: int, reason: str, *, now=None) -> None:
    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()
    conn.execute(
        "UPDATE candidates SET status = 'failed', failed_reason = ?, updated_at = ? WHERE id = ?",
        (reason, timestamp, candidate_id),
    )
    conn.execute(
        "UPDATE groups SET status = 'failed_abandoned', failed_reason = ?, updated_at = ? WHERE id = ?",
        (reason, timestamp, group_id),
    )
    conn.commit()


def run_critic_pass(conn, candidate_id: int, *, static_config: dict = None,
                     anthropic_api_key: str = None, store_id: str = None,
                     gelato_api_key: str = None, replicate_api_token: str = None,
                     now=None) -> dict:
    static_config = static_config if static_config is not None else config.load_static_config()

    attempt_number = 1
    while True:
        state = get_primary_group_state(conn, candidate_id)
        result = evaluate_critic_pass(
            state["image_urls"], state["listing_text"], api_key=anthropic_api_key
        )
        record_critic_attempt(conn, state["group_id"], attempt_number, result, now=now)

        if result["passed"]:
            timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()
            conn.execute(
                "UPDATE candidates SET status = 'primary_review', updated_at = ? WHERE id = ?",
                (timestamp, candidate_id),
            )
            conn.commit()
            return {"candidate_id": candidate_id, "passed": True, "attempts": attempt_number}

        discard_superseded_attempt(
            conn, state["group_product_id"], store_id=store_id, api_key=gelato_api_key
        )

        if attempt_number >= 3:
            abandon_candidate(conn, candidate_id, state["group_id"], result["reason"], now=now)
            research.trigger_fallback_if_needed(conn, now=now)
            return {"candidate_id": candidate_id, "passed": False, "attempts": attempt_number}

        conn.execute("DELETE FROM listing_texts WHERE candidate_id = ?", (candidate_id,))
        conn.commit()

        generate.generate_for_candidate(
            conn, candidate_id, correction_note=result["reason"],
            api_token=replicate_api_token, now=now,
        )
        primary_mockup.create_primary_mockup(
            conn, candidate_id, static_config=static_config, store_id=store_id,
            api_key=gelato_api_key, now=now,
        )
        compliance_draft.build_compliance_draft(
            conn, candidate_id, static_config=static_config,
            anthropic_api_key=anthropic_api_key, now=now,
        )
        attempt_number += 1


def run_critic_pass_cycle(conn, *, static_config: dict = None, anthropic_api_key: str = None,
                           store_id: str = None, gelato_api_key: str = None,
                           replicate_api_token: str = None, now=None) -> list:
    candidate_ids = [
        row["id"] for row in conn.execute(
            """
            SELECT DISTINCT c.id FROM candidates c
            JOIN groups g ON g.candidate_id = c.id AND g.group_type = 'primary'
            JOIN listing_texts lt ON lt.candidate_id = c.id
            WHERE c.status = 'generating'
              AND g.id NOT IN (SELECT group_id FROM critic_pass_attempts WHERE passed = 1)
            ORDER BY c.id
            """
        ).fetchall()
    ]
    processed_ids = []
    for candidate_id in candidate_ids:
        try:
            run_critic_pass(
                conn, candidate_id, static_config=static_config, anthropic_api_key=anthropic_api_key,
                store_id=store_id, gelato_api_key=gelato_api_key,
                replicate_api_token=replicate_api_token, now=now,
            )
        except Exception as exc:
            print(f"run_critic_pass failed for candidate {candidate_id}: {exc}")
            continue
        processed_ids.append(candidate_id)
    return processed_ids
