from datetime import datetime, timedelta, timezone

import pipeline.gelato_client as gelato_client


def cleanup_orphaned_gelato_products(conn, *, store_id=None, api_key=None, now=None) -> list:
    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()
    rows = conn.execute(
        """
        SELECT gp.id, gp.gelato_product_id
        FROM group_products gp
        JOIN groups g ON g.id = gp.group_id
        WHERE gp.gelato_product_id IS NOT NULL
          AND gp.status != 'deleted'
          AND (gp.status = 'publish_failed' OR g.status IN ('rejected', 'failed_abandoned'))
        """
    ).fetchall()

    deleted = []
    for row in rows:
        try:
            gelato_client.delete_product(row["gelato_product_id"], store_id=store_id, api_key=api_key)
        except Exception as exc:
            print(f"cleanup_orphaned_gelato_products failed for group_product {row['id']}: {exc}")
            continue
        conn.execute(
            "UPDATE group_products SET status = 'deleted', updated_at = ? WHERE id = ?",
            (timestamp, row["id"]),
        )
        conn.commit()
        deleted.append(row["id"])
    return deleted


def prune_telegram_events_log(conn, *, retention_days=30, now=None) -> int:
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    cutoff = (now - timedelta(days=retention_days)).isoformat()
    cursor = conn.execute("DELETE FROM telegram_events_log WHERE received_at < ?", (cutoff,))
    conn.commit()
    return cursor.rowcount


def prune_stale_candidates(conn, *, retention_days=30, now=None) -> list:
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    cutoff = (now - timedelta(days=retention_days)).isoformat()
    rows = conn.execute(
        """
        SELECT id FROM candidates
        WHERE status IN ('failed', 'abandoned', 'completed')
          AND updated_at < ?
          AND id NOT IN (
            SELECT g.candidate_id
            FROM groups g
            JOIN group_products gp ON gp.group_id = g.id
            WHERE gp.gelato_product_id IS NOT NULL AND gp.status != 'deleted'
          )
        """,
        (cutoff,),
    ).fetchall()

    pruned = []
    for row in rows:
        candidate_id = row["id"]
        conn.execute(
            "DELETE FROM listing_metrics_snapshots WHERE group_product_id IN "
            "(SELECT id FROM group_products WHERE group_id IN "
            "(SELECT id FROM groups WHERE candidate_id = ?))",
            (candidate_id,),
        )
        conn.execute(
            "DELETE FROM product_images WHERE group_product_id IN "
            "(SELECT id FROM group_products WHERE group_id IN "
            "(SELECT id FROM groups WHERE candidate_id = ?))",
            (candidate_id,),
        )
        conn.execute(
            "DELETE FROM group_products WHERE group_id IN "
            "(SELECT id FROM groups WHERE candidate_id = ?)",
            (candidate_id,),
        )
        conn.execute(
            "DELETE FROM critic_pass_attempts WHERE group_id IN "
            "(SELECT id FROM groups WHERE candidate_id = ?)",
            (candidate_id,),
        )
        conn.execute(
            "DELETE FROM group_messages WHERE group_id IN "
            "(SELECT id FROM groups WHERE candidate_id = ?)",
            (candidate_id,),
        )
        conn.execute("DELETE FROM groups WHERE candidate_id = ?", (candidate_id,))
        conn.execute("DELETE FROM listing_texts WHERE candidate_id = ?", (candidate_id,))
        conn.execute("DELETE FROM candidates WHERE id = ?", (candidate_id,))
        conn.commit()
        pruned.append(candidate_id)
    return pruned


def run_cleanup(conn, *, store_id=None, gelato_api_key=None, retention_days=30, now=None) -> dict:
    gelato_deleted = cleanup_orphaned_gelato_products(
        conn, store_id=store_id, api_key=gelato_api_key, now=now
    )
    candidates_pruned = prune_stale_candidates(conn, retention_days=retention_days, now=now)
    events_pruned = prune_telegram_events_log(conn, retention_days=retention_days, now=now)
    return {
        "gelato_products_deleted": gelato_deleted,
        "candidates_pruned": candidates_pruned,
        "telegram_events_pruned": events_pruned,
    }
