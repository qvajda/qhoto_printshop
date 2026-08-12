"""E12 §4 - re-upload candidate 81's gallery on its DRAFT listing. Throwaway, owner-run.

Why a re-upload and not a repair: alt text and rank are set at image-upload time and
Etsy v3 has no update-image endpoint, so the only way to give the 12 existing images
their alt text and their intended order is to upload them again. Free and re-runnable -
listing 4554354628 is a draft and stays one.

    python scripts/e12_gallery_repair.py plan     # reads only, prints the mapping
    python scripts/e12_gallery_repair.py repair   # deletes the live images, re-uploads

'repair' refuses to run unless a fresh DB backup exists (BACKUP below).

Every DB write is scoped by group_product_id, the same scope patch_etsy_listing's own
reconcile uses - an unscoped write here would wipe another group's reviewed gallery.

ponytail: no new upload loop. group_product.patch_etsy_listing IS the loop, it derives
the fallback alt text for the 10x24 rows, and it re-patches the listing text with the
same values it already holds. Clearing etsy_listing_image_id is all it takes to make it
re-upload. Delete this script once 81's gallery has its owner read-back.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pipeline.config as config
import pipeline.db as db
import pipeline.etsy_client as etsy_client
import pipeline.group_product as group_product

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "db" / "qhoto.sqlite3"
BACKUP = ROOT / "db" / "qhoto.sqlite3.bak-2026-08-13-pre-e12"
LISTING_ID = "4554354628"
CANDIDATE_ID = 81


def _rows(conn, group_product_id):
    return conn.execute(
        "SELECT id, group_id, gallery_order, etsy_listing_image_id, image_type, alt_text "
        "FROM product_images WHERE group_product_id = ? ORDER BY group_id, gallery_order",
        (group_product_id,),
    ).fetchall()


def _group_product(conn):
    row = conn.execute(
        "SELECT id, etsy_listing_id FROM group_products WHERE candidate_id = ?", (CANDIDATE_ID,)
    ).fetchone()
    if row is None or str(row["etsy_listing_id"]) != LISTING_ID:
        raise SystemExit(f"candidate {CANDIDATE_ID} does not own listing {LISTING_ID} - stop")
    return row


def plan(conn):
    gp = _group_product(conn)
    live = etsy_client.get_listing_images(LISTING_ID, dry_run=False)["results"]
    live_rank = {str(i["listing_image_id"]): i["rank"] for i in live}
    print(f"group_product {gp['id']} -> listing {LISTING_ID}, {len(live)} live images")
    for row in _rows(conn, gp["id"]):
        image_id = row["etsy_listing_image_id"]
        print(f"  group {row['group_id']} order {row['gallery_order']} "
              f"image {image_id} live_rank={live_rank.get(str(image_id))} "
              f"alt={row['alt_text']!r}")


def repair(conn, static_config):
    if not BACKUP.exists():
        raise SystemExit(f"no fresh DB backup at {BACKUP} - make one first (PRD §4.1)")
    gp = _group_product(conn)

    # The old images are NOT deleted up front. Etsy refuses to delete the last one
    # ("Listings must have at least 1 image"), so a delete-first pass strands the
    # gallery at one stale image. patch_etsy_listing's own reconcile already deletes
    # every image this candidate does not own - by then the new gallery is up, so the
    # floor is never reached. Same reason its code comment gives for reconciling last.
    live = etsy_client.get_listing_images(LISTING_ID, dry_run=False)["results"]
    print(f"{len(live)} stale image(s) on the listing; the reconcile will remove them")

    # Scoped by group_product_id: this is candidate 81's listing record and no other's.
    cleared = conn.execute(
        "UPDATE product_images SET etsy_listing_image_id = NULL WHERE group_product_id = ?",
        (gp["id"],),
    ).rowcount
    conn.commit()
    print(f"cleared etsy_listing_image_id on {cleared} product_images rows")

    listing_text = dict(conn.execute(
        "SELECT * FROM listing_texts WHERE candidate_id = ?", (CANDIDATE_ID,)
    ).fetchone())
    group_product.patch_etsy_listing(
        conn, gp["id"], listing_text, static_config, dry_run=False,
    )

    print("READ-BACK:")
    for image in etsy_client.get_listing_images(LISTING_ID, dry_run=False)["results"]:
        print(f"  rank {image['rank']:>2} id {image['listing_image_id']} "
              f"alt={image.get('alt_text')!r}")


def main(argv):
    if len(argv) < 2:
        raise SystemExit(__doc__)
    config.load_env()
    conn = db.get_connection(DB_PATH)
    try:
        if argv[1] == "plan":
            plan(conn)
        elif argv[1] == "repair":
            repair(conn, config.load_static_config())
        else:
            raise SystemExit(f"unknown command {argv[1]!r}")
    finally:
        conn.close()


if __name__ == "__main__":
    main(sys.argv)
