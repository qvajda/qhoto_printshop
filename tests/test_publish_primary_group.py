import json as _json
from datetime import datetime
from unittest.mock import patch

import pytest

import pipeline.db as db
import pipeline.primary_mockup as primary_mockup
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


def test_build_size_listing_data_appends_size_suffix_for_5x7_and_10x24():
    listing_text = {
        "title": "monstera line art print", "tags": _json.dumps(["botanical", "wall art"]),
        "description": "desc", "who_made": "i_did", "taxonomy_id": "1027",
        "shipping_profile_id": "", "production_partner_ids": _json.dumps([5717252]),
    }

    data_5x7 = publish_primary_group.build_size_listing_data(listing_text, "5x7", 19)
    data_10x24 = publish_primary_group.build_size_listing_data(listing_text, "10x24", 45)

    assert data_5x7["title"] == "monstera line art print - 5x7 Print"
    assert data_5x7["price"] == 19
    assert data_10x24["title"] == "monstera line art print - 10x24 Panoramic Print"
    assert data_10x24["price"] == 45


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
    assert gp_row["status"] == "created"

    images = conn.execute(
        "SELECT * FROM product_images WHERE group_product_id = ? ORDER BY gallery_order", (gp_id,)
    ).fetchall()
    assert len(images) == 2
    assert images[0]["image_type"] == "flat_mockup"
    assert images[0]["image_url"] == "https://gelato/a3_flat.jpg"
    assert images[1]["image_type"] == "lifestyle"
    conn.close()


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


def _insert_group_product_with_images(conn, group_id, size="A3", *, gelato_product_id="gelato_a3",
                                       image_urls=("https://gelato/a3_flat.jpg", "https://gelato/a3_life.jpg")):
    timestamp = "2026-07-12T10:00:00"
    cursor = conn.execute(
        "INSERT INTO group_products "
        "(group_id, size, orientation, gelato_template_id, gelato_product_id, price_eur, "
        "status, created_at, updated_at) "
        "VALUES (?, ?, 'portrait', 'tpl_x', ?, 35, 'created', ?, ?)",
        (group_id, size, gelato_product_id, timestamp, timestamp),
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


def test_publish_to_etsy_dry_run_skips_image_download_and_writes_published(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_primary_group(conn, candidate_id)
    _insert_listing_text(conn, candidate_id)
    gp_id = _insert_group_product_with_images(conn, group_id)

    with patch("pipeline.publish_primary_group.etsy_client.create_draft_listing",
               return_value={"listing_id": "DRY_RUN_LISTING_ID", "_dry_run": True}) as mock_draft, \
         patch("pipeline.publish_primary_group.etsy_client.upload_listing_image",
               return_value={"_dry_run": True}) as mock_upload, \
         patch("pipeline.publish_primary_group.etsy_client.update_listing_state",
               return_value={"_dry_run": True}) as mock_state, \
         patch("pipeline.publish_primary_group.http.fetch_bytes") as mock_fetch:
        listing_id = publish_primary_group.publish_to_etsy(
            conn, gp_id, candidate_id, "A3", 35, shop_id="shop1",
            dry_run=True, now=datetime(2026, 7, 12, 10, 10, 0),
        )

    mock_fetch.assert_not_called()
    assert mock_upload.call_count == 2
    for call in mock_upload.call_args_list:
        assert call.args[2] == b""
    assert listing_id == "DRY_RUN_LISTING_ID"

    gp_row = conn.execute("SELECT * FROM group_products WHERE id = ?", (gp_id,)).fetchone()
    assert gp_row["etsy_listing_id"] == "DRY_RUN_LISTING_ID"
    assert gp_row["status"] == "published"
    conn.close()


def test_publish_to_etsy_live_downloads_images_and_activates_listing(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_primary_group(conn, candidate_id)
    _insert_listing_text(conn, candidate_id)
    gp_id = _insert_group_product_with_images(conn, group_id)

    calls = []

    def fake_create_draft_listing(shop_id, listing_data, **kwargs):
        calls.append(("draft", shop_id, listing_data["title"]))
        return {"listing_id": 555}

    def fake_upload(shop_id, listing_id, image_bytes, **kwargs):
        calls.append(("upload", shop_id, listing_id, image_bytes))
        return {"listing_image_id": 1}

    def fake_update_state(shop_id, listing_id, state, **kwargs):
        calls.append(("activate", shop_id, listing_id, state))
        return {"state": "active"}

    with patch("pipeline.publish_primary_group.etsy_client.create_draft_listing",
               side_effect=fake_create_draft_listing), \
         patch("pipeline.publish_primary_group.etsy_client.upload_listing_image",
               side_effect=fake_upload), \
         patch("pipeline.publish_primary_group.etsy_client.update_listing_state",
               side_effect=fake_update_state), \
         patch("pipeline.publish_primary_group.http.fetch_bytes",
               return_value=b"real-image-bytes") as mock_fetch:
        listing_id = publish_primary_group.publish_to_etsy(
            conn, gp_id, candidate_id, "A3", 35, shop_id="shop1",
            dry_run=False, now=datetime(2026, 7, 12, 10, 10, 0),
        )

    assert listing_id == "555"
    assert calls[0] == ("draft", "shop1", "monstera line art print - A3 Print")
    assert calls[1] == ("upload", "shop1", 555, b"real-image-bytes")
    assert calls[2] == ("upload", "shop1", 555, b"real-image-bytes")
    assert calls[3] == ("activate", "shop1", 555, "active")
    assert mock_fetch.call_count == 2

    gp_row = conn.execute("SELECT * FROM group_products WHERE id = ?", (gp_id,)).fetchone()
    assert gp_row["etsy_listing_id"] == "555"
    assert gp_row["status"] == "published"
    conn.close()


def test_publish_to_etsy_reuses_existing_listing_on_retry_instead_of_creating_duplicate(tmp_path):
    # Simulates a retry after create_draft_listing succeeded but update_listing_state failed
    # on the first attempt: etsy_listing_id is already set on the row.
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_primary_group(conn, candidate_id)
    _insert_listing_text(conn, candidate_id)
    gp_id = _insert_group_product_with_images(conn, group_id)
    conn.execute("UPDATE group_products SET etsy_listing_id = '555' WHERE id = ?", (gp_id,))
    conn.commit()

    calls = []

    def fake_upload(shop_id, listing_id, image_bytes, **kwargs):
        calls.append(("upload", listing_id))
        return {"listing_image_id": 1}

    def fake_update_state(shop_id, listing_id, state, **kwargs):
        calls.append(("activate", listing_id, state))
        return {"state": "active"}

    with patch("pipeline.publish_primary_group.etsy_client.create_draft_listing") as mock_draft, \
         patch("pipeline.publish_primary_group.etsy_client.upload_listing_image",
               side_effect=fake_upload), \
         patch("pipeline.publish_primary_group.etsy_client.update_listing_state",
               side_effect=fake_update_state), \
         patch("pipeline.publish_primary_group.http.fetch_bytes", return_value=b"bytes"):
        listing_id = publish_primary_group.publish_to_etsy(
            conn, gp_id, candidate_id, "A3", 35, shop_id="shop1",
            dry_run=False, now=datetime(2026, 7, 12, 10, 10, 0),
        )

    mock_draft.assert_not_called()
    assert listing_id == "555"
    assert calls[0] == ("upload", "555")
    assert calls[-1] == ("activate", "555", "active")

    gp_row = conn.execute("SELECT * FROM group_products WHERE id = ?", (gp_id,)).fetchone()
    assert gp_row["etsy_listing_id"] == "555"
    assert gp_row["status"] == "published"
    conn.close()


def test_publish_to_etsy_raises_when_no_listing_text(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_primary_group(conn, candidate_id)
    gp_id = _insert_group_product_with_images(conn, group_id)

    with pytest.raises(ValueError, match="listing_texts"):
        publish_primary_group.publish_to_etsy(
            conn, gp_id, candidate_id, "A3", 35, shop_id="shop1", dry_run=True,
        )
    conn.close()


def test_create_gelato_product_marks_mockup_failed_on_poll_timeout(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_primary_group(conn, candidate_id)
    gp_id = publish_primary_group.create_group_product_row(
        conn, group_id, "A3", "portrait", "tpl_a3", 35, now=datetime(2026, 7, 12, 10, 0, 0),
    )
    candidate = dict(conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone())

    def fake_create_product_from_template(*args, **kwargs):
        return {"id": "gelato_prod_a3_stuck", "isReadyToPublish": False, "productImages": []}

    def fake_poll_until_ready(*args, **kwargs):
        raise primary_mockup.GelatoMockupTimeoutError("gelato_prod_a3_stuck did not become ready")

    with patch("pipeline.publish_primary_group.gelato_client.create_product_from_template",
               side_effect=fake_create_product_from_template), \
         patch("pipeline.publish_primary_group.primary_mockup.poll_until_ready",
               side_effect=fake_poll_until_ready):
        with pytest.raises(primary_mockup.GelatoMockupTimeoutError):
            publish_primary_group.create_gelato_product(
                conn, gp_id, candidate, STATIC_CONFIG, "A3", "portrait",
                store_id="store1", api_key="key1", now=datetime(2026, 7, 12, 10, 5, 0),
            )

    gp_row = conn.execute("SELECT * FROM group_products WHERE id = ?", (gp_id,)).fetchone()
    assert gp_row["status"] == "mockup_failed"
    assert gp_row["gelato_product_id"] == "gelato_prod_a3_stuck"
    assert conn.execute(
        "SELECT * FROM product_images WHERE group_product_id = ?", (gp_id,)
    ).fetchall() == []
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
    gp_row = conn.execute("SELECT status FROM group_products WHERE id = ?", (gp_id,)).fetchone()
    assert gp_row["status"] == "created"
    conn.close()


def _insert_ready_primary_group(conn, candidate_id, niche="monstera line art"):
    group_id = _insert_primary_group(conn, candidate_id, status="pending_review")
    _insert_group_product_with_images(
        conn, group_id, size="8x12", gelato_product_id="gelato_prod_1",
        image_urls=("https://gelato/flat.jpg", "https://gelato/life.jpg"),
    )
    _insert_listing_text(conn, candidate_id, niche=niche)
    return group_id


def test_publish_group_product_succeeds_first_try(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_ready_primary_group(conn, candidate_id)
    gp_id = conn.execute(
        "SELECT id FROM group_products WHERE group_id = ? AND size = '8x12'", (group_id,)
    ).fetchone()["id"]
    candidate = dict(conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone())

    with patch("pipeline.publish_primary_group.publish_to_etsy",
               return_value="listing_1") as mock_publish:
        result = publish_primary_group.publish_group_product(
            conn, gp_id, candidate, STATIC_CONFIG, dry_run=True, now=datetime(2026, 7, 12, 11, 0, 0),
        )

    assert result == "listing_1"
    mock_publish.assert_called_once()
    conn.close()


def test_publish_group_product_creates_gelato_product_when_missing(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_primary_group(conn, candidate_id)
    _insert_listing_text(conn, candidate_id)
    gp_id = publish_primary_group.create_group_product_row(
        conn, group_id, "A3", "portrait", "tpl_a3", 35, now=datetime(2026, 7, 12, 10, 0, 0),
    )
    candidate = dict(conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone())

    with patch("pipeline.publish_primary_group.create_gelato_product",
               return_value="gelato_prod_new") as mock_create, \
         patch("pipeline.publish_primary_group.publish_to_etsy",
               return_value="listing_2") as mock_publish:
        result = publish_primary_group.publish_group_product(
            conn, gp_id, candidate, STATIC_CONFIG, dry_run=True, now=datetime(2026, 7, 12, 11, 0, 0),
        )

    assert result == "listing_2"
    mock_create.assert_called_once()
    mock_publish.assert_called_once()
    conn.close()


def test_publish_group_product_retries_once_then_succeeds(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_ready_primary_group(conn, candidate_id)
    gp_id = conn.execute(
        "SELECT id FROM group_products WHERE group_id = ? AND size = '8x12'", (group_id,)
    ).fetchone()["id"]
    candidate = dict(conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone())

    attempts = {"n": 0}

    def flaky_publish(*args, **kwargs):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise RuntimeError("Etsy throttled")
        return "listing_after_retry"

    with patch("pipeline.publish_primary_group.publish_to_etsy", side_effect=flaky_publish):
        result = publish_primary_group.publish_group_product(
            conn, gp_id, candidate, STATIC_CONFIG, dry_run=True, now=datetime(2026, 7, 12, 11, 0, 0),
        )

    assert result == "listing_after_retry"
    assert attempts["n"] == 2
    conn.close()


def test_publish_group_product_marks_publish_failed_after_second_failure(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_ready_primary_group(conn, candidate_id)
    gp_id = conn.execute(
        "SELECT id FROM group_products WHERE group_id = ? AND size = '8x12'", (group_id,)
    ).fetchone()["id"]
    candidate = dict(conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone())

    with patch("pipeline.publish_primary_group.publish_to_etsy",
               side_effect=RuntimeError("Etsy down")):
        with pytest.raises(RuntimeError, match="Etsy down"):
            publish_primary_group.publish_group_product(
                conn, gp_id, candidate, STATIC_CONFIG, dry_run=True, now=datetime(2026, 7, 12, 11, 0, 0),
            )

    gp_row = conn.execute("SELECT status FROM group_products WHERE id = ?", (gp_id,)).fetchone()
    assert gp_row["status"] == "publish_failed"
    conn.close()


def test_publish_primary_group_publishes_all_four_sizes(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_ready_primary_group(conn, candidate_id)

    published_sizes = []

    def fake_publish_group_product(conn, group_product_id, candidate, static_config, **kwargs):
        row = conn.execute("SELECT size FROM group_products WHERE id = ?", (group_product_id,)).fetchone()
        published_sizes.append(row["size"])
        return f"listing_{row['size']}"

    with patch("pipeline.publish_primary_group.publish_group_product",
               side_effect=fake_publish_group_product):
        result = publish_primary_group.publish_primary_group(
            conn, candidate_id, static_config=STATIC_CONFIG, dry_run=True,
            now=datetime(2026, 7, 12, 11, 0, 0),
        )

    assert result == {"8x12": "published", "A3": "published", "A2": "published", "A1": "published"}
    assert sorted(published_sizes) == ["8x12", "A1", "A2", "A3"]

    group_row = conn.execute("SELECT status FROM groups WHERE id = ?", (group_id,)).fetchone()
    assert group_row["status"] == "approved_published"
    candidate_row = conn.execute("SELECT status FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    assert candidate_row["status"] == "completed"

    sizes_in_db = {
        row["size"] for row in conn.execute(
            "SELECT size FROM group_products WHERE group_id = ?", (group_id,)
        ).fetchall()
    }
    assert sizes_in_db == {"8x12", "A3", "A2", "A1"}
    conn.close()


def test_publish_primary_group_isolates_per_size_failures(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_ready_primary_group(conn, candidate_id)

    def fake_publish_group_product(conn, group_product_id, candidate, static_config, **kwargs):
        row = conn.execute("SELECT size FROM group_products WHERE id = ?", (group_product_id,)).fetchone()
        if row["size"] == "A2":
            raise RuntimeError("A2 template placeholder")
        return f"listing_{row['size']}"

    with patch("pipeline.publish_primary_group.publish_group_product",
               side_effect=fake_publish_group_product):
        result = publish_primary_group.publish_primary_group(
            conn, candidate_id, static_config=STATIC_CONFIG, dry_run=True,
            now=datetime(2026, 7, 12, 11, 0, 0),
        )

    assert result == {"8x12": "published", "A3": "published", "A2": "publish_failed", "A1": "published"}
    group_row = conn.execute("SELECT status FROM groups WHERE id = ?", (group_id,)).fetchone()
    assert group_row["status"] == "approved_published"
    conn.close()


def test_publish_primary_group_is_idempotent_on_reentry_after_partial_crash(tmp_path):
    # Simulates the process crashing/being re-invoked after 8x12 and A3 already published but
    # before A2/A1 ran — a re-run must not re-publish the already-published sizes or spawn
    # duplicate group_products rows for them.
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_ready_primary_group(conn, candidate_id)
    conn.execute(
        "UPDATE group_products SET status = 'published', etsy_listing_id = 'listing_8x12' "
        "WHERE group_id = ? AND size = '8x12'", (group_id,),
    )
    _insert_group_product_with_images(conn, group_id, size="A3", gelato_product_id="gelato_a3")
    conn.execute(
        "UPDATE group_products SET status = 'published', etsy_listing_id = 'listing_a3' "
        "WHERE group_id = ? AND size = 'A3'", (group_id,),
    )
    conn.commit()

    called_for = []

    def fake_publish_group_product(conn, group_product_id, candidate, static_config, **kwargs):
        row = conn.execute("SELECT size FROM group_products WHERE id = ?", (group_product_id,)).fetchone()
        called_for.append(row["size"])
        return f"listing_{row['size']}"

    with patch("pipeline.publish_primary_group.publish_group_product",
               side_effect=fake_publish_group_product):
        result = publish_primary_group.publish_primary_group(
            conn, candidate_id, static_config=STATIC_CONFIG, dry_run=True,
            now=datetime(2026, 7, 12, 11, 0, 0),
        )

    assert sorted(called_for) == ["A1", "A2"]
    assert result == {"8x12": "published", "A3": "published", "A2": "published", "A1": "published"}

    sizes_in_db = [
        row["size"] for row in conn.execute(
            "SELECT size FROM group_products WHERE group_id = ?", (group_id,)
        ).fetchall()
    ]
    assert sorted(sizes_in_db) == ["8x12", "A1", "A2", "A3"]
    conn.close()


def test_publish_primary_group_raises_when_no_live_8x12_product(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_primary_group(conn, candidate_id)
    _insert_listing_text(conn, candidate_id)

    with pytest.raises(ValueError, match="8x12"):
        publish_primary_group.publish_primary_group(
            conn, candidate_id, static_config=STATIC_CONFIG, dry_run=True,
        )
    conn.close()


def test_handle_decision_approve_records_decision_and_publishes(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_ready_primary_group(conn, candidate_id)

    with patch("pipeline.publish_primary_group.publish_primary_group",
               return_value={"8x12": "published", "A3": "published", "A2": "published", "A1": "published"}
               ) as mock_publish:
        result = publish_primary_group.handle_decision(
            conn, candidate_id, group_id, "approve", static_config=STATIC_CONFIG, dry_run=True,
            now=datetime(2026, 7, 12, 12, 0, 0),
        )

    mock_publish.assert_called_once()
    assert result["action"] == "approve"
    group_row = conn.execute("SELECT decision, decided_at FROM groups WHERE id = ?", (group_id,)).fetchone()
    assert group_row["decision"] == "approved"
    assert group_row["decided_at"] == "2026-07-12T12:00:00"
    conn.close()


def test_handle_decision_reject_marks_group_and_candidate(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_ready_primary_group(conn, candidate_id)

    result = publish_primary_group.handle_decision(
        conn, candidate_id, group_id, "reject", static_config=STATIC_CONFIG,
        now=datetime(2026, 7, 12, 12, 0, 0),
    )

    assert result["action"] == "reject"
    group_row = conn.execute("SELECT decision, status FROM groups WHERE id = ?", (group_id,)).fetchone()
    assert group_row["decision"] == "rejected"
    assert group_row["status"] == "rejected"
    candidate_row = conn.execute(
        "SELECT status, failed_reason FROM candidates WHERE id = ?", (candidate_id,)
    ).fetchone()
    assert candidate_row["status"] == "failed"
    assert candidate_row["failed_reason"] == "primary group rejected"
    conn.close()


def test_handle_decision_edit_discards_old_product_and_regenerates(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_ready_primary_group(conn, candidate_id)
    old_gp_id = conn.execute(
        "SELECT id FROM group_products WHERE group_id = ? AND size = '8x12'", (group_id,)
    ).fetchone()["id"]
    publish_primary_group.critic_pass.record_critic_attempt(
        conn, group_id, 1, {"passed": True, "reason": "meets rubric"}, now=datetime(2026, 7, 12, 9, 20, 0),
    )

    def fake_generate_for_candidate(conn, candidate_id, *, correction_note=None, api_token=None, now=None):
        timestamp = now.isoformat() if now else "2026-07-12T12:05:00"
        conn.execute(
            "UPDATE candidates SET base_image_url = 'https://replicate.delivery/v2.png', "
            "status = 'generating', updated_at = ? WHERE id = ?",
            (timestamp, candidate_id),
        )
        conn.commit()

    def fake_create_primary_mockup(conn, candidate_id, *, static_config=None, store_id=None,
                                    api_key=None, now=None, **kwargs):
        timestamp = now.isoformat() if now else "2026-07-12T12:06:00"
        cursor = conn.execute(
            "INSERT INTO group_products "
            "(group_id, size, orientation, gelato_template_id, gelato_product_id, price_eur, "
            "status, created_at, updated_at) "
            "VALUES (?, '8x12', 'portrait', 'tpl_1', 'gelato_prod_v2', 24, 'created', ?, ?)",
            (group_id, timestamp, timestamp),
        )
        conn.execute(
            "UPDATE groups SET status = 'pending_review', updated_at = ? WHERE id = ?",
            (timestamp, group_id),
        )
        conn.commit()
        return {"group_id": group_id, "group_product_id": cursor.lastrowid}

    def fake_build_compliance_draft(conn, candidate_id, *, static_config=None,
                                     anthropic_api_key=None, now=None):
        _insert_listing_text(conn, candidate_id, niche="monstera line art v2")

    with patch("pipeline.publish_primary_group.critic_pass.gelato_client.delete_product") as mock_delete, \
         patch("pipeline.publish_primary_group.generate.generate_for_candidate",
               side_effect=fake_generate_for_candidate), \
         patch("pipeline.publish_primary_group.primary_mockup.create_primary_mockup",
               side_effect=fake_create_primary_mockup), \
         patch("pipeline.publish_primary_group.compliance_draft.build_compliance_draft",
               side_effect=fake_build_compliance_draft):
        result = publish_primary_group.handle_decision(
            conn, candidate_id, group_id, "edit", "make it more pastel", static_config=STATIC_CONFIG,
            now=datetime(2026, 7, 12, 12, 0, 0),
        )

    assert result["action"] == "edit"
    mock_delete.assert_called_once_with("gelato_prod_1", store_id=None, api_key=None)

    # Not asserting "row fetched by old_gp_id is None" here: group_products.id is a plain
    # `INTEGER PRIMARY KEY` (no AUTOINCREMENT), and in this test the discarded row is the
    # table's only row, so SQLite recycles the freed numeric id for the next insert (see
    # db/schema.sql:62). That's normal SQLite ROWID behavior, not a discard bug — checking
    # by the superseded gelato_product_id is the assertion that actually reflects intent.
    assert conn.execute(
        "SELECT * FROM group_products WHERE gelato_product_id = 'gelato_prod_1'"
    ).fetchone() is None
    assert conn.execute(
        "SELECT * FROM critic_pass_attempts WHERE group_id = ?", (group_id,)
    ).fetchall() == []

    candidate_row = conn.execute(
        "SELECT status, base_image_url FROM candidates WHERE id = ?", (candidate_id,)
    ).fetchone()
    assert candidate_row["status"] == "generating"
    assert candidate_row["base_image_url"] == "https://replicate.delivery/v2.png"

    listing_row = conn.execute(
        "SELECT title FROM listing_texts WHERE candidate_id = ?", (candidate_id,)
    ).fetchone()
    assert listing_row["title"] == "monstera line art v2 print"

    group_row = conn.execute("SELECT decision, decision_notes FROM groups WHERE id = ?", (group_id,)).fetchone()
    assert group_row["decision"] == "edited"
    assert group_row["decision_notes"] == "make it more pastel"
    conn.close()


def test_handle_decision_edit_clears_group_messages_so_digest_can_resend(tmp_path):
    # get_or_create_primary_group reuses the same group_id across an edit cycle, and
    # digest.py's query excludes any group already present in group_messages — so if this
    # row survives an edit, the regenerated design can never be re-sent for review.
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_ready_primary_group(conn, candidate_id)
    _insert_group_message(conn, group_id, "987654321", 202)

    with patch("pipeline.publish_primary_group.critic_pass.gelato_client.delete_product"), \
         patch("pipeline.publish_primary_group.generate.generate_for_candidate"), \
         patch("pipeline.publish_primary_group.primary_mockup.create_primary_mockup"), \
         patch("pipeline.publish_primary_group.compliance_draft.build_compliance_draft"):
        publish_primary_group.handle_decision(
            conn, candidate_id, group_id, "edit", now=datetime(2026, 7, 12, 12, 0, 0),
        )

    assert conn.execute(
        "SELECT * FROM group_messages WHERE group_id = ?", (group_id,)
    ).fetchall() == []
    conn.close()


def test_handle_decision_raises_on_unknown_action(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_ready_primary_group(conn, candidate_id)

    with pytest.raises(ValueError, match="Unknown action"):
        publish_primary_group.handle_decision(conn, candidate_id, group_id, "snooze")
    conn.close()


def _insert_group_message(conn, group_id, chat_id, telegram_message_id, sent_at="2026-07-12T09:15:00"):
    conn.execute(
        "INSERT INTO group_messages (group_id, telegram_message_id, chat_id, sent_at) VALUES (?, ?, ?, ?)",
        (group_id, telegram_message_id, chat_id, sent_at),
    )
    conn.commit()


def test_get_and_set_telegram_offset_round_trip(tmp_path):
    conn = _fresh_conn(tmp_path)

    assert publish_primary_group.get_telegram_offset(conn) is None

    publish_primary_group.set_telegram_offset(conn, 100)
    assert publish_primary_group.get_telegram_offset(conn) == 100

    publish_primary_group.set_telegram_offset(conn, 105)
    assert publish_primary_group.get_telegram_offset(conn) == 105
    conn.close()


def test_process_update_discards_non_admin_sender(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_ready_primary_group(conn, candidate_id)
    _insert_group_message(conn, group_id, "987654321", 202)
    update = _callback_update(user_id=111111111, data=f"approve:{group_id}", message_id=202, chat_id=987654321)

    with patch("pipeline.publish_primary_group.handle_decision") as mock_handle, \
         patch("pipeline.publish_primary_group.telegram_client.answer_callback_query") as mock_answer:
        result = publish_primary_group.process_update(
            conn, update, admin_chat_id="987654321", now=datetime(2026, 7, 12, 13, 0, 0),
        )

    assert result is None
    mock_handle.assert_not_called()
    mock_answer.assert_not_called()
    log_row = conn.execute("SELECT * FROM telegram_events_log").fetchone()
    assert log_row["accepted"] == 0
    assert log_row["telegram_user_id"] == "111111111"
    conn.close()


def test_process_update_discards_callback_not_matching_group_messages(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_ready_primary_group(conn, candidate_id)
    _insert_group_message(conn, group_id, "987654321", 202)
    # message_id 999 does not match the group_messages row (202)
    update = _callback_update(user_id=987654321, data=f"approve:{group_id}", message_id=999, chat_id=987654321)

    with patch("pipeline.publish_primary_group.handle_decision") as mock_handle:
        result = publish_primary_group.process_update(
            conn, update, admin_chat_id="987654321", now=datetime(2026, 7, 12, 13, 0, 0),
        )

    assert result is None
    mock_handle.assert_not_called()
    conn.close()


def test_process_update_accepts_admin_callback_and_calls_handle_decision(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_ready_primary_group(conn, candidate_id)
    _insert_group_message(conn, group_id, "987654321", 202)
    update = _callback_update(
        user_id=987654321, data=f"approve:{group_id}", message_id=202, chat_id=987654321, callback_id="cbq1",
    )

    with patch("pipeline.publish_primary_group.handle_decision",
               return_value={"action": "approve", "results": {"8x12": "published"}}) as mock_handle, \
         patch("pipeline.publish_primary_group.telegram_client.answer_callback_query") as mock_answer:
        result = publish_primary_group.process_update(
            conn, update, admin_chat_id="987654321", bot_token="tok1", now=datetime(2026, 7, 12, 13, 0, 0),
        )

    assert result == {"candidate_id": candidate_id, "group_id": group_id,
                       "action": "approve", "results": {"8x12": "published"}}
    mock_handle.assert_called_once()
    assert mock_handle.call_args.args[:3] == (conn, candidate_id, group_id)
    assert mock_handle.call_args.args[3] == "approve"
    mock_answer.assert_called_once_with("cbq1", bot_token="tok1")

    log_row = conn.execute("SELECT * FROM telegram_events_log").fetchone()
    assert log_row["accepted"] == 1
    assert log_row["action_taken"] == "approve"
    conn.close()


def test_process_update_returns_none_for_non_callback_update(tmp_path):
    conn = _fresh_conn(tmp_path)
    update = {"update_id": 1, "message": {"text": "/research botanical"}}

    result = publish_primary_group.process_update(conn, update, admin_chat_id="987654321")

    assert result is None
    assert conn.execute("SELECT * FROM telegram_events_log").fetchall() == []
    conn.close()


def test_run_publish_primary_group_cycle_processes_and_advances_offset(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_ready_primary_group(conn, candidate_id)
    _insert_group_message(conn, group_id, "987654321", 202)
    updates = [_callback_update(update_id=500, user_id=987654321, data=f"approve:{group_id}",
                                 message_id=202, chat_id=987654321, callback_id="cbq1")]

    with patch("pipeline.publish_primary_group.telegram_client.get_updates",
               return_value=updates) as mock_get_updates, \
         patch("pipeline.publish_primary_group.telegram_client.answer_callback_query"), \
         patch("pipeline.publish_primary_group.handle_decision",
               return_value={"action": "approve", "results": {"8x12": "published"}}):
        processed = publish_primary_group.run_publish_primary_group_cycle(
            conn, admin_chat_id="987654321", bot_token="tok1", now=datetime(2026, 7, 12, 13, 0, 0),
        )

    assert len(processed) == 1
    assert mock_get_updates.call_args.kwargs["offset"] is None
    assert publish_primary_group.get_telegram_offset(conn) == 500
    conn.close()


def test_run_publish_primary_group_cycle_uses_persisted_offset_on_next_call(tmp_path):
    conn = _fresh_conn(tmp_path)
    publish_primary_group.set_telegram_offset(conn, 500)

    with patch("pipeline.publish_primary_group.telegram_client.get_updates", return_value=[]) as mock_get_updates:
        publish_primary_group.run_publish_primary_group_cycle(conn, admin_chat_id="987654321", bot_token="tok1")

    assert mock_get_updates.call_args.kwargs["offset"] == 501
    conn.close()


def test_run_publish_primary_group_cycle_isolates_per_update_failures(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_ready_primary_group(conn, candidate_id)
    _insert_group_message(conn, group_id, "987654321", 202)
    updates = [
        _callback_update(update_id=600, user_id=987654321, data=f"approve:{group_id}",
                          message_id=202, chat_id=987654321, callback_id="cbq_bad"),
        {"update_id": 601, "message": {"text": "not a callback"}},
    ]

    with patch("pipeline.publish_primary_group.telegram_client.get_updates", return_value=updates), \
         patch("pipeline.publish_primary_group.telegram_client.answer_callback_query"), \
         patch("pipeline.publish_primary_group.handle_decision", side_effect=RuntimeError("boom")):
        processed = publish_primary_group.run_publish_primary_group_cycle(
            conn, admin_chat_id="987654321", bot_token="tok1", now=datetime(2026, 7, 12, 13, 0, 0),
        )

    assert processed == []
    assert publish_primary_group.get_telegram_offset(conn) == 601

    # A real admin tap that blew up mid-processing must leave a durable trace, not just a
    # print() an unattended hourly cron has no one watching.
    error_log_row = conn.execute(
        "SELECT * FROM telegram_events_log WHERE action_taken LIKE 'error:%'"
    ).fetchone()
    assert error_log_row is not None
    assert error_log_row["accepted"] == 1
    assert error_log_row["telegram_user_id"] == "987654321"
    assert "boom" in error_log_row["action_taken"]
    conn.close()
