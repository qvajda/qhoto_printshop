import json
import urllib.request

import pipeline.config as config
import pipeline.http as http

FLUX_SCHNELL_MODEL = "black-forest-labs/flux-schnell"  # never substitute flux-dev without explicitly flagging it

REPLICATE_API_BASE = "https://api.replicate.com/v1/models"


class ReplicatePredictionTimeoutError(Exception):
    pass


def generate_image(prompt: str, *, api_token: str = None) -> dict:
    api_token = api_token or config.require_env("REPLICATE_API_TOKEN")
    url = f"{REPLICATE_API_BASE}/{FLUX_SCHNELL_MODEL}/predictions"
    body = json.dumps({
        "input": {"prompt": prompt, "aspect_ratio": "2:3", "megapixels": "1"}
    }).encode("utf-8")
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
    result = http.send(request, timeout=65)

    if result.get("status") != "succeeded":
        raise ReplicatePredictionTimeoutError(
            f"Replicate prediction {result.get('id')} did not complete within the "
            f"60s synchronous wait window (status: {result.get('status')}). FLUX.1 "
            f"schnell normally finishes in 1-2s — this likely indicates a "
            f"Replicate-side outage or throttling, not a pipeline bug."
        )

    output = result["output"]
    image_url = output[0] if isinstance(output, list) else output
    return {"image_url": image_url, "prediction_id": result["id"]}
