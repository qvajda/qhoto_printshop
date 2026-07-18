import json
import urllib.request

import pipeline.config as config
import pipeline.http as http

FLUX_SCHNELL_MODEL = "black-forest-labs/flux-schnell"  # never substitute flux-dev without explicitly flagging it

REPLICATE_API_BASE = "https://api.replicate.com/v1/models"


class ReplicatePredictionTimeoutError(Exception):
    pass


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
    result = http.send(request, timeout=65)

    if result.get("status") != "succeeded":
        raise ReplicatePredictionTimeoutError(
            f"Replicate prediction {result.get('id')} on {model} did not complete within "
            f"the 60s synchronous wait window (status: {result.get('status')}). This likely "
            f"indicates a Replicate-side outage or throttling, not a pipeline bug."
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
