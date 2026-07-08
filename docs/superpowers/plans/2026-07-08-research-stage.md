# Research Stage (research.py) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `pipeline/research.py`, the first of 12 pipeline stage modules — trend research (Google-Trends-adjacent Claude web search + Etsy demand-proxy checks + a static event calendar) feeding Go/Hold/Kill classification and writing `candidates` rows, per SPEC_v4.10.md section 3 step 1. Also fixes a live-verified auth bug in the already-merged `etsy_client.py` and adds the Etsy endpoint and new Anthropic wrapper research.py depends on.

**Architecture:** Three independent collector functions (event lookahead = static calendar, no external call; trending-now = Claude web search via a new `anthropic_client.py` + Etsy demand-proxy; on-demand = single topic through the same demand-proxy path) produce a common `RawCandidate` dict shape. A single `classify()` function turns each into a Go/Hold/Kill decision. `run_research_cycle()` orchestrates: collect → classify → write every candidate to SQLite → if nothing classified Go this cycle, pull one term from the safe-evergreen bucket and force it through as Go, so a batch never comes up empty.

**Tech Stack:** Python 3, `sqlite3` (stdlib), `urllib.request` (stdlib, matches existing client wrappers — no `requests`/SDK dependency), `pytest` + `unittest.mock` for tests.

## Global Constraints

- **No schema changes.** `db/schema.sql` is not touched by this plan. Two decisions this relies on, both confirmed by Quentin on 2026-07-08 and recorded so they aren't silently reopened:
  - **Candidate scoring is in-memory only, one research cycle at a time — no persisted score column.** See the `project-candidate-scoring-in-memory-only` memory. Don't add a `signal_score` column without a concrete downstream need.
  - **Hold and Kill candidates get `candidates.status = 'abandoned'`.** `'failed'` is reserved for critic-pass exhaustion (3-attempt cap, per CHANGELOG.md "spec v0.4 → v0.4.1") — confirmed unused anywhere in the codebase today, so no collision. The actual Go/Hold/Kill distinction and the reason live in `go_hold_kill`/`hold_recheck_date`/`kill_reason`, not in `status` — `status='abandoned'` just means "not currently in the active generation pipeline."
- **`research.py` never talks to Telegram directly.** The hourly poll (a separate, not-yet-built module) owns reading `/research <topic>` commands and allowlist-checking the sender. `run_research_cycle()` takes an already-resolved `on_demand_topics: list[str]` parameter — how those topics get persisted/resolved from Telegram events is out of scope here, deferred to the hourly-poll module's own plan.
- **A design is only ever image-generated once** (CLAUDE.md hard constraint) — `research.py` only ever produces `candidates` rows; it never calls Replicate.
- **Etsy demand-proxy endpoint (`findAllListingsActive`) takes `api_key` only, no OAuth access token** — verified live 2026-07-08, see CHANGELOG.md "spec v0.4.9 → v0.4.10" and `docs/etsy_call_response_example_from_manual_tests.txt`. There is **no view-count field** on this endpoint — don't build anything assuming Etsy exposes impression/view data at the keyword level.
- **`x-api-key` must be `keystring:shared_secret`** (colon-joined), not the bare keystring — this is a live-verified bug fix to already-merged, already-tested code (Task 1), not new-endpoint work.
- **The Anthropic web-search tool's exact request/response shape (`WEB_SEARCH_TOOL_TYPE` constant in Task 3) has NOT been verified against a live call.** Built to current best knowledge of the Messages API, but per the standing "verify real API behavior, don't guess" practice (same one that caught the Etsy bug), Task 3 includes a mandatory manual live-verification step before this wrapper is trusted for a real M1 run.
- Every stage module in this pipeline is independently testable and gets its own commit per passing test group, per CLAUDE.md's "commit after each stage passes its manual M1 test."

---

## Task 1: Fix `etsy_client.py`'s `x-api-key` header bug

**Files:**
- Modify: `pipeline/etsy_client.py:11-72`
- Modify: `tests/test_etsy_client.py`

**Interfaces:**
- Produces: `_headers(api_key: str, api_secret: str, access_token: str = None) -> dict` (access_token now optional — Task 2's endpoint doesn't use one). `get_seller_taxonomy_nodes`, `create_draft_listing`, `upload_listing_image` all gain a keyword-only `api_secret: str = None` parameter, defaulting to `config.require_env("ETSY_API_SECRET")`.

- [ ] **Step 1: Update the three existing tests to expect the colon-joined header and pass `api_secret`**

In `tests/test_etsy_client.py`, update these three tests:

```python
def test_get_seller_taxonomy_nodes_builds_correct_request():
    def fake_send(request, timeout=30):
        assert request.full_url == "https://openapi.etsy.com/v3/application/seller-taxonomy/nodes"
        assert request.get_method() == "GET"
        assert request.get_header("X-api-key") == "key1:secret1"
        assert request.get_header("Authorization") == "Bearer token1"
        return {"count": 2, "results": [{"id": 1}, {"id": 2}]}

    with patch("pipeline.etsy_client.http.send", side_effect=fake_send):
        result = etsy_client.get_seller_taxonomy_nodes(api_key="key1", api_secret="secret1", access_token="token1")

    assert result == [{"id": 1}, {"id": 2}]
```

```python
def test_create_draft_listing_sends_listing_data_as_json_body_when_live():
    captured = {}
    listing_data = {"title": "Botanical print", "price": 24.0, "who_made": "i_did"}

    def fake_send(request, timeout=30):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data)
        return {"listing_id": 999, "state": "draft"}

    with patch("pipeline.etsy_client.http.send", side_effect=fake_send):
        result = etsy_client.create_draft_listing(
            "shop1", listing_data, api_key="key1", api_secret="secret1", access_token="token1", dry_run=False
        )

    assert captured["url"] == "https://openapi.etsy.com/v3/application/shops/shop1/listings"
    assert captured["body"] == listing_data
    assert result == {"listing_id": 999, "state": "draft"}
```

```python
def test_upload_listing_image_sends_multipart_body_with_image_bytes_when_live():
    captured = {}

    def fake_send(request, timeout=30):
        captured["url"] = request.full_url
        captured["content_type"] = request.get_header("Content-type")
        captured["body"] = request.data
        return {"listing_image_id": 555}

    with patch("pipeline.etsy_client.http.send", side_effect=fake_send):
        result = etsy_client.upload_listing_image(
            "shop1", "listing1", b"fake-image-bytes",
            api_key="key1", api_secret="secret1", access_token="token1", dry_run=False
        )

    assert captured["url"] == "https://openapi.etsy.com/v3/application/shops/shop1/listings/listing1/images"
    assert captured["content_type"].startswith("multipart/form-data; boundary=")
    assert b"fake-image-bytes" in captured["body"]
    assert b'name="image"' in captured["body"]
    assert result == {"listing_image_id": 555}
```

And `test_dry_run_false_when_live_mode_env_var_is_true`:

```python
def test_dry_run_false_when_live_mode_env_var_is_true(monkeypatch):
    monkeypatch.setenv("ETSY_LIVE_MODE", "true")

    def fake_send(request, timeout=30):
        return {"listing_id": 1}

    with patch("pipeline.etsy_client.http.send", side_effect=fake_send) as mock_send:
        etsy_client.create_draft_listing(
            "shop1", {"title": "x"}, api_key="key1", api_secret="secret1", access_token="token1"
        )

    mock_send.assert_called_once()
```

The two dry-run tests (`test_create_draft_listing_dry_run_makes_no_network_call`, `test_upload_listing_image_dry_run_makes_no_network_call`) and `test_dry_run_defaults_from_live_mode_env_var` are unchanged — dry-run returns before `_headers()` is ever built.

- [ ] **Step 2: Run the tests to confirm they now fail against the current (buggy) implementation**

Run: `python -m pytest tests/test_etsy_client.py -v`
Expected: the three request-building tests FAIL (header assertion mismatch / missing `api_secret` argument type error), the two dry-run tests still PASS.

- [ ] **Step 3: Fix `_headers()` and thread `api_secret` through the three functions**

In `pipeline/etsy_client.py`, replace `_headers` and update all three callers:

```python
def _headers(api_key: str, api_secret: str, access_token: str = None) -> dict:
    headers = {"x-api-key": f"{api_key}:{api_secret}"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    return headers


def get_seller_taxonomy_nodes(*, api_key: str = None, api_secret: str = None, access_token: str = None) -> list:
    api_key = api_key or config.require_env("ETSY_API_KEY")
    api_secret = api_secret or config.require_env("ETSY_API_SECRET")
    access_token = access_token or config.require_env("ETSY_ACCESS_TOKEN")
    url = f"{ETSY_API_BASE}/seller-taxonomy/nodes"
    request = urllib.request.Request(url, headers=_headers(api_key, api_secret, access_token), method="GET")
    result = http.send(request)
    return result["results"]


def create_draft_listing(
    shop_id: str, listing_data: dict, *, api_key: str = None, api_secret: str = None,
    access_token: str = None, dry_run: bool = None
) -> dict:
    if dry_run is None:
        dry_run = not config.is_live_mode("ETSY")

    if dry_run:
        return {"listing_id": "DRY_RUN_LISTING_ID", "state": "draft", "_dry_run": True, **listing_data}

    api_key = api_key or config.require_env("ETSY_API_KEY")
    api_secret = api_secret or config.require_env("ETSY_API_SECRET")
    access_token = access_token or config.require_env("ETSY_ACCESS_TOKEN")
    url = f"{ETSY_API_BASE}/shops/{shop_id}/listings"
    body = json.dumps(listing_data).encode("utf-8")
    headers = _headers(api_key, api_secret, access_token)
    headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    return http.send(request)


def upload_listing_image(
    shop_id: str,
    listing_id: str,
    image_bytes: bytes,
    *,
    api_key: str = None,
    api_secret: str = None,
    access_token: str = None,
    dry_run: bool = None,
) -> dict:
    if dry_run is None:
        dry_run = not config.is_live_mode("ETSY")

    if dry_run:
        return {"listing_image_id": "DRY_RUN_IMAGE_ID", "_dry_run": True}

    api_key = api_key or config.require_env("ETSY_API_KEY")
    api_secret = api_secret or config.require_env("ETSY_API_SECRET")
    access_token = access_token or config.require_env("ETSY_ACCESS_TOKEN")
    url = f"{ETSY_API_BASE}/shops/{shop_id}/listings/{listing_id}/images"

    boundary = uuid.uuid4().hex
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="image.jpg"\r\n'
        f"Content-Type: image/jpeg\r\n\r\n"
    ).encode("utf-8") + image_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

    headers = _headers(api_key, api_secret, access_token)
    headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    return http.send(request)
```

- [ ] **Step 4: Run the tests to confirm they pass**

Run: `python -m pytest tests/test_etsy_client.py -v`
Expected: all PASS (5 existing tests, now updated).

- [ ] **Step 5: Commit**

```bash
git add pipeline/etsy_client.py tests/test_etsy_client.py
git commit -m "fix: join api_key and api_secret in Etsy x-api-key header

Etsy requires keystring:shared_secret, not a bare keystring - confirmed
live (bare keystring gets HTTP 403, joined gets 200). This silently
broke every existing etsy_client.py call. See docs/etsy_call_response_example_from_manual_tests.txt."
```

---

## Task 2: Add `find_all_listings_active` (Etsy demand-proxy endpoint) to `etsy_client.py`

**Files:**
- Modify: `pipeline/etsy_client.py`
- Modify: `tests/test_etsy_client.py`

**Interfaces:**
- Consumes: `_headers(api_key, api_secret, access_token=None)` from Task 1.
- Produces: `find_all_listings_active(keywords: str, *, limit=None, offset=None, sort_on=None, sort_order=None, min_price=None, max_price=None, taxonomy_id=None, shop_location=None, is_safe=None, currency=None, buyer_country=None, api_key=None, api_secret=None) -> dict` — returns the raw `{"count": int, "results": [...]}` response. This is what Task 6's `research.py` demand-proxy check calls.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_etsy_client.py`:

```python
def test_find_all_listings_active_builds_correct_request_with_only_required_param():
    def fake_send(request, timeout=30):
        assert request.full_url == (
            "https://openapi.etsy.com/v3/application/listings/active?keywords=botanical+poster"
        )
        assert request.get_method() == "GET"
        assert request.get_header("X-api-key") == "key1:secret1"
        assert request.get_header("Authorization") is None
        return {"count": 243150, "results": [{"listing_id": 1, "num_favorers": 3}]}

    with patch("pipeline.etsy_client.http.send", side_effect=fake_send):
        result = etsy_client.find_all_listings_active("botanical poster", api_key="key1", api_secret="secret1")

    assert result == {"count": 243150, "results": [{"listing_id": 1, "num_favorers": 3}]}


def test_find_all_listings_active_includes_optional_params_when_given():
    captured = {}

    def fake_send(request, timeout=30):
        captured["url"] = request.full_url
        return {"count": 0, "results": []}

    with patch("pipeline.etsy_client.http.send", side_effect=fake_send):
        etsy_client.find_all_listings_active(
            "botanical poster", limit=10, sort_on="favorites", sort_order="desc",
            api_key="key1", api_secret="secret1",
        )

    assert "limit=10" in captured["url"]
    assert "sort_on=favorites" in captured["url"]
    assert "sort_order=desc" in captured["url"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_etsy_client.py -k find_all_listings_active -v`
Expected: FAIL with `AttributeError: module 'pipeline.etsy_client' has no attribute 'find_all_listings_active'`.

- [ ] **Step 3: Implement it**

Add to `pipeline/etsy_client.py` (needs `import urllib.parse` added at the top alongside the existing `urllib.request` import):

```python
def find_all_listings_active(
    keywords: str,
    *,
    limit: int = None,
    offset: int = None,
    sort_on: str = None,
    sort_order: str = None,
    min_price: float = None,
    max_price: float = None,
    taxonomy_id: str = None,
    shop_location: str = None,
    is_safe: bool = None,
    currency: str = None,
    buyer_country: str = None,
    api_key: str = None,
    api_secret: str = None,
) -> dict:
    api_key = api_key or config.require_env("ETSY_API_KEY")
    api_secret = api_secret or config.require_env("ETSY_API_SECRET")

    params = {"keywords": keywords}
    optional_params = {
        "limit": limit, "offset": offset, "sort_on": sort_on, "sort_order": sort_order,
        "min_price": min_price, "max_price": max_price, "taxonomy_id": taxonomy_id,
        "shop_location": shop_location, "is_safe": is_safe, "currency": currency,
        "buyer_country": buyer_country,
    }
    for key, value in optional_params.items():
        if value is not None:
            params[key] = value

    query = urllib.parse.urlencode(params)
    url = f"{ETSY_API_BASE}/listings/active?{query}"
    request = urllib.request.Request(url, headers=_headers(api_key, api_secret), method="GET")
    return http.send(request)
```

Note: no `access_token` passed to `_headers()` here — this endpoint is `api_key`-only, confirmed live (CHANGELOG.md "spec v0.4.9 → v0.4.10").

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_etsy_client.py -v`
Expected: all PASS (7 tests total).

- [ ] **Step 5: Commit**

```bash
git add pipeline/etsy_client.py tests/test_etsy_client.py
git commit -m "feat: add findAllListingsActive wrapper for Etsy demand-proxy checks"
```

---

## Task 3: Add `pipeline/anthropic_client.py` (Claude web-search wrapper)

**Files:**
- Create: `pipeline/anthropic_client.py`
- Create: `tests/test_anthropic_client.py`
- Modify: `.env.example` (add `ANTHROPIC_API_KEY=`)

**Interfaces:**
- Produces: `research_web_search(prompt: str, *, api_key: str = None, max_tokens: int = 2048) -> dict`, returning `{"text": str, "raw": dict}` where `text` is the concatenated text content blocks from the response. This is what Task 6's `collect_trending_now()` calls.

- [ ] **Step 1: Add `ANTHROPIC_API_KEY` to `.env.example`**

In `.env.example`, add a new line (anywhere near the top, alongside the other API keys):

```
ANTHROPIC_API_KEY=
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_anthropic_client.py`:

```python
import json
from unittest.mock import patch

import pipeline.anthropic_client as anthropic_client


def test_research_web_search_builds_correct_request():
    captured = {}

    def fake_send(request, timeout=30):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["headers"] = {
            "x-api-key": request.get_header("X-api-key"),
            "anthropic-version": request.get_header("Anthropic-version"),
        }
        captured["body"] = json.loads(request.data)
        return {
            "content": [
                {"type": "server_tool_use", "id": "srvtoolu_1", "name": "web_search"},
                {"type": "web_search_tool_result", "tool_use_id": "srvtoolu_1", "content": []},
                {"type": "text", "text": '[{"keyword": "monstera line art", "rationale": "rising interest"}]'},
            ]
        }

    with patch("pipeline.anthropic_client.http.send", side_effect=fake_send):
        result = anthropic_client.research_web_search("find trending botanical keywords", api_key="key1")

    assert captured["url"] == "https://api.anthropic.com/v1/messages"
    assert captured["method"] == "POST"
    assert captured["headers"]["x-api-key"] == "key1"
    assert captured["headers"]["anthropic-version"] == anthropic_client.ANTHROPIC_API_VERSION
    assert captured["body"]["model"] == anthropic_client.ANTHROPIC_MODEL
    assert captured["body"]["messages"] == [{"role": "user", "content": "find trending botanical keywords"}]
    assert captured["body"]["tools"] == [
        {"type": anthropic_client.WEB_SEARCH_TOOL_TYPE, "name": "web_search", "max_uses": 5}
    ]
    assert result["text"] == '[{"keyword": "monstera line art", "rationale": "rising interest"}]'


def test_research_web_search_concatenates_multiple_text_blocks():
    def fake_send(request, timeout=30):
        return {"content": [{"type": "text", "text": "line one"}, {"type": "text", "text": "line two"}]}

    with patch("pipeline.anthropic_client.http.send", side_effect=fake_send):
        result = anthropic_client.research_web_search("prompt", api_key="key1")

    assert result["text"] == "line one\nline two"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_anthropic_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.anthropic_client'`.

- [ ] **Step 4: Implement `pipeline/anthropic_client.py`**

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_anthropic_client.py -v`
Expected: both PASS.

- [ ] **Step 6: Commit**

```bash
git add pipeline/anthropic_client.py tests/test_anthropic_client.py .env.example
git commit -m "feat: add Anthropic web-search client wrapper for trend research"
```

- [ ] **Step 7: Manual live verification (you run this, not the implementing agent — requires a real `ANTHROPIC_API_KEY`)**

Once you have a real key in `.env`, run one live call and compare the raw response shape against what Step 4's code assumes:

```bash
python -c "
import pipeline.config as config
config.load_env()
import pipeline.anthropic_client as ac
result = ac.research_web_search('Find 3 trending Etsy search keywords for botanical/minimalist wall art posters, reply as a JSON list of {keyword, rationale} objects.')
print(result['text'])
print('---RAW---')
import json
print(json.dumps(result['raw'], indent=2))
"
```

Save the masked output to `docs/anthropic_call_response_example_from_manual_tests.txt`, mirroring the existing Etsy/Gelato manual-test logs. If `WEB_SEARCH_TOOL_TYPE`, the response's content-block shape, or anything else differs from what Step 4 assumed, fix `anthropic_client.py` and its tests in a follow-up commit before treating `research.py`'s trending-now path (Task 6) as trustworthy for a real M1 run.

---

## Task 4: `research.py` — safe-evergreen bucket loader

**Files:**
- Create: `pipeline/research.py`
- Create: `tests/test_research.py`

**Interfaces:**
- Consumes: `docs/safe_evergreen_bucket.md` (already exists, approved 2026-07-08).
- Produces: `load_safe_evergreen_terms(path=None) -> list[str]`, `pick_safe_evergreen_fallback(*, rng=None) -> dict` (a `RawCandidate` — see Task 5 for the shared shape).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_research.py`:

```python
import pipeline.research as research


def test_load_safe_evergreen_terms_reads_all_buckets():
    terms = research.load_safe_evergreen_terms()

    assert "monstera line art" in terms
    assert "moon phase print" in terms
    assert "mid century modern wall art" in terms


def test_load_safe_evergreen_terms_excludes_non_bucket_sections():
    terms = research.load_safe_evergreen_terms()

    joined = " ".join(terms).lower()
    assert "zodiac" not in joined
    assert "printify" not in joined


def test_pick_safe_evergreen_fallback_returns_go_eligible_raw_candidate():
    class FakeRng:
        def choice(self, seq):
            return seq[0]

    raw = research.pick_safe_evergreen_fallback(rng=FakeRng())

    assert raw["niche"] == research.load_safe_evergreen_terms()[0]
    assert raw["trend_source"].startswith("safe_evergreen_fallback:")
    assert raw["window_end"] is None
    assert raw["demand_ratio"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_research.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.research'`.

- [ ] **Step 3: Implement**

Create `pipeline/research.py`:

```python
import random
from pathlib import Path

import pipeline.config as config

SAFE_EVERGREEN_BUCKET_PATH = config.REPO_ROOT / "docs" / "safe_evergreen_bucket.md"


def load_safe_evergreen_terms(path=None) -> list:
    path = Path(path) if path else SAFE_EVERGREEN_BUCKET_PATH
    lines = path.read_text(encoding="utf-8").splitlines()

    terms = []
    in_buckets_section = False
    for line in lines:
        stripped = line.strip()
        if stripped == "## Buckets":
            in_buckets_section = True
            continue
        if in_buckets_section and stripped.startswith("## "):
            break
        if not in_buckets_section or stripped.startswith("### ") or not stripped:
            continue
        terms.extend(term.strip() for term in stripped.split(","))
    return terms


def pick_safe_evergreen_fallback(*, rng=None) -> dict:
    rng = rng or random
    term = rng.choice(load_safe_evergreen_terms())
    return {
        "niche": term,
        "trend_source": f"safe_evergreen_fallback:{term}",
        "rationale": "Safe-evergreen bucket fallback - no Go candidate this cycle (docs/safe_evergreen_bucket.md).",
        "window_start": None,
        "window_end": None,
        "demand_ratio": None,
        "listing_count": None,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_research.py -v`
Expected: all 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/research.py tests/test_research.py
git commit -m "feat: add research.py safe-evergreen bucket loader and fallback picker"
```

---

## Task 5: `research.py` — event lookahead collector + timing classification

**Files:**
- Modify: `pipeline/research.py`
- Modify: `tests/test_research.py`

**Interfaces:**
- Produces: `collect_event_lookahead() -> list[dict]` (list of `RawCandidate`, one per entry in `EVENT_WINDOWS_2026` — unfiltered; date-based Go/Hold filtering happens in `classify()`, not here), `classify(raw: dict, *, now=None) -> dict` (returns `{"go_hold_kill": str, "hold_recheck_date": str|None, "kill_reason": str|None}`).
- **`RawCandidate` shape** (shared across all collectors, referenced by every later task):
  ```python
  {
      "niche": str,
      "trend_source": str,
      "rationale": str,
      "window_start": date | None,   # set by collect_event_lookahead only
      "window_end": date | None,     # set by collect_event_lookahead only
      "demand_ratio": float | None,  # set by collect_trending_now / collect_on_demand only
      "listing_count": int | None,   # set by collect_trending_now / collect_on_demand only
  }
  ```

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_research.py`:

```python
from datetime import date


def test_collect_event_lookahead_returns_one_candidate_per_window():
    raw_candidates = research.collect_event_lookahead()

    assert len(raw_candidates) == len(research.EVENT_WINDOWS_2026)
    names = {raw["trend_source"] for raw in raw_candidates}
    assert "event_lookahead:holiday_peak" in names
    assert "event_lookahead:fall_cozy_aesthetic" in names


def test_classify_event_candidate_goes_when_lead_time_available():
    raw = {
        "niche": "x", "trend_source": "event_lookahead:holiday_peak", "rationale": "r",
        "window_start": date(2026, 11, 10), "window_end": date(2026, 12, 20),
        "demand_ratio": None, "listing_count": None,
    }

    result = research.classify(raw, now=date(2026, 11, 1))

    assert result == {"go_hold_kill": "go", "hold_recheck_date": None, "kill_reason": None}


def test_classify_event_candidate_holds_when_window_closed():
    raw = {
        "niche": "x", "trend_source": "event_lookahead:holiday_peak", "rationale": "r",
        "window_start": date(2026, 11, 10), "window_end": date(2026, 12, 20),
        "demand_ratio": None, "listing_count": None,
    }

    result = research.classify(raw, now=date(2026, 12, 25))

    assert result["go_hold_kill"] == "hold"
    assert result["hold_recheck_date"] == "2027-09-11"
    assert result["kill_reason"] is None


def test_classify_event_candidate_holds_when_inside_window_but_too_close_to_close():
    raw = {
        "niche": "x", "trend_source": "event_lookahead:diwali", "rationale": "r",
        "window_start": date(2026, 11, 8), "window_end": date(2026, 11, 8),
        "demand_ratio": None, "listing_count": None,
    }

    result = research.classify(raw, now=date(2026, 11, 1))

    assert result["go_hold_kill"] == "hold"
```

Note: `test_classify_event_candidate_holds_when_window_closed` asserts `hold_recheck_date == "2027-09-11"` — that's `window_start` (2026-11-10) advanced one year (2027-11-10) minus 60 days = 2027-09-11, per spec's "revisit 60 days before next year's window" guidance.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_research.py -v`
Expected: FAIL — `collect_event_lookahead` / `classify` / `EVENT_WINDOWS_2026` don't exist yet.

- [ ] **Step 3: Implement**

Add to `pipeline/research.py` (add `from datetime import date, timedelta` to the imports):

```python
# Rough heuristic per SPEC_v4.10.md section 3 step 1 ("Start these thresholds
# as rough manual heuristics; revisit at M3 once real data exists").
MIN_EVENT_LEAD_DAYS = 14

# Dates are this cycle's (2026-2027) concrete mapping of SPEC_v4.10.md section
# 3 step 1's event table. Diwali's date is lunar-calendar-driven and must be
# re-researched annually; the others' month/day boundaries are this plan's
# concrete interpretation of the spec's prose ranges ("late Nov", "Sept-Oct")
# and should be refreshed monthly per the spec's own instruction.
EVENT_WINDOWS_2026 = [
    {
        "name": "fall_cozy_aesthetic",
        "start": date(2026, 9, 1),
        "end": date(2026, 10, 31),
        "niche_note": "Strong for nature/botanical specifically",
    },
    {
        "name": "holiday_peak",
        "start": date(2026, 11, 10),
        "end": date(2026, 12, 20),
        "niche_note": "Biggest window overall",
    },
    {
        "name": "diwali",
        "start": date(2026, 11, 8),
        "end": date(2026, 11, 8),
        "niche_note": "Cultural gifting/home decor",
    },
    {
        "name": "black_friday_cyber_monday",
        "start": date(2026, 11, 27),
        "end": date(2026, 11, 30),
        "niche_note": "General gift-shopping surge",
    },
    {
        "name": "engagement_season",
        "start": date(2026, 11, 21),
        "end": date(2027, 2, 14),
        "niche_note": "Gift/registry shopping, first home decor",
    },
    {
        "name": "new_year_refresh",
        "start": date(2027, 1, 1),
        "end": date(2027, 1, 31),
        "niche_note": "Self-purchase redecorating",
    },
]


def collect_event_lookahead() -> list:
    return [
        {
            "niche": f"botanical/minimalist wall art - {window['name']}",
            "trend_source": f"event_lookahead:{window['name']}",
            "rationale": window["niche_note"],
            "window_start": window["start"],
            "window_end": window["end"],
            "demand_ratio": None,
            "listing_count": None,
        }
        for window in EVENT_WINDOWS_2026
    ]


def classify(raw: dict, *, now=None) -> dict:
    now = now or date.today()
    if raw.get("window_end") is not None:
        return _classify_by_timing(raw, now)
    if raw.get("demand_ratio") is not None:
        return _classify_by_demand(raw)
    return {"go_hold_kill": "go", "hold_recheck_date": None, "kill_reason": None}


def _classify_by_timing(raw: dict, now: date) -> dict:
    days_until_close = (raw["window_end"] - now).days
    if days_until_close >= MIN_EVENT_LEAD_DAYS:
        return {"go_hold_kill": "go", "hold_recheck_date": None, "kill_reason": None}

    next_year_start = date(raw["window_start"].year + 1, raw["window_start"].month, raw["window_start"].day)
    recheck_date = next_year_start - timedelta(days=60)
    return {"go_hold_kill": "hold", "hold_recheck_date": recheck_date.isoformat(), "kill_reason": None}
```

`_classify_by_demand` is added in Task 6 — `classify()` already calls it, so Task 6 must land before this module is fully usable, but this task's own tests only exercise the timing branch and pass independently.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_research.py -v`
Expected: all PASS (7 tests total so far).

- [ ] **Step 5: Commit**

```bash
git add pipeline/research.py tests/test_research.py
git commit -m "feat: add research.py event-lookahead collector and timing classification"
```

---

## Task 6: `research.py` — demand-proxy classification + trending-now collector

**Files:**
- Modify: `pipeline/research.py`
- Modify: `tests/test_research.py`

**Interfaces:**
- Consumes: `etsy_client.find_all_listings_active(...)` (Task 2), `anthropic_client.research_web_search(...)` (Task 3).
- Produces: `_classify_by_demand(raw: dict) -> dict` (completes `classify()` from Task 5), `collect_trending_now(*, anthropic_api_key=None, etsy_api_key=None, etsy_api_secret=None) -> list[dict]`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_research.py`:

```python
import json
from unittest.mock import patch


def test_classify_demand_candidate_goes_when_ratio_above_threshold():
    raw = {
        "niche": "x", "trend_source": "trending_now:x", "rationale": "r",
        "window_start": None, "window_end": None,
        "demand_ratio": research.KILL_DEMAND_RATIO_THRESHOLD * 10, "listing_count": 1000,
    }

    result = research.classify(raw)

    assert result == {"go_hold_kill": "go", "hold_recheck_date": None, "kill_reason": None}


def test_classify_demand_candidate_kills_when_ratio_below_threshold():
    raw = {
        "niche": "x", "trend_source": "trending_now:x", "rationale": "r",
        "window_start": None, "window_end": None,
        "demand_ratio": research.KILL_DEMAND_RATIO_THRESHOLD / 10, "listing_count": 1000,
    }

    result = research.classify(raw)

    assert result["go_hold_kill"] == "kill"
    assert result["hold_recheck_date"] is None
    assert "1000" in result["kill_reason"]


def test_collect_trending_now_combines_web_search_and_demand_proxy():
    search_response = json.dumps([
        {"keyword": "monstera line art", "rationale": "rising interest"},
        {"keyword": "moon phase print", "rationale": "steady evergreen demand"},
    ])

    def fake_web_search(prompt, api_key=None, max_tokens=2048):
        return {"text": search_response, "raw": {}}

    def fake_find_listings(keywords, **kwargs):
        return {
            "count": 1000,
            "results": [{"num_favorers": 5}, {"num_favorers": 15}],
        }

    with patch("pipeline.research.anthropic_client.research_web_search", side_effect=fake_web_search), \
         patch("pipeline.research.etsy_client.find_all_listings_active", side_effect=fake_find_listings):
        raw_candidates = research.collect_trending_now()

    assert len(raw_candidates) == 2
    assert raw_candidates[0]["niche"] == "monstera line art"
    assert raw_candidates[0]["trend_source"] == "trending_now:monstera line art"
    assert raw_candidates[0]["listing_count"] == 1000
    assert raw_candidates[0]["demand_ratio"] == 10 / 1000
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_research.py -v`
Expected: FAIL — `KILL_DEMAND_RATIO_THRESHOLD` / `collect_trending_now` don't exist, `classify()` on a demand-shaped raw candidate currently returns the Task-5 default `"go"` fallback instead of applying a threshold.

- [ ] **Step 3: Implement**

Add to `pipeline/research.py` (add `import json`, `import pipeline.anthropic_client as anthropic_client`, `import pipeline.etsy_client as etsy_client` to the imports):

```python
# Rough heuristic per SPEC_v4.10.md section 3 step 1 ("a keyword with very
# high competition and no differentiation angle" / "revisit at M3").
KILL_DEMAND_RATIO_THRESHOLD = 0.002

TRENDING_NOW_PROMPT = (
    "You are researching Etsy trends for a shop selling AI-generated botanical/minimalist "
    "wall art and posters. Using web search, identify 3-5 currently trending or rising search "
    "keywords/niches on Etsy that fit this niche (nature, botanical, minimalist landscape wall "
    "art). For each, give a short keyword phrase suitable for an Etsy search and a one-sentence "
    "rationale. Reply with ONLY a JSON list of objects with 'keyword' and 'rationale' fields, "
    "no other text."
)


def _classify_by_demand(raw: dict) -> dict:
    if raw["demand_ratio"] < KILL_DEMAND_RATIO_THRESHOLD:
        return {
            "go_hold_kill": "kill",
            "hold_recheck_date": None,
            "kill_reason": (
                f"demand_ratio {raw['demand_ratio']:.6f} below threshold "
                f"{KILL_DEMAND_RATIO_THRESHOLD} (listing_count={raw['listing_count']})"
            ),
        }
    return {"go_hold_kill": "go", "hold_recheck_date": None, "kill_reason": None}


def _build_demand_checked_candidate(keyword: str, rationale: str, source_label: str, *,
                                     etsy_api_key=None, etsy_api_secret=None) -> dict:
    demand = etsy_client.find_all_listings_active(
        keyword, limit=10, sort_on="favorites", sort_order="desc",
        api_key=etsy_api_key, api_secret=etsy_api_secret,
    )
    listing_count = demand["count"]
    results = demand["results"]
    avg_favorers = (sum(r["num_favorers"] for r in results) / len(results)) if results else 0.0
    demand_ratio = (avg_favorers / listing_count) if listing_count else 0.0
    return {
        "niche": keyword,
        "trend_source": f"{source_label}:{keyword}",
        "rationale": rationale,
        "window_start": None,
        "window_end": None,
        "demand_ratio": demand_ratio,
        "listing_count": listing_count,
    }


def collect_trending_now(*, anthropic_api_key=None, etsy_api_key=None, etsy_api_secret=None) -> list:
    search_result = anthropic_client.research_web_search(TRENDING_NOW_PROMPT, api_key=anthropic_api_key)
    keyword_ideas = json.loads(search_result["text"])
    return [
        _build_demand_checked_candidate(
            idea["keyword"], idea["rationale"], "trending_now",
            etsy_api_key=etsy_api_key, etsy_api_secret=etsy_api_secret,
        )
        for idea in keyword_ideas
    ]
```

Malformed JSON from the Claude call is not caught here — it fails loudly with a `JSONDecodeError`, matching this pipeline's established "never silently skip" posture (CLAUDE.md's placeholder-template rule is the same pattern applied elsewhere).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_research.py -v`
Expected: all PASS (10 tests total so far).

- [ ] **Step 5: Commit**

```bash
git add pipeline/research.py tests/test_research.py
git commit -m "feat: add research.py demand-proxy classification and trending-now collector"
```

---

## Task 7: `research.py` — on-demand collector

**Files:**
- Modify: `pipeline/research.py`
- Modify: `tests/test_research.py`

**Interfaces:**
- Consumes: `_build_demand_checked_candidate(...)` (Task 6).
- Produces: `collect_on_demand(topic: str, *, etsy_api_key=None, etsy_api_secret=None) -> dict` (a single `RawCandidate`, not a list).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_research.py`:

```python
def test_collect_on_demand_returns_single_demand_checked_candidate():
    def fake_find_listings(keywords, **kwargs):
        assert keywords == "coastal minimalist print"
        return {"count": 500, "results": [{"num_favorers": 2}]}

    with patch("pipeline.research.etsy_client.find_all_listings_active", side_effect=fake_find_listings):
        raw = research.collect_on_demand("coastal minimalist print")

    assert raw["niche"] == "coastal minimalist print"
    assert raw["trend_source"] == "telegram_on_demand:coastal minimalist print"
    assert raw["listing_count"] == 500
    assert raw["demand_ratio"] == 2 / 500
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_research.py -v`
Expected: FAIL — `collect_on_demand` doesn't exist yet.

- [ ] **Step 3: Implement**

Add to `pipeline/research.py`:

```python
def collect_on_demand(topic: str, *, etsy_api_key=None, etsy_api_secret=None) -> dict:
    return _build_demand_checked_candidate(
        topic, "Requested via Telegram /research command", "telegram_on_demand",
        etsy_api_key=etsy_api_key, etsy_api_secret=etsy_api_secret,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_research.py -v`
Expected: all PASS (11 tests total so far).

- [ ] **Step 5: Commit**

```bash
git add pipeline/research.py tests/test_research.py
git commit -m "feat: add research.py on-demand (Telegram /research) collector"
```

---

## Task 8: `research.py` — DB writer

**Files:**
- Modify: `pipeline/research.py`
- Modify: `tests/test_research.py`

**Interfaces:**
- Consumes: `db.get_connection` / `db.init_db` (from `pipeline/db.py`, already built).
- Produces: `_insert_candidate(conn, raw: dict, classification: dict, *, now=None) -> int` (returns the new `candidates.id`).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_research.py`:

```python
from datetime import datetime

import pipeline.db as db


def _fresh_conn(tmp_path):
    conn = db.get_connection(tmp_path / "test.sqlite3")
    db.init_db(conn)
    return conn


def test_insert_candidate_writes_go_row_as_pending(tmp_path):
    conn = _fresh_conn(tmp_path)
    raw = {"niche": "monstera line art", "trend_source": "trending_now:monstera line art"}
    classification = {"go_hold_kill": "go", "hold_recheck_date": None, "kill_reason": None}

    candidate_id = research._insert_candidate(conn, raw, classification, now=datetime(2026, 7, 8, 10, 0, 0))

    row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    assert row["niche"] == "monstera line art"
    assert row["go_hold_kill"] == "go"
    assert row["status"] == "pending"
    assert row["created_at"] == "2026-07-08T10:00:00"
    conn.close()


def test_insert_candidate_writes_hold_row_as_abandoned(tmp_path):
    conn = _fresh_conn(tmp_path)
    raw = {"niche": "holiday design", "trend_source": "event_lookahead:holiday_peak"}
    classification = {"go_hold_kill": "hold", "hold_recheck_date": "2027-09-11", "kill_reason": None}

    candidate_id = research._insert_candidate(conn, raw, classification, now=datetime(2026, 7, 8, 10, 0, 0))

    row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    assert row["go_hold_kill"] == "hold"
    assert row["hold_recheck_date"] == "2027-09-11"
    assert row["status"] == "abandoned"
    conn.close()


def test_insert_candidate_writes_kill_row_as_abandoned_with_reason(tmp_path):
    conn = _fresh_conn(tmp_path)
    raw = {"niche": "saturated term", "trend_source": "trending_now:saturated term"}
    classification = {"go_hold_kill": "kill", "hold_recheck_date": None, "kill_reason": "demand_ratio too low"}

    candidate_id = research._insert_candidate(conn, raw, classification, now=datetime(2026, 7, 8, 10, 0, 0))

    row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    assert row["go_hold_kill"] == "kill"
    assert row["kill_reason"] == "demand_ratio too low"
    assert row["status"] == "abandoned"
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_research.py -v`
Expected: FAIL — `_insert_candidate` doesn't exist yet.

- [ ] **Step 3: Implement**

Add to `pipeline/research.py` (add `from datetime import datetime` to the imports, alongside the existing `date`/`timedelta` import):

```python
def _insert_candidate(conn, raw: dict, classification: dict, *, now=None) -> int:
    now = now or datetime.utcnow()
    timestamp = now.isoformat()
    status = "pending" if classification["go_hold_kill"] == "go" else "abandoned"

    cursor = conn.execute(
        """
        INSERT INTO candidates (
            created_at, niche, trend_source, go_hold_kill, hold_recheck_date,
            kill_reason, status, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            timestamp, raw["niche"], raw["trend_source"], classification["go_hold_kill"],
            classification["hold_recheck_date"], classification["kill_reason"], status, timestamp,
        ),
    )
    conn.commit()
    return cursor.lastrowid
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_research.py -v`
Expected: all PASS (14 tests total so far).

- [ ] **Step 5: Commit**

```bash
git add pipeline/research.py tests/test_research.py
git commit -m "feat: add research.py candidates DB writer"
```

---

## Task 9: `research.py` — `run_research_cycle` orchestrator + safe-evergreen fallback wiring

**Files:**
- Modify: `pipeline/research.py`
- Modify: `tests/test_research.py`

**Interfaces:**
- Consumes: every function produced in Tasks 4-8.
- Produces: `run_research_cycle(conn, static_config, *, on_demand_topics=None, now=None) -> list[int]` — the module's public entry point, to be called by the not-yet-built twice-daily batch orchestrator.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_research.py`:

```python
def test_run_research_cycle_writes_all_collected_candidates(tmp_path):
    conn = _fresh_conn(tmp_path)

    def fake_web_search(prompt, api_key=None, max_tokens=2048):
        return {"text": json.dumps([{"keyword": "monstera line art", "rationale": "rising"}]), "raw": {}}

    def fake_find_listings(keywords, **kwargs):
        return {"count": 1000, "results": [{"num_favorers": 50}]}  # ratio 0.05, well above threshold -> go

    with patch("pipeline.research.anthropic_client.research_web_search", side_effect=fake_web_search), \
         patch("pipeline.research.etsy_client.find_all_listings_active", side_effect=fake_find_listings):
        inserted_ids = research.run_research_cycle(conn, {}, now=date(2026, 9, 1))

    rows = conn.execute("SELECT * FROM candidates").fetchall()
    assert len(rows) == len(inserted_ids)
    assert len(rows) == len(research.EVENT_WINDOWS_2026) + 1  # 6 event candidates + 1 trending-now
    conn.close()


def test_run_research_cycle_includes_on_demand_topics(tmp_path):
    conn = _fresh_conn(tmp_path)

    def fake_web_search(prompt, api_key=None, max_tokens=2048):
        return {"text": "[]", "raw": {}}

    def fake_find_listings(keywords, **kwargs):
        return {"count": 1000, "results": [{"num_favorers": 50}]}

    with patch("pipeline.research.anthropic_client.research_web_search", side_effect=fake_web_search), \
         patch("pipeline.research.etsy_client.find_all_listings_active", side_effect=fake_find_listings):
        research.run_research_cycle(conn, {}, on_demand_topics=["desert minimalist art"], now=date(2026, 9, 1))

    row = conn.execute(
        "SELECT * FROM candidates WHERE trend_source = ?", ("telegram_on_demand:desert minimalist art",)
    ).fetchone()
    assert row is not None
    assert row["go_hold_kill"] == "go"
    conn.close()


def test_run_research_cycle_falls_back_to_safe_evergreen_when_nothing_goes(tmp_path):
    conn = _fresh_conn(tmp_path)

    def fake_web_search(prompt, api_key=None, max_tokens=2048):
        return {"text": "[]", "raw": {}}

    with patch("pipeline.research.anthropic_client.research_web_search", side_effect=fake_web_search):
        # now chosen so every event window (including engagement_season, which runs
        # to 2027-02-14 - the latest end date of any window) is within MIN_EVENT_LEAD_DAYS
        # of closing or already closed
        inserted_ids = research.run_research_cycle(conn, {}, now=date(2027, 2, 10))

    rows = conn.execute("SELECT * FROM candidates WHERE go_hold_kill = 'go'").fetchall()
    assert len(rows) == 1
    assert rows[0]["trend_source"].startswith("safe_evergreen_fallback:")
    assert len(inserted_ids) == len(research.EVENT_WINDOWS_2026) + 1  # events (all hold) + 1 fallback
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_research.py -v`
Expected: FAIL — `run_research_cycle` doesn't exist yet.

- [ ] **Step 3: Implement**

Add to `pipeline/research.py`:

```python
def run_research_cycle(conn, static_config, *, on_demand_topics=None, now=None) -> list:
    now_dt = datetime.combine(now, datetime.min.time()) if now else datetime.utcnow()
    today = now_dt.date()
    on_demand_topics = on_demand_topics or []

    raw_candidates = collect_event_lookahead()
    raw_candidates += collect_trending_now()
    for topic in on_demand_topics:
        raw_candidates.append(collect_on_demand(topic))

    inserted_ids = []
    any_go = False
    for raw in raw_candidates:
        classification = classify(raw, now=today)
        if classification["go_hold_kill"] == "go":
            any_go = True
        inserted_ids.append(_insert_candidate(conn, raw, classification, now=now_dt))

    if not any_go:
        fallback_raw = pick_safe_evergreen_fallback()
        fallback_classification = classify(fallback_raw, now=today)
        inserted_ids.append(_insert_candidate(conn, fallback_raw, fallback_classification, now=now_dt))

    return inserted_ids
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_research.py -v`
Expected: all PASS (17 tests total).

- [ ] **Step 5: Run the full test suite to confirm nothing else broke**

Run: `python -m pytest -v`
Expected: all PASS (etsy_client, anthropic_client, research, plus the pre-existing db/config/http/gelato/replicate/telegram suites).

- [ ] **Step 6: Commit**

```bash
git add pipeline/research.py tests/test_research.py
git commit -m "feat: add research.py run_research_cycle orchestrator with safe-evergreen fallback"
```

---

## Self-Review Notes

- **Spec coverage:** trending-now scan (Task 6), event lookahead (Task 5), Telegram on-demand (Task 7, minus the hourly-poll's own topic-persistence — explicitly out of scope, see Global Constraints), Go/Hold/Kill classification (Tasks 5+6), safe-evergreen fallback (Tasks 4+9) are all covered. Design generation, mockup, compliance draft, critic pass, digest are later stage modules, not this plan's scope.
- **Placeholder scan:** no TBD/"add error handling"/"similar to Task N" language. Task 3's Step 7 is a real, concrete manual step (exact command to run), not a placeholder — it mirrors the established `docs/etsy_call_response_example_from_manual_tests.txt` / `docs/gelato_call_response_example_from_manual_tests.txt` pattern already used twice in this repo.
- **Type consistency:** `RawCandidate` shape (defined in Task 5) is used identically by Tasks 6, 7, and 9. `classify()`'s return shape (`go_hold_kill`/`hold_recheck_date`/`kill_reason`) matches `_insert_candidate()`'s expected `classification` argument exactly (Task 8). `find_all_listings_active`'s signature (Task 2) matches every call site in Task 6/7 (`api_key`/`api_secret` keyword names line up).
