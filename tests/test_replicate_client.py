import json
from unittest.mock import patch

import pytest

import pipeline.replicate_client as replicate_client


def test_generate_image_builds_correct_request_and_parses_response():
    captured = {}

    def fake_send(request, timeout=30):
        captured["url"] = request.full_url
        captured["auth_header"] = request.get_header("Authorization")
        captured["prefer_header"] = request.get_header("Prefer")
        captured["body"] = json.loads(request.data)
        captured["timeout"] = timeout
        return {"id": "pred123", "status": "succeeded", "output": ["https://replicate.delivery/out.png"]}

    with patch("pipeline.replicate_client.http.send", side_effect=fake_send):
        result = replicate_client.generate_image("a botanical watercolor poster", api_token="test-token")

    assert captured["url"] == "https://api.replicate.com/v1/models/black-forest-labs/flux-schnell/predictions"
    assert captured["auth_header"] == "Bearer test-token"
    assert captured["prefer_header"] == "wait"
    assert captured["body"]["input"]["prompt"] == "a botanical watercolor poster"
    # Portrait primary template is 8x12 (2:3) - FLUX schnell defaults to square 1:1 and
    # ~1MP unless told otherwise; megapixels="1" is schnell's max native resolution.
    assert captured["body"]["input"]["aspect_ratio"] == "2:3"
    assert captured["body"]["input"]["megapixels"] == "1"
    assert result == {"image_url": "https://replicate.delivery/out.png", "prediction_id": "pred123"}
    # Replicate's Prefer: wait can hold the connection open up to 60s server-side;
    # the client-side socket timeout must be at least that long or the raw
    # URLError/socket timeout fires before our ReplicatePredictionTimeoutError can.
    assert captured["timeout"] >= 60


def test_generate_image_raises_timeout_error_when_not_succeeded():
    def fake_send(request, timeout=30):
        return {"id": "pred456", "status": "processing", "output": None}

    with patch("pipeline.replicate_client.http.send", side_effect=fake_send):
        with pytest.raises(replicate_client.ReplicatePredictionTimeoutError, match="pred456"):
            replicate_client.generate_image("a prompt", api_token="test-token")


def test_api_token_defaults_to_env_var(monkeypatch):
    monkeypatch.setenv("REPLICATE_API_TOKEN", "env-token")
    captured = {}

    def fake_send(request, timeout=30):
        captured["auth_header"] = request.get_header("Authorization")
        return {"id": "pred789", "status": "succeeded", "output": ["https://replicate.delivery/out2.png"]}

    with patch("pipeline.replicate_client.http.send", side_effect=fake_send):
        replicate_client.generate_image("a prompt")

    assert captured["auth_header"] == "Bearer env-token"


def test_upscale_image_builds_correct_request_and_parses_response():
    captured = {}

    def fake_send(request, timeout=30):
        captured["url"] = request.full_url
        captured["auth_header"] = request.get_header("Authorization")
        captured["prefer_header"] = request.get_header("Prefer")
        captured["body"] = json.loads(request.data)
        captured["timeout"] = timeout
        return {"id": "pred-up1", "status": "succeeded", "output": ["https://replicate.delivery/upscaled.png"]}

    with patch("pipeline.replicate_client.http.send", side_effect=fake_send):
        result = replicate_client.upscale_image("https://replicate.delivery/out.png", api_token="test-token")

    assert captured["url"] == "https://api.replicate.com/v1/models/nightmareai/real-esrgan/predictions"
    assert captured["auth_header"] == "Bearer test-token"
    assert captured["prefer_header"] == "wait"
    assert captured["body"]["input"] == {
        "image": "https://replicate.delivery/out.png",
        "scale": 8,
        "face_enhance": False,
    }
    assert result == {"image_url": "https://replicate.delivery/upscaled.png", "prediction_id": "pred-up1"}
    assert captured["timeout"] >= 60


def test_upscale_image_raises_timeout_error_when_not_succeeded():
    def fake_send(request, timeout=30):
        return {"id": "pred-up2", "status": "processing", "output": None}

    with patch("pipeline.replicate_client.http.send", side_effect=fake_send):
        with pytest.raises(replicate_client.ReplicatePredictionTimeoutError, match="pred-up2"):
            replicate_client.upscale_image("https://replicate.delivery/out.png", api_token="test-token")


def test_upscale_image_api_token_defaults_to_env_var(monkeypatch):
    monkeypatch.setenv("REPLICATE_API_TOKEN", "env-token")
    captured = {}

    def fake_send(request, timeout=30):
        captured["auth_header"] = request.get_header("Authorization")
        return {"id": "pred-up3", "status": "succeeded", "output": ["https://replicate.delivery/upscaled2.png"]}

    with patch("pipeline.replicate_client.http.send", side_effect=fake_send):
        replicate_client.upscale_image("https://replicate.delivery/out.png")

    assert captured["auth_header"] == "Bearer env-token"
