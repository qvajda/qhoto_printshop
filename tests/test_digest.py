import json as _json
from datetime import datetime
from unittest.mock import patch

import pytest

import pipeline.digest as digest
import pipeline.db as db


def _fresh_conn(tmp_path):
    conn = db.get_connection(tmp_path / "test.sqlite3")
    db.init_db(conn)
    return conn


def _insert_candidate(conn, niche="monstera line art", *, status="primary_review",
                       base_image_url="https://replicate.delivery/out.png"):
    timestamp = "2026-07-11T09:00:00"
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
                             *, sizes_and_prices=(("8x12", 24), ("A3", 35), ("A2", 39), ("A1", 49)),
                             group_product_status="created"):
    timestamp = "2026-07-11T09:05:00"
    group_cursor = conn.execute(
        "INSERT INTO groups (candidate_id, group_type, status, created_at, updated_at) "
        "VALUES (?, 'primary', 'pending_review', ?, ?)",
        (candidate_id, timestamp, timestamp),
    )
    group_id = group_cursor.lastrowid
    gp_cursor = conn.execute(
        "INSERT INTO group_products "
        "(group_id, gelato_template_id, gelato_product_id, status, created_at, updated_at) "
        "VALUES (?, 'tpl_1', 'gelato_prod_1', ?, ?, ?)",
        (group_id, group_product_status, timestamp, timestamp),
    )
    group_product_id = gp_cursor.lastrowid
    for size, price_eur in sizes_and_prices:
        conn.execute(
            "INSERT INTO group_product_variants "
            "(group_product_id, size, orientation, gelato_template_variant_id, price_eur, created_at) "
            "VALUES (?, ?, 'portrait', 'variant_1', ?, ?)",
            (group_product_id, size, price_eur, timestamp),
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
    timestamp = "2026-07-11T09:10:00"
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


def _insert_ready_candidate(conn, niche="monstera line art"):
    candidate_id = _insert_candidate(conn, niche=niche)
    _insert_primary_gallery(conn, candidate_id)
    _insert_listing_text(conn, candidate_id, niche=niche)
    return candidate_id


def test_get_primary_group_returns_group_id_and_variants(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    expected_group_id, _ = _insert_primary_gallery(
        conn, candidate_id, sizes_and_prices=(("8x12", 24), ("A3", 35)),
    )

    result = digest.get_primary_group(conn, candidate_id)

    assert result == {
        "group_id": expected_group_id,
        "variants": [{"size": "8x12", "price_eur": 24}, {"size": "A3", "price_eur": 35}],
    }
    conn.close()


def test_get_primary_group_raises_when_no_live_group_product(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)

    with pytest.raises(ValueError, match="primary group_product"):
        digest.get_primary_group(conn, candidate_id)
    conn.close()


def test_get_primary_gallery_urls_returns_ordered_urls(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_primary_gallery(
        conn, candidate_id,
        image_urls=("https://gelato/flat.jpg", "https://gelato/life1.jpg", "https://gelato/life2.jpg"),
    )

    urls = digest.get_primary_gallery_urls(conn, candidate_id)

    assert urls == [
        "https://gelato/flat.jpg", "https://gelato/life1.jpg", "https://gelato/life2.jpg",
    ]
    conn.close()


def test_get_listing_text_returns_row(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_listing_text(conn, candidate_id, niche="monstera line art")

    result = digest.get_listing_text(conn, candidate_id)

    assert result["title"] == "monstera line art print"
    assert result["tags"] == _json.dumps(["botanical", "wall art"])
    assert result["description"] == "A print of monstera line art."
    assert result["disclosure_text"] == "AI disclosure text."
    conn.close()


def test_get_listing_text_raises_when_missing(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)

    with pytest.raises(ValueError, match="listing_texts"):
        digest.get_listing_text(conn, candidate_id)
    conn.close()


def test_build_digest_message_text_lists_every_size_and_price():
    # disclosure_text is NOT repeated here - it's already required to be woven into
    # the description itself (see compliance_draft's prompt), so appending the raw
    # disclosure_text field again would just duplicate it in the admin's digest message.
    listing_text = {
        "title": "Monstera Line Art Botanical Print",
        "tags": _json.dumps(["botanical", "wall art"]),
        "description": "A minimalist botanical print.",
        "disclosure_text": "AI disclosure text.",
    }

    text = digest.build_digest_message_text(
        7, 42, listing_text,
        [{"size": "8x12", "price_eur": 24.0}, {"size": "A3", "price_eur": 35.0},
         {"size": "A2", "price_eur": 39.0}, {"size": "A1", "price_eur": 49.0}],
    )

    assert "Candidate #7" in text
    assert "#42" in text
    assert "Monstera Line Art Botanical Print" in text
    assert "A minimalist botanical print." in text
    assert "botanical, wall art" in text
    assert "AI disclosure text." not in text
    assert "8x12 €24.0" in text
    assert "A3 €35.0" in text
    assert "A1 €49.0" in text


def test_build_digest_keyboard_has_three_buttons_with_group_id_callback_data():
    keyboard = digest.build_digest_keyboard(42)

    buttons = keyboard["inline_keyboard"][0]
    assert len(buttons) == 3
    callback_data = [button["callback_data"] for button in buttons]
    assert callback_data == ["approve:42", "edit:42", "reject:42"]


def test_send_primary_digest_sends_media_group_then_message_and_persists_id(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_ready_candidate(conn, niche="monstera line art")
    expected_group_id = conn.execute(
        "SELECT id FROM groups WHERE candidate_id = ? AND group_type = 'primary'", (candidate_id,)
    ).fetchone()["id"]

    calls = []

    def fake_send_media_group(chat_id, photo_urls, *, bot_token=None):
        calls.append(("media_group", chat_id, photo_urls, bot_token))
        return {"ok": True, "result": [{"message_id": 100}, {"message_id": 101}]}

    def fake_send_message(chat_id, text, reply_markup=None, *, bot_token=None):
        calls.append(("message", chat_id, text, reply_markup, bot_token))
        return {"ok": True, "result": {"message_id": 202}}

    with patch("pipeline.digest.telegram_client.send_media_group", side_effect=fake_send_media_group), \
         patch("pipeline.digest.telegram_client.send_message", side_effect=fake_send_message):
        result = digest.send_primary_digest(
            conn, candidate_id, bot_token="test-token", chat_id="admin-chat",
            now=datetime(2026, 7, 11, 9, 30, 0),
        )

    assert result == {
        "candidate_id": candidate_id, "group_id": expected_group_id, "telegram_message_id": 202,
    }

    assert calls[0][0] == "media_group"
    assert calls[0][1] == "admin-chat"
    assert calls[0][2] == ["https://gelato/flat.jpg", "https://gelato/life.jpg"]
    assert calls[1][0] == "message"
    assert calls[1][1] == "admin-chat"
    assert f"Candidate #{candidate_id}" in calls[1][2]
    assert calls[1][3]["inline_keyboard"][0][0]["callback_data"] == f"approve:{expected_group_id}"

    message_row = conn.execute(
        "SELECT * FROM group_messages WHERE group_id = ?", (expected_group_id,)
    ).fetchone()
    assert message_row["telegram_message_id"] == 202
    assert message_row["chat_id"] == "admin-chat"
    assert message_row["sent_at"] == "2026-07-11T09:30:00"
    conn.close()


def test_send_primary_digest_uses_env_chat_id_when_not_passed(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEGRAM_ADMIN_CHAT_ID", "env-admin-chat")
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_ready_candidate(conn, niche="monstera line art")

    with patch("pipeline.digest.telegram_client.send_media_group",
               return_value={"ok": True, "result": []}) as mock_media, \
         patch("pipeline.digest.telegram_client.send_message",
               return_value={"ok": True, "result": {"message_id": 5}}) as mock_message:
        digest.send_primary_digest(conn, candidate_id, bot_token="test-token")

    assert mock_media.call_args.args[0] == "env-admin-chat"
    assert mock_message.call_args.args[0] == "env-admin-chat"
    conn.close()


def test_send_primary_digest_raises_and_writes_no_row_when_listing_text_missing(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_primary_gallery(conn, candidate_id)  # gallery exists, no listing_texts row

    with patch("pipeline.digest.telegram_client.send_media_group") as mock_media, \
         patch("pipeline.digest.telegram_client.send_message") as mock_message:
        with pytest.raises(ValueError, match="listing_texts"):
            digest.send_primary_digest(conn, candidate_id, bot_token="test-token", chat_id="admin-chat")

    mock_media.assert_not_called()
    mock_message.assert_not_called()
    assert conn.execute("SELECT * FROM group_messages").fetchall() == []
    conn.close()


def test_run_digest_cycle_processes_primary_review_candidates(tmp_path):
    conn = _fresh_conn(tmp_path)
    ready_id = _insert_ready_candidate(conn, niche="monstera line art")
    not_ready_id = _insert_candidate(conn, niche="pending one", status="generating")
    _insert_primary_gallery(conn, not_ready_id)
    _insert_listing_text(conn, not_ready_id, niche="pending one")

    with patch("pipeline.digest.telegram_client.send_media_group",
               return_value={"ok": True, "result": []}), \
         patch("pipeline.digest.telegram_client.send_message",
               return_value={"ok": True, "result": {"message_id": 1}}):
        processed_ids = digest.run_digest_cycle(
            conn, bot_token="test-token", chat_id="admin-chat", now=datetime(2026, 7, 11, 9, 30, 0),
        )

    assert processed_ids == [ready_id]
    assert not_ready_id not in processed_ids
    conn.close()


def test_run_digest_cycle_skips_candidates_already_digested(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_ready_candidate(conn, niche="monstera line art")

    with patch("pipeline.digest.telegram_client.send_media_group",
               return_value={"ok": True, "result": []}), \
         patch("pipeline.digest.telegram_client.send_message",
               return_value={"ok": True, "result": {"message_id": 1}}):
        first_run = digest.run_digest_cycle(
            conn, bot_token="test-token", chat_id="admin-chat", now=datetime(2026, 7, 11, 9, 30, 0),
        )
        second_run = digest.run_digest_cycle(
            conn, bot_token="test-token", chat_id="admin-chat", now=datetime(2026, 7, 11, 10, 0, 0),
        )

    assert first_run == [candidate_id]
    assert second_run == []
    conn.close()


def test_run_digest_cycle_isolates_per_candidate_failures(tmp_path):
    conn = _fresh_conn(tmp_path)
    failing_id = _insert_ready_candidate(conn, niche="saturated term")
    succeeding_id = _insert_ready_candidate(conn, niche="moon phase print")

    def fake_send_message(chat_id, text, reply_markup=None, *, bot_token=None):
        if "saturated term" in text:
            raise RuntimeError("Telegram throttled")
        return {"ok": True, "result": {"message_id": 1}}

    with patch("pipeline.digest.telegram_client.send_media_group",
               return_value={"ok": True, "result": []}), \
         patch("pipeline.digest.telegram_client.send_message", side_effect=fake_send_message):
        processed_ids = digest.run_digest_cycle(
            conn, bot_token="test-token", chat_id="admin-chat", now=datetime(2026, 7, 11, 9, 30, 0),
        )

    assert processed_ids == [succeeding_id]

    failing_group_id = conn.execute(
        "SELECT id FROM groups WHERE candidate_id = ? AND group_type = 'primary'", (failing_id,)
    ).fetchone()["id"]
    assert conn.execute(
        "SELECT * FROM group_messages WHERE group_id = ?", (failing_group_id,)
    ).fetchone() is None
    conn.close()


def test_run_digest_cycle_returns_empty_list_when_nothing_ready(tmp_path):
    conn = _fresh_conn(tmp_path)
    _insert_candidate(conn, niche="pending one", status="generating")

    processed_ids = digest.run_digest_cycle(conn, bot_token="test-token", chat_id="admin-chat")

    assert processed_ids == []
    conn.close()
