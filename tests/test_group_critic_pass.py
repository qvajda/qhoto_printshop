import json as _json
from datetime import datetime
from unittest.mock import patch

import pytest

import pipeline.db as db
import pipeline.group_critic_pass as group_critic_pass


def _fresh_conn(tmp_path):
    conn = db.get_connection(tmp_path / "test.sqlite3")
    db.init_db(conn)
    return conn


def _insert_candidate(conn, niche="monstera line art", *, status="primary_review",
                       base_image_url="https://replicate.delivery/out.png"):
    timestamp = "2026-07-13T09:00:00"
    cursor = conn.execute(
        """
        INSERT INTO candidates (created_at, niche, go_hold_kill, status, base_image_url, updated_at)
        VALUES (?, ?, 'go', ?, ?, ?)
        """,
        (timestamp, niche, status, base_image_url, timestamp),
    )
    conn.commit()
    return cursor.lastrowid


def _insert_group_gallery(conn, candidate_id, group_type, size, *,
                           image_urls=("https://gelato/flat.jpg", "https://gelato/life.jpg"),
                           gelato_product_id="gelato_prod_1", group_status="pending_review",
                           group_product_status="created"):
    timestamp = "2026-07-13T09:05:00"
    group_cursor = conn.execute(
        "INSERT INTO groups (candidate_id, group_type, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (candidate_id, group_type, group_status, timestamp, timestamp),
    )
    group_id = group_cursor.lastrowid
    gp_cursor = conn.execute(
        "INSERT INTO group_products "
        "(group_id, gelato_template_id, gelato_product_id, status, created_at, updated_at) "
        "VALUES (?, 'tpl_1', ?, ?, ?, ?)",
        (group_id, gelato_product_id, group_product_status, timestamp, timestamp),
    )
    group_product_id = gp_cursor.lastrowid
    conn.execute(
        "INSERT INTO group_product_variants "
        "(group_product_id, size, orientation, gelato_template_variant_id, price_eur, created_at) "
        "VALUES (?, ?, 'portrait', ?, 19, ?)",
        (group_product_id, size, f"variant_{size}", timestamp),
    )
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
    timestamp = "2026-07-13T09:10:00"
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


def test_get_group_critic_state_returns_gallery_and_listing_text(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_group_gallery(conn, candidate_id, "5x7", "5x7")
    _insert_listing_text(conn, candidate_id)

    state = group_critic_pass.get_group_critic_state(conn, candidate_id, "5x7")

    assert state["image_urls"] == ["https://gelato/flat.jpg", "https://gelato/life.jpg"]
    assert state["listing_text"]["title"] == "monstera line art print"
    conn.close()


def test_get_group_critic_state_raises_when_no_group(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)

    with pytest.raises(ValueError, match="5x7 group"):
        group_critic_pass.get_group_critic_state(conn, candidate_id, "5x7")
    conn.close()


def test_get_group_critic_state_raises_when_no_live_group_product(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_group_gallery(conn, candidate_id, "10x24", "10x24", group_product_status="mockup_failed")

    with pytest.raises(ValueError, match="group_products"):
        group_critic_pass.get_group_critic_state(conn, candidate_id, "10x24")
    conn.close()


def test_get_group_critic_state_raises_when_no_listing_text(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_group_gallery(conn, candidate_id, "5x7", "5x7")

    with pytest.raises(ValueError, match="listing_texts"):
        group_critic_pass.get_group_critic_state(conn, candidate_id, "5x7")
    conn.close()


def test_abandon_group_marks_only_that_group_failed(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id, _ = _insert_group_gallery(conn, candidate_id, "5x7", "5x7")
    other_group_id, _ = _insert_group_gallery(conn, candidate_id, "10x24", "10x24",
                                               gelato_product_id="gelato_prod_2")

    group_critic_pass.abandon_group(
        conn, group_id, "exhausted 3 attempts: off-center crop",
        now=datetime(2026, 7, 13, 12, 0, 0),
    )

    group_row = conn.execute(
        "SELECT status, failed_reason FROM groups WHERE id = ?", (group_id,)
    ).fetchone()
    assert group_row["status"] == "failed_abandoned"
    assert group_row["failed_reason"] == "exhausted 3 attempts: off-center crop"

    other_group_row = conn.execute(
        "SELECT status FROM groups WHERE id = ?", (other_group_id,)
    ).fetchone()
    assert other_group_row["status"] == "pending_review"

    candidate_row = conn.execute(
        "SELECT status FROM candidates WHERE id = ?", (candidate_id,)
    ).fetchone()
    assert candidate_row["status"] == "primary_review"
    conn.close()


STATIC_CONFIG = {
    "gelato_templates": {
        "5x7_portrait": {
            "template_id": "tpl_5x7",
            "template_variant_id": "variant_5x7",
            "image_placeholder_name": "slot_5x7.jpg",
        },
    },
    "prices_eur": {"5x7": 19},
    "aspect_ratio_groups": {"5x7": ["5x7"], "10x24": ["10x24"]},
}


def test_run_group_critic_pass_passes_on_first_attempt(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_group_gallery(conn, candidate_id, "5x7", "5x7")
    _insert_listing_text(conn, candidate_id)

    fake_response = {"text": _json.dumps({"passed": True, "reason": "meets rubric"})}
    with patch("pipeline.critic_pass.anthropic_client.complete_with_images", return_value=fake_response):
        result = group_critic_pass.run_group_critic_pass(
            conn, candidate_id, "5x7", static_config=STATIC_CONFIG, anthropic_api_key="key1",
            store_id="store1", gelato_api_key="key2", now=datetime(2026, 7, 13, 12, 0, 0),
        )

    assert result["passed"] is True
    assert result["attempts"] == 1

    group_row = conn.execute(
        "SELECT status FROM groups WHERE candidate_id = ? AND group_type = '5x7'", (candidate_id,)
    ).fetchone()
    assert group_row["status"] == "pending_review"

    attempts = conn.execute(
        "SELECT * FROM critic_pass_attempts WHERE group_id = ?", (result["group_id"],)
    ).fetchall()
    assert len(attempts) == 1
    assert attempts[0]["passed"] == 1
    conn.close()


def test_run_group_critic_pass_retries_once_then_passes(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_group_gallery(conn, candidate_id, "5x7", "5x7", gelato_product_id="gelato_prod_v1")
    _insert_listing_text(conn, candidate_id)

    critic_responses = iter([
        {"text": _json.dumps({"passed": False, "reason": "crop cuts off the composition"})},
        {"text": _json.dumps({"passed": True, "reason": "meets rubric"})},
    ])

    def fake_create_product_from_template(*args, **kwargs):
        return {"id": "gelato_prod_v2", "isReadyToPublish": False, "productImages": []}

    ready_product = {"isReadyToPublish": True,
                      "productImages": [{"fileUrl": "https://gelato/flat_v2.jpg", "isPrimary": True}]}

    with patch("pipeline.critic_pass.anthropic_client.complete_with_images",
               side_effect=lambda *a, **k: next(critic_responses)), \
         patch("pipeline.critic_pass.gelato_client.delete_product") as mock_delete, \
         patch("pipeline.group_product.gelato_client.create_product_from_template",
               side_effect=fake_create_product_from_template), \
         patch("pipeline.group_product.poll_until_ready", return_value=ready_product):
        result = group_critic_pass.run_group_critic_pass(
            conn, candidate_id, "5x7", static_config=STATIC_CONFIG, anthropic_api_key="key1",
            store_id="store1", gelato_api_key="key2", now=datetime(2026, 7, 13, 12, 0, 0),
        )

    assert result["passed"] is True
    assert result["attempts"] == 2
    mock_delete.assert_called_once_with("gelato_prod_v1", store_id="store1", api_key="key2")

    group_row = conn.execute(
        "SELECT status FROM groups WHERE candidate_id = ? AND group_type = '5x7'", (candidate_id,)
    ).fetchone()
    assert group_row["status"] == "pending_review"

    gp_rows = conn.execute(
        "SELECT * FROM group_products WHERE group_id = ?", (result["group_id"],)
    ).fetchall()
    assert len(gp_rows) == 1
    assert gp_rows[0]["gelato_product_id"] == "gelato_prod_v2"
    assert gp_rows[0]["status"] == "created"

    attempts = conn.execute(
        "SELECT * FROM critic_pass_attempts WHERE group_id = ? ORDER BY attempt_number",
        (result["group_id"],),
    ).fetchall()
    assert len(attempts) == 2
    assert attempts[0]["passed"] == 0
    assert attempts[0]["failure_reason"] == "crop cuts off the composition"
    assert attempts[1]["passed"] == 1
    conn.close()


def test_run_group_critic_pass_abandons_only_this_group_after_three_failures(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_group_gallery(conn, candidate_id, "5x7", "5x7", gelato_product_id="gelato_prod_v1")
    _insert_group_gallery(conn, candidate_id, "10x24", "10x24", gelato_product_id="gelato_prod_other")
    _insert_listing_text(conn, candidate_id)

    critic_responses = iter([
        {"text": _json.dumps({"passed": False, "reason": "reason one"})},
        {"text": _json.dumps({"passed": False, "reason": "reason two"})},
        {"text": _json.dumps({"passed": False, "reason": "reason three"})},
    ])

    def fake_create_product_from_template(*args, **kwargs):
        return {"id": "gelato_prod_retry", "isReadyToPublish": False, "productImages": []}

    ready_product = {"isReadyToPublish": True,
                      "productImages": [{"fileUrl": "https://gelato/flat_retry.jpg", "isPrimary": True}]}

    with patch("pipeline.critic_pass.anthropic_client.complete_with_images",
               side_effect=lambda *a, **k: next(critic_responses)), \
         patch("pipeline.critic_pass.gelato_client.delete_product") as mock_delete, \
         patch("pipeline.group_product.gelato_client.create_product_from_template",
               side_effect=fake_create_product_from_template), \
         patch("pipeline.group_product.poll_until_ready", return_value=ready_product):
        result = group_critic_pass.run_group_critic_pass(
            conn, candidate_id, "5x7", static_config=STATIC_CONFIG, anthropic_api_key="key1",
            store_id="store1", gelato_api_key="key2", now=datetime(2026, 7, 13, 12, 0, 0),
        )

    assert result["passed"] is False
    assert result["attempts"] == 3
    assert mock_delete.call_count == 3

    group_row = conn.execute(
        "SELECT status, failed_reason FROM groups WHERE candidate_id = ? AND group_type = '5x7'",
        (candidate_id,),
    ).fetchone()
    assert group_row["status"] == "failed_abandoned"
    assert group_row["failed_reason"] == "reason three"

    # Untouched: candidate itself, and the sibling 10x24 group.
    candidate_row = conn.execute("SELECT status FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    assert candidate_row["status"] == "primary_review"

    other_group_row = conn.execute(
        "SELECT status FROM groups WHERE candidate_id = ? AND group_type = '10x24'", (candidate_id,)
    ).fetchone()
    assert other_group_row["status"] == "pending_review"
    conn.close()


def test_run_group_critic_pass_cycle_processes_ready_groups_and_skips_uncreated(tmp_path):
    conn = _fresh_conn(tmp_path)
    ready_id = _insert_candidate(conn, niche="monstera line art")
    _insert_group_gallery(conn, ready_id, "5x7", "5x7")
    _insert_listing_text(conn, ready_id, niche="monstera line art")

    not_ready_id = _insert_candidate(conn, niche="moon phase print")
    _insert_group_gallery(conn, not_ready_id, "10x24", "10x24", group_product_status="mockup_failed")
    _insert_listing_text(conn, not_ready_id, niche="moon phase print")

    fake_response = {"text": _json.dumps({"passed": True, "reason": "meets rubric"})}
    with patch("pipeline.critic_pass.anthropic_client.complete_with_images", return_value=fake_response):
        processed = group_critic_pass.run_group_critic_pass_cycle(
            conn, anthropic_api_key="key1", store_id="store1", gelato_api_key="key2",
            now=datetime(2026, 7, 13, 20, 0, 0),
        )

    assert processed == [{"candidate_id": ready_id, "group_type": "5x7", "passed": True}]
    conn.close()


def test_run_group_critic_pass_cycle_skips_groups_already_passed(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_group_gallery(conn, candidate_id, "5x7", "5x7")
    _insert_listing_text(conn, candidate_id)

    fake_response = {"text": _json.dumps({"passed": True, "reason": "meets rubric"})}
    with patch("pipeline.critic_pass.anthropic_client.complete_with_images", return_value=fake_response):
        first_run = group_critic_pass.run_group_critic_pass_cycle(
            conn, anthropic_api_key="key1", store_id="store1", gelato_api_key="key2",
            now=datetime(2026, 7, 13, 20, 0, 0),
        )
        second_run = group_critic_pass.run_group_critic_pass_cycle(
            conn, anthropic_api_key="key1", store_id="store1", gelato_api_key="key2",
            now=datetime(2026, 7, 13, 21, 0, 0),
        )

    assert first_run == [{"candidate_id": candidate_id, "group_type": "5x7", "passed": True}]
    assert second_run == []
    conn.close()


def test_run_group_critic_pass_cycle_excludes_abandoned_group_from_rerun(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_group_gallery(conn, candidate_id, "5x7", "5x7", gelato_product_id="gelato_prod_v1")
    _insert_listing_text(conn, candidate_id)

    fail_response = {"text": _json.dumps({"passed": False, "reason": "reason"})}

    def fake_create_product_from_template(*args, **kwargs):
        return {"id": "gelato_prod_retry", "isReadyToPublish": False, "productImages": []}

    ready_product = {"isReadyToPublish": True,
                      "productImages": [{"fileUrl": "https://gelato/flat_retry.jpg", "isPrimary": True}]}

    with patch("pipeline.critic_pass.anthropic_client.complete_with_images", return_value=fail_response), \
         patch("pipeline.critic_pass.gelato_client.delete_product"), \
         patch("pipeline.group_product.gelato_client.create_product_from_template",
               side_effect=fake_create_product_from_template), \
         patch("pipeline.group_product.poll_until_ready", return_value=ready_product):
        first_run = group_critic_pass.run_group_critic_pass_cycle(
            conn, anthropic_api_key="key1", store_id="store1", gelato_api_key="key2",
            now=datetime(2026, 7, 13, 20, 0, 0),
        )
        second_run = group_critic_pass.run_group_critic_pass_cycle(
            conn, anthropic_api_key="key1", store_id="store1", gelato_api_key="key2",
            now=datetime(2026, 7, 13, 22, 0, 0),
        )

    assert first_run == [{"candidate_id": candidate_id, "group_type": "5x7", "passed": False}]
    # After abandonment, groups.status is 'failed_abandoned', not 'pending_review' — excluded.
    assert second_run == []
    conn.close()


def test_run_group_critic_pass_cycle_isolates_per_group_operational_failures(tmp_path):
    conn = _fresh_conn(tmp_path)
    failing_id = _insert_candidate(conn, niche="saturated term")
    _insert_group_gallery(conn, failing_id, "5x7", "5x7")
    _insert_listing_text(conn, failing_id, niche="saturated term")

    succeeding_id = _insert_candidate(conn, niche="moon phase print")
    _insert_group_gallery(conn, succeeding_id, "10x24", "10x24")
    _insert_listing_text(conn, succeeding_id, niche="moon phase print")

    def fake_complete_with_images(prompt, image_urls, *, api_key=None, max_tokens=1024):
        if "saturated term" in prompt:
            raise RuntimeError("Anthropic throttled")
        return {"text": _json.dumps({"passed": True, "reason": "meets rubric"})}

    with patch("pipeline.critic_pass.anthropic_client.complete_with_images",
               side_effect=fake_complete_with_images):
        processed = group_critic_pass.run_group_critic_pass_cycle(
            conn, anthropic_api_key="key1", store_id="store1", gelato_api_key="key2",
            now=datetime(2026, 7, 13, 20, 0, 0),
        )

    assert processed == [{"candidate_id": succeeding_id, "group_type": "10x24", "passed": True}]

    failing_group_row = conn.execute(
        "SELECT status FROM groups WHERE candidate_id = ? AND group_type = '5x7'", (failing_id,)
    ).fetchone()
    assert failing_group_row["status"] == "pending_review"  # untouched — exception before any write
    conn.close()


def test_run_group_critic_pass_cycle_returns_empty_list_when_nothing_ready(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_group_gallery(conn, candidate_id, "5x7", "5x7", group_product_status="mockup_failed")

    processed = group_critic_pass.run_group_critic_pass_cycle(conn)

    assert processed == []
    conn.close()
