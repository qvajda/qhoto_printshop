import json as _json
from datetime import datetime
from unittest.mock import patch

import pytest

import pipeline.critic_pass as critic_pass
import pipeline.db as db


def test_build_critic_prompt_includes_rubric_and_listing_text():
    listing_text = {
        "title": "Monstera Line Art Botanical Print",
        "description": "A minimalist botanical print.",
    }

    prompt = critic_pass.build_critic_prompt(listing_text, 3)

    assert "Monstera Line Art Botanical Print" in prompt
    assert "A minimalist botanical print." in prompt
    assert "named artist's style" in prompt
    assert "watermark-like elements" in prompt
    assert "off-center or cut-off composition" in prompt
    assert "3 gallery images" in prompt
    assert "'passed' (boolean)" in prompt


def _fresh_conn(tmp_path):
    conn = db.get_connection(tmp_path / "test.sqlite3")
    db.init_db(conn)
    return conn


def _insert_candidate(conn, niche="monstera line art", *, status="generating",
                       base_image_url="https://replicate.delivery/out.png"):
    timestamp = "2026-07-10T11:00:00"
    cursor = conn.execute(
        """
        INSERT INTO candidates (created_at, niche, go_hold_kill, status, base_image_url, updated_at)
        VALUES (?, ?, 'go', ?, ?, ?)
        """,
        (timestamp, niche, status, base_image_url, timestamp),
    )
    conn.commit()
    return cursor.lastrowid


def _insert_primary_gallery(conn, candidate_id,
                             image_urls=("https://gelato/flat.jpg", "https://gelato/life.jpg"),
                             *, gelato_product_id="gelato_prod_1", group_product_status="created"):
    timestamp = "2026-07-10T11:05:00"
    group_cursor = conn.execute(
        "INSERT INTO groups (candidate_id, group_type, status, created_at, updated_at) "
        "VALUES (?, 'primary', 'pending_review', ?, ?)",
        (candidate_id, timestamp, timestamp),
    )
    group_id = group_cursor.lastrowid
    gp_cursor = conn.execute(
        "INSERT INTO group_products "
        "(group_id, size, orientation, gelato_template_id, gelato_product_id, price_eur, "
        "status, created_at, updated_at) "
        "VALUES (?, '8x12', 'portrait', 'tpl_1', ?, 24, ?, ?, ?)",
        (group_id, gelato_product_id, group_product_status, timestamp, timestamp),
    )
    group_product_id = gp_cursor.lastrowid
    for order, image_url in enumerate(image_urls):
        image_type = "flat_mockup" if order == 0 else "lifestyle"
        conn.execute(
            "INSERT INTO product_images (group_product_id, image_url, alt_text, gallery_order, image_type) "
            "VALUES (?, ?, 'placeholder alt', ?, ?)",
            (group_product_id, image_url, order, image_type),
        )
    conn.commit()
    return group_id, group_product_id


def _insert_listing_text(conn, candidate_id, niche="monstera line art"):
    timestamp = "2026-07-10T11:10:00"
    conn.execute(
        """
        INSERT INTO listing_texts (
            candidate_id, title, tags, description, disclosure_text,
            who_made, production_partner_ids, taxonomy_id, shipping_profile_id, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            candidate_id, f"{niche} print", _json.dumps(["botanical", "wall art"]),
            f"A print of {niche}.", "disclosure text",
            "i_did", _json.dumps([5717252]), "1027", "", timestamp,
        ),
    )
    conn.commit()


def _insert_ready_candidate(conn, niche="monstera line art"):
    candidate_id = _insert_candidate(conn, niche=niche)
    _insert_primary_gallery(conn, candidate_id)
    _insert_listing_text(conn, candidate_id, niche=niche)
    return candidate_id


def test_get_primary_group_state_returns_gallery_and_listing_text(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_ready_candidate(conn, niche="monstera line art")

    state = critic_pass.get_primary_group_state(conn, candidate_id)

    assert state["image_urls"] == ["https://gelato/flat.jpg", "https://gelato/life.jpg"]
    assert state["listing_text"]["title"] == "monstera line art print"
    assert state["listing_text"]["description"] == "A print of monstera line art."
    conn.close()


def test_get_primary_group_state_raises_when_no_primary_group(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)

    with pytest.raises(ValueError, match="primary group"):
        critic_pass.get_primary_group_state(conn, candidate_id)
    conn.close()


def test_get_primary_group_state_raises_when_no_listing_text(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_primary_gallery(conn, candidate_id)

    with pytest.raises(ValueError, match="listing_texts"):
        critic_pass.get_primary_group_state(conn, candidate_id)
    conn.close()


def test_evaluate_critic_pass_returns_parsed_result():
    listing_text = {"title": "Monstera Line Art Botanical Print", "description": "A minimalist botanical print."}
    fake_response = {"text": _json.dumps({"passed": True, "reason": "meets rubric"})}

    with patch("pipeline.critic_pass.anthropic_client.complete_with_images",
               return_value=fake_response) as mock_call:
        result = critic_pass.evaluate_critic_pass(
            ["https://gelato/a.jpg", "https://gelato/b.jpg"], listing_text, api_key="key1"
        )

    mock_call.assert_called_once()
    called_prompt, called_images = mock_call.call_args.args
    assert "Monstera Line Art Botanical Print" in called_prompt
    assert called_images == ["https://gelato/a.jpg", "https://gelato/b.jpg"]
    assert mock_call.call_args.kwargs["api_key"] == "key1"
    assert result == {"passed": True, "reason": "meets rubric"}


def test_evaluate_critic_pass_raises_on_missing_key():
    listing_text = {"title": "A title", "description": "A description."}
    fake_response = {"text": _json.dumps({"passed": False})}

    with patch("pipeline.critic_pass.anthropic_client.complete_with_images", return_value=fake_response):
        with pytest.raises(ValueError, match="reason"):
            critic_pass.evaluate_critic_pass(["https://gelato/a.jpg"], listing_text, api_key="key1")


def test_record_critic_attempt_stores_pass(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id, _ = _insert_primary_gallery(conn, candidate_id)

    attempt_id = critic_pass.record_critic_attempt(
        conn, group_id, 1, {"passed": True, "reason": "meets rubric"},
        now=datetime(2026, 7, 10, 12, 0, 0),
    )

    row = conn.execute("SELECT * FROM critic_pass_attempts WHERE id = ?", (attempt_id,)).fetchone()
    assert row["group_id"] == group_id
    assert row["attempt_number"] == 1
    assert row["passed"] == 1
    assert row["failure_reason"] is None
    assert row["created_at"] == "2026-07-10T12:00:00"
    conn.close()


def test_record_critic_attempt_stores_failure_with_reason_and_correction_notes(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id, _ = _insert_primary_gallery(conn, candidate_id)

    attempt_id = critic_pass.record_critic_attempt(
        conn, group_id, 1, {"passed": False, "reason": "composition is off-center"},
        correction_notes="composition is off-center", now=datetime(2026, 7, 10, 12, 0, 0),
    )

    row = conn.execute("SELECT * FROM critic_pass_attempts WHERE id = ?", (attempt_id,)).fetchone()
    assert row["passed"] == 0
    assert row["failure_reason"] == "composition is off-center"
    assert row["correction_notes"] == "composition is off-center"
    conn.close()


def test_discard_superseded_attempt_deletes_gelato_product_and_rows(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _group_id, group_product_id = _insert_primary_gallery(conn, candidate_id)

    with patch("pipeline.critic_pass.gelato_client.delete_product") as mock_delete:
        critic_pass.discard_superseded_attempt(
            conn, group_product_id, store_id="store1", api_key="key2"
        )

    mock_delete.assert_called_once_with("gelato_prod_1", store_id="store1", api_key="key2")

    assert conn.execute(
        "SELECT * FROM group_products WHERE id = ?", (group_product_id,)
    ).fetchone() is None
    assert conn.execute(
        "SELECT * FROM product_images WHERE group_product_id = ?", (group_product_id,)
    ).fetchall() == []
    conn.close()


def test_discard_superseded_attempt_skips_gelato_call_when_no_product_id(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _group_id, group_product_id = _insert_primary_gallery(
        conn, candidate_id, gelato_product_id=None, group_product_status="pending"
    )

    with patch("pipeline.critic_pass.gelato_client.delete_product") as mock_delete:
        critic_pass.discard_superseded_attempt(conn, group_product_id, store_id="store1", api_key="key2")

    mock_delete.assert_not_called()
    assert conn.execute(
        "SELECT * FROM group_products WHERE id = ?", (group_product_id,)
    ).fetchone() is None
    conn.close()


def test_abandon_candidate_marks_candidate_and_group_failed(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id, _ = _insert_primary_gallery(conn, candidate_id)

    critic_pass.abandon_candidate(
        conn, candidate_id, group_id, "exhausted 3 attempts: off-center composition",
        now=datetime(2026, 7, 10, 12, 30, 0),
    )

    candidate_row = conn.execute(
        "SELECT status, failed_reason, updated_at FROM candidates WHERE id = ?", (candidate_id,)
    ).fetchone()
    assert candidate_row["status"] == "failed"
    assert candidate_row["failed_reason"] == "exhausted 3 attempts: off-center composition"
    assert candidate_row["updated_at"] == "2026-07-10T12:30:00"

    group_row = conn.execute(
        "SELECT status, failed_reason FROM groups WHERE id = ?", (group_id,)
    ).fetchone()
    assert group_row["status"] == "failed_abandoned"
    assert group_row["failed_reason"] == "exhausted 3 attempts: off-center composition"
    conn.close()
