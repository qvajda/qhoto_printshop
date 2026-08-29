"""#157: audits every LIVE Etsy listing for the two GL-53/GL-55 defects the DB alone
cannot catch - a listing_texts row can be clean while the listing it was drafted for
was patched before the guardrail existed (candidates 40/41/42/49), or hand-edited on
Etsy afterwards (candidate 49's own manual fix, which never round-tripped into the DB).

Read-only: every call is etsy_client.get_listing, never update_listing. Reads the LIVE
listing, not the DB row - a script that flags candidate 49 (owner-fixed by hand on Etsy)
would prove it read the DB instead.

Usage:
    python scripts/listing_copy_audit.py

Exits 0 with no defective listings, 1 otherwise.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pipeline.compliance_draft as compliance_draft
import pipeline.db as db
import pipeline.etsy_client as etsy_client

DB_PATH = ROOT / "db" / "qhoto.sqlite3"


def audit_listing_copy(conn) -> list:
    """Returns [(etsy_listing_id, candidate_id, reason), ...] for every published
    listing whose live title/tags/description trips FORBIDDEN_TERMS or SEASONAL_TERMS."""
    rows = conn.execute(
        "SELECT DISTINCT etsy_listing_id, candidate_id FROM group_products "
        "WHERE etsy_listing_id IS NOT NULL AND etsy_listing_id != 'DRY_RUN_ETSY_LISTING_ID'"
    ).fetchall()

    defective = []
    for row in rows:
        listing_id = row["etsy_listing_id"]
        listing = etsy_client.get_listing(listing_id, dry_run=False)
        title = listing.get("title") or ""
        tags = listing.get("tags") or []
        description = listing.get("description") or ""
        try:
            compliance_draft.check_forbidden_terms(title, tags, description)
            compliance_draft.check_seasonal_terms(title, tags, description)
        except ValueError as exc:
            defective.append((listing_id, row["candidate_id"], str(exc)))
    return defective


def main() -> int:
    conn = db.get_connection(DB_PATH)
    defective = audit_listing_copy(conn)
    for listing_id, candidate_id, reason in defective:
        print(f"listing {listing_id} (candidate {candidate_id}): {reason}")
    if not defective:
        print("no defective listings found")
    return 1 if defective else 0


if __name__ == "__main__":
    sys.exit(main())
