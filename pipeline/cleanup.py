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


def reclaim_stranded_pending_group_products(conn, *, max_age_minutes=10, now=None) -> list:
    """GL-16: create_or_reuse_group_product commits a 'pending' group_products row,
    then enters the try block that actually calls Gelato. A hard kill in that
    narrow window (row committed, no Gelato call made) leaves a row neither of
    that function's own lookups recognize - not 'created'/'published' (live), not
    'mockup_failed'/'publish_failed' (reusable/deletable) - so it's invisible and
    leaks forever while every later cron cycle inserts a fresh row instead of
    reclaiming it. No Gelato product was ever created for it (gelato_product_id
    is still NULL), so there's nothing to delete_product - just remove the row.
    10-minute default sits with margin above group_product.poll_until_ready's
    300s (5 min) timeout, so a still-legitimately-in-flight create is never
    reclaimed out from under itself."""
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    cutoff = (now - timedelta(minutes=max_age_minutes)).isoformat()
    rows = conn.execute(
        "SELECT id FROM group_products WHERE status = 'pending' AND gelato_product_id IS NULL "
        "AND created_at < ?",
        (cutoff,),
    ).fetchall()

    reclaimed = []
    for row in rows:
        conn.execute("DELETE FROM group_product_variants WHERE group_product_id = ?", (row["id"],))
        conn.execute("DELETE FROM group_products WHERE id = ?", (row["id"],))
        conn.commit()
        reclaimed.append(row["id"])
    return reclaimed


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
            "DELETE FROM group_product_variants WHERE group_product_id IN "
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


def run_cleanup(conn, *, store_id=None, gelato_api_key=None, retention_days=30,
                 stranded_pending_max_age_minutes=10, now=None) -> dict:
    gelato_deleted = cleanup_orphaned_gelato_products(
        conn, store_id=store_id, api_key=gelato_api_key, now=now
    )
    stranded_reclaimed = reclaim_stranded_pending_group_products(
        conn, max_age_minutes=stranded_pending_max_age_minutes, now=now
    )
    candidates_pruned = prune_stale_candidates(conn, retention_days=retention_days, now=now)
    events_pruned = prune_telegram_events_log(conn, retention_days=retention_days, now=now)
    return {
        "gelato_products_deleted": gelato_deleted,
        "stranded_pending_group_products_reclaimed": stranded_reclaimed,
        "candidates_pruned": candidates_pruned,
        "telegram_events_pruned": events_pruned,
    }
