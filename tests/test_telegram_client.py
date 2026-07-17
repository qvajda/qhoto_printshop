import json
from unittest.mock import patch

import pytest

import pipeline.telegram_client as telegram_client


def test_send_media_group_builds_correct_request_and_parses_response():
    captured = {}

    def fake_send(request, timeout=30):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["body"] = json.loads(request.data)
        return {"ok": True, "result": {"message_id": 1}}

    with patch("pipeline.telegram_client.http.send", side_effect=fake_send):
        result = telegram_client.send_media_group(
            "12345", ["https://example.com/a.jpg", "https://example.com/b.jpg"], bot_token="test-token"
        )

    assert captured["url"] == "https://api.telegram.org/bottest-token/sendMediaGroup"
    assert captured["method"] == "POST"
    assert captured["body"]["chat_id"] == "12345"
    assert captured["body"]["media"] == [
        {"type": "photo", "media": "https://example.com/a.jpg"},
        {"type": "photo", "media": "https://example.com/b.jpg"},
    ]
    assert result == {"ok": True, "result": {"message_id": 1}}


def test_send_media_group_uploads_local_paths_as_multipart(tmp_path):
    # Regression: locally cover-cropped previews (pipeline.image_crop) have no public
    # URL, so sendMediaGroup must upload them as multipart attachments instead of
    # referencing a URL string.
    image_path = tmp_path / "cropped.jpg"
    image_path.write_bytes(b"fake-jpeg-bytes")
    captured = {}

    def fake_send(request, timeout=30):
        captured["content_type"] = request.headers.get("Content-type") or request.headers.get("Content-Type")
        captured["body"] = request.data
        return {"ok": True, "result": {"message_id": 3}}

    with patch("pipeline.telegram_client.http.send", side_effect=fake_send):
        result = telegram_client.send_media_group(
            "12345", ["https://example.com/a.jpg", str(image_path)], bot_token="test-token"
        )

    assert "multipart/form-data" in captured["content_type"]
    assert b"fake-jpeg-bytes" in captured["body"]
    assert b"attach://attach1" in captured["body"]
    assert b"https://example.com/a.jpg" in captured["body"]
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
