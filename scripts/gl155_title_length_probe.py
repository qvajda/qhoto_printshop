"""Compare drafted title lengths against live Etsy titles, for #155.

Read-only: GETs listings, never writes. Prints `listing_id | len(title) | title`
for every published `group_product`, matched against the title `listing_texts`
drafted for that candidate, plus min/median/max on both sides.

ponytail: throwaway, owner-run once for the #155 verdict — delete once
docs/constraints/006-etsy-title-length.md lands.

Usage:
    python scripts/gl155_title_length_probe.py
"""
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pipeline.db as db
import pipeline.etsy_client as etsy_client

DB_PATH = ROOT / "db" / "qhoto.sqlite3"


def main():
    conn = db.get_connection(DB_PATH)
    rows = conn.execute(
        """
        SELECT gp.etsy_listing_id, lt.title
        FROM group_products gp
        JOIN listing_texts lt ON lt.candidate_id = gp.candidate_id
        WHERE gp.status = 'published' AND gp.etsy_listing_id IS NOT NULL
        ORDER BY gp.id
        """
    ).fetchall()

    draft_lengths, live_lengths = [], []
    print("listing_id | draft_len | live_len | title")
    for listing_id, draft_title in rows:
        draft_lengths.append(len(draft_title))
        listing = etsy_client.get_listing(listing_id)
        live_title = listing.get("title")
        live_len = len(live_title) if live_title else None
        if live_len is not None:
            live_lengths.append(live_len)
        print(f"{listing_id} | {len(draft_title)} | {live_len} | {draft_title}")

    if draft_lengths:
        print(
            f"\ndraft: min={min(draft_lengths)} median={statistics.median(draft_lengths)} "
            f"max={max(draft_lengths)} n={len(draft_lengths)}"
        )
    if live_lengths:
        print(
            f"live:  min={min(live_lengths)} median={statistics.median(live_lengths)} "
            f"max={max(live_lengths)} n={len(live_lengths)}"
        )
    else:
        print("\nlive: no live reads (ETSY_LIVE_MODE not set or no credentials — dry_run stub only)")


if __name__ == "__main__":
    main()
