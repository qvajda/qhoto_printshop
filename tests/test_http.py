import io
import urllib.error
import urllib.request
from unittest.mock import MagicMock, patch

import pytest

import pipeline.http as http


def _mock_response(body: bytes):
    mock_resp = MagicMock()
    mock_resp.read.return_value = body
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False
    return mock_resp


def test_send_returns_parsed_json_on_success():
    request = urllib.request.Request("https://example.com/api")

    with patch("urllib.request.urlopen", return_value=_mock_response(b'{"ok": true}')) as mock_urlopen:
        result = http.send(request)

    assert result == {"ok": True}
    mock_urlopen.assert_called_once_with(request, timeout=30)


def test_send_returns_empty_dict_on_empty_body():
    request = urllib.request.Request("https://example.com/api")

    with patch("urllib.request.urlopen", return_value=_mock_response(b"")):
        result = http.send(request)

    assert result == {}


def test_send_raises_http_error_on_non_2xx():
    request = urllib.request.Request("https://example.com/api")
    error = urllib.error.HTTPError(
        url="https://example.com/api", code=400, msg="Bad Request",
        hdrs=None, fp=io.BytesIO(b'{"error": "bad input"}'),
    )

    with patch("urllib.request.urlopen", side_effect=error):
        with pytest.raises(http.HTTPError) as exc_info:
            http.send(request)

    assert exc_info.value.status_code == 400
    assert "bad input" in exc_info.value.body


def test_send_respects_custom_timeout():
    request = urllib.request.Request("https://example.com/api")

    with patch("urllib.request.urlopen", return_value=_mock_response(b"{}")) as mock_urlopen:
        http.send(request, timeout=5)

    mock_urlopen.assert_called_once_with(request, timeout=5)
