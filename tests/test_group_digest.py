import json as _json
from datetime import datetime
from unittest.mock import patch

import pytest

import pipeline.db as db
import pipeline.group_digest as group_digest


def _fresh_conn(tmp_path):
    conn = db.get_connection(tmp_path / "test.sqlite3")
    db.init_db(conn)
    return conn


def _insert_candidate(conn, niche="monstera line art", *, status="primary_review",
                       base_image_url="https://replicate.delivery/out.png"):
    timestamp = "2026-07-14T09:00:00"
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
                           price_eur=19, group_status="pending_review",
                           group_product_status="created"):
    timestamp = "2026-07-14T09:05:00"
    group_cursor = conn.execute(
        "INSERT INTO groups (candidate_id, group_type, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (candidate_id, group_type, group_status, timestamp, timestamp),
    )
    group_id = group_cursor.lastrowid
    gp_cursor = conn.execute(
        "INSERT INTO group_products "
        "(group_id, size, orientation, gelato_template_id, gelato_product_id, price_eur, "
        "status, created_at, updated_at) "
        "VALUES (?, ?, 'portrait', 'tpl_1', 'gelato_prod_1', ?, ?, ?, ?)",
        (group_id, size, price_eur, group_product_status, timestamp, timestamp),
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
    timestamp = "2026-07-14T09:10:00"
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


def _insert_critic_pass(conn, group_id, *, attempt_number=1, passed=1):
    timestamp = "2026-07-14T09:15:00"
    conn.execute(
        "INSERT INTO critic_pass_attempts (group_id, attempt_number, passed, created_at) "
        "VALUES (?, ?, ?, ?)",
        (group_id, attempt_number, passed, timestamp),
    )
    conn.commit()


def test_get_review_group_returns_candidate_type_and_price(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id, _ = _insert_group_gallery(conn, candidate_id, "5x7", "5x7", price_eur=19)

    result = group_digest.get_review_group(conn, group_id)

    assert result == {"candidate_id": candidate_id, "group_type": "5x7", "price_eur": 19}
    conn.close()


def test_get_review_group_raises_when_no_live_group_product(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id, _ = _insert_group_gallery(
        conn, candidate_id, "5x7", "5x7", group_product_status="mockup_failed",
    )

    with pytest.raises(ValueError, match="group_product"):
        group_digest.get_review_group(conn, group_id)
    conn.close()


def test_get_group_gallery_urls_returns_ordered_urls(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id, _ = _insert_group_gallery(
        conn, candidate_id, "10x24", "10x24",
        image_urls=("https://gelato/flat.jpg", "https://gelato/life1.jpg", "https://gelato/life2.jpg"),
    )

    urls = group_digest.get_group_gallery_urls(conn, group_id)

    assert urls == [
        "https://gelato/flat.jpg", "https://gelato/life1.jpg", "https://gelato/life2.jpg",
    ]
    conn.close()


def test_build_group_digest_message_text_includes_group_type_and_price():
    listing_text = {
        "title": "Monstera Line Art Botanical Print",
        "tags": _json.dumps(["botanical", "wall art"]),
        "description": "A minimalist botanical print.",
        "disclosure_text": "AI disclosure text.",
    }

    text = group_digest.build_group_digest_message_text(7, 42, "5x7", listing_text, 19)

    assert "Candidate #7" in text
    assert "5x7 group" in text
    assert "#42" in text
    assert "Monstera Line Art Botanical Print" in text
    assert "A minimalist botanical print." in text
    assert "botanical, wall art" in text
    assert "AI disclosure text." in text
    assert "19" in text


def test_send_group_digest_sends_media_group_then_message_and_persists_id(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id, _ = _insert_group_gallery(conn, candidate_id, "5x7", "5x7", price_eur=19)
    _insert_listing_text(conn, candidate_id)

    calls = []

    def fake_send_media_group(chat_id, photo_urls, *, bot_token=None):
        calls.append(("media_group", chat_id, photo_urls, bot_token))
        return {"ok": True, "result": [{"message_id": 100}, {"message_id": 101}]}

    def fake_send_message(chat_id, text, reply_markup=None, *, bot_token=None):
        calls.append(("message", chat_id, text, reply_markup, bot_token))
        return {"ok": True, "result": {"message_id": 202}}

    with patch("pipeline.group_digest.telegram_client.send_media_group", side_effect=fake_send_media_group), \
         patch("pipeline.group_digest.telegram_client.send_message", side_effect=fake_send_message):
        result = group_digest.send_group_digest(
            conn, group_id, bot_token="test-token", chat_id="admin-chat",
            now=datetime(2026, 7, 14, 9, 30, 0),
        )

    assert result == {
        "candidate_id": candidate_id, "group_id": group_id, "telegram_message_id": 202,
    }

    assert calls[0][0] == "media_group"
    assert calls[0][1] == "admin-chat"
    assert calls[0][2] == ["https://gelato/flat.jpg", "https://gelato/life.jpg"]
    assert calls[1][0] == "message"
    assert calls[1][1] == "admin-chat"
    assert f"Candidate #{candidate_id}" in calls[1][2]
    assert "5x7 group" in calls[1][2]
    assert calls[1][3]["inline_keyboard"][0][0]["callback_data"] == f"approve:{group_id}"

    message_row = conn.execute(
        "SELECT * FROM group_messages WHERE group_id = ?", (group_id,)
    ).fetchone()
    assert message_row["telegram_message_id"] == 202
    assert message_row["chat_id"] == "admin-chat"
    assert message_row["sent_at"] == "2026-07-14T09:30:00"
    conn.close()


def test_send_group_digest_uses_env_chat_id_when_not_passed(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEGRAM_ADMIN_CHAT_ID", "env-admin-chat")
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id, _ = _insert_group_gallery(conn, candidate_id, "10x24", "10x24")
    _insert_listing_text(conn, candidate_id)

    with patch("pipeline.group_digest.telegram_client.send_media_group",
               return_value={"ok": True, "result": []}) as mock_media, \
         patch("pipeline.group_digest.telegram_client.send_message",
               return_value={"ok": True, "result": {"message_id": 5}}) as mock_message:
        group_digest.send_group_digest(conn, group_id, bot_token="test-token")

    assert mock_media.call_args.args[0] == "env-admin-chat"
    assert mock_message.call_args.args[0] == "env-admin-chat"
    conn.close()


def test_send_group_digest_raises_and_writes_no_row_when_listing_text_missing(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id, _ = _insert_group_gallery(conn, candidate_id, "5x7", "5x7")  # no listing_texts row

    with patch("pipeline.group_digest.telegram_client.send_media_group") as mock_media, \
         patch("pipeline.group_digest.telegram_client.send_message") as mock_message:
        with pytest.raises(ValueError, match="listing_texts"):
            group_digest.send_group_digest(conn, group_id, bot_token="test-token", chat_id="admin-chat")

    mock_media.assert_not_called()
    mock_message.assert_not_called()
    assert conn.execute("SELECT * FROM group_messages").fetchall() == []
    conn.close()


def _insert_ready_group(conn, niche, group_type, size, *, price_eur=19):
    candidate_id = _insert_candidate(conn, niche=niche)
    group_id, _ = _insert_group_gallery(conn, candidate_id, group_type, size, price_eur=price_eur)
    _insert_listing_text(conn, candidate_id, niche=niche)
    _insert_critic_pass(conn, group_id, passed=1)
    return candidate_id, group_id


def test_run_group_digest_cycle_processes_critic_passed_groups(tmp_path):
    conn = _fresh_conn(tmp_path)
    _, ready_group_id = _insert_ready_group(conn, "monstera line art", "5x7", "5x7")

    not_passed_candidate_id = _insert_candidate(conn, niche="pending crop")
    not_passed_group_id, _ = _insert_group_gallery(conn, not_passed_candidate_id, "10x24", "10x24")
    _insert_listing_text(conn, not_passed_candidate_id, niche="pending crop")
    # no critic_pass_attempts row -> not yet critic-passed

    with patch("pipeline.group_digest.telegram_client.send_media_group",
               return_value={"ok": True, "result": []}), \
         patch("pipeline.group_digest.telegram_client.send_message",
               return_value={"ok": True, "result": {"message_id": 1}}):
        processed_ids = group_digest.run_group_digest_cycle(
            conn, bot_token="test-token", chat_id="admin-chat", now=datetime(2026, 7, 14, 9, 30, 0),
        )

    assert processed_ids == [ready_group_id]
    assert not_passed_group_id not in processed_ids
    conn.close()


def test_run_group_digest_cycle_skips_groups_already_digested(tmp_path):
    conn = _fresh_conn(tmp_path)
    _, group_id = _insert_ready_group(conn, "monstera line art", "5x7", "5x7")

    with patch("pipeline.group_digest.telegram_client.send_media_group",
               return_value={"ok": True, "result": []}), \
         patch("pipeline.group_digest.telegram_client.send_message",
               return_value={"ok": True, "result": {"message_id": 1}}):
        first_run = group_digest.run_group_digest_cycle(
            conn, bot_token="test-token", chat_id="admin-chat", now=datetime(2026, 7, 14, 9, 30, 0),
        )
        second_run = group_digest.run_group_digest_cycle(
            conn, bot_token="test-token", chat_id="admin-chat", now=datetime(2026, 7, 14, 10, 0, 0),
        )

    assert first_run == [group_id]
    assert second_run == []
    conn.close()


def test_run_group_digest_cycle_isolates_per_group_failures(tmp_path):
    conn = _fresh_conn(tmp_path)
    _, failing_group_id = _insert_ready_group(conn, "saturated term", "5x7", "5x7")
    _, succeeding_group_id = _insert_ready_group(conn, "moon phase print", "10x24", "10x24")

    def fake_send_message(chat_id, text, reply_markup=None, *, bot_token=None):
        if "saturated term" in text:
            raise RuntimeError("Telegram throttled")
        return {"ok": True, "result": {"message_id": 1}}

    with patch("pipeline.group_digest.telegram_client.send_media_group",
               return_value={"ok": True, "result": []}), \
         patch("pipeline.group_digest.telegram_client.send_message", side_effect=fake_send_message):
        processed_ids = group_digest.run_group_digest_cycle(
            conn, bot_token="test-token", chat_id="admin-chat", now=datetime(2026, 7, 14, 9, 30, 0),
        )

    assert processed_ids == [succeeding_group_id]
    assert conn.execute(
        "SELECT * FROM group_messages WHERE group_id = ?", (failing_group_id,)
    ).fetchone() is None
    conn.close()


def test_run_group_digest_cycle_ignores_primary_groups(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    primary_group_id, _ = _insert_group_gallery(conn, candidate_id, "primary", "8x12", price_eur=24)
    _insert_listing_text(conn, candidate_id)
    _insert_critic_pass(conn, primary_group_id, passed=1)

    processed_ids = group_digest.run_group_digest_cycle(
        conn, bot_token="test-token", chat_id="admin-chat",
    )

    assert processed_ids == []
    conn.close()


def test_run_group_digest_cycle_returns_empty_list_when_nothing_ready(tmp_path):
    conn = _fresh_conn(tmp_path)
    _insert_candidate(conn, niche="pending one", status="generating")

    processed_ids = group_digest.run_group_digest_cycle(conn, bot_token="test-token", chat_id="admin-chat")

    assert processed_ids == []
    conn.close()
