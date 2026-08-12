"""GL-36 (rescoped 2026-08-05): the pipeline is not the only writer to the
resources it tracks. Two drift shapes GL-13 exposed:

1. A candidate stuck in 'generating' (a crashed/never-resolved Replicate
   prediction) blocks nothing downstream by itself, but leaks forever if no
   cadence ever revisits it - age it out.
2. A group_products row claims 'published' against an Etsy listing that no
   longer exists (deleted by hand, or by Gelato's own sync). Positive matching
   only: a row is marked 'listing_missing' on a DEFINITIVE 404, never on a
   timeout/401/5xx - GL-33's lesson is that a bad afternoon at a third-party
   API must not read as "the whole shop is dead."
"""
from datetime import datetime, timedelta, timezone

import pipeline.etsy_client as etsy_client
import pipeline.http as http


def age_out_stranded_generating(conn, *, max_age_hours=12, now=None) -> list:
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    cutoff = (now - timedelta(hours=max_age_hours)).isoformat()
    rows = conn.execute(
        "SELECT id FROM candidates WHERE status = 'generating' AND updated_at < ?",
        (cutoff,),
    ).fetchall()

    aged_out = []
    for row in rows:
        conn.execute(
            "UPDATE candidates SET status = 'failed', "
            "failed_reason = 'gl36_generation_stalled', updated_at = ? WHERE id = ?",
            (now.isoformat(), row["id"]),
        )
        conn.commit()
        aged_out.append(row["id"])
    return aged_out


def reconcile_etsy_listings(
    conn, *, shop_id=None, api_key=None, api_secret=None, access_token=None,
    now=None, dry_run_override=None,
) -> dict:
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    rows = conn.execute(
        "SELECT id, etsy_listing_id FROM group_products "
        "WHERE status = 'published' AND etsy_listing_id IS NOT NULL"
    ).fetchall()

    checked = 0
    marked_missing = []
    skipped_errors = []
    for row in rows:
        checked += 1
        try:
            # E10c: this probed get_listing_inventory until 2026-08-12, and that made the
            # 404 branch below unreachable for the only case it exists for - Etsy returns
            # 200 on /listings/{id}/inventory for a listing that has been deleted. Two
            # rows (candidates 40 and 41) sat 'published' against 404 listings and a live
            # reconcile marked neither. See etsy_client.get_listing for the measurements.
            etsy_client.get_listing(
                row["etsy_listing_id"], api_key=api_key, api_secret=api_secret,
                access_token=access_token, dry_run=dry_run_override,
            )
        except http.HTTPError as exc:
            if exc.status_code == 404:
                conn.execute(
                    "UPDATE group_products SET status = 'listing_missing', updated_at = ? WHERE id = ?",
                    (now.isoformat(), row["id"]),
                )
                conn.commit()
                marked_missing.append(row["id"])
            else:
                skipped_errors.append(row["id"])
            continue
        except Exception:
            skipped_errors.append(row["id"])
            continue

    return {"checked": checked, "marked_missing": marked_missing, "skipped_errors": skipped_errors}


def run_reconcile(conn, **kwargs) -> dict:
    generating_kwargs = {k: v for k, v in kwargs.items() if k in ("max_age_hours", "now")}
    etsy_kwargs = {
        k: v for k, v in kwargs.items()
        if k in ("shop_id", "api_key", "api_secret", "access_token", "now", "dry_run_override")
    }
    return {
        "aged_out_candidates": age_out_stranded_generating(conn, **generating_kwargs),
        "etsy_reconcile": reconcile_etsy_listings(conn, **etsy_kwargs),
    }
