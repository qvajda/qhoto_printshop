# API Client Wrappers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the four thin HTTP client wrappers (`telegram_client.py`, `replicate_client.py`, `gelato_client.py`, `etsy_client.py`) that future pipeline stage modules will call into, plus the shared transport helper and config-schema change they depend on.

**Architecture:** One shared stdlib-`urllib` transport seam (`pipeline/http.py`), one config-schema update to carry Gelato's per-template variant/placeholder IDs and a per-service live-mode flag (`pipeline/config.py`, `config/static_config.json`), then four independent client modules built on top. Gelato and Etsy calls that mutate remote state (`create_product_from_template`, `delete_product`, `create_draft_listing`, `upload_listing_image`) default to a fail-closed dry-run mode controlled by a per-service `.env` flag.

**Tech Stack:** Python 3, stdlib `urllib.request`/`urllib.error`/`json` (no `requests`), `pytest`, `unittest.mock`.

Full design rationale: `docs/superpowers/specs/2026-07-08-api-client-wrappers-design.md`.

## Global Constraints

These apply project-wide, not just to this plan's six tasks:
- Image generation: Replicate + FLUX.1 `schnell` only (`FLUX_SCHNELL_MODEL = "black-forest-labs/flux-schnell"`). Never substitute FLUX.1 `dev` without explicitly raising it first — different commercial license.
- Runtime is discrete scheduled functions on two cron cadences — not a persistent service, not one agent loop. These four modules are not pipeline stages; they have no retry/orchestration policy of their own.
- Critic-pass retry cap is exactly 3 attempts per group, then abandon that group: log `failed`, `DELETE` its Gelato product(s) via `gelato_client.delete_product`. Not implemented in this plan — these are the wrappers a future `critic_pass.py`/`group_critic_pass.py` will call.
- Telegram digest = `sendMediaGroup` + separate `sendMessage`, never combined — `telegram_client.py` exposes them as two distinct functions for exactly this reason.
- Static configuration (Gelato template IDs, Etsy `taxonomy_id`/`shipping_profile_id`/`production_partner_ids`/`who_made`, Telegram admin ID) is resolved once and read from config — never discovered dynamically at runtime. `gelato_client.get_template()` is the one exception: a real Gelato endpoint wrapper, but only ever invoked manually when resolving a new template's metadata by hand, never called by a pipeline stage.
- **Placeholder policy:** a still-placeholder `template_id`, `template_variant_id`, or `image_placeholder_name` reaching a real (non-mocked, non-dry-run) `create_product_from_template` call must fail loudly — never silently skip or proceed with a fake ID.
- **Never call Etsy publish or Gelato product-create against real endpoints without an explicit go-ahead.** Implemented here as fail-closed per-service live-mode flags (`GELATO_LIVE_MODE`, `ETSY_LIVE_MODE` — absent or anything other than the literal string `"true"` means dry-run).
- Telegram admin/allowlist user ID and all API credentials are read from `.env` (git-ignored), never hardcoded in source.
- Follow `pipeline/config.py`'s existing conventions: plain module-level functions (no classes for config/client state), explicit params with sane `None`-defaulting-to-`require_env(...)` behavior, stdlib only.

---

## Task 1: Shared HTTP transport (`pipeline/http.py`)

**Files:**
- Create: `pipeline/http.py`
- Test: `tests/test_http.py`

**Interfaces:**
- Consumes: nothing (foundation for all four clients).
- Produces: `pipeline.http.HTTPError(status_code: int, body: str)` (exception), `pipeline.http.send(request: urllib.request.Request, timeout: int = 30) -> dict`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_http.py`:

```python
import io
import urllib.error
import urllib.request
from unittest.mock import MagicMock, patch

import pytest

import pipeline.http as http


def _mock_response(body: bytes):
    mock_resp = MagicMock()
    mock_resp.read.return_value = body
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False
    return mock_resp


def test_send_returns_parsed_json_on_success():
    request = urllib.request.Request("https://example.com/api")

    with patch("urllib.request.urlopen", return_value=_mock_response(b'{"ok": true}')) as mock_urlopen:
        result = http.send(request)

    assert result == {"ok": True}
    mock_urlopen.assert_called_once_with(request, timeout=30)


def test_send_returns_empty_dict_on_empty_body():
    request = urllib.request.Request("https://example.com/api")

    with patch("urllib.request.urlopen", return_value=_mock_response(b"")):
        result = http.send(request)

    assert result == {}


def test_send_raises_http_error_on_non_2xx():
    request = urllib.request.Request("https://example.com/api")
    error = urllib.error.HTTPError(
        url="https://example.com/api", code=400, msg="Bad Request",
        hdrs=None, fp=io.BytesIO(b'{"error": "bad input"}'),
    )

    with patch("urllib.request.urlopen", side_effect=error):
        with pytest.raises(http.HTTPError) as exc_info:
            http.send(request)

    assert exc_info.value.status_code == 400
    assert "bad input" in exc_info.value.body


def test_send_respects_custom_timeout():
    request = urllib.request.Request("https://example.com/api")

    with patch("urllib.request.urlopen", return_value=_mock_response(b"{}")) as mock_urlopen:
        http.send(request, timeout=5)

    mock_urlopen.assert_called_once_with(request, timeout=5)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_http.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.http'`

- [ ] **Step 3: Write `pipeline/http.py`**

```python
import json
import urllib.error
import urllib.request


class HTTPError(Exception):
    def __init__(self, status_code: int, body: str):
        self.status_code = status_code
        self.body = body
        super().__init__(f"HTTP {status_code}: {body}")


def send(request: urllib.request.Request, timeout: int = 30) -> dict:
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw_body = response.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        raise HTTPError(e.code, e.read().decode("utf-8")) from e

    if not raw_body:
        return {}
    return json.loads(raw_body)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_http.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add pipeline/http.py tests/test_http.py
git commit -m "feat: add shared stdlib HTTP transport helper"
```

---

## Task 2: Config schema change — Gelato template metadata + live-mode flag

**Files:**
- Modify: `config/static_config.json`
- Modify: `pipeline/config.py:49-51`
- Modify: `tests/test_config.py`

**Interfaces:**
- Consumes: nothing new (extends the existing foundation-layer config module).
- Produces: `pipeline.config.get_template_variant(static_config: dict, size: str, orientation: str) -> dict` (returns `{"template_id": ..., "template_variant_id": ..., "image_placeholder_name": ...}`), `pipeline.config.is_live_mode(service: str) -> bool`. `pipeline.config.get_template_id` keeps its existing name/signature/return type (`str`) but now reads the nested `template_id` field.

- [ ] **Step 1: Update the failing/changed tests first**

Replace the three affected tests in `tests/test_config.py` (currently at lines 68-90) with:

```python
def test_get_template_id_returns_configured_value():
    static_config = {
        "gelato_templates": {
            "8x12_portrait": {
                "template_id": "tpl_real_abc123",
                "template_variant_id": "variant_real_456",
                "image_placeholder_name": "real_image_slot.jpg",
            }
        }
    }

    result = config.get_template_id(static_config, "8x12", "portrait")

    assert result == "tpl_real_abc123"


def test_get_template_id_raises_on_unknown_size_orientation():
    static_config = {
        "gelato_templates": {
            "8x12_portrait": {
                "template_id": "tpl_real_abc123",
                "template_variant_id": "variant_real_456",
                "image_placeholder_name": "real_image_slot.jpg",
            }
        }
    }

    with pytest.raises(KeyError):
        config.get_template_id(static_config, "5x7", "landscape")


def test_get_template_variant_returns_full_entry():
    static_config = {
        "gelato_templates": {
            "8x12_portrait": {
                "template_id": "tpl_real_abc123",
                "template_variant_id": "variant_real_456",
                "image_placeholder_name": "real_image_slot.jpg",
            }
        }
    }

    result = config.get_template_variant(static_config, "8x12", "portrait")

    assert result == {
        "template_id": "tpl_real_abc123",
        "template_variant_id": "variant_real_456",
        "image_placeholder_name": "real_image_slot.jpg",
    }


def test_get_template_variant_raises_on_unknown_size_orientation():
    static_config = {
        "gelato_templates": {
            "8x12_portrait": {
                "template_id": "tpl_real_abc123",
                "template_variant_id": "variant_real_456",
                "image_placeholder_name": "real_image_slot.jpg",
            }
        }
    }

    with pytest.raises(KeyError):
        config.get_template_variant(static_config, "5x7", "landscape")


def test_repo_static_config_has_all_twelve_template_slots_with_full_metadata():
    static_config = config.load_static_config()

    sizes = ["5x7", "8x12", "A3", "A2", "10x24", "A1"]
    for size in sizes:
        for orientation in ("portrait", "landscape"):
            key = f"{size}_{orientation}"
            entry = static_config["gelato_templates"][key]
            assert "template_id" in entry
            assert "template_variant_id" in entry
            assert "image_placeholder_name" in entry


def test_is_live_mode_false_when_env_var_unset(monkeypatch):
    monkeypatch.delenv("QHOTOTEST_LIVE_MODE", raising=False)

    assert config.is_live_mode("QHOTOTEST") is False


def test_is_live_mode_false_when_env_var_not_exactly_true(monkeypatch):
    monkeypatch.setenv("QHOTOTEST_LIVE_MODE", "1")

    assert config.is_live_mode("QHOTOTEST") is False


def test_is_live_mode_true_when_env_var_is_exactly_true(monkeypatch):
    monkeypatch.setenv("QHOTOTEST_LIVE_MODE", "true")

    assert config.is_live_mode("QHOTOTEST") is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_config.py -v`
Expected: FAIL — `test_get_template_id_returns_configured_value` and its sibling now fail because `get_template_id` doesn't read the nested shape yet; `get_template_variant`/`is_live_mode` fail with `AttributeError: module 'pipeline.config' has no attribute ...`; `test_repo_static_config_has_all_twelve_template_slots_with_full_metadata` fails because the repo's `static_config.json` doesn't have the nested shape yet.

- [ ] **Step 3: Update `config/static_config.json`**

Replace the `gelato_templates` block (lines 2-15) with:

```json
{
  "gelato_templates": {
    "5x7_portrait": {
      "template_id": "PLACEHOLDER_5x7_PORTRAIT",
      "template_variant_id": "PLACEHOLDER_5x7_PORTRAIT_VARIANT",
      "image_placeholder_name": "PLACEHOLDER_5x7_PORTRAIT_IMAGE_SLOT"
    },
    "5x7_landscape": {
      "template_id": "PLACEHOLDER_5x7_LANDSCAPE",
      "template_variant_id": "PLACEHOLDER_5x7_LANDSCAPE_VARIANT",
      "image_placeholder_name": "PLACEHOLDER_5x7_LANDSCAPE_IMAGE_SLOT"
    },
    "8x12_portrait": {
      "template_id": "PLACEHOLDER_8x12_PORTRAIT",
      "template_variant_id": "PLACEHOLDER_8x12_PORTRAIT_VARIANT",
      "image_placeholder_name": "PLACEHOLDER_8x12_PORTRAIT_IMAGE_SLOT"
    },
    "8x12_landscape": {
      "template_id": "PLACEHOLDER_8x12_LANDSCAPE",
      "template_variant_id": "PLACEHOLDER_8x12_LANDSCAPE_VARIANT",
      "image_placeholder_name": "PLACEHOLDER_8x12_LANDSCAPE_IMAGE_SLOT"
    },
    "A3_portrait": {
      "template_id": "PLACEHOLDER_A3_PORTRAIT",
      "template_variant_id": "PLACEHOLDER_A3_PORTRAIT_VARIANT",
      "image_placeholder_name": "PLACEHOLDER_A3_PORTRAIT_IMAGE_SLOT"
    },
    "A3_landscape": {
      "template_id": "PLACEHOLDER_A3_LANDSCAPE",
      "template_variant_id": "PLACEHOLDER_A3_LANDSCAPE_VARIANT",
      "image_placeholder_name": "PLACEHOLDER_A3_LANDSCAPE_IMAGE_SLOT"
    },
    "A2_portrait": {
      "template_id": "PLACEHOLDER_A2_PORTRAIT",
      "template_variant_id": "PLACEHOLDER_A2_PORTRAIT_VARIANT",
      "image_placeholder_name": "PLACEHOLDER_A2_PORTRAIT_IMAGE_SLOT"
    },
    "A2_landscape": {
      "template_id": "PLACEHOLDER_A2_LANDSCAPE",
      "template_variant_id": "PLACEHOLDER_A2_LANDSCAPE_VARIANT",
      "image_placeholder_name": "PLACEHOLDER_A2_LANDSCAPE_IMAGE_SLOT"
    },
    "10x24_portrait": {
      "template_id": "PLACEHOLDER_10x24_PORTRAIT",
      "template_variant_id": "PLACEHOLDER_10x24_PORTRAIT_VARIANT",
      "image_placeholder_name": "PLACEHOLDER_10x24_PORTRAIT_IMAGE_SLOT"
    },
    "10x24_landscape": {
      "template_id": "PLACEHOLDER_10x24_LANDSCAPE",
      "template_variant_id": "PLACEHOLDER_10x24_LANDSCAPE_VARIANT",
      "image_placeholder_name": "PLACEHOLDER_10x24_LANDSCAPE_IMAGE_SLOT"
    },
    "A1_portrait": {
      "template_id": "PLACEHOLDER_A1_PORTRAIT",
      "template_variant_id": "PLACEHOLDER_A1_PORTRAIT_VARIANT",
      "image_placeholder_name": "PLACEHOLDER_A1_PORTRAIT_IMAGE_SLOT"
    },
    "A1_landscape": {
      "template_id": "PLACEHOLDER_A1_LANDSCAPE",
      "template_variant_id": "PLACEHOLDER_A1_LANDSCAPE_VARIANT",
      "image_placeholder_name": "PLACEHOLDER_A1_LANDSCAPE_IMAGE_SLOT"
    }
  },
  "prices_eur": {
    "5x7": 19,
    "8x12": 24,
    "A3": 35,
    "A2": 39,
    "10x24": 45,
    "A1": 49
  },
  "aspect_ratio_groups": {
    "primary": ["8x12", "A3", "A2", "A1"],
    "5x7": ["5x7"],
    "10x24": ["10x24"]
  },
  "primary_size": "8x12",
  "etsy_taxonomy_id": "",
  "etsy_shipping_profile_id": "",
  "etsy_production_partner_ids": [],
  "etsy_who_made": ""
}
```

- [ ] **Step 4: Update `pipeline/config.py`**

Replace lines 49-51 (`get_template_id`) with:

```python
def get_template_id(static_config: dict, size: str, orientation: str) -> str:
    key = f"{size}_{orientation}"
    return static_config["gelato_templates"][key]["template_id"]


def get_template_variant(static_config: dict, size: str, orientation: str) -> dict:
    key = f"{size}_{orientation}"
    return static_config["gelato_templates"][key]


def is_live_mode(service: str) -> bool:
    return os.environ.get(f"{service}_LIVE_MODE") == "true"
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_config.py tests/test_db.py -v`
Expected: PASS (all tests in both files)

- [ ] **Step 6: Commit**

```bash
git add config/static_config.json pipeline/config.py tests/test_config.py
git commit -m "feat: extend Gelato template config with variant/placeholder IDs and add live-mode flag helper"
```

---

## Task 3: `telegram_client.py`

**Files:**
- Create: `pipeline/telegram_client.py`
- Test: `tests/test_telegram_client.py`

**Interfaces:**
- Consumes: `pipeline.http.send` (Task 1), `pipeline.config.require_env` (foundation layer).
- Produces: `pipeline.telegram_client.TelegramAPIError`, `send_media_group(chat_id: str, photo_urls: list[str], *, bot_token: str = None) -> dict`, `send_message(chat_id: str, text: str, reply_markup: dict = None, *, bot_token: str = None) -> dict`, `get_updates(offset: int = None, timeout: int = 0, *, bot_token: str = None) -> list`, `answer_callback_query(callback_query_id: str, text: str = None, *, bot_token: str = None) -> dict`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_telegram_client.py`:

```python
import json
from unittest.mock import patch

import pytest

import pipeline.telegram_client as telegram_client


def test_send_media_group_builds_correct_request_and_parses_response():
    captured = {}

    def fake_send(request, timeout=30):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["body"] = json.loads(request.data)
        return {"ok": True, "result": {"message_id": 1}}

    with patch("pipeline.telegram_client.http.send", side_effect=fake_send):
        result = telegram_client.send_media_group(
            "12345", ["https://example.com/a.jpg", "https://example.com/b.jpg"], bot_token="test-token"
        )

    assert captured["url"] == "https://api.telegram.org/bottest-token/sendMediaGroup"
    assert captured["method"] == "POST"
    assert captured["body"]["chat_id"] == "12345"
    assert captured["body"]["media"] == [
        {"type": "photo", "media": "https://example.com/a.jpg"},
        {"type": "photo", "media": "https://example.com/b.jpg"},
    ]
    assert result == {"ok": True, "result": {"message_id": 1}}


def test_send_message_includes_reply_markup_when_given():
    captured = {}
    keyboard = {"inline_keyboard": [[{"text": "Approve", "callback_data": "approve:1:primary"}]]}

    def fake_send(request, timeout=30):
        captured["body"] = json.loads(request.data)
        return {"ok": True, "result": {"message_id": 2}}

    with patch("pipeline.telegram_client.http.send", side_effect=fake_send):
        telegram_client.send_message("12345", "Draft listing text", keyboard, bot_token="test-token")

    assert captured["body"]["text"] == "Draft listing text"
    assert captured["body"]["reply_markup"] == keyboard


def test_send_message_omits_reply_markup_when_not_given():
    captured = {}

    def fake_send(request, timeout=30):
        captured["body"] = json.loads(request.data)
        return {"ok": True, "result": {"message_id": 3}}

    with patch("pipeline.telegram_client.http.send", side_effect=fake_send):
        telegram_client.send_message("12345", "Just text", bot_token="test-token")

    assert "reply_markup" not in captured["body"]


def test_get_updates_returns_result_list():
    def fake_send(request, timeout=30):
        return {"ok": True, "result": [{"update_id": 1}, {"update_id": 2}]}

    with patch("pipeline.telegram_client.http.send", side_effect=fake_send):
        result = telegram_client.get_updates(bot_token="test-token")

    assert result == [{"update_id": 1}, {"update_id": 2}]


def test_answer_callback_query_sends_callback_id_and_text():
    captured = {}

    def fake_send(request, timeout=30):
        captured["body"] = json.loads(request.data)
        return {"ok": True, "result": True}

    with patch("pipeline.telegram_client.http.send", side_effect=fake_send):
        telegram_client.answer_callback_query("cbq123", "Approved!", bot_token="test-token")

    assert captured["body"]["callback_query_id"] == "cbq123"
    assert captured["body"]["text"] == "Approved!"


def test_raises_telegram_api_error_when_ok_is_false():
    def fake_send(request, timeout=30):
        return {"ok": False, "description": "Bad Request: chat not found"}

    with patch("pipeline.telegram_client.http.send", side_effect=fake_send):
        with pytest.raises(telegram_client.TelegramAPIError, match="chat not found"):
            telegram_client.send_message("bad_chat", "text", bot_token="test-token")


def test_bot_token_defaults_to_env_var(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "env-token")
    captured = {}

    def fake_send(request, timeout=30):
        captured["url"] = request.full_url
        return {"ok": True, "result": {}}

    with patch("pipeline.telegram_client.http.send", side_effect=fake_send):
        telegram_client.send_message("123", "hi")

    assert "env-token" in captured["url"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_telegram_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.telegram_client'`

- [ ] **Step 3: Write `pipeline/telegram_client.py`**

```python
import json
import urllib.request

import pipeline.config as config
import pipeline.http as http

TELEGRAM_API_BASE = "https://api.telegram.org/bot"


class TelegramAPIError(Exception):
    pass


def _post(method: str, payload: dict, bot_token: str) -> dict:
    url = f"{TELEGRAM_API_BASE}{bot_token}/{method}"
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    result = http.send(request)
    if not result.get("ok"):
        raise TelegramAPIError(result.get("description", "Unknown Telegram API error"))
    return result


def send_media_group(chat_id: str, photo_urls: list, *, bot_token: str = None) -> dict:
    bot_token = bot_token or config.require_env("TELEGRAM_BOT_TOKEN")
    media = [{"type": "photo", "media": url} for url in photo_urls]
    return _post("sendMediaGroup", {"chat_id": chat_id, "media": media}, bot_token)


def send_message(chat_id: str, text: str, reply_markup: dict = None, *, bot_token: str = None) -> dict:
    bot_token = bot_token or config.require_env("TELEGRAM_BOT_TOKEN")
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    return _post("sendMessage", payload, bot_token)


def get_updates(offset: int = None, timeout: int = 0, *, bot_token: str = None) -> list:
    bot_token = bot_token or config.require_env("TELEGRAM_BOT_TOKEN")
    payload = {"timeout": timeout}
    if offset is not None:
        payload["offset"] = offset
    result = _post("getUpdates", payload, bot_token)
    return result["result"]


def answer_callback_query(callback_query_id: str, text: str = None, *, bot_token: str = None) -> dict:
    bot_token = bot_token or config.require_env("TELEGRAM_BOT_TOKEN")
    payload = {"callback_query_id": callback_query_id}
    if text is not None:
        payload["text"] = text
    return _post("answerCallbackQuery", payload, bot_token)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_telegram_client.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add pipeline/telegram_client.py tests/test_telegram_client.py
git commit -m "feat: add Telegram Bot API client wrapper"
```

---

## Task 4: `replicate_client.py`

**Files:**
- Create: `pipeline/replicate_client.py`
- Test: `tests/test_replicate_client.py`

**Interfaces:**
- Consumes: `pipeline.http.send` (Task 1), `pipeline.config.require_env` (foundation layer).
- Produces: `pipeline.replicate_client.FLUX_SCHNELL_MODEL` (constant), `pipeline.replicate_client.ReplicatePredictionTimeoutError`, `generate_image(prompt: str, *, api_token: str = None) -> dict` (returns `{"image_url": str, "prediction_id": str}`).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_replicate_client.py`:

```python
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
        return {"id": "pred123", "status": "succeeded", "output": ["https://replicate.delivery/out.png"]}

    with patch("pipeline.replicate_client.http.send", side_effect=fake_send):
        result = replicate_client.generate_image("a botanical watercolor poster", api_token="test-token")

    assert captured["url"] == "https://api.replicate.com/v1/models/black-forest-labs/flux-schnell/predictions"
    assert captured["auth_header"] == "Bearer test-token"
    assert captured["prefer_header"] == "wait"
    assert captured["body"]["input"]["prompt"] == "a botanical watercolor poster"
    assert result == {"image_url": "https://replicate.delivery/out.png", "prediction_id": "pred123"}


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_replicate_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.replicate_client'`

- [ ] **Step 3: Write `pipeline/replicate_client.py`**

```python
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
    body = json.dumps({"input": {"prompt": prompt}}).encode("utf-8")
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
    result = http.send(request)

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_replicate_client.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add pipeline/replicate_client.py tests/test_replicate_client.py
git commit -m "feat: add Replicate FLUX.1 schnell client wrapper"
```

---

## Task 5: `gelato_client.py`

**Files:**
- Create: `pipeline/gelato_client.py`
- Modify: `.env.example`
- Test: `tests/test_gelato_client.py`

**Interfaces:**
- Consumes: `pipeline.http.send` (Task 1), `pipeline.config.{require_env, is_placeholder, is_live_mode}` (foundation layer + Task 2).
- Produces: `pipeline.gelato_client.GelatoPlaceholderTemplateError`, `get_template(template_id: str, *, store_id: str = None, api_key: str = None) -> dict`, `get_product(product_id: str, *, store_id: str = None, api_key: str = None) -> dict`, `create_product_from_template(template_id: str, template_variant_id: str, image_placeholder_name: str, image_url: str, title: str, *, store_id: str = None, api_key: str = None, dry_run: bool = None) -> dict`, `delete_product(product_id: str, *, store_id: str = None, api_key: str = None, dry_run: bool = None) -> None`.

Note: no `GelatoAPIError` — unlike Telegram, Gelato signals failure via HTTP status codes, which `pipeline.http.HTTPError` (Task 1) already covers. A same-status success/failure envelope isn't part of this API, so a separate wrapper exception would be unused dead code.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_gelato_client.py`:

```python
import json
from unittest.mock import patch

import pytest

import pipeline.config as config
import pipeline.gelato_client as gelato_client


def test_get_template_builds_correct_request():
    captured = {}

    def fake_send(request, timeout=30):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["api_key_header"] = request.get_header("X-api-key")
        return {"id": "tpl_abc", "variants": []}

    with patch("pipeline.gelato_client.http.send", side_effect=fake_send):
        result = gelato_client.get_template("tpl_abc", store_id="store1", api_key="key1")

    assert captured["url"] == "https://ecommerce.gelatoapis.com/v1/stores/store1/templates/tpl_abc"
    assert captured["method"] == "GET"
    assert captured["api_key_header"] == "key1"
    assert result == {"id": "tpl_abc", "variants": []}


def test_get_product_builds_correct_request():
    def fake_send(request, timeout=30):
        assert request.full_url == "https://ecommerce.gelatoapis.com/v1/stores/store1/products/prod1"
        assert request.get_method() == "GET"
        return {"id": "prod1", "productImages": []}

    with patch("pipeline.gelato_client.http.send", side_effect=fake_send):
        result = gelato_client.get_product("prod1", store_id="store1", api_key="key1")

    assert result == {"id": "prod1", "productImages": []}


def test_create_product_from_template_dry_run_makes_no_network_call():
    with patch("pipeline.gelato_client.http.send") as mock_send:
        result = gelato_client.create_product_from_template(
            "tpl_real", "variant_real", "image_slot_real.jpg", "https://img.example/x.png",
            "Botanical print", store_id="store1", api_key="key1", dry_run=True,
        )

    mock_send.assert_not_called()
    assert result["_dry_run"] is True
    assert result["title"] == "Botanical print"


def test_create_product_from_template_raises_on_placeholder_template_id_when_live():
    with patch("pipeline.gelato_client.http.send") as mock_send:
        with pytest.raises(gelato_client.GelatoPlaceholderTemplateError, match="template_id"):
            gelato_client.create_product_from_template(
                "PLACEHOLDER_8x12_PORTRAIT", "variant_real", "image_slot_real.jpg",
                "https://img.example/x.png", "Botanical print",
                store_id="store1", api_key="key1", dry_run=False,
            )

    mock_send.assert_not_called()


def test_create_product_from_template_raises_on_placeholder_variant_id_when_live():
    with patch("pipeline.gelato_client.http.send") as mock_send:
        with pytest.raises(gelato_client.GelatoPlaceholderTemplateError, match="template_variant_id"):
            gelato_client.create_product_from_template(
                "tpl_real", "PLACEHOLDER_8x12_PORTRAIT_VARIANT", "image_slot_real.jpg",
                "https://img.example/x.png", "Botanical print",
                store_id="store1", api_key="key1", dry_run=False,
            )

    mock_send.assert_not_called()


def test_create_product_from_template_sends_correct_request_when_live():
    captured = {}

    def fake_send(request, timeout=30):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data)
        return {"id": "prod_new", "status": "created", "previewUrl": None, "productImages": []}

    with patch("pipeline.gelato_client.http.send", side_effect=fake_send):
        result = gelato_client.create_product_from_template(
            "tpl_real_123", "variant_real_456", "011_mt_sunday_brook.JPG",
            "https://img.example/x.png", "Botanical print",
            store_id="store1", api_key="key1", dry_run=False,
        )

    assert captured["url"] == "https://ecommerce.gelatoapis.com/v1/stores/store1/products:create-from-template"
    assert captured["body"]["templateId"] == "tpl_real_123"
    assert captured["body"]["title"] == "Botanical print"
    assert captured["body"]["isVisibleInTheOnlineStore"] is False
    assert captured["body"]["variants"] == [{
        "templateVariantId": "variant_real_456",
        "imagePlaceholders": [{"name": "011_mt_sunday_brook.JPG", "fileUrl": "https://img.example/x.png"}],
    }]
    assert result["id"] == "prod_new"


def test_delete_product_dry_run_makes_no_network_call():
    with patch("pipeline.gelato_client.http.send") as mock_send:
        gelato_client.delete_product("prod1", store_id="store1", api_key="key1", dry_run=True)

    mock_send.assert_not_called()


def test_delete_product_sends_delete_request_when_live():
    captured = {}

    def fake_send(request, timeout=30):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        return {}

    with patch("pipeline.gelato_client.http.send", side_effect=fake_send):
        gelato_client.delete_product("prod1", store_id="store1", api_key="key1", dry_run=False)

    assert captured["url"] == "https://ecommerce.gelatoapis.com/v1/stores/store1/products/prod1"
    assert captured["method"] == "DELETE"


def test_dry_run_defaults_from_live_mode_env_var(monkeypatch):
    monkeypatch.delenv("GELATO_LIVE_MODE", raising=False)

    with patch("pipeline.gelato_client.http.send") as mock_send:
        result = gelato_client.create_product_from_template(
            "tpl_real", "variant_real", "image_slot_real.jpg", "https://img.example/x.png",
            "Botanical print", store_id="store1", api_key="key1",
        )

    mock_send.assert_not_called()
    assert result["_dry_run"] is True


def test_dry_run_false_when_live_mode_env_var_is_true(monkeypatch):
    monkeypatch.setenv("GELATO_LIVE_MODE", "true")

    def fake_send(request, timeout=30):
        return {"id": "prod_x", "status": "created"}

    with patch("pipeline.gelato_client.http.send", side_effect=fake_send) as mock_send:
        gelato_client.create_product_from_template(
            "tpl_real", "variant_real", "image_slot_real.jpg", "https://img.example/x.png",
            "Botanical print", store_id="store1", api_key="key1",
        )

    mock_send.assert_called_once()


def test_missing_store_id_raises_when_live_and_not_provided(monkeypatch):
    monkeypatch.delenv("GELATO_STORE_ID", raising=False)

    with pytest.raises(config.MissingConfigError):
        gelato_client.create_product_from_template(
            "tpl_real", "variant_real", "image_slot_real.jpg", "https://img.example/x.png",
            "Botanical print", api_key="key1", dry_run=False,
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_gelato_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.gelato_client'`

- [ ] **Step 3: Write `pipeline/gelato_client.py`**

```python
import json
import urllib.request

import pipeline.config as config
import pipeline.http as http

GELATO_API_BASE = "https://ecommerce.gelatoapis.com/v1"


class GelatoPlaceholderTemplateError(Exception):
    pass


def _headers(api_key: str) -> dict:
    return {"X-API-KEY": api_key, "Content-Type": "application/json"}


def get_template(template_id: str, *, store_id: str = None, api_key: str = None) -> dict:
    api_key = api_key or config.require_env("GELATO_API_KEY")
    store_id = store_id or config.require_env("GELATO_STORE_ID")
    url = f"{GELATO_API_BASE}/stores/{store_id}/templates/{template_id}"
    request = urllib.request.Request(url, headers=_headers(api_key), method="GET")
    return http.send(request)


def get_product(product_id: str, *, store_id: str = None, api_key: str = None) -> dict:
    api_key = api_key or config.require_env("GELATO_API_KEY")
    store_id = store_id or config.require_env("GELATO_STORE_ID")
    url = f"{GELATO_API_BASE}/stores/{store_id}/products/{product_id}"
    request = urllib.request.Request(url, headers=_headers(api_key), method="GET")
    return http.send(request)


def create_product_from_template(
    template_id: str,
    template_variant_id: str,
    image_placeholder_name: str,
    image_url: str,
    title: str,
    *,
    store_id: str = None,
    api_key: str = None,
    dry_run: bool = None,
) -> dict:
    if dry_run is None:
        dry_run = not config.is_live_mode("GELATO")

    if dry_run:
        return {
            "id": "DRY_RUN_PRODUCT_ID",
            "storeId": store_id or "DRY_RUN_STORE_ID",
            "title": title,
            "status": "created",
            "previewUrl": None,
            "productImages": [],
            "isReadyToPublish": False,
            "_dry_run": True,
        }

    for label, value in (
        ("template_id", template_id),
        ("template_variant_id", template_variant_id),
        ("image_placeholder_name", image_placeholder_name),
    ):
        if config.is_placeholder(value):
            raise GelatoPlaceholderTemplateError(
                f"Refusing to create a real Gelato product with a placeholder "
                f"{label} ({value!r}). Fill in the real value in "
                f"config/static_config.json before making a live call."
            )

    api_key = api_key or config.require_env("GELATO_API_KEY")
    store_id = store_id or config.require_env("GELATO_STORE_ID")
    url = f"{GELATO_API_BASE}/stores/{store_id}/products:create-from-template"
    body = json.dumps({
        "templateId": template_id,
        "title": title,
        "isVisibleInTheOnlineStore": False,
        "variants": [
            {
                "templateVariantId": template_variant_id,
                "imagePlaceholders": [
                    {"name": image_placeholder_name, "fileUrl": image_url}
                ],
            }
        ],
    }).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers=_headers(api_key), method="POST")
    return http.send(request)


def delete_product(product_id: str, *, store_id: str = None, api_key: str = None, dry_run: bool = None) -> None:
    if dry_run is None:
        dry_run = not config.is_live_mode("GELATO")

    if dry_run:
        return

    api_key = api_key or config.require_env("GELATO_API_KEY")
    store_id = store_id or config.require_env("GELATO_STORE_ID")
    url = f"{GELATO_API_BASE}/stores/{store_id}/products/{product_id}"
    request = urllib.request.Request(url, headers=_headers(api_key), method="DELETE")
    http.send(request)
```

- [ ] **Step 4: Add the new env vars to `.env.example`**

Append after `GELATO_API_KEY=` (currently line 7):

```
GELATO_STORE_ID=
GELATO_LIVE_MODE=
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_gelato_client.py -v`
Expected: PASS (11 passed)

- [ ] **Step 6: Commit**

```bash
git add pipeline/gelato_client.py tests/test_gelato_client.py .env.example
git commit -m "feat: add Gelato client wrapper with dry-run and placeholder gating"
```

---

## Task 6: `etsy_client.py`

**Files:**
- Create: `pipeline/etsy_client.py`
- Modify: `.env.example`
- Test: `tests/test_etsy_client.py`

**Interfaces:**
- Consumes: `pipeline.http.send` (Task 1), `pipeline.config.{require_env, is_live_mode}` (foundation layer + Task 2).
- Produces: `get_seller_taxonomy_nodes(*, api_key: str = None, access_token: str = None) -> list`, `create_draft_listing(shop_id: str, listing_data: dict, *, api_key: str = None, access_token: str = None, dry_run: bool = None) -> dict`, `upload_listing_image(shop_id: str, listing_id: str, image_bytes: bytes, *, api_key: str = None, access_token: str = None, dry_run: bool = None) -> dict`.

Note: no `EtsyAPIError` — same reasoning as Gelato (see Task 5): Etsy signals failure via HTTP status codes, already covered by `pipeline.http.HTTPError`.

Note: Etsy's Open API v3 requires **two** credentials on every call — the app's API key/client ID (`x-api-key` header) and the OAuth `access_token` (`Authorization: Bearer` header) — so these functions take both `api_key` and `access_token`, both defaulting from `.env` (`ETSY_API_KEY`, `ETSY_ACCESS_TOKEN`, already present in `.env.example`). This is slightly more explicit than the earlier design doc's `access_token`-only sketch, needed because Etsy genuinely requires both headers on every request.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_etsy_client.py`:

```python
import json
from unittest.mock import patch

import pytest

import pipeline.etsy_client as etsy_client


def test_get_seller_taxonomy_nodes_builds_correct_request():
    def fake_send(request, timeout=30):
        assert request.full_url == "https://openapi.etsy.com/v3/application/seller-taxonomy/nodes"
        assert request.get_method() == "GET"
        assert request.get_header("X-api-key") == "key1"
        assert request.get_header("Authorization") == "Bearer token1"
        return {"count": 2, "results": [{"id": 1}, {"id": 2}]}

    with patch("pipeline.etsy_client.http.send", side_effect=fake_send):
        result = etsy_client.get_seller_taxonomy_nodes(api_key="key1", access_token="token1")

    assert result == [{"id": 1}, {"id": 2}]


def test_create_draft_listing_dry_run_makes_no_network_call():
    listing_data = {"title": "Botanical print", "price": 24.0}

    with patch("pipeline.etsy_client.http.send") as mock_send:
        result = etsy_client.create_draft_listing(
            "shop1", listing_data, api_key="key1", access_token="token1", dry_run=True
        )

    mock_send.assert_not_called()
    assert result["_dry_run"] is True
    assert result["title"] == "Botanical print"


def test_create_draft_listing_sends_listing_data_as_json_body_when_live():
    captured = {}
    listing_data = {"title": "Botanical print", "price": 24.0, "who_made": "i_did"}

    def fake_send(request, timeout=30):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data)
        return {"listing_id": 999, "state": "draft"}

    with patch("pipeline.etsy_client.http.send", side_effect=fake_send):
        result = etsy_client.create_draft_listing(
            "shop1", listing_data, api_key="key1", access_token="token1", dry_run=False
        )

    assert captured["url"] == "https://openapi.etsy.com/v3/application/shops/shop1/listings"
    assert captured["body"] == listing_data
    assert result == {"listing_id": 999, "state": "draft"}


def test_upload_listing_image_dry_run_makes_no_network_call():
    with patch("pipeline.etsy_client.http.send") as mock_send:
        result = etsy_client.upload_listing_image(
            "shop1", "listing1", b"fake-image-bytes", api_key="key1", access_token="token1", dry_run=True
        )

    mock_send.assert_not_called()
    assert result["_dry_run"] is True


def test_upload_listing_image_sends_multipart_body_with_image_bytes_when_live():
    captured = {}

    def fake_send(request, timeout=30):
        captured["url"] = request.full_url
        captured["content_type"] = request.get_header("Content-type")
        captured["body"] = request.data
        return {"listing_image_id": 555}

    with patch("pipeline.etsy_client.http.send", side_effect=fake_send):
        result = etsy_client.upload_listing_image(
            "shop1", "listing1", b"fake-image-bytes", api_key="key1", access_token="token1", dry_run=False
        )

    assert captured["url"] == "https://openapi.etsy.com/v3/application/shops/shop1/listings/listing1/images"
    assert captured["content_type"].startswith("multipart/form-data; boundary=")
    assert b"fake-image-bytes" in captured["body"]
    assert b'name="image"' in captured["body"]
    assert result == {"listing_image_id": 555}


def test_dry_run_defaults_from_live_mode_env_var(monkeypatch):
    monkeypatch.delenv("ETSY_LIVE_MODE", raising=False)

    with patch("pipeline.etsy_client.http.send") as mock_send:
        result = etsy_client.create_draft_listing(
            "shop1", {"title": "x"}, api_key="key1", access_token="token1"
        )

    mock_send.assert_not_called()
    assert result["_dry_run"] is True


def test_dry_run_false_when_live_mode_env_var_is_true(monkeypatch):
    monkeypatch.setenv("ETSY_LIVE_MODE", "true")

    def fake_send(request, timeout=30):
        return {"listing_id": 1}

    with patch("pipeline.etsy_client.http.send", side_effect=fake_send) as mock_send:
        etsy_client.create_draft_listing("shop1", {"title": "x"}, api_key="key1", access_token="token1")

    mock_send.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_etsy_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.etsy_client'`

- [ ] **Step 3: Write `pipeline/etsy_client.py`**

```python
import json
import urllib.request
import uuid

import pipeline.config as config
import pipeline.http as http

ETSY_API_BASE = "https://openapi.etsy.com/v3/application"


def _headers(api_key: str, access_token: str) -> dict:
    return {"x-api-key": api_key, "Authorization": f"Bearer {access_token}"}


def get_seller_taxonomy_nodes(*, api_key: str = None, access_token: str = None) -> list:
    api_key = api_key or config.require_env("ETSY_API_KEY")
    access_token = access_token or config.require_env("ETSY_ACCESS_TOKEN")
    url = f"{ETSY_API_BASE}/seller-taxonomy/nodes"
    request = urllib.request.Request(url, headers=_headers(api_key, access_token), method="GET")
    result = http.send(request)
    return result["results"]


def create_draft_listing(
    shop_id: str, listing_data: dict, *, api_key: str = None, access_token: str = None, dry_run: bool = None
) -> dict:
    if dry_run is None:
        dry_run = not config.is_live_mode("ETSY")

    if dry_run:
        return {"listing_id": "DRY_RUN_LISTING_ID", "state": "draft", "_dry_run": True, **listing_data}

    api_key = api_key or config.require_env("ETSY_API_KEY")
    access_token = access_token or config.require_env("ETSY_ACCESS_TOKEN")
    url = f"{ETSY_API_BASE}/shops/{shop_id}/listings"
    body = json.dumps(listing_data).encode("utf-8")
    headers = _headers(api_key, access_token)
    headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    return http.send(request)


def upload_listing_image(
    shop_id: str,
    listing_id: str,
    image_bytes: bytes,
    *,
    api_key: str = None,
    access_token: str = None,
    dry_run: bool = None,
) -> dict:
    if dry_run is None:
        dry_run = not config.is_live_mode("ETSY")

    if dry_run:
        return {"listing_image_id": "DRY_RUN_IMAGE_ID", "_dry_run": True}

    api_key = api_key or config.require_env("ETSY_API_KEY")
    access_token = access_token or config.require_env("ETSY_ACCESS_TOKEN")
    url = f"{ETSY_API_BASE}/shops/{shop_id}/listings/{listing_id}/images"

    boundary = uuid.uuid4().hex
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="image.jpg"\r\n'
        f"Content-Type: image/jpeg\r\n\r\n"
    ).encode("utf-8") + image_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

    headers = _headers(api_key, access_token)
    headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    return http.send(request)
```

- [ ] **Step 4: Add the new env var to `.env.example`**

Append after `ETSY_SHOP_ID=` (currently line 6):

```
ETSY_LIVE_MODE=
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_etsy_client.py -v`
Expected: PASS (7 passed)

- [ ] **Step 6: Run the full test suite**

Run: `pytest -v`
Expected: PASS (all tests across `test_db.py`, `test_config.py`, `test_http.py`, `test_telegram_client.py`, `test_replicate_client.py`, `test_gelato_client.py`, `test_etsy_client.py`)

- [ ] **Step 7: Commit**

```bash
git add pipeline/etsy_client.py tests/test_etsy_client.py .env.example
git commit -m "feat: add Etsy Open API v3 client wrapper"
```

---

## What this plan deliberately does not cover

The 12 pipeline stage modules (`research.py` through `cleanup.py`) that call into these four clients — each needs its own plan once this lands, per CLAUDE.md's "commit after each stage passes its manual M1 test" convention. Also out of scope, noted in the design doc as explicit follow-ups:
- `etsy_auth.py` (OAuth refresh-token grant) — needed before M2's unattended runs.
- The poll loop that waits for a Gelato product's `productImages` to populate after `create_product_from_template` — this is `primary_mockup.py`'s job, not the client's.
