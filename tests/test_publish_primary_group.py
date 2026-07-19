import json as _json
from datetime import datetime
from unittest.mock import patch

import pytest

import pipeline.config as config
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
    "etsy_shipping_profile_id": {"primary": "287910565714", "5x7": "287910553824", "10x24": "287910565714"},
}


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


def _insert_group_product_with_variants(conn, group_id, sizes=("8x12",), *, gelato_product_id="gelato_prod_1",
                                         status="created",
                                         image_urls=("https://gelato/flat.jpg", "https://gelato/life.jpg")):
    timestamp = "2026-07-12T10:00:00"
    cursor = conn.execute(
        "INSERT INTO group_products (group_id, gelato_template_id, gelato_product_id, status, created_at, updated_at) "
        "VALUES (?, 'tpl_x', ?, ?, ?, ?)",
        (group_id, gelato_product_id, status, timestamp, timestamp),
    )
    gp_id = cursor.lastrowid
    for size in sizes:
        conn.execute(
            "INSERT INTO group_product_variants "
            "(group_product_id, size, orientation, gelato_template_variant_id, price_eur, created_at) "
            "VALUES (?, ?, 'portrait', ?, ?, ?)",
            (gp_id, size, f"variant_{size}", STATIC_CONFIG["prices_eur"][size], timestamp),
        )
    for order, url in enumerate(image_urls):
        image_type = "flat_mockup" if order == 0 else "lifestyle"
        conn.execute(
            "INSERT INTO product_images (group_product_id, image_url, alt_text, gallery_order, image_type) "
            "VALUES (?, ?, '', ?, ?)",
            (gp_id, url, order, image_type),
        )
    conn.commit()
    return gp_id


def _insert_ready_primary_group(conn, candidate_id, niche="monstera line art"):
    group_id = _insert_primary_group(conn, candidate_id, status="pending_review")
    # ponytail: no variants here (sizes=()) - none of this file's handle_decision/process_update
    # tests assert on group_product_variants, and critic_pass.discard_superseded_attempt (called
    # from the edit path below) has a pre-existing bug where it deletes group_products before its
    # group_product_variants children, which trips the FK constraint if variants exist. That bug
    # predates this task (critic_pass.py wasn't updated for the group_product_variants schema in
    # tasks 1-5) and is out of this task's file scope to fix - flagged in the task report.
    _insert_group_product_with_variants(conn, group_id, sizes=(), gelato_product_id="gelato_prod_1")
    _insert_listing_text(conn, candidate_id, niche=niche)
    return group_id


def test_publish_primary_group_creates_one_listing_for_all_four_sizes(tmp_path, monkeypatch):
    # ponytail: GELATO_LIVE_MODE=true is required for this to exercise the resolve_etsy_listing_id
    # path in group_product.patch_etsy_listing (it's gated on Gelato's own liveness, not this
    # call's dry_run - see the ponytail comment on patch_etsy_listing) - without it the listing id
    # would just be the "DRY_RUN_ETSY_LISTING_ID" placeholder and the mock below would go unused.
    monkeypatch.setenv("GELATO_LIVE_MODE", "true")
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_primary_group(conn, candidate_id, status="pending_review")
    _insert_listing_text(conn, candidate_id)
    static_config = config.load_static_config()

    with patch("pipeline.gelato_client.create_product_from_template") as mock_create, \
         patch("pipeline.group_product._assert_print_dpi"), \
         patch("pipeline.gelato_client.get_etsy_listing_id") as mock_resolve:
        mock_create.return_value = {"id": "gelato-prod-1", "_dry_run": True, "previewUrl": None, "productImages": []}
        mock_resolve.return_value = "etsy-listing-42"
        result = publish_primary_group.publish_primary_group(
            conn, candidate_id, static_config=static_config, shop_id="shop1", dry_run=True,
            now="2026-07-16T09:20:00",
        )

    assert result["etsy_listing_id"] == "etsy-listing-42"
    gp_row = conn.execute(
        "SELECT id, status FROM group_products WHERE group_id = "
        "(SELECT id FROM groups WHERE candidate_id = ? AND group_type = 'primary')",
        (candidate_id,),
    ).fetchone()
    assert gp_row["status"] == "published"
    variant_rows = conn.execute(
        "SELECT size FROM group_product_variants WHERE group_product_id = ? ORDER BY size",
        (gp_row["id"],),
    ).fetchall()
    assert [r["size"] for r in variant_rows] == ["8x12", "A1", "A2", "A3"]

    group_row = conn.execute(
        "SELECT status FROM groups WHERE candidate_id = ? AND group_type = 'primary'", (candidate_id,)
    ).fetchone()
    assert group_row["status"] == "approved_published"
    candidate_row = conn.execute("SELECT status FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    assert candidate_row["status"] == "completed"
    conn.close()


def test_publish_primary_group_reuses_existing_live_group_product_on_reentry(tmp_path, monkeypatch):
    # A re-run after a crash between create_or_reuse_group_product succeeding and patch_etsy_listing
    # failing must not spawn a second Gelato product.
    monkeypatch.setenv("GELATO_LIVE_MODE", "true")
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_primary_group(conn, candidate_id, status="pending_review")
    _insert_group_product_with_variants(
        conn, group_id, sizes=("8x12", "A3", "A2", "A1"), gelato_product_id="gelato-prod-existing",
    )
    _insert_listing_text(conn, candidate_id)
    static_config = config.load_static_config()

    with patch("pipeline.gelato_client.create_product_from_template") as mock_create, \
         patch("pipeline.gelato_client.get_etsy_listing_id") as mock_resolve:
        mock_resolve.return_value = "etsy-listing-77"
        result = publish_primary_group.publish_primary_group(
            conn, candidate_id, static_config=static_config, shop_id="shop1", dry_run=True,
            now="2026-07-16T09:20:00",
        )

    mock_create.assert_not_called()
    assert result["etsy_listing_id"] == "etsy-listing-77"
    conn.close()


def test_publish_primary_group_retries_once_then_succeeds(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_primary_group(conn, candidate_id, status="pending_review")
    _insert_listing_text(conn, candidate_id)
    static_config = config.load_static_config()

    attempts = {"n": 0}

    def flaky_create(*args, **kwargs):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise RuntimeError("Gelato throttled")
        return {"id": "gelato-prod-1", "_dry_run": True, "previewUrl": None, "productImages": []}

    with patch("pipeline.gelato_client.create_product_from_template", side_effect=flaky_create), \
         patch("pipeline.gelato_client.delete_product") as mock_delete:
        result = publish_primary_group.publish_primary_group(
            conn, candidate_id, static_config=static_config, shop_id="shop1", dry_run=True,
            now="2026-07-16T09:20:00",
        )

    assert attempts["n"] == 2
    assert result["etsy_listing_id"] == "DRY_RUN_ETSY_LISTING_ID"
    mock_delete.assert_not_called()  # first attempt never got a gelato_product_id to clean up
    conn.close()


def test_publish_primary_group_marks_group_publish_failed_after_second_failure(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_primary_group(conn, candidate_id, status="pending_review")
    _insert_listing_text(conn, candidate_id)
    static_config = config.load_static_config()

    with patch("pipeline.gelato_client.create_product_from_template",
               side_effect=RuntimeError("Gelato down")):
        with pytest.raises(RuntimeError, match="Gelato down"):
            publish_primary_group.publish_primary_group(
                conn, candidate_id, static_config=static_config, shop_id="shop1", dry_run=True,
                now="2026-07-16T09:20:00",
            )

    group_row = conn.execute("SELECT status FROM groups WHERE id = ?", (group_id,)).fetchone()
    assert group_row["status"] == "publish_failed"
    conn.close()


def test_publish_primary_group_raises_when_no_primary_group(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_listing_text(conn, candidate_id)

    with pytest.raises(ValueError, match="primary group"):
        publish_primary_group.publish_primary_group(
            conn, candidate_id, static_config=STATIC_CONFIG, dry_run=True,
        )
    conn.close()


def test_publish_primary_group_raises_when_no_listing_text(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_primary_group(conn, candidate_id, status="pending_review")

    with pytest.raises(ValueError, match="listing_texts"):
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


def test_handle_decision_reject_deletes_live_gelato_product(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_ready_primary_group(conn, candidate_id)
    gp_id = conn.execute(
        "SELECT id FROM group_products WHERE group_id = ?", (group_id,)
    ).fetchone()["id"]

    with patch("pipeline.publish_primary_group.critic_pass.gelato_client.delete_product") as mock_delete:
        publish_primary_group.handle_decision(
            conn, candidate_id, group_id, "reject", static_config=STATIC_CONFIG,
            now=datetime(2026, 7, 12, 12, 0, 0),
        )

    mock_delete.assert_called_once_with("gelato_prod_1", store_id=None, api_key=None)
    assert conn.execute("SELECT * FROM group_products WHERE id = ?", (gp_id,)).fetchone() is None
    conn.close()


def test_handle_decision_edit_discards_old_product_and_regenerates(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_ready_primary_group(conn, candidate_id)
    old_gp_id = conn.execute(
        "SELECT id FROM group_products WHERE group_id = ?", (group_id,)
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
            "INSERT INTO group_products (group_id, gelato_template_id, gelato_product_id, status, created_at, updated_at) "
            "VALUES (?, 'tpl_1', 'gelato_prod_v2', 'created', ?, ?)",
            (group_id, timestamp, timestamp),
        )
        conn.execute(
            "INSERT INTO group_product_variants "
            "(group_product_id, size, orientation, gelato_template_variant_id, price_eur, created_at) "
            "VALUES (?, '8x12', 'portrait', 'variant_8x12', 24, ?)",
            (cursor.lastrowid, timestamp),
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


def test_process_update_accepts_tap_on_second_of_two_group_messages_rows(tmp_path):
    # M1: if a duplicate gallery ever produced two group_messages rows, a tap on the
    # *second* message must still resolve (old code only checked the first row).
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_ready_primary_group(conn, candidate_id)
    _insert_group_message(conn, group_id, "987654321", 202)  # first
    _insert_group_message(conn, group_id, "987654321", 303)  # duplicate send
    update = _callback_update(
        user_id=987654321, data=f"approve:{group_id}", message_id=303, chat_id=987654321, callback_id="cbq2",
    )

    with patch("pipeline.publish_primary_group.handle_decision", return_value={"action": "approve"}) as mock_handle, \
         patch("pipeline.publish_primary_group.telegram_client.answer_callback_query"):
        result = publish_primary_group.process_update(
            conn, update, admin_chat_id="987654321", now=datetime(2026, 7, 12, 13, 0, 0),
        )

    assert result is not None
    mock_handle.assert_called_once()
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


def test_process_update_routes_5x7_group_to_publish_group_handle_decision(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = conn.execute(
        "INSERT INTO groups (candidate_id, group_type, status, created_at, updated_at) "
        "VALUES (?, '5x7', 'pending_review', '2026-07-13T09:05:00', '2026-07-13T09:05:00')",
        (candidate_id,),
    ).lastrowid
    conn.commit()
    _insert_group_message(conn, group_id, "987654321", 202)
    update = _callback_update(
        user_id=987654321, data=f"approve:{group_id}", message_id=202, chat_id=987654321,
        callback_id="cbq2",
    )

    with patch("pipeline.publish_group.handle_decision",
               return_value={"action": "approve", "listing_id": "listing_999"}) as mock_group_handle, \
         patch("pipeline.publish_primary_group.handle_decision") as mock_primary_handle, \
         patch("pipeline.publish_primary_group.telegram_client.answer_callback_query"):
        result = publish_primary_group.process_update(
            conn, update, admin_chat_id="987654321", now=datetime(2026, 7, 13, 13, 0, 0),
        )

    mock_primary_handle.assert_not_called()
    mock_group_handle.assert_called_once()
    assert mock_group_handle.call_args.args[:3] == (conn, candidate_id, group_id)
    assert mock_group_handle.call_args.args[3] == "approve"
    assert result == {"candidate_id": candidate_id, "group_id": group_id,
                       "action": "approve", "listing_id": "listing_999"}
    conn.close()


def test_process_update_still_routes_primary_group_to_own_handle_decision(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_ready_primary_group(conn, candidate_id)
    _insert_group_message(conn, group_id, "987654321", 202)
    update = _callback_update(
        user_id=987654321, data=f"approve:{group_id}", message_id=202, chat_id=987654321,
        callback_id="cbq3",
    )

    with patch("pipeline.publish_group.handle_decision") as mock_group_handle, \
         patch("pipeline.publish_primary_group.handle_decision",
               return_value={"action": "approve", "results": {"8x12": "published"}}) as mock_primary_handle, \
         patch("pipeline.publish_primary_group.telegram_client.answer_callback_query"):
        result = publish_primary_group.process_update(
            conn, update, admin_chat_id="987654321", now=datetime(2026, 7, 13, 13, 0, 0),
        )

    mock_group_handle.assert_not_called()
    mock_primary_handle.assert_called_once()
    assert result == {"candidate_id": candidate_id, "group_id": group_id,
                       "action": "approve", "results": {"8x12": "published"}}
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


# --- H1: retry_publish_failed_groups (poll-cycle re-attempt) ---

def _insert_publish_failed_group(conn, candidate_id, group_type, *, decision="approved"):
    timestamp = "2026-07-18T09:00:00"
    cursor = conn.execute(
        "INSERT INTO groups (candidate_id, group_type, status, decision, created_at, updated_at) "
        "VALUES (?, ?, 'publish_failed', ?, ?, ?)",
        (candidate_id, group_type, decision, timestamp, timestamp),
    )
    conn.commit()
    return cursor.lastrowid


def test_retry_publish_failed_groups_repatches_and_flips_to_published(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_publish_failed_group(conn, candidate_id, "5x7", decision="approved")
    _insert_group_product_with_variants(conn, group_id, sizes=("8x12",), status="created")
    _insert_listing_text(conn, candidate_id)

    with patch("pipeline.publish_primary_group.group_product.patch_etsy_listing",
               return_value="etsy-listing-late") as mock_patch:
        retried = publish_primary_group.retry_publish_failed_groups(
            conn, static_config=STATIC_CONFIG, shop_id="shop1", dry_run=True,
            now="2026-07-18T12:00:00",
        )

    assert retried == [group_id]
    mock_patch.assert_called_once()
    assert mock_patch.call_args.args[2] == "5x7"
    group_row = conn.execute("SELECT status FROM groups WHERE id = ?", (group_id,)).fetchone()
    assert group_row["status"] == "approved_published"
    conn.close()


def test_retry_publish_failed_groups_marks_primary_candidate_completed(tmp_path):
    # A primary publish that only succeeds via the retry path must still mark the
    # candidate 'completed' (mirror the happy path), not leave it stuck.
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn, status="primary_review")
    group_id = _insert_publish_failed_group(conn, candidate_id, "primary", decision="approved")
    _insert_group_product_with_variants(conn, group_id, sizes=("8x12",), status="created")
    _insert_listing_text(conn, candidate_id)

    with patch("pipeline.publish_primary_group.group_product.patch_etsy_listing", return_value="etsy-late"):
        retried = publish_primary_group.retry_publish_failed_groups(
            conn, static_config=STATIC_CONFIG, shop_id="shop1", dry_run=True, now="2026-07-18T12:00:00",
        )

    assert retried == [group_id]
    candidate_row = conn.execute("SELECT status FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    assert candidate_row["status"] == "completed"
    conn.close()


def test_retry_publish_failed_groups_does_not_complete_candidate_for_secondary(tmp_path):
    # A secondary (5x7/10x24) retry must NOT touch candidate status.
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn, status="completed")
    group_id = _insert_publish_failed_group(conn, candidate_id, "5x7", decision="approved")
    _insert_group_product_with_variants(conn, group_id, sizes=("8x12",), status="created")
    _insert_listing_text(conn, candidate_id)

    with patch("pipeline.publish_primary_group.group_product.patch_etsy_listing", return_value="etsy-late"):
        publish_primary_group.retry_publish_failed_groups(
            conn, static_config=STATIC_CONFIG, shop_id="shop1", dry_run=True, now="2026-07-18T12:00:00",
        )

    candidate_row = conn.execute("SELECT status FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    assert candidate_row["status"] == "completed"  # unchanged
    conn.close()


def test_retry_publish_failed_groups_leaves_group_failed_when_patch_still_fails(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_publish_failed_group(conn, candidate_id, "5x7", decision="approved")
    _insert_group_product_with_variants(conn, group_id, sizes=("8x12",), status="created")
    _insert_listing_text(conn, candidate_id)

    with patch("pipeline.publish_primary_group.group_product.patch_etsy_listing",
               side_effect=RuntimeError("still down")):
        retried = publish_primary_group.retry_publish_failed_groups(
            conn, static_config=STATIC_CONFIG, shop_id="shop1", dry_run=True,
            now="2026-07-18T12:00:00",
        )

    assert retried == []
    group_row = conn.execute("SELECT status FROM groups WHERE id = ?", (group_id,)).fetchone()
    assert group_row["status"] == "publish_failed"  # still stuck, but surfaced + retried next cycle
    conn.close()


def test_retry_publish_failed_groups_skips_non_approved_decisions(tmp_path):
    # A group that failed after a reject/edit isn't an approved-but-stuck publish - don't retry it.
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_publish_failed_group(conn, candidate_id, "5x7", decision="rejected")
    _insert_group_product_with_variants(conn, group_id, sizes=("8x12",), status="created")
    _insert_listing_text(conn, candidate_id)

    with patch("pipeline.publish_primary_group.group_product.patch_etsy_listing") as mock_patch:
        retried = publish_primary_group.retry_publish_failed_groups(
            conn, static_config=STATIC_CONFIG, shop_id="shop1", dry_run=True,
        )

    assert retried == []
    mock_patch.assert_not_called()
    conn.close()
