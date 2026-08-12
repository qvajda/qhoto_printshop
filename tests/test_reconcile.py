from datetime import datetime
from unittest.mock import patch

import pipeline.db as db
import pipeline.http as http
import pipeline.reconcile as reconcile


def _conn(tmp_path):
    conn = db.get_connection(tmp_path / "test.sqlite3")
    db.init_db(conn)
    return conn


def _insert_candidate(conn, id, status, updated_at):
    conn.execute(
        "INSERT INTO candidates (id, created_at, niche, go_hold_kill, status, updated_at) "
        "VALUES (?, ?, 'test', 'go', ?, ?)",
        (id, updated_at, status, updated_at),
    )
    conn.commit()


def test_age_out_marks_stale_generating_candidate_as_failed(tmp_path):
    conn = _conn(tmp_path)
    _insert_candidate(conn, 1, "generating", "2026-08-01T00:00:00")

    result = reconcile.age_out_stranded_generating(
        conn, max_age_hours=12, now=datetime(2026, 8, 5, 0, 0, 0)
    )

    assert result == [1]
    row = conn.execute("SELECT status, failed_reason FROM candidates WHERE id = 1").fetchone()
    assert row["status"] == "failed"
    assert "gl36" in row["failed_reason"]


def test_age_out_leaves_recent_generating_candidate_alone(tmp_path):
    conn = _conn(tmp_path)
    _insert_candidate(conn, 1, "generating", "2026-08-04T23:00:00")

    result = reconcile.age_out_stranded_generating(
        conn, max_age_hours=12, now=datetime(2026, 8, 5, 0, 0, 0)
    )

    assert result == []
    row = conn.execute("SELECT status FROM candidates WHERE id = 1").fetchone()
    assert row["status"] == "generating"


def test_age_out_ignores_non_generating_candidates(tmp_path):
    conn = _conn(tmp_path)
    _insert_candidate(conn, 1, "completed", "2026-08-01T00:00:00")

    result = reconcile.age_out_stranded_generating(
        conn, max_age_hours=12, now=datetime(2026, 8, 5, 0, 0, 0)
    )

    assert result == []


def _insert_published_group_product(conn, id, etsy_listing_id):
    conn.execute(
        "INSERT INTO candidates (id, created_at, niche, go_hold_kill, status, updated_at) "
        "VALUES (1, 'x', 'test', 'go', 'completed', 'x')"
    )
    conn.execute(
        "INSERT INTO groups (id, candidate_id, group_type, status, created_at, updated_at) "
        "VALUES (1, 1, 'primary', 'approved_published', 'x', 'x')"
    )
    conn.execute(
        "INSERT INTO group_products (id, group_id, candidate_id, gelato_template_id, "
        "etsy_listing_id, status, created_at, updated_at) "
        "VALUES (?, 1, 1, 'tmpl', ?, 'published', 'x', 'x')",
        (id, etsy_listing_id),
    )
    conn.commit()


def test_reconcile_marks_listing_missing_on_definitive_404(tmp_path):
    conn = _conn(tmp_path)
    _insert_published_group_product(conn, 1, "listing-123")

    with patch(
        "pipeline.etsy_client.get_listing",
        side_effect=http.HTTPError(404, "not found"),
    ):
        result = reconcile.reconcile_etsy_listings(conn, shop_id="shop", dry_run_override=False)

    assert result["marked_missing"] == [1]
    row = conn.execute("SELECT status FROM group_products WHERE id = 1").fetchone()
    assert row["status"] == "listing_missing"


def test_reconcile_skips_on_non_404_error(tmp_path):
    conn = _conn(tmp_path)
    _insert_published_group_product(conn, 1, "listing-123")

    with patch(
        "pipeline.etsy_client.get_listing",
        side_effect=http.HTTPError(500, "server error"),
    ):
        result = reconcile.reconcile_etsy_listings(conn, shop_id="shop", dry_run_override=False)

    assert result["marked_missing"] == []
    assert result["skipped_errors"] == [1]
    row = conn.execute("SELECT status FROM group_products WHERE id = 1").fetchone()
    assert row["status"] == "published"


def test_reconcile_leaves_row_alone_when_listing_found(tmp_path):
    conn = _conn(tmp_path)
    _insert_published_group_product(conn, 1, "listing-123")

    with patch(
        "pipeline.etsy_client.get_listing",
        return_value={"listing_id": "listing-123"},
    ):
        result = reconcile.reconcile_etsy_listings(conn, shop_id="shop", dry_run_override=False)

    assert result["marked_missing"] == []
    row = conn.execute("SELECT status FROM group_products WHERE id = 1").fetchone()
    assert row["status"] == "published"


def test_reconcile_ignores_rows_without_etsy_listing_id(tmp_path):
    conn = _conn(tmp_path)
    _insert_published_group_product(conn, 1, None)

    with patch("pipeline.etsy_client.get_listing") as mock_get:
        result = reconcile.reconcile_etsy_listings(conn, shop_id="shop", dry_run_override=False)

    mock_get.assert_not_called()
    assert result["checked"] == 0


def test_reconcile_probes_the_listing_resource_not_its_inventory(tmp_path):
    """E10c, and the reason the other tests in this file passed against a broken probe:
    they mock whichever function the code calls, so the endpoint choice was invisible to
    them. Etsy returns 200 on /listings/{id}/inventory for a DELETED listing and 404 only
    on /listings/{id} (measured live on 4548623111), so probing inventory makes the 404
    branch unreachable for the only case it exists for. This asserts the choice itself."""
    conn = _conn(tmp_path)
    _insert_published_group_product(conn, 1, "listing-123")

    with patch("pipeline.etsy_client.get_listing",
               side_effect=http.HTTPError(404, "not found")) as mock_listing,          patch("pipeline.etsy_client.get_listing_inventory") as mock_inventory:
        result = reconcile.reconcile_etsy_listings(conn, shop_id="shop", dry_run_override=False)

    mock_inventory.assert_not_called()
    assert mock_listing.call_count == 1
    assert result["marked_missing"] == [1]
