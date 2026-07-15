import json as _json
from datetime import datetime
from unittest.mock import patch

import pytest

import pipeline.db as db
import pipeline.publish_group as publish_group
import pipeline.publish_primary_group as publish_primary_group


def _fresh_conn(tmp_path):
    conn = db.get_connection(tmp_path / "test.sqlite3")
    db.init_db(conn)
    return conn


def _insert_candidate(conn, niche="monstera line art", *, status="primary_review",
                       base_image_url="https://replicate.delivery/out.png"):
    timestamp = "2026-07-12T09:00:00"
    cursor = conn.execute(
        """
        INSERT INTO candidates (created_at, niche, go_hold_kill, status, base_image_url, updated_at)
        VALUES (?, ?, 'go', ?, ?, ?)
        """,
        (timestamp, niche, status, base_image_url, timestamp),
    )
    conn.commit()
    return cursor.lastrowid


def _insert_group(conn, candidate_id, group_type, *, status="pending_review"):
    timestamp = "2026-07-13T09:05:00"
    cursor = conn.execute(
        "INSERT INTO groups (candidate_id, group_type, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (candidate_id, group_type, status, timestamp, timestamp),
    )
    conn.commit()
    return cursor.lastrowid


def _insert_listing_text(conn, candidate_id, niche="monstera line art"):
    timestamp = "2026-07-12T09:10:00"
    conn.execute(
        """
        INSERT INTO listing_texts (
            candidate_id, title, tags, description, disclosure_text,
            who_made, production_partner_ids, taxonomy_id, shipping_profile_id, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            candidate_id, f"{niche} print", _json.dumps(["botanical", "wall art"]),
            f"A print of {niche}.", "AI disclosure text.",
            "i_did", _json.dumps([5717252]), "1027", "", timestamp,
        ),
    )
    conn.commit()


def _insert_group_product_with_images(conn, group_id, size, *, gelato_product_id="gelato_5x7",
                                       price_eur=19,
                                       image_urls=("https://gelato/flat.jpg", "https://gelato/life.jpg")):
    timestamp = "2026-07-13T10:00:00"
    cursor = conn.execute(
        "INSERT INTO group_products "
        "(group_id, size, orientation, gelato_template_id, gelato_product_id, price_eur, "
        "status, created_at, updated_at) "
        "VALUES (?, ?, 'portrait', 'tpl_x', ?, ?, 'created', ?, ?)",
        (group_id, size, gelato_product_id, price_eur, timestamp, timestamp),
    )
    gp_id = cursor.lastrowid
    for order, url in enumerate(image_urls):
        image_type = "flat_mockup" if order == 0 else "lifestyle"
        conn.execute(
            "INSERT INTO product_images (group_product_id, image_url, alt_text, gallery_order, image_type) "
            "VALUES (?, ?, '', ?, ?)",
            (gp_id, url, order, image_type),
        )
    conn.commit()
    return gp_id


def _insert_ready_5x7_group(conn, candidate_id):
    group_id = _insert_group(conn, candidate_id, "5x7", status="pending_review")
    gp_id = _insert_group_product_with_images(conn, group_id, "5x7")
    _insert_listing_text(conn, candidate_id)
    return group_id, gp_id


STATIC_CONFIG = {
    "gelato_templates": {
        "5x7_portrait": {
            "template_id": "tpl_5x7", "template_variant_id": "variant_5x7",
            "image_placeholder_name": "slot_5x7.jpg",
        },
    },
    "prices_eur": {"5x7": 19},
    "aspect_ratio_groups": {"primary": ["8x12", "A3", "A2", "A1"], "5x7": ["5x7"], "10x24": ["10x24"]},
    "etsy_shipping_profile_id": {"primary": "287910565714", "5x7": "287910553824", "10x24": "287910565714"},
}


def test_handle_decision_approve_publishes_group_and_sets_status(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id, gp_id = _insert_ready_5x7_group(conn, candidate_id)

    with patch("pipeline.publish_group.publish_primary_group.publish_group_product",
               return_value="listing_777") as mock_publish:
        result = publish_group.handle_decision(
            conn, candidate_id, group_id, "approve", static_config=STATIC_CONFIG, dry_run=True,
            now=datetime(2026, 7, 13, 12, 0, 0),
        )

    mock_publish.assert_called_once()
    assert mock_publish.call_args.args[1] == gp_id
    assert result["action"] == "approve"
    assert result["listing_id"] == "listing_777"

    group_row = conn.execute(
        "SELECT decision, status, decided_at FROM groups WHERE id = ?", (group_id,)
    ).fetchone()
    assert group_row["decision"] == "approved"
    assert group_row["status"] == "approved_published"
    assert group_row["decided_at"] == "2026-07-13T12:00:00"

    candidate_row = conn.execute(
        "SELECT status FROM candidates WHERE id = ?", (candidate_id,)
    ).fetchone()
    assert candidate_row["status"] == "primary_review"  # untouched
    conn.close()


def test_handle_decision_approve_raises_when_no_live_group_product(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_group(conn, candidate_id, "5x7", status="pending_review")

    with pytest.raises(ValueError, match="No live group_product"):
        publish_group.handle_decision(
            conn, candidate_id, group_id, "approve", static_config=STATIC_CONFIG,
        )
    conn.close()


def test_handle_decision_approve_marks_group_publish_failed_on_publish_failure(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id, gp_id = _insert_ready_5x7_group(conn, candidate_id)

    with patch("pipeline.publish_group.publish_primary_group.publish_group_product",
               side_effect=RuntimeError("etsy down")):
        with pytest.raises(RuntimeError, match="etsy down"):
            publish_group.handle_decision(
                conn, candidate_id, group_id, "approve", static_config=STATIC_CONFIG, dry_run=True,
                now=datetime(2026, 7, 13, 12, 0, 0),
            )

    group_row = conn.execute("SELECT status FROM groups WHERE id = ?", (group_id,)).fetchone()
    assert group_row["status"] == "publish_failed"
    conn.close()


def test_handle_decision_reject_deletes_product_and_marks_group_rejected(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id, gp_id = _insert_ready_5x7_group(conn, candidate_id)

    with patch("pipeline.publish_group.critic_pass.gelato_client.delete_product") as mock_delete:
        result = publish_group.handle_decision(
            conn, candidate_id, group_id, "reject", "not vibing with this crop",
            now=datetime(2026, 7, 13, 12, 0, 0),
        )

    mock_delete.assert_called_once_with("gelato_5x7", store_id=None, api_key=None)
    assert result["action"] == "reject"

    group_row = conn.execute(
        "SELECT decision, decision_notes, status FROM groups WHERE id = ?", (group_id,)
    ).fetchone()
    assert group_row["decision"] == "rejected"
    assert group_row["decision_notes"] == "not vibing with this crop"
    assert group_row["status"] == "rejected"

    assert conn.execute(
        "SELECT * FROM group_products WHERE id = ?", (gp_id,)
    ).fetchone() is None

    candidate_row = conn.execute(
        "SELECT status FROM candidates WHERE id = ?", (candidate_id,)
    ).fetchone()
    assert candidate_row["status"] == "primary_review"  # untouched
    conn.close()


def test_handle_decision_reject_with_no_live_product_still_marks_rejected(tmp_path):
    # e.g. the group's product already failed publish earlier and was never recreated —
    # reject should still record the decision without requiring a live Gelato product to delete.
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_group(conn, candidate_id, "5x7", status="pending_review")

    with patch("pipeline.publish_group.critic_pass.gelato_client.delete_product") as mock_delete:
        result = publish_group.handle_decision(conn, candidate_id, group_id, "reject")

    mock_delete.assert_not_called()
    assert result["action"] == "reject"
    group_row = conn.execute("SELECT status FROM groups WHERE id = ?", (group_id,)).fetchone()
    assert group_row["status"] == "rejected"
    conn.close()


def test_handle_decision_edit_discards_product_and_attempts_leaves_status_alone(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id, gp_id = _insert_ready_5x7_group(conn, candidate_id)
    publish_primary_group.critic_pass.record_critic_attempt(
        conn, group_id, 1, {"passed": True, "reason": "meets rubric"},
        now=datetime(2026, 7, 13, 9, 20, 0),
    )
    conn.execute(
        "INSERT INTO group_messages (group_id, telegram_message_id, chat_id, sent_at) "
        "VALUES (?, 202, '987654321', '2026-07-13T09:15:00')",
        (group_id,),
    )
    conn.commit()

    with patch("pipeline.publish_group.critic_pass.gelato_client.delete_product") as mock_delete:
        result = publish_group.handle_decision(
            conn, candidate_id, group_id, "edit", "crop feels too tight",
            now=datetime(2026, 7, 13, 12, 0, 0),
        )

    mock_delete.assert_called_once_with("gelato_5x7", store_id=None, api_key=None)
    assert result["action"] == "edit"

    assert conn.execute("SELECT * FROM group_products WHERE id = ?", (gp_id,)).fetchone() is None
    assert conn.execute(
        "SELECT * FROM critic_pass_attempts WHERE group_id = ?", (group_id,)
    ).fetchall() == []
    assert conn.execute(
        "SELECT * FROM group_messages WHERE group_id = ?", (group_id,)
    ).fetchall() == []

    group_row = conn.execute(
        "SELECT decision, decision_notes, status FROM groups WHERE id = ?", (group_id,)
    ).fetchone()
    assert group_row["decision"] == "edited"
    assert group_row["decision_notes"] == "crop feels too tight"
    assert group_row["status"] == "pending_review"  # left as-is, confirmed with user
    conn.close()


def test_handle_decision_edit_with_no_live_product_still_clears_attempts_and_messages(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_group(conn, candidate_id, "5x7", status="pending_review")
    publish_primary_group.critic_pass.record_critic_attempt(
        conn, group_id, 1, {"passed": False, "reason": "off-center"},
        now=datetime(2026, 7, 13, 9, 20, 0),
    )

    with patch("pipeline.publish_group.critic_pass.gelato_client.delete_product") as mock_delete:
        result = publish_group.handle_decision(conn, candidate_id, group_id, "edit")

    mock_delete.assert_not_called()
    assert result["action"] == "edit"
    assert conn.execute(
        "SELECT * FROM critic_pass_attempts WHERE group_id = ?", (group_id,)
    ).fetchall() == []
    conn.close()


def test_handle_decision_raises_on_unknown_action(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id, _ = _insert_ready_5x7_group(conn, candidate_id)

    with pytest.raises(ValueError, match="Unknown action"):
        publish_group.handle_decision(conn, candidate_id, group_id, "snooze")
    conn.close()
