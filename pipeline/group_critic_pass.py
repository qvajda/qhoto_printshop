from datetime import datetime, timezone

import pipeline.critic_pass as critic_pass
import pipeline.config as config
import pipeline.group_mockup as group_mockup


def get_group_critic_state(conn, candidate_id: int, group_type: str) -> dict:
    group_row = conn.execute(
        "SELECT id FROM groups WHERE candidate_id = ? AND group_type = ?",
        (candidate_id, group_type),
    ).fetchone()
    if group_row is None:
        raise ValueError(f"No {group_type} group for candidate {candidate_id}")
    group_id = group_row["id"]

    group_product_row = conn.execute(
        "SELECT id FROM group_products WHERE group_id = ? AND status = 'created'",
        (group_id,),
    ).fetchone()
    if group_product_row is None:
        raise ValueError(
            f"No live group_products row for candidate {candidate_id}'s {group_type} group"
        )
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


def abandon_group(conn, group_id: int, reason: str, *, now=None) -> None:
    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()
    conn.execute(
        "UPDATE groups SET status = 'failed_abandoned', failed_reason = ?, updated_at = ? WHERE id = ?",
        (reason, timestamp, group_id),
    )
    conn.commit()


def run_group_critic_pass(conn, candidate_id: int, group_type: str, *, static_config: dict = None,
                           anthropic_api_key: str = None, store_id: str = None,
                           gelato_api_key: str = None, now=None) -> dict:
    static_config = static_config if static_config is not None else config.load_static_config()

    group_row = conn.execute(
        "SELECT id FROM groups WHERE candidate_id = ? AND group_type = ?",
        (candidate_id, group_type),
    ).fetchone()
    if group_row is None:
        raise ValueError(f"No {group_type} group for candidate {candidate_id}")
    group_id = group_row["id"]

    max_attempt_row = conn.execute(
        "SELECT MAX(attempt_number) AS max_attempt FROM critic_pass_attempts WHERE group_id = ?",
        (group_id,),
    ).fetchone()
    attempt_number = (max_attempt_row["max_attempt"] or 0) + 1

    while True:
        state = get_group_critic_state(conn, candidate_id, group_type)
        result = critic_pass.evaluate_critic_pass(
            state["image_urls"], state["listing_text"], api_key=anthropic_api_key
        )
        critic_pass.record_critic_attempt(conn, group_id, attempt_number, result, now=now)

        if result["passed"]:
            return {"group_id": group_id, "passed": True, "attempts": attempt_number}

        critic_pass.discard_superseded_attempt(
            conn, state["group_product_id"], store_id=store_id, api_key=gelato_api_key
        )

        if attempt_number >= 3:
            abandon_group(conn, group_id, result["reason"], now=now)
            return {"group_id": group_id, "passed": False, "attempts": attempt_number}

        group_mockup.create_group_mockup(
            conn, candidate_id, group_type, static_config=static_config,
            store_id=store_id, api_key=gelato_api_key, now=now,
        )
        attempt_number += 1


def run_group_critic_pass_cycle(conn, *, static_config: dict = None, anthropic_api_key: str = None,
                                 store_id: str = None, gelato_api_key: str = None, now=None) -> list:
    static_config = static_config if static_config is not None else config.load_static_config()

    pairs = conn.execute(
        """
        SELECT DISTINCT g.candidate_id, g.group_type
        FROM groups g
        JOIN group_products gp ON gp.group_id = g.id
        WHERE g.group_type IN ('5x7', '10x24')
          AND g.status = 'pending_review'
          AND gp.status = 'created'
          AND g.id NOT IN (SELECT group_id FROM critic_pass_attempts WHERE passed = 1)
        ORDER BY g.candidate_id, g.group_type
        """
    ).fetchall()

    processed = []
    for row in pairs:
        candidate_id, group_type = row["candidate_id"], row["group_type"]
        try:
            result = run_group_critic_pass(
                conn, candidate_id, group_type, static_config=static_config,
                anthropic_api_key=anthropic_api_key, store_id=store_id,
                gelato_api_key=gelato_api_key, now=now,
            )
        except Exception as exc:
            print(f"run_group_critic_pass failed for candidate {candidate_id} "
                  f"group_type {group_type}: {exc}")
            continue
        processed.append({
            "candidate_id": candidate_id, "group_type": group_type, "passed": result["passed"],
        })
    return processed
