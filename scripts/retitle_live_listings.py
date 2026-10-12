"""#257: read the LIVE Etsy title of every published listing, and retitle the ones that
fail the poster-first title rules (#245, TITLE-FORMAT F2). Title only - no tags,
description or URLs.

Preview by default (no PATCH). --apply PATCHes {"title": ...} on the failing ids, then
reads the title back and fails on mismatch (GL-22a Q2: a 200 is not evidence).

Usage:
    python scripts/retitle_live_listings.py            # preview
    python scripts/retitle_live_listings.py --apply

Exits 0 only if no listing errored; per-item failures are printed and fail the run once
at the end (GL-46).
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pipeline.compliance_draft as compliance_draft
import pipeline.config as config
import pipeline.db as db
import pipeline.etsy_client as etsy_client

DB_PATH = ROOT / "db" / "qhoto.sqlite3"


def title_rule_failed(title: str):
    """Reason string if the title breaks the poster-in-clause-one or banned-term rules,
    else None. Same patterns compliance_draft enforces on new drafts."""
    first_clause = (title or "").split(",")[0]
    if not compliance_draft._POSTER_PATTERN.search(first_clause):
        return "no 'poster' in first clause"
    match = compliance_draft._TITLE_BANNED_PATTERN.search(title)
    if match:
        return f"banned term {match.group(0)!r}"
    return None


def draft_title(conn, candidate_id: int) -> str:
    """New title via compliance_draft's own generator + validators (3 attempts, failure
    fed back, same as build_compliance_draft). Nothing is written to listing_texts."""
    candidate = dict(conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone())
    image_types = [g["image_type"] for g in compliance_draft.get_primary_gallery(conn, candidate_id)]
    feedback = None
    for _ in range(3):
        try:
            draft = compliance_draft.generate_draft_text(candidate, image_types, retry_feedback=feedback)
            compliance_draft.validate_listing_text(
                draft["title"], draft["tags"], draft["description"], draft["alt_texts"])
            compliance_draft.validate_draft_formula(draft["title"], draft["tags"])
            return draft["title"]
        except ValueError as exc:
            last = exc
            feedback = f"Your previous attempt failed validation: {exc}. Fix this and keep every other requirement."
    raise last


def run(conn, *, apply: bool = False, shop_id: str = None, draft_fn=draft_title) -> list:
    """Returns the list of error strings; empty means every listing was clean or fixed."""
    rows = conn.execute(
        "SELECT DISTINCT etsy_listing_id, candidate_id FROM group_products "
        "WHERE status = 'published' AND etsy_listing_id IS NOT NULL "
        "AND etsy_listing_id != 'DRY_RUN_ETSY_LISTING_ID'"
    ).fetchall()
    errors = []
    for row in rows:
        listing_id = row["etsy_listing_id"]
        try:
            live = etsy_client.get_listing(listing_id, dry_run=False).get("title") or ""
            reason = title_rule_failed(live)
            if reason is None:
                continue
            proposed = draft_fn(conn, row["candidate_id"])
            print(f"{listing_id} | {live} | {proposed} | {reason}")
            if not apply:
                continue
            etsy_client.update_listing(shop_id, listing_id, {"title": proposed}, dry_run=False)
            readback = etsy_client.get_listing(listing_id, dry_run=False).get("title")
            if readback != proposed:
                raise RuntimeError(f"read-back mismatch: live title is {readback!r}")
        except Exception as exc:
            errors.append(f"{listing_id}: {exc}")
            print(f"{listing_id} | ERROR | {exc}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="PATCH titles (default: preview only)")
    args = parser.parse_args()
    config.load_env(None)
    shop_id = config.require_env("ETSY_SHOP_ID") if args.apply else None
    errors = run(db.get_connection(DB_PATH), apply=args.apply, shop_id=shop_id)
    if errors:
        print(f"{len(errors)} listing(s) failed", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
