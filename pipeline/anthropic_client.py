import json
import re
import urllib.request

import pipeline.config as config
import pipeline.http as http

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


def complete_with_images(prompt: str, image_urls: list, *, api_key: str = None, max_tokens: int = 1024) -> dict:
    api_key = api_key or config.require_env("ANTHROPIC_API_KEY")
    content = [
        {"type": "image", "source": {"type": "url", "url": image_url}}
        for image_url in image_urls
    ]
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
