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
        "(group_id, gelato_template_id, gelato_product_id, "
        "status, created_at, updated_at) "
        "VALUES (?, 'tpl_x', ?, ?, ?, ?)",
        (group_id, gelato_product_id, status, timestamp, timestamp),
    )
    group_product_id = cursor.lastrowid
    conn.execute(
        "INSERT INTO group_product_variants "
        "(group_product_id, size, orientation, gelato_template_variant_id, price_eur, created_at) "
        "VALUES (?, '5x7', 'portrait', 'variant_x', 19, ?)",
        (group_product_id, timestamp),
    )
    conn.commit()
    return group_product_id


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


def _insert_telegram_event(conn, *, received_at):
    cursor = conn.execute(
        "INSERT INTO telegram_events_log (received_at, telegram_user_id, raw_payload, accepted) "
        "VALUES (?, '111', '{}', 1)",
        (received_at,),
    )
    conn.commit()
    return cursor.lastrowid


def test_prune_telegram_events_log_deletes_rows_older_than_retention(tmp_path):
    conn = _fresh_conn(tmp_path)
    old_id = _insert_telegram_event(conn, received_at="2026-06-01T09:00:00")
    new_id = _insert_telegram_event(conn, received_at="2026-07-10T09:00:00")

    count = cleanup.prune_telegram_events_log(
        conn, retention_days=30, now=datetime(2026, 7, 14, 9, 0, 0)
    )

    assert count == 1
    remaining_ids = [
        row["id"] for row in conn.execute("SELECT id FROM telegram_events_log").fetchall()
    ]
    assert remaining_ids == [new_id]
    conn.close()


def test_prune_telegram_events_log_keeps_rows_within_retention(tmp_path):
    conn = _fresh_conn(tmp_path)
    _insert_telegram_event(conn, received_at="2026-07-01T09:00:00")

    count = cleanup.prune_telegram_events_log(
        conn, retention_days=30, now=datetime(2026, 7, 14, 9, 0, 0)
    )

    assert count == 0
    conn.close()


def _insert_full_candidate_tree(conn, *, candidate_status="failed", updated_at="2026-06-01T09:00:00",
                                 group_product_status="deleted", gelato_product_id=None):
    candidate_id = _insert_candidate(conn, status=candidate_status, updated_at=updated_at)
    group_id = _insert_group(conn, candidate_id, status="failed_abandoned")
    gp_id = _insert_group_product(
        conn, group_id, gelato_product_id=gelato_product_id, status=group_product_status
    )
    conn.execute(
        "INSERT INTO product_images (group_product_id, image_url, alt_text, gallery_order, image_type) "
        "VALUES (?, 'https://x/y.jpg', '', 0, 'flat_mockup')",
        (gp_id,),
    )
    conn.execute(
        "INSERT INTO listing_metrics_snapshots (group_product_id, snapshot_date, views, num_favorers, orders_count) "
        "VALUES (?, '2026-06-02', 10, 1, 0)",
        (gp_id,),
    )
    conn.execute(
        "INSERT INTO critic_pass_attempts (group_id, attempt_number, passed, created_at) "
        "VALUES (?, 1, 1, '2026-06-01T09:06:00')",
        (group_id,),
    )
    conn.execute(
        "INSERT INTO group_messages (group_id, telegram_message_id, chat_id, sent_at) "
        "VALUES (?, 555, '111', '2026-06-01T09:07:00')",
        (group_id,),
    )
    conn.execute(
        "INSERT INTO listing_texts (candidate_id, title, tags, description, disclosure_text, "
        "who_made, production_partner_ids, taxonomy_id, shipping_profile_id, created_at) "
        "VALUES (?, 't', '[]', 'd', 'disc', 'i_did', '[5717252]', '1027', '', '2026-06-01T09:01:00')",
        (candidate_id,),
    )
    conn.commit()
    return candidate_id, group_id, gp_id


def test_prune_stale_candidates_cascade_deletes_eligible_candidate(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id, group_id, gp_id = _insert_full_candidate_tree(conn)

    result = cleanup.prune_stale_candidates(
        conn, retention_days=30, now=datetime(2026, 7, 14, 9, 0, 0)
    )

    assert result == [candidate_id]
    assert conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone() is None
    assert conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone() is None
    assert conn.execute("SELECT * FROM group_products WHERE id = ?", (gp_id,)).fetchone() is None
    assert conn.execute(
        "SELECT * FROM group_product_variants WHERE group_product_id = ?", (gp_id,)
    ).fetchone() is None
    assert conn.execute(
        "SELECT * FROM product_images WHERE group_product_id = ?", (gp_id,)
    ).fetchone() is None
    assert conn.execute(
        "SELECT * FROM listing_metrics_snapshots WHERE group_product_id = ?", (gp_id,)
    ).fetchone() is None
    assert conn.execute(
        "SELECT * FROM critic_pass_attempts WHERE group_id = ?", (group_id,)
    ).fetchone() is None
    assert conn.execute(
        "SELECT * FROM group_messages WHERE group_id = ?", (group_id,)
    ).fetchone() is None
    assert conn.execute(
        "SELECT * FROM listing_texts WHERE candidate_id = ?", (candidate_id,)
    ).fetchone() is None
    conn.close()


def test_prune_stale_candidates_skips_candidate_with_live_gelato_product(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id, _, _ = _insert_full_candidate_tree(
        conn, group_product_status="publish_failed", gelato_product_id="still_live"
    )

    result = cleanup.prune_stale_candidates(
        conn, retention_days=30, now=datetime(2026, 7, 14, 9, 0, 0)
    )

    assert result == []
    assert conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone() is not None
    conn.close()


def test_prune_stale_candidates_skips_non_terminal_status(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn, status="primary_review", updated_at="2026-06-01T09:00:00")

    result = cleanup.prune_stale_candidates(
        conn, retention_days=30, now=datetime(2026, 7, 14, 9, 0, 0)
    )

    assert result == []
    conn.close()


def test_prune_stale_candidates_skips_candidate_newer_than_cutoff(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn, status="completed", updated_at="2026-07-10T09:00:00")

    result = cleanup.prune_stale_candidates(
        conn, retention_days=30, now=datetime(2026, 7, 14, 9, 0, 0)
    )

    assert result == []
    conn.close()


def test_run_cleanup_calls_all_three_and_returns_summary(tmp_path):
    conn = _fresh_conn(tmp_path)

    # orphaned Gelato product
    orphan_candidate_id = _insert_candidate(conn, status="failed", updated_at="2026-07-13T09:00:00")
    orphan_group_id = _insert_group(conn, orphan_candidate_id, status="rejected")
    orphan_gp_id = _insert_group_product(conn, orphan_group_id, gelato_product_id="gelato_orphan", status="created")

    # stale candidate eligible for pruning (no live Gelato product)
    stale_candidate_id, _, _ = _insert_full_candidate_tree(
        conn, updated_at="2026-06-01T09:00:00", group_product_status="deleted"
    )

    # stale telegram event
    _insert_telegram_event(conn, received_at="2026-06-01T09:00:00")

    with patch("pipeline.cleanup.gelato_client.delete_product") as mock_delete:
        result = cleanup.run_cleanup(conn, retention_days=30, now=datetime(2026, 7, 14, 9, 0, 0))

    mock_delete.assert_called_once_with("gelato_orphan", store_id=None, api_key=None)
    assert result == {
        "gelato_products_deleted": [orphan_gp_id],
        "candidates_pruned": [stale_candidate_id],
        "telegram_events_pruned": 1,
    }
    conn.close()
