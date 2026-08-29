"""#157: unit coverage for scripts/listing_copy_audit.py's audit_listing_copy, since a
live run against the real shop can't happen from an isolated test DB. Verifies the
function reads the LIVE Etsy listing (never the DB row) and reports the two GL-53/GL-55
defect classes by listing id."""
import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pipeline.db as db

_SPEC = importlib.util.spec_from_file_location(
    "listing_copy_audit", Path(__file__).resolve().parents[1] / "scripts" / "listing_copy_audit.py"
)
listing_copy_audit = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(listing_copy_audit)


def _fresh_conn(tmp_path):
    conn = db.get_connection(tmp_path / "test.sqlite3")
    db.init_db(conn)
    return conn


def _insert_candidate(conn):
    timestamp = "2026-07-16T09:00:00"
    cursor = conn.execute(
        "INSERT INTO candidates (created_at, niche, go_hold_kill, status, base_image_url, "
        "updated_at) VALUES (?, 'monstera line art', 'go', 'primary_review', ?, ?)",
        (timestamp, "https://replicate.delivery/out.png", timestamp),
    )
    conn.commit()
    return cursor.lastrowid


def _insert_group(conn, candidate_id):
    timestamp = "2026-07-16T09:05:00"
    cursor = conn.execute(
        "INSERT INTO groups (candidate_id, group_type, status, created_at, updated_at) "
        "VALUES (?, 'primary', 'pending_review', ?, ?)",
        (candidate_id, timestamp, timestamp),
    )
    conn.commit()
    return cursor.lastrowid


def _insert_group_product(conn, etsy_listing_id):
    candidate_id = _insert_candidate(conn)
    group_id = _insert_group(conn, candidate_id)
    conn.execute(
        "INSERT INTO group_products (group_id, candidate_id, gelato_template_id, "
        "etsy_listing_id, status, created_at, updated_at) VALUES (?, ?, 'tpl', ?, 'published', "
        "'2026-07-16T09:00:00', '2026-07-16T09:00:00')",
        (group_id, candidate_id, etsy_listing_id),
    )
    conn.commit()
    return candidate_id


def test_audit_listing_copy_flags_live_forbidden_and_seasonal_terms(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_ids = {
        listing_id: _insert_group_product(conn, listing_id)
        for listing_id in ("clean-1", "bad-2", "bad-3")
    }

    def fake_get_listing(listing_id, **kwargs):
        return {
            "clean-1": {"title": "Botanical Line Art", "tags": ["botanical"], "description": "A poster."},
            "bad-2": {"title": "Wall Art, Printable Download", "tags": [], "description": ""},
            "bad-3": {"title": "Autumn Leaf Print", "tags": [], "description": "Perfect for Christmas."},
        }[listing_id]

    with patch("pipeline.etsy_client.get_listing", side_effect=fake_get_listing) as mock_get:
        defective = listing_copy_audit.audit_listing_copy(conn)

    assert {"clean-1", "bad-2", "bad-3"} == {c.args[0] for c in mock_get.call_args_list}
    assert [d[0] for d in defective] == ["bad-2", "bad-3"]
    assert defective[0][1] == candidate_ids["bad-2"]
    assert defective[1][1] == candidate_ids["bad-3"]


def test_audit_listing_copy_ignores_placeholder_ids(tmp_path):
    conn = _fresh_conn(tmp_path)
    _insert_group_product(conn, "DRY_RUN_ETSY_LISTING_ID")

    with patch("pipeline.etsy_client.get_listing") as mock_get:
        defective = listing_copy_audit.audit_listing_copy(conn)

    mock_get.assert_not_called()
    assert defective == []
