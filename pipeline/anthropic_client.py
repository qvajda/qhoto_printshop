import json
import urllib.request

import pipeline.config as config
import pipeline.http as http

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
