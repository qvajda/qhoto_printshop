import base64
import io
import json
import logging
import re

import anthropic
from PIL import Image

import pipeline.config as config
import pipeline.http as http

logger = logging.getLogger(__name__)

# Anthropic rejects URL-fetched images over 5MB outright ("Unable to download the
# file") - hit live 2026-07-17 with a ~6.9MB raw Replicate generation output used as
# a group-critic image fallback.
MAX_IMAGE_URL_BYTES = 5 * 1024 * 1024

# pause_turn can legally repeat on a long tool-use turn; cap continuations so a
# stuck turn fails loudly instead of looping forever.
_MAX_PAUSE_TURN_CONTINUATIONS = 5

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)

ANTHROPIC_MODEL = "claude-sonnet-5"
# Cheap-tier model for calls that don't need Sonnet's full reasoning (S4-b's art-brief
# text call, S4-d's single-image sanity pre-filter) - both were built against complete()/
# complete_with_images() before those functions could pick a model, so they silently rode
# Sonnet; wired here at fan-in via the new `model` param on both functions.
HAIKU_MODEL = "claude-haiku-4-5-20251001"
# Verified 2026-07-21 against the installed `anthropic` SDK's shipped type defs
# (anthropic.types.web_search_tool_20250305_param.WebSearchTool20250305Param and
# anthropic.types.stop_reason.StopReason) - this clears the standing UNVERIFIED
# marker: "web_search_20250305" is still a valid, current tool type (newer dated
# variants exist - 20260209, 20260318 - but 20250305 has not been removed), and
# "pause_turn" is a real StopReason meaning "we paused a long-running turn; you
# may provide the response back as-is in a subsequent request to let the model
# continue" - i.e. resend the returned content as an assistant turn to continue.
WEB_SEARCH_TOOL_TYPE = "web_search_20250305"


class NoTextContentError(RuntimeError):
    """A successful Anthropic response had zero text blocks (e.g. a tool-only
    turn that ended without ever producing text). This is a domain invariant
    the SDK has no opinion on - it can't know callers here always want text."""

    def __init__(self, block_types: list):
        self.block_types = block_types
        super().__init__(f"Anthropic response had no text content blocks (got: {block_types!r})")


class TruncatedResponseError(RuntimeError):
    """stop_reason == 'max_tokens': the response was cut off mid-generation.
    Actionable (raise the max_tokens cap), not a transport failure the SDK's
    own retry logic could have fixed by retrying."""

    def __init__(self, max_tokens):
        super().__init__(f"Anthropic response truncated at max_tokens={max_tokens}; raise the cap")


class MalformedJSONError(ValueError):
    """parse_json_response's text wasn't valid JSON. Subclasses ValueError so
    existing `except ValueError` retry loops (e.g. compliance_draft) keep
    working unchanged - a malformed-JSON model response is exactly the kind
    of thing worth feeding back as retry feedback."""

    def __init__(self, text: str, cause: Exception):
        self.snippet = text[:200]
        super().__init__(f"Anthropic response was not valid JSON: {self.snippet!r}")
        self.__cause__ = cause


def parse_json_response(text: str) -> dict:
    """Parse a Claude text response as JSON, tolerating a ```json ... ``` fence
    around it - despite "no other text" instructions, the model wraps its
    answer in a markdown fence often enough that a bare json.loads is unreliable."""
    match = _JSON_FENCE_RE.match(text.strip())
    candidate = match.group(1) if match else text
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise MalformedJSONError(text, exc) from exc


def _client(api_key: str = None) -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=api_key or config.require_env("ANTHROPIC_API_KEY"))


def _log_call(message) -> None:
    usage = message.usage
    logger.info(
        "anthropic call request_id=%s stop_reason=%s input_tokens=%s output_tokens=%s",
        getattr(message, "_request_id", None), message.stop_reason,
        usage.input_tokens, usage.output_tokens,
    )


def _serialize_content(blocks: list) -> list:
    return [block.model_dump(exclude_unset=True) if hasattr(block, "model_dump") else block for block in blocks]


def _create_message(client, **params):
    """Call messages.create, transparently continuing a paused long-running
    turn (stop_reason == 'pause_turn') per API docs: resend the prior
    response's content back as an assistant turn to let the model continue."""
    messages = list(params.pop("messages"))
    message = None
    for _ in range(_MAX_PAUSE_TURN_CONTINUATIONS):
        message = client.messages.create(messages=messages, **params)
        _log_call(message)
        if message.stop_reason != "pause_turn":
            return message
        messages = messages + [{"role": "assistant", "content": _serialize_content(message.content)}]
    return message


def _send_message(client, **params) -> dict:
    message = _create_message(client, **params)
    if message.stop_reason == "max_tokens":
        raise TruncatedResponseError(params.get("max_tokens"))
    text_blocks = [block.text for block in message.content if getattr(block, "type", None) == "text"]
    if not text_blocks:
        raise NoTextContentError([getattr(block, "type", None) for block in message.content])
    return {"text": "\n".join(text_blocks), "raw": message}


def research_web_search(prompt: str, *, api_key: str = None, max_tokens: int = 2048) -> dict:
    client = _client(api_key)
    return _send_message(
        client,
        model=ANTHROPIC_MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
        tools=[{"type": WEB_SEARCH_TOOL_TYPE, "name": "web_search", "max_uses": 5}],
    )


def complete(prompt: str, *, api_key: str = None, max_tokens: int = 1024, model: str = None) -> dict:
    client = _client(api_key)
    return _send_message(
        client,
        model=model or ANTHROPIC_MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )


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
        head = http.head(image_url, timeout=10)
        content_length = int(head.headers.get("Content-Length") or 0)
    except (http.HTTPError, ValueError):
        content_length = 0

    if 0 < content_length <= MAX_IMAGE_URL_BYTES:
        return {"type": "image", "source": {"type": "url", "url": image_url}}
    raw = http.fetch_bytes(image_url)
    return _downscaled_base64_block(raw)


def complete_with_images(prompt: str, image_urls: list, *, api_key: str = None, max_tokens: int = 1024,
                          model: str = None) -> dict:
    client = _client(api_key)
    content = [_image_content_block(image_url) for image_url in image_urls]
    content.append({"type": "text", "text": prompt})
    return _send_message(
        client,
        model=model or ANTHROPIC_MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": content}],
    )
