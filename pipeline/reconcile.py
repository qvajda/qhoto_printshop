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
import urllib.request
from datetime import datetime, timedelta, timezone

import pipeline.config as config
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


def find_unconfirmed_gelato_creates(conn, *, older_than_minutes=15, now=None) -> list:
    """GL-32: report-only. A row whose gelato_create_intent_at is older than the cutoff
    and still carries no gelato_product_id crashed between the Gelato POST returning and
    the id-recording UPDATE committing - a real product no DB sweep can see. Never
    touches the network or mutates a row; finding the orphan is this function's whole
    job, resolving it against the live API is a separate, owner-gated step."""
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    cutoff = (now - timedelta(minutes=older_than_minutes)).isoformat()
    rows = conn.execute(
        "SELECT id FROM group_products WHERE gelato_product_id IS NULL "
        "AND gelato_create_intent_at IS NOT NULL AND gelato_create_intent_at < ?",
        (cutoff,),
    ).fetchall()
    return [row["id"] for row in rows]


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


def _fetch_all_shop_listings(shop_id, *, api_key=None, api_secret=None, access_token=None, dry_run=None) -> list:
    """225: the DB->Etsy direction (reconcile_etsy_listings) can't see a listing no row
    ever claimed - Gelato pushed twice for one product and the loser never got a row.
    Sweeps every state (active/inactive/draft/expired): the orphan that prompted this is
    a draft, and a hand-made listing that never went active is exactly what the allowlist
    carve-out in find_unclaimed_etsy_listings has to tell apart from it. `includes=Images`
    pulls the gallery inline so a zero-image listing is visible without a second call per
    listing."""
    if dry_run is None:
        dry_run = not config.is_live_mode("ETSY")
    if dry_run:
        return []

    api_key = api_key or config.require_env("ETSY_API_KEY")
    api_secret = api_secret or config.require_env("ETSY_API_SECRET")
    access_token = access_token or config.require_env("ETSY_ACCESS_TOKEN")

    listings = []
    for state in ("active", "inactive", "draft", "expired"):
        offset = 0
        while True:
            url = (
                f"{etsy_client.ETSY_API_BASE}/shops/{shop_id}/listings"
                f"?state={state}&includes=Images&limit=100&offset={offset}"
            )

            def _build(token, url=url):
                return urllib.request.Request(
                    url, headers=etsy_client._headers(api_key, api_secret, token), method="GET"
                )

            page = etsy_client._call_with_refresh(_build, access_token)
            results = page.get("results", [])
            listings.extend(results)
            if len(results) < 100:
                break
            offset += 100
    return listings


def find_unclaimed_etsy_listings(
    conn, *, shop_id=None, api_key=None, api_secret=None, access_token=None, dry_run_override=None,
) -> dict:
    """225: report-only, the same posture as find_unconfirmed_gelato_creates - names the
    orphan, deletes nothing. A listing no group_products row claims is "unclaimed"; the
    6 pre-pipeline hand-made listings are unclaimed too and always will be, so the wrong
    thing to flag as urgent is "unclaimed" alone - unclaimed_zero_images is the actual
    signal, since a real listing has a gallery and an orphan draft never got one."""
    claimed = {
        str(row["etsy_listing_id"])
        for row in conn.execute(
            "SELECT etsy_listing_id FROM group_products WHERE etsy_listing_id IS NOT NULL"
        ).fetchall()
    }
    listings = _fetch_all_shop_listings(
        shop_id, api_key=api_key, api_secret=api_secret, access_token=access_token, dry_run=dry_run_override,
    )

    unclaimed = []
    unclaimed_zero_images = []
    for listing in listings:
        listing_id = listing["listing_id"]
        if str(listing_id) in claimed:
            continue
        unclaimed.append(listing_id)
        if not listing.get("images"):
            unclaimed_zero_images.append(listing_id)

    return {"unclaimed": unclaimed, "unclaimed_zero_images": unclaimed_zero_images}


def run_reconcile(conn, **kwargs) -> dict:
    generating_kwargs = {k: v for k, v in kwargs.items() if k in ("max_age_hours", "now")}
    etsy_kwargs = {
        k: v for k, v in kwargs.items()
        if k in ("shop_id", "api_key", "api_secret", "access_token", "now", "dry_run_override")
    }
    unclaimed_kwargs = {
        k: v for k, v in kwargs.items()
        if k in ("shop_id", "api_key", "api_secret", "access_token", "dry_run_override")
    }
    return {
        "aged_out_candidates": age_out_stranded_generating(conn, **generating_kwargs),
        "etsy_reconcile": reconcile_etsy_listings(conn, **etsy_kwargs),
        "unclaimed_etsy_listings": find_unclaimed_etsy_listings(conn, **unclaimed_kwargs),
    }
