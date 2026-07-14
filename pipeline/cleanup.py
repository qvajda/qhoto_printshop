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
