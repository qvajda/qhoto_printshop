from datetime import datetime
from unittest.mock import patch

import pipeline.cleanup as cleanup
import pipeline.db as db


def _fresh_conn(tmp_path):
    conn = db.get_connection(tmp_path / "test.sqlite3")
    db.init_db(conn)
    return conn


def _insert_candidate(conn, *, status="failed", updated_at="2026-06-01T09:00:00"):
    cursor = conn.execute(
        "INSERT INTO candidates (created_at, niche, go_hold_kill, status, updated_at) "
        "VALUES (?, 'monstera line art', 'go', ?, ?)",
        (updated_at, status, updated_at),
    )
    conn.commit()
    return cursor.lastrowid


def _insert_group(conn, candidate_id, *, group_type="5x7", status="rejected"):
    timestamp = "2026-06-01T09:05:00"
    cursor = conn.execute(
        "INSERT INTO groups (candidate_id, group_type, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (candidate_id, group_type, status, timestamp, timestamp),
    )
    conn.commit()
    return cursor.lastrowid


def _insert_group_product(conn, group_id, *, gelato_product_id="gelato_x", status="publish_failed"):
    timestamp = "2026-06-01T09:10:00"
    cursor = conn.execute(
        "INSERT INTO group_products "
        "(group_id, size, orientation, gelato_template_id, gelato_product_id, price_eur, "
        "status, created_at, updated_at) "
        "VALUES (?, '5x7', 'portrait', 'tpl_x', ?, 19, ?, ?, ?)",
        (group_id, gelato_product_id, status, timestamp, timestamp),
    )
    conn.commit()
    return cursor.lastrowid


def test_cleanup_orphaned_deletes_publish_failed_product_regardless_of_group_status(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_group(conn, candidate_id, status="pending_review")
    gp_id = _insert_group_product(conn, group_id, gelato_product_id="gelato_pf", status="publish_failed")

    with patch("pipeline.cleanup.gelato_client.delete_product") as mock_delete:
        result = cleanup.cleanup_orphaned_gelato_products(conn, now=datetime(2026, 7, 14, 9, 0, 0))

    mock_delete.assert_called_once_with("gelato_pf", store_id=None, api_key=None)
    assert result == [gp_id]
    row = conn.execute("SELECT status FROM group_products WHERE id = ?", (gp_id,)).fetchone()
    assert row["status"] == "deleted"
    conn.close()


def test_cleanup_orphaned_deletes_product_under_rejected_group(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_group(conn, candidate_id, status="rejected")
    gp_id = _insert_group_product(conn, group_id, gelato_product_id="gelato_r", status="created")

    with patch("pipeline.cleanup.gelato_client.delete_product") as mock_delete:
        result = cleanup.cleanup_orphaned_gelato_products(conn)

    mock_delete.assert_called_once_with("gelato_r", store_id=None, api_key=None)
    assert result == [gp_id]
    conn.close()


def test_cleanup_orphaned_skips_already_deleted_and_healthy_rows(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_group(conn, candidate_id, status="approved_published")
    _insert_group_product(conn, group_id, gelato_product_id="gelato_ok", status="published")
    _insert_group_product(conn, group_id, gelato_product_id="gelato_gone", status="deleted")

    with patch("pipeline.cleanup.gelato_client.delete_product") as mock_delete:
        result = cleanup.cleanup_orphaned_gelato_products(conn)

    mock_delete.assert_not_called()
    assert result == []
    conn.close()


def test_cleanup_orphaned_continues_past_delete_failure(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_group(conn, candidate_id, status="rejected")
    gp_id = _insert_group_product(conn, group_id, gelato_product_id="gelato_fail", status="created")

    with patch("pipeline.cleanup.gelato_client.delete_product", side_effect=Exception("network error")):
        result = cleanup.cleanup_orphaned_gelato_products(conn)

    assert result == []
    row = conn.execute("SELECT status FROM group_products WHERE id = ?", (gp_id,)).fetchone()
    assert row["status"] == "created"  # untouched, retried next run
    conn.close()
