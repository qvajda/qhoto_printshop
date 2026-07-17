import base64
import io
import json
import re
import urllib.error
import urllib.request

from PIL import Image

import pipeline.config as config
import pipeline.http as http

# Anthropic rejects URL-fetched images over 5MB outright ("Unable to download the
# file") - hit live 2026-07-17 with a ~6.9MB raw Replicate generation output used as
# a group-critic image fallback.
MAX_IMAGE_URL_BYTES = 5 * 1024 * 1024

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


def parse_json_response(text: str) -> dict:
    """Parse a Claude text response as JSON, tolerating a ```json ... ``` fence
    around it - despite "no other text" instructions, the model wraps its
    answer in a markdown fence often enough that a bare json.loads is unreliable."""
    match = _JSON_FENCE_RE.match(text.strip())
    return json.loads(match.group(1) if match else text)

ANTHROPIC_API_BASE = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VERSION = "2023-06-01"
ANTHROPIC_MODEL = "claude-sonnet-5"
# UNVERIFIED against a live call as of 2026-07-08 - see this module's design doc
# (docs/superpowers/plans/2026-07-08-research-stage.md, Task 3) for the required
# manual verification step before this is trusted for a real M1 run.
WEB_SEARCH_TOOL_TYPE = "web_search_20250305"


def _headers(api_key: str) -> dict:
    return {
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_API_VERSION,
        "content-type": "application/json",
    }


def research_web_search(prompt: str, *, api_key: str = None, max_tokens: int = 2048) -> dict:
    api_key = api_key or config.require_env("ANTHROPIC_API_KEY")
    body = json.dumps({
        "model": ANTHROPIC_MODEL,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
        "tools": [{"type": WEB_SEARCH_TOOL_TYPE, "name": "web_search", "max_uses": 5}],
    }).encode("utf-8")
    request = urllib.request.Request(ANTHROPIC_API_BASE, data=body, headers=_headers(api_key), method="POST")
    result = http.send(request, timeout=60)
    text_blocks = [block["text"] for block in result.get("content", []) if block.get("type") == "text"]
    return {"text": "\n".join(text_blocks), "raw": result}


def complete(prompt: str, *, api_key: str = None, max_tokens: int = 1024) -> dict:
    api_key = api_key or config.require_env("ANTHROPIC_API_KEY")
    body = json.dumps({
        "model": ANTHROPIC_MODEL,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")
    request = urllib.request.Request(ANTHROPIC_API_BASE, data=body, headers=_headers(api_key), method="POST")
    result = http.send(request, timeout=60)
    text_blocks = [block["text"] for block in result.get("content", []) if block.get("type") == "text"]
    return {"text": "\n".join(text_blocks), "raw": result}


def _downscaled_base64_block(raw: bytes) -> dict:
    image = Image.open(io.BytesIO(raw)).convert("RGB")
    image.thumbnail((2000, 2000))
    quality = 85
    while True:
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=quality)
        if buffer.tell() <= MAX_IMAGE_URL_BYTES or quality <= 20:
            break
        quality -= 15
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": "image/jpeg",
            "data": base64.b64encode(buffer.getvalue()).decode("ascii"),
        },
    }


def _image_content_block(image_url: str) -> dict:
    if not image_url.startswith(("http://", "https://")):
        # Locally cover-cropped preview (pipeline.image_crop) - no public URL exists
        # for it, so it's always sent as base64.
        with open(image_url, "rb") as f:
            return _downscaled_base64_block(f.read())

    try:
        head = urllib.request.urlopen(urllib.request.Request(image_url, method="HEAD"), timeout=10)
        content_length = int(head.headers.get("Content-Length") or 0)
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError):
        content_length = 0

    if 0 < content_length <= MAX_IMAGE_URL_BYTES:
        return {"type": "image", "source": {"type": "url", "url": image_url}}
    raw = urllib.request.urlopen(urllib.request.Request(image_url), timeout=30).read()
    return _downscaled_base64_block(raw)


def complete_with_images(prompt: str, image_urls: list, *, api_key: str = None, max_tokens: int = 1024) -> dict:
    api_key = api_key or config.require_env("ANTHROPIC_API_KEY")
    content = [_image_content_block(image_url) for image_url in image_urls]
    content.append({"type": "text", "text": prompt})
    body = json.dumps({
        "model": ANTHROPIC_MODEL,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": content}],
    }).encode("utf-8")
    request = urllib.request.Request(ANTHROPIC_API_BASE, data=body, headers=_headers(api_key), method="POST")
    result = http.send(request, timeout=60)
    text_blocks = [block["text"] for block in result.get("content", []) if block.get("type") == "text"]
    return {"text": "\n".join(text_blocks), "raw": result}
