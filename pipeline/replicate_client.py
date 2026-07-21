import json
import urllib.request

import pipeline.config as config
import pipeline.http as http

FLUX_SCHNELL_MODEL = "black-forest-labs/flux-schnell"  # never substitute flux-dev without explicitly flagging it

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


def _predict(model: str, input_body: dict, *, api_token: str) -> dict:
    url = f"{REPLICATE_API_BASE}/{model}/predictions"
    body = json.dumps({"input": input_body}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_token}",
            "Prefer": "wait",
        },
        method="POST",
    )
    # The 60s "Prefer: wait" window (timeout=65 for HTTP overhead) was sized for FLUX
    # schnell's typical 1-2s generate latency. real-esrgan's actual latency - especially
    # a cold boot - hasn't been measured against it; if upscale calls routinely exceed
    # this window, they'll need either a longer timeout or a polling fallback instead of
    # synchronous "Prefer: wait".
    try:
        result = http.send(request, timeout=65)
    except http.HTTPError as exc:
        if exc.status_code == 429:
            raise ReplicateThrottledError(retry_after=_parse_retry_after(exc.headers)) from exc
        raise

    if result.get("status") != "succeeded":
        raise ReplicatePredictionTimeoutError(
            f"Replicate prediction {result.get('id')} on {model} did not complete within "
            f"the 60s synchronous wait window (status: {result.get('status')}). This is not "
            f"the granted-credit rate cap (that raises HTTP 429 as ReplicateThrottledError) - "
            f"it likely indicates a genuine Replicate-side outage, not a pipeline bug."
        )

    output = result["output"]
    image_url = output[0] if isinstance(output, list) else output
    return {"image_url": image_url, "prediction_id": result["id"]}


def generate_image(prompt: str, *, api_token: str = None) -> dict:
    api_token = api_token or config.require_env("REPLICATE_API_TOKEN")
    return _predict(
        FLUX_SCHNELL_MODEL,
        {"prompt": prompt, "aspect_ratio": "2:3", "megapixels": "1"},
        api_token=api_token,
    )


def upscale_image(image_url: str, *, api_token: str = None) -> dict:
    api_token = api_token or config.require_env("REPLICATE_API_TOKEN")
    return _predict(
        UPSCALE_MODEL,
        {"image": image_url, "scale": 8, "face_enhance": False},
        api_token=api_token,
    )
