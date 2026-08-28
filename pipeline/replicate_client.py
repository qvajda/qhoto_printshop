import base64
import json
import time
import urllib.request

import pipeline.config as config
import pipeline.http as http

FLUX_SCHNELL_MODEL = "black-forest-labs/flux-schnell"  # never substitute flux-dev without explicitly flagging it

# ADR-0008: scene generation is a separate concern from artwork generation and is
# not bound to the schnell licence. Every output carries a SynthID watermark.
NANO_BANANA_PRO_MODEL = "google/nano-banana-pro"

REPLICATE_API_BASE = "https://api.replicate.com/v1/models"


class ReplicatePredictionTimeoutError(Exception):
    pass


# R2-d (docs/2026-07-21-generation-quality-round2-plan.md, FM-6): round 1
# misdiagnosed a 6/min throttle as low balance. Replicate's docs state the
# real cause: an account with granted credit and no payment method on file
# is capped at 1 request/second, 6 requests/minute (replicate.com/docs/
# topics/predictions/rate-limits) - this is a HARD documented cap, not a
# generic "outage or throttling" the old _predict error text speculated.
# The fix is primarily an owner account action (add a payment method /
# enable auto-reload); this typed error exists so callers can tell a 429
# apart from a real timeout/outage and so pacing logic has something to
# catch and back off on.
_DEFAULT_THROTTLE_RETRY_AFTER_SECONDS = 10.0  # 6/min cap -> ~10s min safe gap


class ReplicateThrottledError(Exception):
    """Raised on HTTP 429. `retry_after` is the seconds to wait before the
    next call - taken from Replicate's `Retry-After` response header when
    present, else a sane fallback consistent with the documented 6/min cap."""

    def __init__(self, retry_after: float = None):
        self.retry_after = (
            retry_after if retry_after is not None else _DEFAULT_THROTTLE_RETRY_AFTER_SECONDS
        )
        super().__init__(
            "Replicate rate limit hit (HTTP 429): accounts with granted credit and no "
            "payment method on file are capped at 1 request/second, 6 requests/minute "
            "(replicate.com/docs/topics/predictions/rate-limits). This is not a generic "
            "outage - add a payment method or enable credit auto-reload to lift the cap. "
            f"Retry after {self.retry_after}s."
        )


def _parse_retry_after(headers: dict) -> float:
    """Case-insensitive lookup - httpx preserves the header's original casing
    when converted to a plain dict. Returns None if absent or unparseable."""
    for key, value in (headers or {}).items():
        if key.lower() == "retry-after":
            try:
                return float(value)
            except (TypeError, ValueError):
                return None
    return None


UPSCALE_MODEL = "nightmareai/real-esrgan"  # pure super-resolution GAN, no diffusion/hallucinated
# content - safer for compliance than a diffusion-based upscaler. scale=8 lifts the 832x1216 FLUX
# master to 6656x9728 (~285 DPI at A1, the largest offered size), clearing Gelato's 150 DPI poster
# minimum with margin; scale=4 (3328x4864) only reached ~142 DPI at A1 (B5). Task 10 verifies
# Replicate accepts scale=8 at this input size live before the E2E burns a candidate on it.


# GL-59: the old synchronous "Prefer: wait" window gave up at 60s counting QUEUE time,
# so candidates 78 and 83 raised a timeout on predictions Replicate's own dashboard
# showed executing in 2.8s and 3.7s - queued behind the 6/min cap, then finishing into
# nobody listening. Submit + poll instead: queue time no longer counts against a
# latency budget, and a real timeout now means the job genuinely never terminated.
PREDICTION_POLL_TIMEOUT_SECONDS = 600.0
PREDICTION_POLL_INTERVAL_SECONDS = 2.0
_TERMINAL_STATUSES = ("succeeded", "failed", "canceled")


class ReplicatePredictionFailedError(Exception):
    """Replicate itself reported the prediction failed/canceled - a terminal answer,
    not a timeout. Distinct from ReplicatePredictionTimeoutError so the next reader
    does not go looking for a slow network."""


def _send(request):
    """Shared 429 -> ReplicateThrottledError translation. A rate-cap 429 is NOT a
    timeout and must never be reported as one."""
    try:
        return http.send(request, timeout=65)
    except http.HTTPError as exc:
        if exc.status_code == 429:
            raise ReplicateThrottledError(retry_after=_parse_retry_after(exc.headers)) from exc
        raise


def _predict(model: str, input_body: dict, *, api_token: str,
             poll_timeout: float = None, poll_interval: float = None,
             sleep_fn=time.sleep, time_fn=time.monotonic) -> dict:
    poll_timeout = PREDICTION_POLL_TIMEOUT_SECONDS if poll_timeout is None else poll_timeout
    poll_interval = PREDICTION_POLL_INTERVAL_SECONDS if poll_interval is None else poll_interval
    auth_headers = {"Authorization": f"Bearer {api_token}"}

    url = f"{REPLICATE_API_BASE}/{model}/predictions"
    body = json.dumps({"input": input_body}).encode("utf-8")
    result = _send(urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json", **auth_headers},
        method="POST",
    ))

    deadline = time_fn() + poll_timeout
    while result.get("status") not in _TERMINAL_STATUSES:
        if time_fn() >= deadline:
            raise ReplicatePredictionTimeoutError(
                f"Replicate prediction {result.get('id')} on {model} was still "
                f"{result.get('status')!r} after polling for {poll_timeout:.0f}s. This is not "
                f"the granted-credit rate cap (that raises HTTP 429 as ReplicateThrottledError) "
                f"and not a queue wait (queue time no longer counts against this budget) - it "
                f"indicates a genuine Replicate-side stall."
            )
        sleep_fn(poll_interval)
        poll_url = (result.get("urls") or {}).get("get") or f"https://api.replicate.com/v1/predictions/{result['id']}"
        result = _send(urllib.request.Request(poll_url, headers=auth_headers, method="GET"))

    if result["status"] != "succeeded":
        raise ReplicatePredictionFailedError(
            f"Replicate prediction {result.get('id')} on {model} ended {result['status']}: "
            f"{result.get('error')}"
        )

    output = result["output"]
    image_url = output[0] if isinstance(output, list) else output
    return {"image_url": image_url, "prediction_id": result["id"], "raw": result}


def generate_image(prompt: str, *, api_token: str = None, **poll_kwargs) -> dict:
    api_token = api_token or config.require_env("REPLICATE_API_TOKEN")
    return _predict(
        FLUX_SCHNELL_MODEL,
        {"prompt": prompt, "aspect_ratio": "2:3", "megapixels": "1"},
        api_token=api_token, **poll_kwargs,
    )


def _encode_reference_image(image: str) -> str:
    """Local geometry-card paths become base64 data URIs (they're ~17KB, well inside
    Replicate's practical body-size limit - no upload endpoint or host needed).
    https:// entries pass through untouched."""
    if image.startswith(("http://", "https://")):
        return image
    with open(image, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def generate_scene(prompt: str, reference_images: list, *, api_token: str = None, **poll_kwargs) -> dict:
    api_token = api_token or config.require_env("REPLICATE_API_TOKEN")
    return _predict(
        NANO_BANANA_PRO_MODEL,
        {"prompt": prompt, "image_input": [_encode_reference_image(img) for img in reference_images]},
        api_token=api_token, **poll_kwargs,
    )


def upscale_image(image_url: str, *, api_token: str = None, **poll_kwargs) -> dict:
    api_token = api_token or config.require_env("REPLICATE_API_TOKEN")
    return _predict(
        UPSCALE_MODEL,
        {"image": image_url, "scale": 8, "face_enhance": False},
        api_token=api_token, **poll_kwargs,
    )
