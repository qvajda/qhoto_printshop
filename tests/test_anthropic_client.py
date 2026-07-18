import json
from unittest.mock import MagicMock, patch

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


def _fake_head_response(content_length=1024):
    response = MagicMock()
    response.headers = {"Content-Length": str(content_length)}
    return response


def test_complete_with_images_builds_correct_request_with_image_blocks_before_text():
    captured = {}

    def fake_send(request, timeout=30):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["body"] = json.loads(request.data)
        return {"content": [{"type": "text", "text": '{"passed": true, "reason": "ok"}'}]}

    with patch("pipeline.anthropic_client.http.send", side_effect=fake_send), \
         patch("pipeline.anthropic_client.http.head", return_value=_fake_head_response()):
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

    with patch("pipeline.anthropic_client.http.send", side_effect=fake_send), \
         patch("pipeline.anthropic_client.http.head", return_value=_fake_head_response()):
        result = anthropic_client.complete_with_images("prompt", ["https://gelato/a.jpg"], api_key="key1")

    assert result["text"] == "line one\nline two"


def test_complete_with_images_falls_back_to_base64_when_over_size_cap():
    # Regression: Anthropic rejects URL-fetched images over 5MB outright ("Unable to
    # download the file") - hit live 2026-07-17 with a ~6.9MB raw Replicate generation
    # output used as a group-critic image fallback. Oversized images must be downscaled
    # and sent as base64 instead of as a URL source.
    import io

    from PIL import Image

    captured = {}

    def fake_send(request, timeout=30):
        captured["body"] = json.loads(request.data)
        return {"content": [{"type": "text", "text": "ok"}]}

    big_image = Image.new("RGB", (10, 10), color="red")
    buffer = io.BytesIO()
    big_image.save(buffer, format="PNG")
    raw_bytes = buffer.getvalue()

    with patch("pipeline.anthropic_client.http.send", side_effect=fake_send), \
         patch("pipeline.anthropic_client.http.head",
               return_value=_fake_head_response(content_length=10 * 1024 * 1024)), \
         patch("pipeline.anthropic_client.http.fetch_bytes", return_value=raw_bytes):
        anthropic_client.complete_with_images("prompt", ["https://replicate.delivery/huge.png"], api_key="key1")

    content = captured["body"]["messages"][0]["content"]
    assert content[0]["type"] == "image"
    assert content[0]["source"]["type"] == "base64"
    assert content[0]["source"]["media_type"] == "image/jpeg"
    assert len(content[0]["source"]["data"]) > 0


def test_complete_with_images_sends_local_paths_as_base64_without_http_fetch(tmp_path):
    # Regression: locally cover-cropped previews (pipeline.image_crop) have no public
    # URL - they must be read straight off disk and base64-encoded, never HEAD/GET'd.
    import io

    from PIL import Image

    image = Image.new("RGB", (10, 10), color="blue")
    image_path = tmp_path / "cropped.jpg"
    image.save(image_path, format="JPEG")

    captured = {}

    def fake_send(request, timeout=30):
        captured["body"] = json.loads(request.data)
        return {"content": [{"type": "text", "text": "ok"}]}

    with patch("pipeline.anthropic_client.http.send", side_effect=fake_send), \
         patch("pipeline.anthropic_client.http.head") as mock_head, \
         patch("pipeline.anthropic_client.http.fetch_bytes") as mock_fetch:
        anthropic_client.complete_with_images("prompt", [str(image_path)], api_key="key1")

    mock_head.assert_not_called()
    mock_fetch.assert_not_called()
    content = captured["body"]["messages"][0]["content"]
    assert content[0]["source"]["type"] == "base64"
    assert content[0]["source"]["media_type"] == "image/jpeg"
