from datetime import datetime, timezone

import pipeline.config as config
import pipeline.critic_pass as critic_pass
import pipeline.group_product as group_product
import pipeline.publish_primary_group as publish_primary_group


def get_live_group_product(conn, group_id: int) -> dict:
    """v4.12: resolved through the group's CANDIDATE - the listing record is the
    candidate's, shared by every group, and carries no Gelato product until publish."""
    group_row = conn.execute("SELECT candidate_id FROM groups WHERE id = ?", (group_id,)).fetchone()
    row = None if group_row is None else group_product.live_product_row(
        conn, group_row["candidate_id"], group_id
    )
    if row is None:
        raise ValueError(f"No live group_product for group {group_id}")
    return dict(row)


def _discard_group_contribution(conn, candidate_id, group_id, *, store_id=None, gelato_api_key=None):
    """Drop this group's variants and gallery images from the candidate's listing record.
    Deletes nothing shared: no Gelato product, no Etsy listing, no group_products row."""
    live_row = group_product.live_product_row(conn, candidate_id, group_id)
    if live_row is not None:
        critic_pass.discard_superseded_attempt(
            conn, live_row["id"], group_id, store_id=store_id, api_key=gelato_api_key,
        )


def handle_decision(conn, candidate_id, group_id, action, decision_notes=None, *,
                     static_config=None, store_id=None, gelato_api_key=None, shop_id=None,
                     etsy_api_key=None, etsy_api_secret=None, etsy_access_token=None,
                     dry_run=None, now=None) -> dict:
    timestamp = now if isinstance(now, str) else (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()
    # One map, shared with the listener that may have recorded this decision already.
    decision = publish_primary_group.DECISION_BY_ACTION.get(action)

    if action == "approve":
        publish_primary_group.record_decision(conn, group_id, decision, decision_notes, now=now)
        static_config = static_config if static_config is not None else config.load_static_config()
        # v4.12 [D1]: a secondary approval doesn't publish anything by itself - it just
        # settles one more group. The candidate's single listing is created once, when
        # the gate below finds every group decided.
        result = publish_primary_group.publish_primary_group(
            conn, candidate_id, static_config=static_config, store_id=store_id,
            gelato_api_key=gelato_api_key, shop_id=shop_id, etsy_api_key=etsy_api_key,
            etsy_api_secret=etsy_api_secret, etsy_access_token=etsy_access_token,
            dry_run=dry_run, now=now,
        )
        return {"action": "approve", **result}

    if action == "reject":
        publish_primary_group.record_decision(conn, group_id, decision, decision_notes, now=now)
        # Rejecting a secondary group deletes NOTHING shared (CLAUDE.md v4.12): its own
        # sizes and images leave the candidate's listing build, the product/listing and
        # every other group's rows are untouched.
        _discard_group_contribution(
            conn, candidate_id, group_id, store_id=store_id, gelato_api_key=gelato_api_key,
        )
        conn.execute(
            "UPDATE groups SET status = 'rejected', updated_at = ? WHERE id = ?",
            (timestamp, group_id),
        )
        conn.commit()
        # The rejection may have been the last undecided group - the candidate then
        # publishes with the sizes that did pass.
        static_config = static_config if static_config is not None else config.load_static_config()
        result = publish_primary_group.publish_primary_group(
            conn, candidate_id, static_config=static_config, store_id=store_id,
            gelato_api_key=gelato_api_key, shop_id=shop_id, etsy_api_key=etsy_api_key,
            etsy_api_secret=etsy_api_secret, etsy_access_token=etsy_access_token,
            dry_run=dry_run, now=now,
        )
        return {"action": "reject", **result}

    if action == "edit":
        publish_primary_group.record_decision(conn, group_id, decision, decision_notes, now=now)
        _discard_group_contribution(
            conn, candidate_id, group_id, store_id=store_id, gelato_api_key=gelato_api_key,
        )
        conn.execute("DELETE FROM critic_pass_attempts WHERE group_id = ?", (group_id,))
        conn.execute("DELETE FROM group_messages WHERE group_id = ?", (group_id,))
        conn.commit()
        return {"action": "edit"}

    raise ValueError(f"Unknown action {action!r}")
