import urllib.request
from unittest.mock import patch

import httpx
import pytest

import pipeline.http as http


def _resp(status_code, content=b"", headers=None):
    return httpx.Response(status_code, content=content, headers=headers or {})


def test_send_returns_parsed_json_on_success():
    request = urllib.request.Request("https://example.com/api")

    with patch.object(http._client, "request", return_value=_resp(200, b'{"ok": true}')):
        result = http.send(request)

    assert result == {"ok": True}


def test_send_returns_empty_dict_on_empty_body():
    request = urllib.request.Request("https://example.com/api")

    with patch.object(http._client, "request", return_value=_resp(200, b"")):
        assert http.send(request) == {}


def test_send_raises_http_error_on_non_2xx():
    request = urllib.request.Request("https://example.com/api")

    with patch.object(http._client, "request", return_value=_resp(400, b'{"error": "bad input"}')):
        with pytest.raises(http.HTTPError) as exc_info:
            http.send(request)

    assert exc_info.value.status_code == 400
    assert "bad input" in exc_info.value.body


def test_send_translates_method_url_headers_body_timeout():
    captured = {}

    def fake_request(method, url, headers=None, content=None, timeout=30):
        captured.update(method=method, url=url, headers=headers, content=content, timeout=timeout)
        return _resp(200, b"{}")

    request = urllib.request.Request(
        "https://example.com/api", data=b"payload", headers={"X-Api-Key": "k"}, method="POST"
    )
    with patch.object(http._client, "request", side_effect=fake_request):
        http.send(request, timeout=5)

    assert captured["method"] == "POST"
    assert captured["url"] == "https://example.com/api"
    assert captured["headers"]["X-api-key"] == "k"
    assert captured["content"] == b"payload"
    assert captured["timeout"] == 5


def test_fetch_bytes_returns_raw_bytes_on_success():
    with patch.object(http._client, "request", return_value=_resp(200, b"\x89PNG raw bytes")) as mock_req:
        result = http.fetch_bytes("https://gelato/flat.jpg")

    assert result == b"\x89PNG raw bytes"
    assert mock_req.call_args.args == ("GET", "https://gelato/flat.jpg")


def test_fetch_bytes_raises_http_error_on_non_2xx():
    with patch.object(http._client, "request", return_value=_resp(404, b"not found")):
        with pytest.raises(http.HTTPError) as exc_info:
            http.fetch_bytes("https://gelato/missing.jpg")

    assert exc_info.value.status_code == 404


def test_retries_on_cloudflare_1010_with_long_backoff_then_succeeds():
    slept = []
    responses = [
        _resp(403, b"<html>error code: 1010</html>"),
        _resp(403, b"<html>error code: 1010</html>"),
        _resp(200, b'{"ok": true}'),
    ]
    request = urllib.request.Request("https://api.gelato.com/x")
    with patch.object(http._client, "request", side_effect=responses):
        result = http.send(request, sleep_fn=slept.append)

    assert result == {"ok": True}
    assert slept == [60, 120]  # long backoff, never a tight 3s retry


def test_gives_up_after_three_1010_backoffs_and_reports_cf_ray():
    slept = []
    resp = _resp(403, b"error code: 1010", headers={"cf-ray": "8abc-BRU"})
    request = urllib.request.Request("https://api.gelato.com/x")
    with patch.object(http._client, "request", return_value=resp):
        with pytest.raises(http.HTTPError) as exc_info:
            http.send(request, sleep_fn=slept.append)

    assert slept == [60, 120, 240]  # three waits, then give up
    assert exc_info.value.status_code == 403
    assert exc_info.value.headers.get("cf-ray") == "8abc-BRU"


def test_plain_403_is_not_1010_retried():
    slept = []
    request = urllib.request.Request("https://api.gelato.com/x")
    with patch.object(http._client, "request", return_value=_resp(403, b"Forbidden")):
        with pytest.raises(http.HTTPError):
            http.send(request, sleep_fn=slept.append)

    assert slept == []
