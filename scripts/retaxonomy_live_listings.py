"""#262: move every published listing to a taxonomy id (default: static_config's
etsy_taxonomy_id), re-apply the listing properties, and read both back.

Preview by default (no write). --apply PATCHes {"taxonomy_id": ...} on every listing whose
LIVE value differs, re-PUTs etsy_listing_properties, then reads taxonomy and properties
back and fails on mismatch (GL-22a Q2: a 200 is not evidence). --to <id> is the revert:
`--to 1027 --apply` puts the old id back (the properties are PUT from static config, so
set it to the matching leaf's ids first if they differ).

Usage:
    python scripts/retaxonomy_live_listings.py            # preview
    python scripts/retaxonomy_live_listings.py --apply
    python scripts/retaxonomy_live_listings.py --to 1027 --apply

Exits 0 only if no listing errored; per-item failures are printed and fail the run once
at the end (GL-46).
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pipeline.config as config
import pipeline.db as db
import pipeline.etsy_client as etsy_client

DB_PATH = ROOT / "db" / "qhoto.sqlite3"


def _live_properties(shop_id: str, listing_id: str) -> dict:
    """property_id -> set of value_ids, read from the live listing."""
    rows = etsy_client.get_listing_properties(shop_id, listing_id, dry_run=False)
    return {int(p["property_id"]): {int(v) for v in p.get("value_ids", [])} for p in rows}


def run(conn, *, to: int, properties: list, apply: bool = False, shop_id: str = None) -> list:
    """Returns the list of error strings; empty means every listing was already on `to` or fixed."""
    rows = conn.execute(
        "SELECT DISTINCT etsy_listing_id FROM group_products "
        "WHERE status = 'published' AND etsy_listing_id IS NOT NULL "
        "AND etsy_listing_id != 'DRY_RUN_ETSY_LISTING_ID'"
    ).fetchall()
    errors = []
    for row in rows:
        listing_id = row["etsy_listing_id"]
        try:
            live = etsy_client.get_listing(listing_id, dry_run=False).get("taxonomy_id")
            if live == to:
                continue
            print(f"{listing_id} | {live} -> {to}")
            if not apply:
                continue
            etsy_client.update_listing(shop_id, listing_id, {"taxonomy_id": to}, dry_run=False)
            for prop in properties:
                etsy_client.update_listing_property(
                    shop_id, listing_id, prop["property_id"], [prop["value_id"]], [prop["value"]],
                    dry_run=False)
            readback = etsy_client.get_listing(listing_id, dry_run=False).get("taxonomy_id")
            if readback != to:
                raise RuntimeError(f"read-back mismatch: live taxonomy_id is {readback!r}")
            live_props = _live_properties(shop_id, listing_id)
            for prop in properties:
                if prop["value_id"] not in live_props.get(prop["property_id"], set()):
                    raise RuntimeError(f"read-back mismatch: property {prop['name']!r} not set")
        except Exception as exc:
            errors.append(f"{listing_id}: {exc}")
            print(f"{listing_id} | ERROR | {exc}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="PATCH listings (default: preview only)")
    parser.add_argument("--to", type=int, help="target taxonomy id (default: etsy_taxonomy_id in static config)")
    args = parser.parse_args()
    config.load_env(None)
    static = config.load_static_config()
    shop_id = config.require_env("ETSY_SHOP_ID") if args.apply else None
    errors = run(
        db.get_connection(DB_PATH), to=args.to or int(static["etsy_taxonomy_id"]),
        properties=static["etsy_listing_properties"], apply=args.apply, shop_id=shop_id)
    if errors:
        print(f"{len(errors)} listing(s) failed", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
