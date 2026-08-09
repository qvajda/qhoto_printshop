import json
from unittest.mock import patch

import pytest

import pipeline.telegram_client as telegram_client


def test_send_media_group_downloads_urls_and_uploads_as_multipart():
    # Telegram's own server-side URL fetch (bare 'media' URL string) proved
    # unreliable for our composited galleries (WEBPAGE_CURL_FAILED live, GL-13 R3,
    # 2026-08-02) - every http(s) URL is now downloaded here and attached instead
    # of referenced by URL.
    captured = {}

    def fake_fetch_bytes(url, timeout=30, sleep_fn=None):
        return b"remote-bytes-for-" + url.encode("utf-8")

    def fake_send(request, timeout=30):
        captured["content_type"] = request.headers.get("Content-type") or request.headers.get("Content-Type")
        captured["body"] = request.data
        return {"ok": True, "result": {"message_id": 1}}

    with patch("pipeline.telegram_client.http.fetch_bytes", side_effect=fake_fetch_bytes), \
         patch("pipeline.telegram_client.http.send", side_effect=fake_send):
        result = telegram_client.send_media_group(
            "12345", ["https://example.com/a.jpg", "https://example.com/b.jpg"], bot_token="test-token"
        )

    assert "multipart/form-data" in captured["content_type"]
    assert b"attach://attach0" in captured["body"]
    assert b"attach://attach1" in captured["body"]
    assert b"remote-bytes-for-https://example.com/a.jpg" in captured["body"]
    assert b"remote-bytes-for-https://example.com/b.jpg" in captured["body"]
    assert b"https://example.com/a.jpg\"" not in captured["body"]  # never referenced as a bare URL
    assert result == {"ok": True, "result": {"message_id": 1}}


def test_send_media_group_uploads_local_paths_as_multipart(tmp_path):
    # Regression: locally cover-cropped previews (pipeline.image_crop) have no public
    # URL, so sendMediaGroup must upload them as multipart attachments instead of
    # referencing a URL string.
    image_path = tmp_path / "cropped.jpg"
    image_path.write_bytes(b"fake-jpeg-bytes")
    captured = {}

    def fake_fetch_bytes(url, timeout=30, sleep_fn=None):
        return b"remote-bytes"

    def fake_send(request, timeout=30):
        captured["content_type"] = request.headers.get("Content-type") or request.headers.get("Content-Type")
        captured["body"] = request.data
        return {"ok": True, "result": {"message_id": 3}}

    with patch("pipeline.telegram_client.http.fetch_bytes", side_effect=fake_fetch_bytes), \
         patch("pipeline.telegram_client.http.send", side_effect=fake_send):
        result = telegram_client.send_media_group(
            "12345", ["https://example.com/a.jpg", str(image_path)], bot_token="test-token"
        )

    assert "multipart/form-data" in captured["content_type"]
    assert b"fake-jpeg-bytes" in captured["body"]
    assert b"attach://attach1" in captured["body"]
    assert b"remote-bytes" in captured["body"]
    assert result == {"ok": True, "result": {"message_id": 3}}


def test_send_message_includes_reply_markup_when_given():
    captured = {}
    keyboard = {"inline_keyboard": [[{"text": "Approve", "callback_data": "approve:1:primary"}]]}

    def fake_send(request, timeout=30):
        captured["body"] = json.loads(request.data)
        return {"ok": True, "result": {"message_id": 2}}

    with patch("pipeline.telegram_client.http.send", side_effect=fake_send):
        telegram_client.send_message("12345", "Draft listing text", keyboard, bot_token="test-token")

    assert captured["body"]["text"] == "Draft listing text"
    assert captured["body"]["reply_markup"] == keyboard


def test_send_message_omits_reply_markup_when_not_given():
    captured = {}

    def fake_send(request, timeout=30):
        captured["body"] = json.loads(request.data)
        return {"ok": True, "result": {"message_id": 3}}

    with patch("pipeline.telegram_client.http.send", side_effect=fake_send):
        telegram_client.send_message("12345", "Just text", bot_token="test-token")

    assert "reply_markup" not in captured["body"]


def test_get_updates_returns_result_list():
    def fake_send(request, timeout=30):
        return {"ok": True, "result": [{"update_id": 1}, {"update_id": 2}]}

    with patch("pipeline.telegram_client.http.send", side_effect=fake_send):
        result = telegram_client.get_updates(bot_token="test-token")

    assert result == [{"update_id": 1}, {"update_id": 2}]


def test_answer_callback_query_sends_callback_id_and_text():
    captured = {}

    def fake_send(request, timeout=30):
        captured["body"] = json.loads(request.data)
        return {"ok": True, "result": True}

    with patch("pipeline.telegram_client.http.send", side_effect=fake_send):
        telegram_client.answer_callback_query("cbq123", "Approved!", bot_token="test-token")

    assert captured["body"]["callback_query_id"] == "cbq123"
    assert captured["body"]["text"] == "Approved!"


def test_raises_telegram_api_error_when_ok_is_false():
    def fake_send(request, timeout=30):
        return {"ok": False, "description": "Bad Request: chat not found"}

    with patch("pipeline.telegram_client.http.send", side_effect=fake_send):
        with pytest.raises(telegram_client.TelegramAPIError, match="chat not found"):
            telegram_client.send_message("bad_chat", "text", bot_token="test-token")


def test_bot_token_defaults_to_env_var(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "env-token")
    captured = {}

    def fake_send(request, timeout=30):
        captured["url"] = request.full_url
        return {"ok": True, "result": {}}

    with patch("pipeline.telegram_client.http.send", side_effect=fake_send):
        telegram_client.send_message("123", "hi")

    assert "env-token" in captured["url"]


def test_get_updates_asserts_allowed_updates_and_logs_the_raw_response(tmp_path):
    # GL-45: Telegram keeps allowed_updates sticky from whatever last set it, so the
    # property has to be asserted on every call rather than inherited. The raw
    # response goes to a file, not the DB - a DB-write failure must not be able to
    # hide the measurement that proves what Telegram did or did not send.
    captured = {}
    response = {"ok": True, "result": [{"update_id": 7}]}

    def fake_send(request, timeout=30):
        captured["body"] = json.loads(request.data)
        return response

    log_path = tmp_path / "logs" / "getupdates.log"
    with patch("pipeline.telegram_client.http.send", side_effect=fake_send):
        telegram_client.get_updates(offset=5, bot_token="test-token", raw_log_path=log_path)

    assert captured["body"]["allowed_updates"] == ["message", "callback_query"]
    assert captured["body"]["offset"] == 5
    logged = json.loads(log_path.read_text().splitlines()[-1])
    assert logged["offset"] == 5
    assert logged["response"] == response


def test_edit_message_reply_markup_sends_chat_message_and_markup():
    captured = {}

    def fake_send(request, timeout=30):
        captured["body"] = json.loads(request.data)
        return {"ok": True, "result": True}

    markup = {"inline_keyboard": [[{"text": "✅ Approved", "callback_data": "noop:12"}]]}
    with patch("pipeline.telegram_client.http.send", side_effect=fake_send):
        telegram_client.edit_message_reply_markup(123, 456, markup, bot_token="test-token")

    assert captured["body"] == {"chat_id": 123, "message_id": 456, "reply_markup": markup}
