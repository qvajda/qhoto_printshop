import json
from unittest.mock import patch

import pytest

import pipeline.http as http
import pipeline.replicate_client as replicate_client


def test_generate_image_builds_correct_request_and_parses_response():
    captured = {}

    def fake_send(request, timeout=30):
        captured["url"] = request.full_url
        captured["auth_header"] = request.get_header("Authorization")
        captured["body"] = json.loads(request.data)
        captured["timeout"] = timeout
        return {"id": "pred123", "status": "succeeded", "output": ["https://replicate.delivery/out.png"]}

    with patch("pipeline.replicate_client.http.send", side_effect=fake_send):
        result = replicate_client.generate_image("a botanical watercolor poster", api_token="test-token")

    assert captured["url"] == "https://api.replicate.com/v1/models/black-forest-labs/flux-schnell/predictions"
    assert captured["auth_header"] == "Bearer test-token"
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


def test_generate_image_raises_timeout_error_only_after_the_poll_budget_is_spent():
    # GL-59: a still-queued prediction is no longer a timeout on the first look -
    # only exhausting the poll budget is.
    def fake_send(request, timeout=30):
        return {"id": "pred456", "status": "processing", "output": None}

    clock = iter([0.0, 0.0, 5.0, 99.0])
    with patch("pipeline.replicate_client.http.send", side_effect=fake_send):
        with pytest.raises(replicate_client.ReplicatePredictionTimeoutError, match="pred456"):
            replicate_client.generate_image(
                "a prompt", api_token="test-token", poll_timeout=10.0,
                sleep_fn=lambda _: None, time_fn=lambda: next(clock),
            )


def test_generate_image_succeeds_when_a_queued_prediction_finishes_while_polling():
    # GL-59, the actual defect: candidates 78/83 raised a timeout on predictions that
    # executed in under 4s, because the 60s window counted queue time.
    responses = [
        {"id": "pred-q", "status": "starting", "output": None,
         "urls": {"get": "https://api.replicate.com/v1/predictions/pred-q"}},
        {"id": "pred-q", "status": "processing", "output": None,
         "urls": {"get": "https://api.replicate.com/v1/predictions/pred-q"}},
        {"id": "pred-q", "status": "succeeded", "output": ["https://replicate.delivery/q.png"]},
    ]
    polled = []

    def fake_send(request, timeout=30):
        if request.get_method() == "GET":
            polled.append(request.full_url)
        return responses.pop(0)

    with patch("pipeline.replicate_client.http.send", side_effect=fake_send):
        result = replicate_client.generate_image(
            "a prompt", api_token="test-token", sleep_fn=lambda _: None,
        )

    assert result == {"image_url": "https://replicate.delivery/q.png", "prediction_id": "pred-q"}
    assert polled == ["https://api.replicate.com/v1/predictions/pred-q"] * 2


def test_a_replicate_side_failure_is_not_reported_as_a_timeout():
    def fake_send(request, timeout=30):
        return {"id": "pred-f", "status": "failed", "error": "NSFW content detected"}

    with patch("pipeline.replicate_client.http.send", side_effect=fake_send):
        with pytest.raises(replicate_client.ReplicatePredictionFailedError, match="NSFW"):
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
        captured["body"] = json.loads(request.data)
        captured["timeout"] = timeout
        return {"id": "pred-up1", "status": "succeeded", "output": ["https://replicate.delivery/upscaled.png"]}

    with patch("pipeline.replicate_client.http.send", side_effect=fake_send):
        result = replicate_client.upscale_image("https://replicate.delivery/out.png", api_token="test-token")

    assert captured["url"] == "https://api.replicate.com/v1/models/nightmareai/real-esrgan/predictions"
    assert captured["auth_header"] == "Bearer test-token"
    assert captured["body"]["input"] == {
        "image": "https://replicate.delivery/out.png",
        "scale": 8,
        "face_enhance": False,
    }
    assert result == {"image_url": "https://replicate.delivery/upscaled.png", "prediction_id": "pred-up1"}
    assert captured["timeout"] >= 60


def test_upscale_image_raises_timeout_error_when_the_poll_budget_is_spent():
    def fake_send(request, timeout=30):
        return {"id": "pred-up2", "status": "processing", "output": None}

    clock = iter([0.0, 0.0, 99.0])
    with patch("pipeline.replicate_client.http.send", side_effect=fake_send):
        with pytest.raises(replicate_client.ReplicatePredictionTimeoutError, match="pred-up2"):
            replicate_client.upscale_image(
                "https://replicate.delivery/out.png", api_token="test-token", poll_timeout=10.0,
                sleep_fn=lambda _: None, time_fn=lambda: next(clock),
            )


def test_upscale_image_api_token_defaults_to_env_var(monkeypatch):
    monkeypatch.setenv("REPLICATE_API_TOKEN", "env-token")
    captured = {}

    def fake_send(request, timeout=30):
        captured["auth_header"] = request.get_header("Authorization")
        return {"id": "pred-up3", "status": "succeeded", "output": ["https://replicate.delivery/upscaled2.png"]}

    with patch("pipeline.replicate_client.http.send", side_effect=fake_send):
        replicate_client.upscale_image("https://replicate.delivery/out.png")

    assert captured["auth_header"] == "Bearer env-token"


# R2-d (docs/2026-07-21-generation-quality-round2-plan.md, FM-6): typed 429 handling.
def test_generate_image_raises_typed_throttle_error_on_429_honoring_retry_after_header():
    def fake_send(request, timeout=30):
        raise http.HTTPError(429, "rate limited", headers={"Retry-After": "23"})

    with patch("pipeline.replicate_client.http.send", side_effect=fake_send):
        with pytest.raises(replicate_client.ReplicateThrottledError) as exc_info:
            replicate_client.generate_image("a prompt", api_token="test-token")

    assert exc_info.value.retry_after == 23.0
    assert "429" in str(exc_info.value)
    assert "payment method" in str(exc_info.value)


def test_generate_image_throttle_error_falls_back_when_no_retry_after_header():
    def fake_send(request, timeout=30):
        raise http.HTTPError(429, "rate limited", headers={})

    with patch("pipeline.replicate_client.http.send", side_effect=fake_send):
        with pytest.raises(replicate_client.ReplicateThrottledError) as exc_info:
            replicate_client.generate_image("a prompt", api_token="test-token")

    assert exc_info.value.retry_after == replicate_client._DEFAULT_THROTTLE_RETRY_AFTER_SECONDS


def test_generate_image_non_429_http_error_is_not_wrapped_as_throttle_error():
    def fake_send(request, timeout=30):
        raise http.HTTPError(500, "server error", headers={})

    with patch("pipeline.replicate_client.http.send", side_effect=fake_send):
        with pytest.raises(http.HTTPError) as exc_info:
            replicate_client.generate_image("a prompt", api_token="test-token")

    assert exc_info.value.status_code == 500


def test_timeout_error_text_does_not_speculate_generic_throttling():
    # R2-d: the misleading "outage or throttling, not a pipeline bug" text is
    # replaced - throttling is now a distinct typed error (429), so a genuine
    # non-succeeded status should read as an outage, not a re-guess at throttling.
    def fake_send(request, timeout=30):
        return {"id": "pred999", "status": "processing", "output": None}

    clock = iter([0.0, 0.0, 99.0])
    with patch("pipeline.replicate_client.http.send", side_effect=fake_send):
        with pytest.raises(replicate_client.ReplicatePredictionTimeoutError) as exc_info:
            replicate_client.generate_image(
                "a prompt", api_token="test-token", poll_timeout=10.0,
                sleep_fn=lambda _: None, time_fn=lambda: next(clock),
            )

    message = str(exc_info.value)
    assert "stall" in message.lower()
    assert "rate cap" in message.lower() or "ReplicateThrottledError" in message
