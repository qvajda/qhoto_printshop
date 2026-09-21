"""#230: daily views/num_favorers snapshot per published listing into
listing_metrics_snapshots. orders_count is written NULL - getListing carries no order
count, and a literal 0 would look measured (GL-53 shape).

Dry-run gates only the DB write: rows are still selected and the get_listing call still
goes through (it returns a metrics-free stub in dry-run, counted as would-write only when
metrics are present)."""
from datetime import datetime, timezone

import pipeline.config as config
import pipeline.etsy_client as etsy_client


def run_listing_metrics(
    conn, *, api_key=None, api_secret=None, access_token=None, today=None, dry_run_override=None,
) -> dict:
    today = today or datetime.now(timezone.utc).date().isoformat()
    dry_run = dry_run_override if dry_run_override is not None else not config.is_live_mode("ETSY")
    rows = conn.execute(
        "SELECT id, etsy_listing_id FROM group_products "
        "WHERE status = 'published' AND etsy_listing_id IS NOT NULL "
        "AND id NOT IN (SELECT group_product_id FROM listing_metrics_snapshots WHERE snapshot_date = ?)",
        (today,),
    ).fetchall()

    written = []
    failed = []
    for row in rows:
        try:
            listing = etsy_client.get_listing(
                row["etsy_listing_id"], api_key=api_key, api_secret=api_secret,
                access_token=access_token, dry_run=dry_run_override,
            )
            # dry-run stub has no metrics; it is never written, so don't demand them.
            views, favorers = listing.get("views"), listing.get("num_favorers")
            if not dry_run:
                views, favorers = listing["views"], listing["num_favorers"]
        except Exception as exc:
            failed.append(f"{row['etsy_listing_id']} ({exc})")
            continue
        if not dry_run:
            conn.execute(
                "INSERT INTO listing_metrics_snapshots "
                "(group_product_id, snapshot_date, views, num_favorers, orders_count) "
                "VALUES (?, ?, ?, ?, NULL)",
                (row["id"], today, views, favorers),
            )
            conn.commit()
        written.append(row["id"])

    # GL-46: no status column on a snapshot row, so fail once, after the loop, naming ids.
    if failed and not dry_run:
        raise RuntimeError(f"listing_metrics: {len(failed)} listing(s) failed: {'; '.join(failed)}")
    return {"selected": len(rows), "written": [] if dry_run else written, "would_write": len(written), "failed": failed}
