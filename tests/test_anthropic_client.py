import json
from unittest.mock import patch

import pipeline.anthropic_client as anthropic_client


def test_research_web_search_builds_correct_request():
    captured = {}

    def fake_send(request, timeout=30):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["headers"] = {
            "x-api-key": request.get_header("X-api-key"),
            "anthropic-version": request.get_header("Anthropic-version"),
        }
        captured["body"] = json.loads(request.data)
        return {
            "content": [
                {"type": "server_tool_use", "id": "srvtoolu_1", "name": "web_search"},
                {"type": "web_search_tool_result", "tool_use_id": "srvtoolu_1", "content": []},
                {"type": "text", "text": '[{"keyword": "monstera line art", "rationale": "rising interest"}]'},
            ]
        }

    with patch("pipeline.anthropic_client.http.send", side_effect=fake_send):
        result = anthropic_client.research_web_search("find trending botanical keywords", api_key="key1")

    assert captured["url"] == "https://api.anthropic.com/v1/messages"
    assert captured["method"] == "POST"
    assert captured["headers"]["x-api-key"] == "key1"
    assert captured["headers"]["anthropic-version"] == anthropic_client.ANTHROPIC_API_VERSION
    assert captured["body"]["model"] == anthropic_client.ANTHROPIC_MODEL
    assert captured["body"]["messages"] == [{"role": "user", "content": "find trending botanical keywords"}]
    assert captured["body"]["tools"] == [
        {"type": anthropic_client.WEB_SEARCH_TOOL_TYPE, "name": "web_search", "max_uses": 5}
    ]
    assert result["text"] == '[{"keyword": "monstera line art", "rationale": "rising interest"}]'


def test_research_web_search_concatenates_multiple_text_blocks():
    def fake_send(request, timeout=30):
        return {"content": [{"type": "text", "text": "line one"}, {"type": "text", "text": "line two"}]}

    with patch("pipeline.anthropic_client.http.send", side_effect=fake_send):
        result = anthropic_client.research_web_search("prompt", api_key="key1")

    assert result["text"] == "line one\nline two"


def test_complete_builds_correct_request_without_tools():
    captured = {}

    def fake_send(request, timeout=30):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["body"] = json.loads(request.data)
        return {"content": [{"type": "text", "text": '{"title": "Botanical Wall Art"}'}]}

    with patch("pipeline.anthropic_client.http.send", side_effect=fake_send):
        result = anthropic_client.complete("draft some listing text", api_key="key1")

    assert captured["url"] == "https://api.anthropic.com/v1/messages"
    assert captured["method"] == "POST"
    assert captured["body"]["model"] == anthropic_client.ANTHROPIC_MODEL
    assert captured["body"]["max_tokens"] == 1024
    assert captured["body"]["messages"] == [{"role": "user", "content": "draft some listing text"}]
    assert "tools" not in captured["body"]
    assert result["text"] == '{"title": "Botanical Wall Art"}'


def test_complete_concatenates_multiple_text_blocks():
    def fake_send(request, timeout=30):
        return {"content": [{"type": "text", "text": "line one"}, {"type": "text", "text": "line two"}]}

    with patch("pipeline.anthropic_client.http.send", side_effect=fake_send):
        result = anthropic_client.complete("prompt", api_key="key1")

    assert result["text"] == "line one\nline two"


def test_complete_with_images_builds_correct_request_with_image_blocks_before_text():
    captured = {}

    def fake_send(request, timeout=30):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["body"] = json.loads(request.data)
        return {"content": [{"type": "text", "text": '{"passed": true, "reason": "ok"}'}]}

    with patch("pipeline.anthropic_client.http.send", side_effect=fake_send):
        result = anthropic_client.complete_with_images(
            "review these images", ["https://gelato/a.jpg", "https://gelato/b.jpg"], api_key="key1"
        )

    assert captured["url"] == "https://api.anthropic.com/v1/messages"
    assert captured["method"] == "POST"
    assert captured["body"]["model"] == anthropic_client.ANTHROPIC_MODEL
    assert captured["body"]["max_tokens"] == 1024
    content = captured["body"]["messages"][0]["content"]
    assert content == [
        {"type": "image", "source": {"type": "url", "url": "https://gelato/a.jpg"}},
        {"type": "image", "source": {"type": "url", "url": "https://gelato/b.jpg"}},
        {"type": "text", "text": "review these images"},
    ]
    assert result["text"] == '{"passed": true, "reason": "ok"}'


def test_complete_with_images_concatenates_multiple_text_blocks():
    def fake_send(request, timeout=30):
        return {"content": [{"type": "text", "text": "line one"}, {"type": "text", "text": "line two"}]}

    with patch("pipeline.anthropic_client.http.send", side_effect=fake_send):
        result = anthropic_client.complete_with_images("prompt", ["https://gelato/a.jpg"], api_key="key1")

    assert result["text"] == "line one\nline two"
