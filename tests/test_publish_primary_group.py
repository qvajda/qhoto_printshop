import json as _json
from datetime import datetime
from unittest.mock import patch

import pytest

import pipeline.db as db
import pipeline.publish_primary_group as publish_primary_group


def _callback_update(update_id=100000001, user_id=987654321, data="approve:42",
                      message_id=202, chat_id=987654321, callback_id="cbq123"):
    return {
        "update_id": update_id,
        "callback_query": {
            "id": callback_id,
            "from": {"id": user_id, "is_bot": False, "first_name": "Admin"},
            "message": {
                "message_id": message_id,
                "chat": {"id": chat_id, "type": "private"},
                "date": 1234567890,
                "text": "Candidate #7 - Primary group (#42)",
            },
            "chat_instance": "abc123",
            "data": data,
        },
    }


def test_resolve_callback_parses_action_group_id_and_routing_fields():
    update = _callback_update()

    parsed = publish_primary_group.resolve_callback(update)

    assert parsed == {
        "telegram_user_id": 987654321,
        "callback_query_id": "cbq123",
        "action": "approve",
        "group_id": 42,
        "message_id": 202,
        "chat_id": 987654321,
    }


def test_resolve_callback_parses_edit_and_reject_actions():
    edit_parsed = publish_primary_group.resolve_callback(_callback_update(data="edit:7"))
    reject_parsed = publish_primary_group.resolve_callback(_callback_update(data="reject:7"))

    assert edit_parsed["action"] == "edit"
    assert reject_parsed["action"] == "reject"
    assert edit_parsed["group_id"] == 7


def test_resolve_callback_returns_none_for_non_callback_update():
    update = {"update_id": 5, "message": {"text": "/research botanical"}}

    assert publish_primary_group.resolve_callback(update) is None


def test_is_admin_true_when_ids_match_across_int_and_str():
    assert publish_primary_group.is_admin(987654321, "987654321") is True
    assert publish_primary_group.is_admin("987654321", 987654321) is True


def test_is_admin_false_when_ids_differ():
    assert publish_primary_group.is_admin(111111111, "987654321") is False


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


def _insert_primary_group(conn, candidate_id, *, status="pending_review"):
    timestamp = "2026-07-12T09:05:00"
    cursor = conn.execute(
        "INSERT INTO groups (candidate_id, group_type, status, created_at, updated_at) "
        "VALUES (?, 'primary', ?, ?, ?)",
        (candidate_id, status, timestamp, timestamp),
    )
    conn.commit()
    return cursor.lastrowid


def test_log_telegram_event_writes_accepted_row(tmp_path):
    conn = _fresh_conn(tmp_path)

    event_id = publish_primary_group.log_telegram_event(
        conn, 987654321, {"update_id": 1}, True, "approve",
        now=datetime(2026, 7, 12, 9, 0, 0),
    )

    row = conn.execute("SELECT * FROM telegram_events_log WHERE id = ?", (event_id,)).fetchone()
    assert row["telegram_user_id"] == "987654321"
    assert row["accepted"] == 1
    assert row["action_taken"] == "approve"
    assert row["raw_payload"] == '{"update_id": 1}'
    assert row["received_at"] == "2026-07-12T09:00:00"
    conn.close()


def test_log_telegram_event_writes_discarded_row_with_no_action(tmp_path):
    conn = _fresh_conn(tmp_path)

    event_id = publish_primary_group.log_telegram_event(
        conn, 111111111, {"update_id": 2}, False, now=datetime(2026, 7, 12, 9, 0, 0),
    )

    row = conn.execute("SELECT * FROM telegram_events_log WHERE id = ?", (event_id,)).fetchone()
    assert row["accepted"] == 0
    assert row["action_taken"] is None
    conn.close()


def test_record_decision_writes_decision_notes_and_decided_at(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_primary_group(conn, candidate_id)

    publish_primary_group.record_decision(
        conn, group_id, "edited", "make it more pastel", now=datetime(2026, 7, 12, 9, 30, 0),
    )

    row = conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone()
    assert row["decision"] == "edited"
    assert row["decision_notes"] == "make it more pastel"
    assert row["decided_at"] == "2026-07-12T09:30:00"
    assert row["updated_at"] == "2026-07-12T09:30:00"
    conn.close()


def test_record_decision_allows_null_notes(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_primary_group(conn, candidate_id)

    publish_primary_group.record_decision(conn, group_id, "approved", now=datetime(2026, 7, 12, 9, 30, 0))

    row = conn.execute("SELECT decision, decision_notes FROM groups WHERE id = ?", (group_id,)).fetchone()
    assert row["decision"] == "approved"
    assert row["decision_notes"] is None
    conn.close()


def _listing_text_row(title="Monstera Line Art Botanical Print", tags=("botanical", "wall art")):
    return {
        "title": title,
        "tags": _json.dumps(list(tags)),
        "description": "A minimalist botanical print.",
        "disclosure_text": "AI disclosure text.",
        "who_made": "i_did",
        "production_partner_ids": _json.dumps([5717252]),
        "taxonomy_id": "1027",
        "shipping_profile_id": "",
    }


def test_build_size_listing_data_appends_size_suffix_for_secondary_sizes():
    data = publish_primary_group.build_size_listing_data(_listing_text_row(), "A3", 35)

    assert data["title"] == "Monstera Line Art Botanical Print - A3 Print"
    assert data["price"] == 35
    assert data["description"] == "A minimalist botanical print."
    assert data["tags"] == ["botanical", "wall art"]
    assert data["who_made"] == "i_did"
    assert data["when_made"] == "made_to_order"
    assert data["is_supply"] is False
    assert data["taxonomy_id"] == "1027"
    assert data["production_partner_ids"] == [5717252]


def test_build_size_listing_data_uses_base_title_unchanged_for_8x12():
    data = publish_primary_group.build_size_listing_data(_listing_text_row(), "8x12", 24)

    assert data["title"] == "Monstera Line Art Botanical Print"
    assert data["price"] == 24


def test_build_size_listing_data_raises_when_suffixed_title_exceeds_140_chars():
    long_title = "x" * 137  # + " - A3 Print" (11 chars) = 148, over the 140 cap
    listing_text = _listing_text_row(title=long_title)

    with pytest.raises(ValueError, match="140"):
        publish_primary_group.build_size_listing_data(listing_text, "A3", 35)


STATIC_CONFIG = {
    "gelato_templates": {
        "8x12_portrait": {
            "template_id": "tpl_8x12", "template_variant_id": "variant_8x12",
            "image_placeholder_name": "slot_8x12.jpg",
        },
        "A3_portrait": {
            "template_id": "tpl_a3", "template_variant_id": "variant_a3",
            "image_placeholder_name": "slot_a3.jpg",
        },
        "A2_portrait": {
            "template_id": "tpl_a2", "template_variant_id": "variant_a2",
            "image_placeholder_name": "slot_a2.jpg",
        },
        "A1_portrait": {
            "template_id": "tpl_a1", "template_variant_id": "variant_a1",
            "image_placeholder_name": "slot_a1.jpg",
        },
    },
    "prices_eur": {"8x12": 24, "A3": 35, "A2": 39, "A1": 49},
    "aspect_ratio_groups": {"primary": ["8x12", "A3", "A2", "A1"], "5x7": ["5x7"], "10x24": ["10x24"]},
}


def test_create_group_product_row_inserts_pending_row(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_primary_group(conn, candidate_id)

    gp_id = publish_primary_group.create_group_product_row(
        conn, group_id, "A3", "portrait", "tpl_a3", 35, now=datetime(2026, 7, 12, 10, 0, 0),
    )

    row = conn.execute("SELECT * FROM group_products WHERE id = ?", (gp_id,)).fetchone()
    assert row["group_id"] == group_id
    assert row["size"] == "A3"
    assert row["orientation"] == "portrait"
    assert row["gelato_template_id"] == "tpl_a3"
    assert row["price_eur"] == 35
    assert row["status"] == "pending"
    assert row["gelato_product_id"] is None
    conn.close()


def test_create_gelato_product_writes_product_id_and_ordered_gallery(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_primary_group(conn, candidate_id)
    gp_id = publish_primary_group.create_group_product_row(
        conn, group_id, "A3", "portrait", "tpl_a3", 35, now=datetime(2026, 7, 12, 10, 0, 0),
    )
    candidate = dict(conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone())

    def fake_create_product_from_template(template_id, template_variant_id, image_placeholder_name,
                                           image_url, title, *, store_id=None, api_key=None, **kwargs):
        assert template_id == "tpl_a3"
        assert template_variant_id == "variant_a3"
        assert image_placeholder_name == "slot_a3.jpg"
        assert image_url == "https://replicate.delivery/out.png"
        return {"id": "gelato_prod_a3", "isReadyToPublish": False, "productImages": []}

    def fake_get_product(product_id, *, store_id=None, api_key=None):
        return {
            "id": product_id, "isReadyToPublish": True,
            "productImages": [
                {"fileUrl": "https://gelato/a3_life.jpg", "isPrimary": False},
                {"fileUrl": "https://gelato/a3_flat.jpg", "isPrimary": True},
            ],
        }

    with patch("pipeline.publish_primary_group.gelato_client.create_product_from_template",
               side_effect=fake_create_product_from_template), \
         patch("pipeline.publish_primary_group.primary_mockup.gelato_client.get_product",
               side_effect=fake_get_product):
        gelato_product_id = publish_primary_group.create_gelato_product(
            conn, gp_id, candidate, STATIC_CONFIG, "A3", "portrait",
            store_id="store1", api_key="key1", now=datetime(2026, 7, 12, 10, 5, 0),
        )

    assert gelato_product_id == "gelato_prod_a3"

    gp_row = conn.execute("SELECT * FROM group_products WHERE id = ?", (gp_id,)).fetchone()
    assert gp_row["gelato_product_id"] == "gelato_prod_a3"

    images = conn.execute(
        "SELECT * FROM product_images WHERE group_product_id = ? ORDER BY gallery_order", (gp_id,)
    ).fetchall()
    assert len(images) == 2
    assert images[0]["image_type"] == "flat_mockup"
    assert images[0]["image_url"] == "https://gelato/a3_flat.jpg"
    assert images[1]["image_type"] == "lifestyle"
    conn.close()


def test_create_gelato_product_dry_run_skips_polling(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_primary_group(conn, candidate_id)
    gp_id = publish_primary_group.create_group_product_row(
        conn, group_id, "A3", "portrait", "tpl_a3", 35, now=datetime(2026, 7, 12, 10, 0, 0),
    )
    candidate = dict(conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone())

    def fake_create_product_from_template(*args, **kwargs):
        return {"id": "DRY_RUN_PRODUCT_ID", "previewUrl": None, "productImages": [], "_dry_run": True}

    with patch("pipeline.publish_primary_group.gelato_client.create_product_from_template",
               side_effect=fake_create_product_from_template), \
         patch("pipeline.publish_primary_group.primary_mockup.gelato_client.get_product") as mock_get_product:
        publish_primary_group.create_gelato_product(
            conn, gp_id, candidate, STATIC_CONFIG, "A3", "portrait",
            store_id="store1", api_key="key1", now=datetime(2026, 7, 12, 10, 5, 0),
        )

    mock_get_product.assert_not_called()
    images = conn.execute("SELECT * FROM product_images WHERE group_product_id = ?", (gp_id,)).fetchall()
    assert len(images) == 1
    assert images[0]["image_type"] == "flat_mockup"
    conn.close()
