# API Client Wrappers — Design

**Status:** approved, pending final read-through
**Scope:** four thin HTTP wrapper modules (`telegram_client.py`, `replicate_client.py`,
`gelato_client.py`, `etsy_client.py`) that future pipeline stage modules (`research.py`,
`generate.py`, `primary_mockup.py`, ...) will call into. These are not pipeline stages
themselves — no cron cadence, no retry/orchestration policy, no business logic. They
build requests, send them, parse responses, and raise on failure.

Builds directly on the foundation layer (`pipeline/db.py`, `pipeline/config.py`) from
`docs/superpowers/plans/2026-07-06-qhoto-pipeline-foundation.md`, reusing its
conventions: stdlib only where reasonable, explicit params with sane defaults,
`MissingConfigError`/`require_env` for required secrets.

## Non-goals

- No pipeline stage logic (no critic-pass retry loop, no Go/Hold/Kill, no digest
  formatting, no polling *policy* — see "Async product creation" below).
- No Etsy OAuth token refresh (explicitly deferred — see that section).
- No Telegram inline-keyboard *construction* (callback-data encoding for
  candidate_id/group_type is a stage-module concern).

## 1. Shared HTTP transport — `pipeline/http.py`

One shared low-level seam used by all four clients, to avoid four near-identical
copies of "build a `urllib.request.Request`, send it, check status, decode JSON, raise
on failure":

```python
class HTTPError(Exception):
    def __init__(self, status_code: int, body: str):
        ...

def send(request: urllib.request.Request, timeout: int = 30) -> dict:
    """Opens the request via urllib. Raises HTTPError on non-2xx status.
    Returns json.loads(response_body), or {} if the body is empty."""
```

Callers (each client) build their own `urllib.request.Request` — JSON body via
`json.dumps(...).encode()` + `Content-Type: application/json`, or, for Etsy's one
multipart call, a hand-built `multipart/form-data` body — and pass it to `http.send()`.
This keeps `http.py` transport-only; each client owns its own exception type and
response-shape parsing on top of it.

**Why stdlib over `requests`:** consistent with `pipeline/config.py`'s existing
rationale for skipping `python-dotenv` (a small amount of code is simpler than a new
dependency). The one rough edge is Etsy's multipart image upload, which stdlib makes
uglier than `requests` would — accepted as a one-time cost in exchange for zero new
dependencies across the whole client layer.

**Testing:** tests use `unittest.mock.patch` on `urllib.request.urlopen` (the actual
network boundary) to inject canned responses and assert on the constructed request's
method/URL/headers/body. No live network calls, no new test dependency.

## 2. `telegram_client.py`

```python
def send_media_group(chat_id: str, photo_urls: list[str], *, bot_token: str = None) -> dict
def send_message(chat_id: str, text: str, reply_markup: dict = None, *, bot_token: str = None) -> dict
def get_updates(offset: int = None, timeout: int = 0, *, bot_token: str = None) -> list[dict]
def answer_callback_query(callback_query_id: str, text: str = None, *, bot_token: str = None) -> dict
```

- `bot_token=None` defaults to `config.require_env("TELEGRAM_BOT_TOKEN")`.
- Telegram wraps errors in a 200-status envelope (`{"ok": false, "description": ...}`);
  all four functions check `ok` and raise `TelegramAPIError(description)` when false,
  independent of `http.py`'s HTTP-status-level `HTTPError`.
- No keyboard-building helper here — `send_message`'s `reply_markup` is whatever dict
  the calling stage module hands it. Callback-data encoding (candidate_id + group_type
  for Approve/Edit/Reject) is a stage-module concern (digest.py, group_digest.py).
- No dry-run gating — not covered by CLAUDE.md's "never call without explicit
  go-ahead" constraint (that applies specifically to Etsy publish and Gelato
  product-create). A `dry_run` param may still be added later for test convenience if
  it turns out to matter, but isn't required now.

## 3. `replicate_client.py`

```python
FLUX_SCHNELL_MODEL = "black-forest-labs/flux-schnell"  # never substitute flux-dev without explicitly flagging it

class ReplicatePredictionTimeoutError(Exception): ...

def generate_image(prompt: str, *, api_token: str = None) -> dict
    # -> {"image_url": ..., "prediction_id": ...}
```

- Uses Replicate's `Prefer: wait` header to block synchronously on the model's
  predictions endpoint (schnell typically finishes in 1-2s) rather than a
  create-then-poll loop — one HTTP call, simpler client.
- After the response returns, checks the `status` field. If it isn't `"succeeded"`
  (i.e. the 60s synchronous wait window elapsed without finishing), raises
  `ReplicatePredictionTimeoutError` with an explicit message:
  *"Replicate prediction {id} did not complete within the 60s synchronous wait window
  (status: {status}). FLUX.1 schnell normally finishes in 1-2s — this likely indicates
  a Replicate-side outage or throttling, not a pipeline bug."*
- No dry-run gating (not covered by the hard constraint; schnell calls are cheap
  enough — ~$0.003/image — that this wasn't flagged as needing one).

## 4. `gelato_client.py`

```python
def get_template(template_id: str, *, store_id: str = None, api_key: str = None) -> dict
def create_product_from_template(
    template_id: str, template_variant_id: str, image_placeholder_name: str,
    image_url: str, title: str, *, store_id: str = None, api_key: str = None,
    dry_run: bool = None,
) -> dict
def get_product(product_id: str, *, store_id: str = None, api_key: str = None) -> dict
def delete_product(product_id: str, *, store_id: str = None, api_key: str = None, dry_run: bool = None) -> None
```

### Discovery from manually-run test calls (`docs/gelato_call_response_example_from_manual_tests.txt`)

Two real findings that shaped this signature list, neither obvious from the spec:

1. **`imagePlaceholders[].name` is not a fixed slot label** (e.g. not something generic
   like `"ImageFront"`) — the real test call used `"011_mt_sunday_brook.JPG"`, an
   asset-name-like identifier specific to how that template's placeholder was set up
   in the Gelato dashboard. Same for `templateVariantId` — required in the create
   request body, and not derivable from the template ID alone. Both are fixed once a
   template exists (same category as the template ID itself: resolved once, never
   discovered at runtime, per CLAUDE.md's static-config principle) — so both get
   folded into `config/static_config.json` alongside the template ID (see section 6),
   not fetched live by any pipeline stage. `get_template(template_id)` still exists on
   the client as a real wrapper around Gelato's fetch-by-id endpoint, but it's a
   one-off manual-resolution tool (used the same way you already use the Gelato
   dashboard to obtain the template ID itself) — no stage module calls it at runtime.
2. **Product creation is asynchronous.** The response immediately after
   `create-from-template` (`response2` in the test file) has `previewUrl: null`, empty
   `productImages`, `isReadyToPublish: false`, `status: "created"`. A later `GET` on
   the same product ID (`response1`) shows it fully rendered — `productImages`
   populated, `isReadyToPublish: true`. So `get_product(product_id)` is required as a
   second client function, and whatever future stage calls
   `create_product_from_template` (`primary_mockup.py`) must poll `get_product` until
   the gallery is populated before handing images to compliance-draft/critic-pass.
   **The client does not own this poll loop** — it exposes the two raw calls only;
   poll interval, timeout, and what happens on timeout are stage-level orchestration
   decisions for `primary_mockup.py` (out of scope for this plan) to make.

### Placeholder / dry-run gating

- `create_product_from_template` and `delete_product` both resolve
  `dry_run = dry_run if dry_run is not None else not config.is_live_mode("GELATO")`.
- When `dry_run` is `True`: log the request that would have been made, return a mock
  response shaped like the real one, make no network call.
- When `dry_run` is `False` (real call): first check
  `config.is_placeholder(...)` against **all three** of `template_id`,
  `template_variant_id`, and `image_placeholder_name` (each following the same
  `PLACEHOLDER_...` convention) and raise loudly if any is still a placeholder — a
  placeholder variant ID or placeholder name reaching a live call is exactly as
  dangerous as a placeholder template ID.
- `store_id` defaults to `os.environ.get("GELATO_STORE_ID")` when `dry_run` is `True`
  (a blank/missing value is fine — nothing goes over the wire), but resolves via
  `config.require_env("GELATO_STORE_ID")` (raises `MissingConfigError` with a clear
  message) when `dry_run` is `False` — i.e. you're only asked to fill it in exactly
  when it's about to matter.

## 5. `etsy_client.py`

```python
def get_seller_taxonomy_nodes(*, access_token: str = None) -> list[dict]
def create_draft_listing(shop_id: str, listing_data: dict, *, access_token: str = None, dry_run: bool = None) -> dict
def upload_listing_image(shop_id: str, listing_id: str, image_bytes: bytes, *, access_token: str = None, dry_run: bool = None) -> dict
```

- `listing_data` is a plain dict assembled by the calling stage (compliance-draft /
  publish-primary-group / publish-group) — the client doesn't know about
  `who_made`/title-length limits/tag counts, it posts what it's given. Etsy field
  validation (13 tags ≤20 chars, 140-char title) stays a stage-level concern per
  CLAUDE.md, not duplicated here.
- **Image upload confirmed as binary, not URL-based**: Etsy's Open API v3
  `uploadListingImage` takes either raw `image` bytes (multipart) or a
  `listing_image_id` referencing an already-uploaded image — no URL-fetch parameter
  exists in v3 (confirmed via Etsy's own docs/GitHub discussions). So
  `upload_listing_image` takes `image_bytes: bytes` — the calling stage is
  responsible for downloading Gelato's `fileUrl`/`previewUrl` bytes first.
- Same `dry_run` mechanism as Gelato: `ETSY_LIVE_MODE` env var, defaults to dry-run
  (fail-closed), gates `create_draft_listing` and `upload_listing_image` (the two
  "publish"-adjacent calls) but not `get_seller_taxonomy_nodes` (read-only, resolved
  once per CLAUDE.md's static-config policy anyway).

### Deferred: OAuth token refresh

Etsy access tokens expire hourly (`ETSY_ACCESS_TOKEN` in `.env`, alongside
`ETSY_REFRESH_TOKEN`). **`etsy_client.py` does not auto-refresh on a 401** — this is
explicitly out of scope for this plan. Noted here so it isn't silently lost: a
separate `etsy_auth.py` helper implementing the refresh-token grant will be needed
before M2's unattended scheduled runs (M1 is manual, one-candidate-at-a-time, so
re-authenticating by hand between runs is acceptable for now).

## 6. Config schema change (touches already-merged code)

`config/static_config.json`'s `gelato_templates` entries change from a flat
template-ID string per size/orientation to an object carrying all three Gelato-side
identifiers discovered above:

```json
"8x12_portrait": {
  "template_id": "PLACEHOLDER_8x12_PORTRAIT",
  "template_variant_id": "PLACEHOLDER_8x12_PORTRAIT_VARIANT",
  "image_placeholder_name": "PLACEHOLDER_8x12_PORTRAIT_IMAGE_SLOT"
}
```
(same for all 12 size/orientation entries)

`pipeline/config.py` changes (already-merged file, `pipeline/config.py:49-51`):

- `get_template_id(static_config, size, orientation) -> str` — keeps its existing
  name and return type (still returns just the template ID string), but now reads
  `static_config["gelato_templates"][key]["template_id"]` instead of the flat string.
- New: `get_template_variant(static_config, size, orientation) -> dict` — returns the
  full entry (`template_id`, `template_variant_id`, `image_placeholder_name`), which
  is what `gelato_client.create_product_from_template` actually needs.
- `is_placeholder(value: str) -> bool` is unchanged (still just checks the
  `PLACEHOLDER_` prefix), but now gets called against all three fields individually
  by `gelato_client.py`, not just the template ID.

`tests/test_config.py` needs corresponding updates: the fixture in
`test_get_template_id_returns_configured_value` and
`test_get_template_id_raises_on_unknown_size_orientation` moves from a flat string to
the nested-dict shape; `test_repo_static_config_has_all_twelve_template_slots` checks
for the three nested keys per slot instead of a bare string; new tests cover
`get_template_variant`.

## 7. File / module layout

```
pipeline/
  http.py                  # shared transport: send(request) -> dict, raises HTTPError
  telegram_client.py
  replicate_client.py
  gelato_client.py
  etsy_client.py
tests/
  test_http.py
  test_telegram_client.py
  test_replicate_client.py
  test_gelato_client.py
  test_etsy_client.py
```

`.env.example` gains `GELATO_STORE_ID=`, `GELATO_LIVE_MODE=`, `ETSY_LIVE_MODE=`
(blank placeholders, same convention as the existing entries).

## 8. Live-mode flags — final mechanism

Per-service, not global (M1's milestones fill in Gelato templates before Etsy publish
is even attempted, so independent control matters):

- `GELATO_LIVE_MODE` and `ETSY_LIVE_MODE`, read via a new
  `config.is_live_mode(service: str) -> bool` helper, called as
  `config.is_live_mode("GELATO")` / `config.is_live_mode("ETSY")` — it reads
  `os.environ.get(f"{service}_LIVE_MODE")` and returns `True` only if that value is
  exactly `"true"`; anything else, including unset, is dry-run.
- Default (unset) is always dry-run — fail-closed, satisfying CLAUDE.md's "never call
  Etsy publish or Gelato product-create against real endpoints without an explicit
  go-ahead."
- Each gated client function's `dry_run` parameter can still be overridden directly
  (e.g. from tests) independent of the env var.
