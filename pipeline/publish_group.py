from datetime import datetime, timezone

import pipeline.config as config
import pipeline.critic_pass as critic_pass
import pipeline.publish_primary_group as publish_primary_group


def get_live_group_product(conn, group_id: int) -> dict:
    row = conn.execute(
        "SELECT * FROM group_products WHERE group_id = ? AND status IN ('created', 'published') "
        "ORDER BY id LIMIT 1",
        (group_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"No live group_product for group {group_id}")
    return dict(row)


def handle_decision(conn, candidate_id, group_id, action, decision_notes=None, *,
                     static_config=None, store_id=None, gelato_api_key=None, shop_id=None,
                     etsy_api_key=None, etsy_api_secret=None, etsy_access_token=None,
                     dry_run=None, now=None) -> dict:
    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()

    if action == "approve":
        publish_primary_group.record_decision(conn, group_id, "approved", decision_notes, now=now)
        static_config = static_config if static_config is not None else config.load_static_config()

        group_product = get_live_group_product(conn, group_id)
        candidate = dict(
            conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
        )

        listing_id = publish_primary_group.publish_group_product(
            conn, group_product["id"], candidate, static_config, store_id=store_id,
            gelato_api_key=gelato_api_key, shop_id=shop_id, etsy_api_key=etsy_api_key,
            etsy_api_secret=etsy_api_secret, etsy_access_token=etsy_access_token,
            dry_run=dry_run, now=now,
        )

        conn.execute(
            "UPDATE groups SET status = 'approved_published', updated_at = ? WHERE id = ?",
            (timestamp, group_id),
        )
        conn.commit()
        return {"action": "approve", "listing_id": listing_id}

    if action == "reject":
        publish_primary_group.record_decision(conn, group_id, "rejected", decision_notes, now=now)

        live_row = conn.execute(
            "SELECT id FROM group_products WHERE group_id = ? AND status IN ('created', 'published') "
            "ORDER BY id LIMIT 1",
            (group_id,),
        ).fetchone()
        if live_row is not None:
            critic_pass.discard_superseded_attempt(
                conn, live_row["id"], store_id=store_id, api_key=gelato_api_key,
            )

        conn.execute(
            "UPDATE groups SET status = 'rejected', updated_at = ? WHERE id = ?",
            (timestamp, group_id),
        )
        conn.commit()
        return {"action": "reject"}

    if action == "edit":
        publish_primary_group.record_decision(conn, group_id, "edited", decision_notes, now=now)

        live_row = conn.execute(
            "SELECT id FROM group_products WHERE group_id = ? AND status IN ('created', 'published') "
            "ORDER BY id LIMIT 1",
            (group_id,),
        ).fetchone()
        if live_row is not None:
            critic_pass.discard_superseded_attempt(
                conn, live_row["id"], store_id=store_id, api_key=gelato_api_key,
            )

        conn.execute("DELETE FROM critic_pass_attempts WHERE group_id = ?", (group_id,))
        conn.execute("DELETE FROM group_messages WHERE group_id = ?", (group_id,))
        conn.commit()
        return {"action": "edit"}

    raise ValueError(f"Unknown action {action!r}")
