"""GL-67 (#94) - bring an existing design up to current standards WITHOUT regenerating
the artwork. One entry point over shipped stages: redraft copy (GL-56), re-render
mockups (the compositor), re-upload the gallery with ranks (GL-57), create-or-reuse the
Gelato product (GL-22a Q2's create-once rule). No new machinery - see each function's
docstring for the shipped call it makes.

v4.12 forces the shape: no API path adds a variant to an existing Gelato product, so
"rebuild" means create a new listing record, verify it, THEN retire (delete) the old
one(s) - never the reverse. `rebuild` never deletes; `retire` is the only subcommand
that does, and only once the new listing is confirmed live (has a gelato_product_id
and an etsy_listing_id).

The draft/published split is read live, never guessed: `etsy_client.get_listing`'s
`state` field is the only thing that discriminates a deleted/draft listing from a live
one (GL-36 E10c). A published listing is refused unless
`--published-loses-url-age-stats` is passed, because that is what rebuilding it costs
(GL-41 froze the permanent URL; a republish also loses age and stats). Unknown (the
listing_id is missing, or the live GET fails) is refused the same way - unknown is not
draft.

    python scripts/rebuild_design.py plan CANDIDATE_ID
    python scripts/rebuild_design.py rebuild CANDIDATE_ID [--published-loses-url-age-stats]
    python scripts/rebuild_design.py retire CANDIDATE_ID OLD_GROUP_PRODUCT_ID [OLD_GROUP_PRODUCT_ID ...]
    python scripts/rebuild_design.py gallery-repair CANDIDATE_ID

`retire` is its own subcommand, not the last step of `rebuild`, so the human
verification in between (does the new listing actually look right?) cannot be skipped
by a script that already has the delete call loaded.

`gallery-repair` is GL-67's second customer: correcting the gallery of a listing
published before GL-57 (ranks/alt-text set at upload time, no update-image endpoint).
It is the same delete-and-re-upload-with-ranks step as `rebuild`'s gallery patch, not a
second implementation - it just clears `etsy_listing_image_id` and calls
`group_product.patch_etsy_listing` again, generalising `scripts/e12_gallery_repair.py`
to any candidate.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pipeline.config as config
import pipeline.db as db
import pipeline.etsy_client as etsy_client
import pipeline.gelato_client as gelato_client
import pipeline.group_mockup as group_mockup
import pipeline.group_product as group_product
import pipeline.publish_primary_group as publish_primary_group

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "db" / "qhoto.sqlite3"

_PUBLISHED_STATES = ("active", "inactive", "sold_out")


class RebuildRefusedError(Exception):
    """Raised when the case (draft vs published vs unknown) cannot be resolved to a
    safe rebuild - the point of this row is that refusing is the correct output here,
    guessing is the expensive failure it exists to prevent (GL-67)."""


def _timestamp(now) -> str:
    return now if isinstance(now, str) else (
        now or datetime.now(timezone.utc).replace(tzinfo=None)
    ).isoformat()


def classify_listing_case(etsy_listing_id, *, api_key=None, api_secret=None, access_token=None) -> str:
    """Reads the listing's live state - never the DB's opinion of it (CLAUDE.md v4.12:
    `group_products.status` for a pre-review candidate carries no product id and means
    nothing here). Returns 'draft', 'published', or 'unknown'."""
    if not etsy_listing_id:
        return "unknown"
    try:
        listing = etsy_client.get_listing(
            etsy_listing_id, api_key=api_key, api_secret=api_secret,
            access_token=access_token, dry_run=False,
        )
    except Exception:
        return "unknown"
    state = listing.get("state")
    if state == "draft":
        return "draft"
    if state in _PUBLISHED_STATES:
        return "published"
    return "unknown"


def plan(conn, candidate_id, *, etsy_api_key=None, etsy_api_secret=None, etsy_access_token=None) -> dict:
    """Reads only. Reports what a `rebuild` would do, without doing it."""
    old_summary = group_product.live_product_row(conn, candidate_id)
    if old_summary is None:
        return {"candidate_id": candidate_id, "old_group_product_id": None, "case": "no_listing"}
    old_row = conn.execute("SELECT * FROM group_products WHERE id = ?", (old_summary["id"],)).fetchone()
    case = classify_listing_case(
        old_row["etsy_listing_id"], api_key=etsy_api_key, api_secret=etsy_api_secret,
        access_token=etsy_access_token,
    )
    group_ids = group_product.included_group_ids(conn, candidate_id)
    return {
        "candidate_id": candidate_id,
        "old_group_product_id": old_row["id"],
        "old_etsy_listing_id": old_row["etsy_listing_id"],
        "old_gelato_product_id": old_row["gelato_product_id"],
        "case": case,
        "included_group_ids": group_ids,
    }


def rebuild(conn, candidate_id, *, static_config=None, store_id=None, gelato_api_key=None,
            shop_id=None, etsy_api_key=None, etsy_api_secret=None, etsy_access_token=None,
            anthropic_api_key=None, published_loses_url_age_stats=False, dry_run=None,
            now=None) -> dict:
    """Steps 1-3 of the plan: redraft copy, re-render mockups on a NEW listing record,
    create-or-reuse the Gelato product and patch the Etsy listing it pushes. Never
    deletes anything - `retire` does that, once the new listing is verified."""
    static_config = static_config if static_config is not None else config.load_static_config()
    timestamp = _timestamp(now)

    candidate_row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    if candidate_row is None:
        raise ValueError(f"No candidate with id {candidate_id}")
    candidate = dict(candidate_row)

    old_summary = group_product.live_product_row(conn, candidate_id)
    if old_summary is None:
        raise ValueError(f"Candidate {candidate_id} has no existing listing record - nothing to rebuild")
    # live_product_row's SELECT list is a summary (id/gelato_product_id/status/candidate_id
    # only) - fetch the full row for etsy_listing_id.
    old_row = conn.execute("SELECT * FROM group_products WHERE id = ?", (old_summary["id"],)).fetchone()
    if not old_row["etsy_listing_id"]:
        raise ValueError(
            f"Candidate {candidate_id}'s group_products row {old_row['id']} has no "
            f"etsy_listing_id - cannot classify draft vs published, refusing to guess"
        )

    case = classify_listing_case(
        old_row["etsy_listing_id"], api_key=etsy_api_key, api_secret=etsy_api_secret,
        access_token=etsy_access_token,
    )
    if case == "unknown":
        raise RebuildRefusedError(
            f"Candidate {candidate_id}: could not determine listing "
            f"{old_row['etsy_listing_id']}'s state (missing or the live GET failed) - "
            f"refusing to guess whether it is a draft or published"
        )
    if case == "published" and not published_loses_url_age_stats:
        raise RebuildRefusedError(
            f"Candidate {candidate_id}: listing {old_row['etsy_listing_id']} is "
            f"published. Rebuilding it republishes as a new listing, losing its URL "
            f"(GL-41), its age and its stats. Pass --published-loses-url-age-stats to "
            f"proceed anyway."
        )

    primary_group_id = conn.execute(
        "SELECT id FROM groups WHERE candidate_id = ? AND group_type = 'primary'", (candidate_id,)
    ).fetchone()["id"]
    # GL-56: copy-only redo. No generate call, no mockup re-render, no
    # _discard_group_contribution - base_image_* stays byte-identical (CLAUDE.md: a
    # design is image-generated once).
    publish_primary_group.handle_decision(
        conn, candidate_id, primary_group_id, "redraft", static_config=static_config,
        store_id=store_id, gelato_api_key=gelato_api_key, anthropic_api_key=anthropic_api_key,
        now=now,
    )

    # Makes live_product_row miss, so the render pass below opens a fresh row instead of
    # reusing the superseded one (v4.12: no API path adds a variant post-create).
    conn.execute(
        "UPDATE group_products SET status = 'deleted', updated_at = ? WHERE id = ?",
        (timestamp, old_row["id"]),
    )
    conn.commit()

    group_ids = group_product.included_group_ids(conn, candidate_id)
    if not group_ids:
        raise ValueError(f"Candidate {candidate_id} has no group whose review passed - nothing to rebuild")
    for group_id in group_ids:
        group_type = conn.execute(
            "SELECT group_type FROM groups WHERE id = ?", (group_id,)
        ).fetchone()["group_type"]
        sizes = group_mockup._group_sizes(static_config, group_type)
        group_product.render_group_mockups(conn, group_id, sizes, candidate, static_config, now=now)

    result = publish_primary_group.publish_candidate(
        conn, candidate_id, static_config=static_config, store_id=store_id,
        gelato_api_key=gelato_api_key, shop_id=shop_id, etsy_api_key=etsy_api_key,
        etsy_api_secret=etsy_api_secret, etsy_access_token=etsy_access_token,
        dry_run=dry_run, now=now,
    )
    return {"old_group_product_id": old_row["id"], **result}


def retire(conn, candidate_id, old_group_product_ids, *, store_id=None, gelato_api_key=None,
           etsy_api_key=None, etsy_api_secret=None, etsy_access_token=None, dry_run=None) -> list:
    """Deletes exactly the enumerated old listing(s)/product(s) - the destructive half
    of the plan, and the only one. Refuses unless the candidate's current listing
    record is confirmed live (both ids present), so a rebuild that never finished
    can't take the old listing down with it."""
    new_summary = group_product.live_product_row(conn, candidate_id)
    new_row = (
        conn.execute("SELECT * FROM group_products WHERE id = ?", (new_summary["id"],)).fetchone()
        if new_summary is not None else None
    )
    if new_row is None or not new_row["gelato_product_id"] or not new_row["etsy_listing_id"]:
        raise RebuildRefusedError(
            f"Candidate {candidate_id}: no confirmed-live listing record "
            f"(gelato_product_id and etsy_listing_id both required) - refusing to "
            f"retire the old one(s)"
        )

    retired = []
    for old_id in old_group_product_ids:
        old = conn.execute(
            "SELECT * FROM group_products WHERE id = ? AND candidate_id = ?",
            (old_id, candidate_id),
        ).fetchone()
        if old is None:
            raise ValueError(f"group_products {old_id} does not belong to candidate {candidate_id}")
        if old["etsy_listing_id"]:
            etsy_client.delete_listing(
                old["etsy_listing_id"], api_key=etsy_api_key, api_secret=etsy_api_secret,
                access_token=etsy_access_token, dry_run=dry_run,
            )
        if old["gelato_product_id"]:
            gelato_client.delete_product(
                old["gelato_product_id"], store_id=store_id, api_key=gelato_api_key, dry_run=dry_run,
            )
        retired.append(old_id)
    return retired


def gallery_repair(conn, candidate_id, static_config, *, shop_id=None, dry_run=None, now=None) -> str:
    """GL-67's second customer. Re-uploads the candidate's live gallery with ranks and
    alt text - the same step `rebuild` uses, generalised from
    `scripts/e12_gallery_repair.py`'s single hardcoded candidate."""
    gp = group_product.live_product_row(conn, candidate_id)
    if gp is None:
        raise ValueError(f"Candidate {candidate_id} has no listing record to repair")

    # Not deleted up front - Etsy refuses to delete a listing's last image, so
    # patch_etsy_listing's own reconcile (run after the fresh upload) is what removes
    # the stale ones, exactly as scripts/e12_gallery_repair.py does.
    conn.execute(
        "UPDATE product_images SET etsy_listing_image_id = NULL WHERE group_product_id = ?",
        (gp["id"],),
    )
    conn.commit()

    listing_text_row = conn.execute(
        "SELECT * FROM listing_texts WHERE candidate_id = ?", (candidate_id,)
    ).fetchone()
    if listing_text_row is None:
        raise ValueError(f"No listing_texts row for candidate {candidate_id}")

    return group_product.patch_etsy_listing(
        conn, gp["id"], dict(listing_text_row), static_config, shop_id=shop_id, dry_run=dry_run, now=now,
    )


def main(argv):
    if len(argv) < 3:
        raise SystemExit(__doc__)
    command, candidate_id = argv[1], int(argv[2])
    config.load_env()
    conn = db.get_connection(DB_PATH)
    try:
        if command == "plan":
            result = plan(conn, candidate_id)
            for key, value in result.items():
                print(f"{key}: {value}")
        elif command == "rebuild":
            published_flag = "--published-loses-url-age-stats" in argv[3:]
            result = rebuild(conn, candidate_id, published_loses_url_age_stats=published_flag)
            print(result)
        elif command == "retire":
            old_ids = [int(a) for a in argv[3:]]
            if not old_ids:
                raise SystemExit("retire needs at least one OLD_GROUP_PRODUCT_ID")
            print(retire(conn, candidate_id, old_ids))
        elif command == "gallery-repair":
            print(gallery_repair(conn, candidate_id, config.load_static_config()))
        else:
            raise SystemExit(f"unknown command {command!r}")
    finally:
        conn.close()


if __name__ == "__main__":
    main(sys.argv)
