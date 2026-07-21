from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import pipeline.anthropic_client as anthropic_client


def _usage(input_tokens=10, output_tokens=5):
    return SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens)


def _text_block(text):
    return SimpleNamespace(type="text", text=text)


def _message(content, stop_reason="end_turn", request_id="req_123"):
    message = SimpleNamespace(
        content=content, stop_reason=stop_reason, usage=_usage(), id="msg_1",
    )
    message._request_id = request_id
    return message


def _fake_client(create_side_effect):
    """A stand-in for anthropic.Anthropic() exposing only .messages.create,
    which is all anthropic_client touches on the client object."""
    client = MagicMock()
    client.messages.create.side_effect = create_side_effect
    return client


def _patch_anthropic(client):
    return patch("pipeline.anthropic_client.anthropic.Anthropic", return_value=client)


def test_research_web_search_builds_correct_request():
    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return _message([
            SimpleNamespace(type="server_tool_use", id="srvtoolu_1", name="web_search"),
            SimpleNamespace(type="web_search_tool_result", tool_use_id="srvtoolu_1", content=[]),
            _text_block('[{"keyword": "monstera line art", "rationale": "rising interest"}]'),
        ])

    client = _fake_client(fake_create)
    with _patch_anthropic(client):
        result = anthropic_client.research_web_search("find trending botanical keywords", api_key="key1")

    assert captured["model"] == anthropic_client.ANTHROPIC_MODEL
    assert captured["messages"] == [{"role": "user", "content": "find trending botanical keywords"}]
    assert captured["tools"] == [
        {"type": anthropic_client.WEB_SEARCH_TOOL_TYPE, "name": "web_search", "max_uses": 5}
    ]
    assert result["text"] == '[{"keyword": "monstera line art", "rationale": "rising interest"}]'


def test_research_web_search_concatenates_multiple_text_blocks():
    def fake_create(**kwargs):
        return _message([_text_block("line one"), _text_block("line two")])

    with _patch_anthropic(_fake_client(fake_create)):
        result = anthropic_client.research_web_search("prompt", api_key="key1")

    assert result["text"] == "line one\nline two"


def test_complete_builds_correct_request_without_tools():
    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return _message([_text_block('{"title": "Botanical Wall Art"}')])

    with _patch_anthropic(_fake_client(fake_create)):
        result = anthropic_client.complete("draft some listing text", api_key="key1")

    assert captured["model"] == anthropic_client.ANTHROPIC_MODEL
    assert captured["max_tokens"] == 1024
    assert captured["messages"] == [{"role": "user", "content": "draft some listing text"}]
    assert "tools" not in captured
    assert result["text"] == '{"title": "Botanical Wall Art"}'


def test_complete_concatenates_multiple_text_blocks():
    def fake_create(**kwargs):
        return _message([_text_block("line one"), _text_block("line two")])

    with _patch_anthropic(_fake_client(fake_create)):
        result = anthropic_client.complete("prompt", api_key="key1")

    assert result["text"] == "line one\nline two"


def test_complete_raises_no_text_content_error_when_no_text_blocks():
    # A tool-only turn (or any turn that ends without ever emitting text) is a real,
    # nameable failure - not a transport hiccup the SDK's retries could fix.
    def fake_create(**kwargs):
        return _message([SimpleNamespace(type="tool_use", id="t1", name="whatever", input={})])

    with _patch_anthropic(_fake_client(fake_create)) as _:
        with pytest.raises(anthropic_client.NoTextContentError) as excinfo:
            anthropic_client.complete("prompt", api_key="key1")

    assert excinfo.value.block_types == ["tool_use"]


def test_complete_raises_truncated_response_error_on_max_tokens():
    def fake_create(**kwargs):
        return _message([_text_block("cut off mid")], stop_reason="max_tokens")

    with _patch_anthropic(_fake_client(fake_create)):
        with pytest.raises(anthropic_client.TruncatedResponseError):
            anthropic_client.complete("prompt", api_key="key1", max_tokens=50)


def test_complete_continues_a_paused_turn_and_returns_the_final_text():
    # stop_reason == "pause_turn": per the API docs, resend the response's content
    # back as an assistant turn to let a long-running turn continue.
    responses = iter([
        _message([SimpleNamespace(type="server_tool_use", id="t1", name="web_search")], stop_reason="pause_turn"),
        _message([_text_block("final answer")], stop_reason="end_turn"),
    ])
    captured_messages = []

    def fake_create(**kwargs):
        captured_messages.append(kwargs["messages"])
        return next(responses)

    with _patch_anthropic(_fake_client(fake_create)):
        result = anthropic_client.complete("prompt", api_key="key1")

    assert result["text"] == "final answer"
    assert len(captured_messages) == 2
    # second call continues with the first response's content as an assistant turn
    assert captured_messages[1][-1]["role"] == "assistant"


def _fake_head_response(content_length=1024):
    response = MagicMock()
    response.headers = {"Content-Length": str(content_length)}
    return response


def test_complete_with_images_builds_correct_request_with_image_blocks_before_text():
    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return _message([_text_block('{"passed": true, "reason": "ok"}')])

    with _patch_anthropic(_fake_client(fake_create)), \
         patch("pipeline.anthropic_client.http.head", return_value=_fake_head_response()):
        result = anthropic_client.complete_with_images(
            "review these images", ["https://gelato/a.jpg", "https://gelato/b.jpg"], api_key="key1"
        )

    assert captured["model"] == anthropic_client.ANTHROPIC_MODEL
    assert captured["max_tokens"] == 1024
    content = captured["messages"][0]["content"]
    assert content == [
        {"type": "image", "source": {"type": "url", "url": "https://gelato/a.jpg"}},
        {"type": "image", "source": {"type": "url", "url": "https://gelato/b.jpg"}},
        {"type": "text", "text": "review these images"},
    ]
    assert result["text"] == '{"passed": true, "reason": "ok"}'


def test_complete_with_images_concatenates_multiple_text_blocks():
    def fake_create(**kwargs):
        return _message([_text_block("line one"), _text_block("line two")])

    with _patch_anthropic(_fake_client(fake_create)), \
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

    def fake_create(**kwargs):
        captured.update(kwargs)
        return _message([_text_block("ok")])

    big_image = Image.new("RGB", (10, 10), color="red")
    buffer = io.BytesIO()
    big_image.save(buffer, format="PNG")
    raw_bytes = buffer.getvalue()

    with _patch_anthropic(_fake_client(fake_create)), \
         patch("pipeline.anthropic_client.http.head",
               return_value=_fake_head_response(content_length=10 * 1024 * 1024)), \
         patch("pipeline.anthropic_client.http.fetch_bytes", return_value=raw_bytes):
        anthropic_client.complete_with_images("prompt", ["https://replicate.delivery/huge.png"], api_key="key1")

    content = captured["messages"][0]["content"]
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

    def fake_create(**kwargs):
        captured.update(kwargs)
        return _message([_text_block("ok")])

    with _patch_anthropic(_fake_client(fake_create)), \
         patch("pipeline.anthropic_client.http.head") as mock_head, \
         patch("pipeline.anthropic_client.http.fetch_bytes") as mock_fetch:
        anthropic_client.complete_with_images("prompt", [str(image_path)], api_key="key1")

    mock_head.assert_not_called()
    mock_fetch.assert_not_called()
    content = captured["messages"][0]["content"]
    assert content[0]["source"]["type"] == "base64"
    assert content[0]["source"]["media_type"] == "image/jpeg"


def test_parse_json_response_raises_malformed_json_error_on_bad_json():
    with pytest.raises(anthropic_client.MalformedJSONError) as excinfo:
        anthropic_client.parse_json_response("not json at all")

    assert "not json at all" in excinfo.value.snippet


def test_parse_json_response_still_strips_json_fence():
    result = anthropic_client.parse_json_response('```json\n{"a": 1}\n```')

    assert result == {"a": 1}
