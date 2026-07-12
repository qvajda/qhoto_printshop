# Publish Primary Group Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `pipeline/publish_primary_group.py`, the hourly-poll pipeline stage that reads an admin's Approve/Edit/Reject decision on `digest.py`'s primary-group Telegram message and, on approval, publishes all four primary-group sizes (8x12, A3, A2, A1) as Gelato products + live Etsy listings.

**Architecture:** Two new small additions to existing client modules (`http.fetch_bytes`, `etsy_client.update_listing_state`), one new DB table (`telegram_offset`, for `getUpdates` offset tracking), and one new stage module built bottom-up: callback parsing → decision recording → per-size Etsy listing data → per-size Gelato product creation → per-size Etsy publish → retry-once wrapper → 4-size orchestrator → approve/edit/reject routing → the hourly-poll entrypoint.

**Tech Stack:** Python stdlib (`sqlite3`, `urllib.request`, `json`, `datetime`), `pytest` + `unittest.mock.patch` for tests, existing `pipeline/` client modules.

## Global Constraints

- Every inbound Telegram message/callback is checked against `TELEGRAM_ADMIN_CHAT_ID` before being treated as real; anything else is discarded and logged, never acted on (CLAUDE.md).
- A design is only ever image-generated once. The edit path regenerates the primary size only — never triggers the 5x7/10x24 groups (CLAUDE.md, SPEC_v4.10.md D6).
- This stage does **not** trigger `group_mockup.py`/`group_critic_pass.py`/`group_digest.py` — it leaves `groups.status = 'approved_published'` on the primary group for a future stage to find (agreed design scope, section 2 of the design doc).
- A still-placeholder Gelato `templateId` reaching a real (non-dry-run) `create_product_from_template` call must fail loud — already enforced by `gelato_client.GelatoPlaceholderTemplateError`; no new enforcement needed here (CLAUDE.md).
- `etsy_section_id` and the per-size `etsy_shipping_profile_id` mapping remain unresolved in `config/static_config.json` — out of scope for this stage (agreed in design review). Real (non-dry-run) Etsy publish calls stay blocked on those until filled in; dry-run/mocked builds and tests are unaffected.
- Never call Gelato/Etsy real endpoints without an explicit go-ahead — every new client function threads a `dry_run` parameter the same way `gelato_client`/`etsy_client` already do (CLAUDE.md).
- Etsy's `who_made`/`is_supply`/`when_made` must be `"i_did"`/`false`/`"made_to_order"` together on every listing (CLAUDE.md) — pulled from the already-resolved `listing_texts` row plus a fixed `when_made`/`is_supply` pair.

---

### Task 1: `telegram_offset` table

**Files:**
- Modify: `db/schema.sql`
- Test: `tests/test_db.py`

**Interfaces:**
- Produces: a `telegram_offset` table (`id INTEGER PRIMARY KEY CHECK (id = 1)`, `last_update_id INTEGER NOT NULL`) — a single-row table holding the last Telegram `update_id` processed, so the hourly poll doesn't reprocess old updates.

- [ ] **Step 1: Write the failing test**

Add `"telegram_offset"` to the `EXPECTED_TABLES` set near the top of `tests/test_db.py`:

```python
EXPECTED_TABLES = {
    "candidates",
    "listing_texts",
    "groups",
    "critic_pass_attempts",
    "group_products",
    "product_images",
    "group_messages",
    "telegram_events_log",
    "listing_metrics_snapshots",
    "telegram_offset",
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_db.py::test_init_db_creates_all_tables -v`
Expected: FAIL — `telegram_offset` not in `tables`.

- [ ] **Step 3: Add the table to the schema**

Append to `db/schema.sql`:

```sql
CREATE TABLE IF NOT EXISTS telegram_offset (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  last_update_id INTEGER NOT NULL
);
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_db.py -v`
Expected: PASS (all `test_db.py` tests, including the existing idempotency/foreign-key ones).

- [ ] **Step 5: Commit**

```bash
git add db/schema.sql tests/test_db.py
git commit -m "feat: add telegram_offset table for hourly-poll update_id tracking"
```

---

### Task 2: `http.fetch_bytes`

**Files:**
- Modify: `pipeline/http.py`
- Test: `tests/test_http.py`

**Interfaces:**
- Produces: `http.fetch_bytes(url: str, timeout: int = 30) -> bytes` — raises `http.HTTPError` on non-2xx, same as `http.send`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_http.py`:

```python
def test_fetch_bytes_returns_raw_bytes_on_success():
    captured = {}

    def fake_urlopen(request, timeout=30):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        return _mock_response(b"\x89PNG raw bytes")

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        result = http.fetch_bytes("https://gelato/flat.jpg")

    assert result == b"\x89PNG raw bytes"
    assert captured["url"] == "https://gelato/flat.jpg"
    assert captured["method"] == "GET"


def test_fetch_bytes_raises_http_error_on_non_2xx():
    error = urllib.error.HTTPError(
        url="https://gelato/missing.jpg", code=404, msg="Not Found",
        hdrs=None, fp=io.BytesIO(b"not found"),
    )

    with patch("urllib.request.urlopen", side_effect=error):
        with pytest.raises(http.HTTPError) as exc_info:
            http.fetch_bytes("https://gelato/missing.jpg")

    assert exc_info.value.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_http.py -v`
Expected: FAIL — `AttributeError: module 'pipeline.http' has no attribute 'fetch_bytes'`.

- [ ] **Step 3: Implement `fetch_bytes`**

Add to `pipeline/http.py` (below `send`):

```python
def fetch_bytes(url: str, timeout: int = 30) -> bytes:
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as e:
        raise HTTPError(e.code, e.read().decode("utf-8")) from e
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_http.py -v`
Expected: PASS (all tests in the file).

- [ ] **Step 5: Commit**

```bash
git add pipeline/http.py tests/test_http.py
git commit -m "feat: add http.fetch_bytes for downloading raw image bytes"
```

---

### Task 3: `etsy_client.update_listing_state`

**Files:**
- Modify: `pipeline/etsy_client.py`
- Test: `tests/test_etsy_client.py`

**Interfaces:**
- Produces: `etsy_client.update_listing_state(shop_id: str, listing_id: str, state: str, *, api_key=None, api_secret=None, access_token=None, dry_run=None) -> dict`. Verified live against Etsy's OpenAPI 3.0 spec: `PATCH /v3/application/shops/{shop_id}/listings/{listing_id}` with body `{"state": state}` — the only way to move `draft` → `active`; the listing must already have at least one image uploaded first.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_etsy_client.py`:

```python
def test_update_listing_state_dry_run_makes_no_network_call():
    with patch("pipeline.etsy_client.http.send") as mock_send:
        result = etsy_client.update_listing_state(
            "shop1", "listing1", "active", api_key="key1", access_token="token1", dry_run=True
        )

    mock_send.assert_not_called()
    assert result == {"listing_id": "listing1", "state": "active", "_dry_run": True}


def test_update_listing_state_sends_patch_with_state_body_when_live():
    captured = {}

    def fake_send(request, timeout=30):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["body"] = json.loads(request.data)
        return {"listing_id": 999, "state": "active"}

    with patch("pipeline.etsy_client.http.send", side_effect=fake_send):
        result = etsy_client.update_listing_state(
            "shop1", "listing1", "active",
            api_key="key1", api_secret="secret1", access_token="token1", dry_run=False,
        )

    assert captured["url"] == "https://openapi.etsy.com/v3/application/shops/shop1/listings/listing1"
    assert captured["method"] == "PATCH"
    assert captured["body"] == {"state": "active"}
    assert result == {"listing_id": 999, "state": "active"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_etsy_client.py -v`
Expected: FAIL — `AttributeError: module 'pipeline.etsy_client' has no attribute 'update_listing_state'`.

- [ ] **Step 3: Implement `update_listing_state`**

Add to `pipeline/etsy_client.py` (below `create_draft_listing`):

```python
def update_listing_state(
    shop_id: str, listing_id: str, state: str, *, api_key: str = None, api_secret: str = None,
    access_token: str = None, dry_run: bool = None
) -> dict:
    if dry_run is None:
        dry_run = not config.is_live_mode("ETSY")

    if dry_run:
        return {"listing_id": listing_id, "state": state, "_dry_run": True}

    api_key = api_key or config.require_env("ETSY_API_KEY")
    api_secret = api_secret or config.require_env("ETSY_API_SECRET")
    access_token = access_token or config.require_env("ETSY_ACCESS_TOKEN")
    url = f"{ETSY_API_BASE}/shops/{shop_id}/listings/{listing_id}"
    body = json.dumps({"state": state}).encode("utf-8")
    headers = _headers(api_key, api_secret, access_token)
    headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, headers=headers, method="PATCH")
    return http.send(request)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_etsy_client.py -v`
Expected: PASS (all tests in the file).

- [ ] **Step 5: Commit**

```bash
git add pipeline/etsy_client.py tests/test_etsy_client.py
git commit -m "feat: add etsy_client.update_listing_state to activate draft listings"
```

---

### Task 4: callback parsing and admin allowlist check

**Files:**
- Create: `pipeline/publish_primary_group.py`
- Test: `tests/test_publish_primary_group.py`

**Interfaces:**
- Produces:
  - `resolve_callback(update: dict) -> dict | None` — `{telegram_user_id, callback_query_id, action, group_id, message_id, chat_id}` or `None` if the update isn't a callback_query.
  - `is_admin(telegram_user_id, admin_chat_id) -> bool`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_publish_primary_group.py`:

```python
import pipeline.publish_primary_group as publish_primary_group


def _callback_update(update_id=100000001, user_id=987654321, data="approve:42",
                      message_id=202, chat_id=987654321, callback_id="cbq123"):
    return {
        "update_id": update_id,
        "callback_query": {
            "id": callback_id,
            "from": {"id": user_id, "is_bot": False, "first_name": "Admin"},
            "message": {
                "message_id": message_id,
                "chat": {"id": chat_id, "type": "private"},
                "date": 1234567890,
                "text": "Candidate #7 - Primary group (#42)",
            },
            "chat_instance": "abc123",
            "data": data,
        },
    }


def test_resolve_callback_parses_action_group_id_and_routing_fields():
    update = _callback_update()

    parsed = publish_primary_group.resolve_callback(update)

    assert parsed == {
        "telegram_user_id": 987654321,
        "callback_query_id": "cbq123",
        "action": "approve",
        "group_id": 42,
        "message_id": 202,
        "chat_id": 987654321,
    }


def test_resolve_callback_parses_edit_and_reject_actions():
    edit_parsed = publish_primary_group.resolve_callback(_callback_update(data="edit:7"))
    reject_parsed = publish_primary_group.resolve_callback(_callback_update(data="reject:7"))

    assert edit_parsed["action"] == "edit"
    assert reject_parsed["action"] == "reject"
    assert edit_parsed["group_id"] == 7


def test_resolve_callback_returns_none_for_non_callback_update():
    update = {"update_id": 5, "message": {"text": "/research botanical"}}

    assert publish_primary_group.resolve_callback(update) is None


def test_is_admin_true_when_ids_match_across_int_and_str():
    assert publish_primary_group.is_admin(987654321, "987654321") is True
    assert publish_primary_group.is_admin("987654321", 987654321) is True


def test_is_admin_false_when_ids_differ():
    assert publish_primary_group.is_admin(111111111, "987654321") is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_publish_primary_group.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pipeline.publish_primary_group'`.

- [ ] **Step 3: Implement `resolve_callback` and `is_admin`**

Create `pipeline/publish_primary_group.py`:

```python
import json
from datetime import datetime, timezone

import pipeline.compliance_draft as compliance_draft
import pipeline.config as config
import pipeline.critic_pass as critic_pass
import pipeline.etsy_client as etsy_client
import pipeline.gelato_client as gelato_client
import pipeline.generate as generate
import pipeline.http as http
import pipeline.primary_mockup as primary_mockup
import pipeline.telegram_client as telegram_client


def resolve_callback(update: dict) -> dict | None:
    callback_query = update.get("callback_query")
    if callback_query is None:
        return None

    action, _, group_id = callback_query["data"].partition(":")
    return {
        "telegram_user_id": callback_query["from"]["id"],
        "callback_query_id": callback_query["id"],
        "action": action,
        "group_id": int(group_id),
        "message_id": callback_query["message"]["message_id"],
        "chat_id": callback_query["message"]["chat"]["id"],
    }


def is_admin(telegram_user_id, admin_chat_id) -> bool:
    return str(telegram_user_id) == str(admin_chat_id)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_publish_primary_group.py -v`
Expected: PASS (all 5 tests).

- [ ] **Step 5: Commit**

```bash
git add pipeline/publish_primary_group.py tests/test_publish_primary_group.py
git commit -m "feat: add publish_primary_group callback parsing and admin check"
```

---

### Task 5: event logging and decision recording

**Files:**
- Modify: `pipeline/publish_primary_group.py`
- Test: `tests/test_publish_primary_group.py`

**Interfaces:**
- Consumes: `pipeline.db` (`get_connection`, `init_db`), schema tables `telegram_events_log`, `groups`.
- Produces:
  - `log_telegram_event(conn, telegram_user_id, raw_payload, accepted, action_taken=None, *, now=None) -> int`
  - `record_decision(conn, group_id, decision, decision_notes=None, *, now=None) -> None` — writes `groups.decision`/`decision_notes`/`decided_at`/`updated_at`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_publish_primary_group.py` (add these imports at the top alongside the existing one):

```python
from datetime import datetime

import pipeline.db as db


def _fresh_conn(tmp_path):
    conn = db.get_connection(tmp_path / "test.sqlite3")
    db.init_db(conn)
    return conn


def _insert_candidate(conn, niche="monstera line art", *, status="primary_review",
                       base_image_url="https://replicate.delivery/out.png"):
    timestamp = "2026-07-12T09:00:00"
    cursor = conn.execute(
        """
        INSERT INTO candidates (created_at, niche, go_hold_kill, status, base_image_url, updated_at)
        VALUES (?, ?, 'go', ?, ?, ?)
        """,
        (timestamp, niche, status, base_image_url, timestamp),
    )
    conn.commit()
    return cursor.lastrowid


def _insert_primary_group(conn, candidate_id, *, status="pending_review"):
    timestamp = "2026-07-12T09:05:00"
    cursor = conn.execute(
        "INSERT INTO groups (candidate_id, group_type, status, created_at, updated_at) "
        "VALUES (?, 'primary', ?, ?, ?)",
        (candidate_id, status, timestamp, timestamp),
    )
    conn.commit()
    return cursor.lastrowid


def test_log_telegram_event_writes_accepted_row(tmp_path):
    conn = _fresh_conn(tmp_path)

    event_id = publish_primary_group.log_telegram_event(
        conn, 987654321, {"update_id": 1}, True, "approve",
        now=datetime(2026, 7, 12, 9, 0, 0),
    )

    row = conn.execute("SELECT * FROM telegram_events_log WHERE id = ?", (event_id,)).fetchone()
    assert row["telegram_user_id"] == "987654321"
    assert row["accepted"] == 1
    assert row["action_taken"] == "approve"
    assert row["raw_payload"] == '{"update_id": 1}'
    assert row["received_at"] == "2026-07-12T09:00:00"
    conn.close()


def test_log_telegram_event_writes_discarded_row_with_no_action(tmp_path):
    conn = _fresh_conn(tmp_path)

    event_id = publish_primary_group.log_telegram_event(
        conn, 111111111, {"update_id": 2}, False, now=datetime(2026, 7, 12, 9, 0, 0),
    )

    row = conn.execute("SELECT * FROM telegram_events_log WHERE id = ?", (event_id,)).fetchone()
    assert row["accepted"] == 0
    assert row["action_taken"] is None
    conn.close()


def test_record_decision_writes_decision_notes_and_decided_at(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_primary_group(conn, candidate_id)

    publish_primary_group.record_decision(
        conn, group_id, "edited", "make it more pastel", now=datetime(2026, 7, 12, 9, 30, 0),
    )

    row = conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone()
    assert row["decision"] == "edited"
    assert row["decision_notes"] == "make it more pastel"
    assert row["decided_at"] == "2026-07-12T09:30:00"
    assert row["updated_at"] == "2026-07-12T09:30:00"
    conn.close()


def test_record_decision_allows_null_notes(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_primary_group(conn, candidate_id)

    publish_primary_group.record_decision(conn, group_id, "approved", now=datetime(2026, 7, 12, 9, 30, 0))

    row = conn.execute("SELECT decision, decision_notes FROM groups WHERE id = ?", (group_id,)).fetchone()
    assert row["decision"] == "approved"
    assert row["decision_notes"] is None
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_publish_primary_group.py -v`
Expected: FAIL — `AttributeError` for `log_telegram_event` and `record_decision`.

- [ ] **Step 3: Implement `log_telegram_event` and `record_decision`**

Add to `pipeline/publish_primary_group.py`:

```python
def log_telegram_event(conn, telegram_user_id, raw_payload, accepted, action_taken=None, *, now=None) -> int:
    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()
    cursor = conn.execute(
        """
        INSERT INTO telegram_events_log (received_at, telegram_user_id, raw_payload, accepted, action_taken)
        VALUES (?, ?, ?, ?, ?)
        """,
        (timestamp, str(telegram_user_id), json.dumps(raw_payload), 1 if accepted else 0, action_taken),
    )
    conn.commit()
    return cursor.lastrowid


def record_decision(conn, group_id, decision, decision_notes=None, *, now=None) -> None:
    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()
    conn.execute(
        "UPDATE groups SET decision = ?, decision_notes = ?, decided_at = ?, updated_at = ? WHERE id = ?",
        (decision, decision_notes, timestamp, timestamp, group_id),
    )
    conn.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_publish_primary_group.py -v`
Expected: PASS (all tests in the file).

- [ ] **Step 5: Commit**

```bash
git add pipeline/publish_primary_group.py tests/test_publish_primary_group.py
git commit -m "feat: add telegram event logging and group decision recording"
```

---

### Task 6: per-size Etsy listing data

**Files:**
- Modify: `pipeline/publish_primary_group.py`
- Test: `tests/test_publish_primary_group.py`

**Interfaces:**
- Consumes: `compliance_draft.validate_listing_text(title: str, tags: list) -> None` (raises `ValueError` on Etsy's 140-char title / 13-tag / 20-char-tag limits).
- Produces: `build_size_listing_data(listing_text: dict, size: str, price_eur: float) -> dict` — `listing_text` is a full `listing_texts` DB row (title, tags, description, who_made, production_partner_ids, taxonomy_id, shipping_profile_id). Returns the dict `etsy_client.create_draft_listing` expects as `listing_data`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_publish_primary_group.py`:

```python
import json as _json


def _listing_text_row(title="Monstera Line Art Botanical Print", tags=("botanical", "wall art")):
    return {
        "title": title,
        "tags": _json.dumps(list(tags)),
        "description": "A minimalist botanical print.",
        "disclosure_text": "AI disclosure text.",
        "who_made": "i_did",
        "production_partner_ids": _json.dumps([5717252]),
        "taxonomy_id": "1027",
        "shipping_profile_id": "",
    }


def test_build_size_listing_data_appends_size_suffix_for_secondary_sizes():
    data = publish_primary_group.build_size_listing_data(_listing_text_row(), "A3", 35)

    assert data["title"] == "Monstera Line Art Botanical Print - A3 Print"
    assert data["price"] == 35
    assert data["description"] == "A minimalist botanical print."
    assert data["tags"] == ["botanical", "wall art"]
    assert data["who_made"] == "i_did"
    assert data["when_made"] == "made_to_order"
    assert data["is_supply"] is False
    assert data["taxonomy_id"] == "1027"
    assert data["production_partner_ids"] == [5717252]


def test_build_size_listing_data_uses_base_title_unchanged_for_8x12():
    data = publish_primary_group.build_size_listing_data(_listing_text_row(), "8x12", 24)

    assert data["title"] == "Monstera Line Art Botanical Print"
    assert data["price"] == 24


def test_build_size_listing_data_raises_when_suffixed_title_exceeds_140_chars():
    long_title = "x" * 137  # + " - A3 Print" (11 chars) = 148, over the 140 cap
    listing_text = _listing_text_row(title=long_title)

    with pytest.raises(ValueError, match="140"):
        publish_primary_group.build_size_listing_data(listing_text, "A3", 35)
```

Add `import pytest` at the top of `tests/test_publish_primary_group.py` if not already present.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_publish_primary_group.py -v`
Expected: FAIL — `AttributeError: module 'pipeline.publish_primary_group' has no attribute 'build_size_listing_data'`.

- [ ] **Step 3: Implement `build_size_listing_data`**

Add to `pipeline/publish_primary_group.py`:

```python
# Etsy has no "unlimited stock" flag for made-to-order POD items; 999 is the
# conventional large-placeholder quantity for this listing style.
LISTING_QUANTITY = 999

SIZE_TITLE_SUFFIXES = {
    "8x12": "",
    "A3": " - A3 Print",
    "A2": " - A2 Print",
    "A1": " - A1 Print",
}


def build_size_listing_data(listing_text: dict, size: str, price_eur: float) -> dict:
    tags = json.loads(listing_text["tags"])
    title = f"{listing_text['title']}{SIZE_TITLE_SUFFIXES[size]}"
    compliance_draft.validate_listing_text(title, tags)
    return {
        "title": title,
        "description": listing_text["description"],
        "price": price_eur,
        "quantity": LISTING_QUANTITY,
        "who_made": listing_text["who_made"],
        "when_made": "made_to_order",
        "is_supply": False,
        "taxonomy_id": listing_text["taxonomy_id"],
        "shipping_profile_id": listing_text["shipping_profile_id"],
        "production_partner_ids": json.loads(listing_text["production_partner_ids"]),
        "tags": tags,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_publish_primary_group.py -v`
Expected: PASS (all tests in the file).

- [ ] **Step 5: Commit**

```bash
git add pipeline/publish_primary_group.py tests/test_publish_primary_group.py
git commit -m "feat: add per-size Etsy listing data builder with title-cap revalidation"
```

---

### Task 7: Gelato product creation for a secondary size

**Files:**
- Modify: `pipeline/publish_primary_group.py`
- Test: `tests/test_publish_primary_group.py`

**Interfaces:**
- Consumes: `config.get_template_variant(static_config, size, orientation) -> dict`, `gelato_client.create_product_from_template(...)`, `primary_mockup.poll_until_ready(product_id, *, store_id=None, api_key=None, poll_interval=3.0, timeout=90.0, ...) -> dict`.
- Produces:
  - `create_group_product_row(conn, group_id, size, orientation, template_id, price_eur, *, now=None) -> int` — inserts a `group_products` row with `status='pending'`, no `gelato_product_id` yet.
  - `create_gelato_product(conn, group_product_id, candidate, static_config, size, orientation, *, store_id=None, api_key=None, now=None) -> str` — creates the Gelato product, writes `gelato_product_id`, fetches/orders the gallery, inserts `product_images` rows (same ordering as `primary_mockup.py`). Wraps the create-then-poll-then-insert sequence in try/except exactly like `primary_mockup.create_primary_mockup` does: `status='created'` on success, `status='mockup_failed'` on any exception (re-raised) — this matters because `gelato_product_id` gets written to the row *before* polling, so a poll timeout would otherwise leave a row that looks like it has a live Gelato product but has zero `product_images` rows. Task 9's retry-once wrapper checks this row's `status` (not just whether `gelato_product_id` is set) before deciding whether to re-create it, so a timed-out row is correctly discarded and retried from scratch rather than resumed into a broken zero-image Etsy publish.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_publish_primary_group.py`:

```python
STATIC_CONFIG = {
    "gelato_templates": {
        "8x12_portrait": {
            "template_id": "tpl_8x12", "template_variant_id": "variant_8x12",
            "image_placeholder_name": "slot_8x12.jpg",
        },
        "A3_portrait": {
            "template_id": "tpl_a3", "template_variant_id": "variant_a3",
            "image_placeholder_name": "slot_a3.jpg",
        },
        "A2_portrait": {
            "template_id": "tpl_a2", "template_variant_id": "variant_a2",
            "image_placeholder_name": "slot_a2.jpg",
        },
        "A1_portrait": {
            "template_id": "tpl_a1", "template_variant_id": "variant_a1",
            "image_placeholder_name": "slot_a1.jpg",
        },
    },
    "prices_eur": {"8x12": 24, "A3": 35, "A2": 39, "A1": 49},
    "aspect_ratio_groups": {"primary": ["8x12", "A3", "A2", "A1"], "5x7": ["5x7"], "10x24": ["10x24"]},
}


def test_create_group_product_row_inserts_pending_row(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_primary_group(conn, candidate_id)

    gp_id = publish_primary_group.create_group_product_row(
        conn, group_id, "A3", "portrait", "tpl_a3", 35, now=datetime(2026, 7, 12, 10, 0, 0),
    )

    row = conn.execute("SELECT * FROM group_products WHERE id = ?", (gp_id,)).fetchone()
    assert row["group_id"] == group_id
    assert row["size"] == "A3"
    assert row["orientation"] == "portrait"
    assert row["gelato_template_id"] == "tpl_a3"
    assert row["price_eur"] == 35
    assert row["status"] == "pending"
    assert row["gelato_product_id"] is None
    conn.close()


def test_create_gelato_product_writes_product_id_and_ordered_gallery(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_primary_group(conn, candidate_id)
    gp_id = publish_primary_group.create_group_product_row(
        conn, group_id, "A3", "portrait", "tpl_a3", 35, now=datetime(2026, 7, 12, 10, 0, 0),
    )
    candidate = dict(conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone())

    def fake_create_product_from_template(template_id, template_variant_id, image_placeholder_name,
                                           image_url, title, *, store_id=None, api_key=None, **kwargs):
        assert template_id == "tpl_a3"
        assert template_variant_id == "variant_a3"
        assert image_placeholder_name == "slot_a3.jpg"
        assert image_url == "https://replicate.delivery/out.png"
        return {"id": "gelato_prod_a3", "isReadyToPublish": False, "productImages": []}

    def fake_get_product(product_id, *, store_id=None, api_key=None):
        return {
            "id": product_id, "isReadyToPublish": True,
            "productImages": [
                {"fileUrl": "https://gelato/a3_life.jpg", "isPrimary": False},
                {"fileUrl": "https://gelato/a3_flat.jpg", "isPrimary": True},
            ],
        }

    with patch("pipeline.publish_primary_group.gelato_client.create_product_from_template",
               side_effect=fake_create_product_from_template), \
         patch("pipeline.publish_primary_group.primary_mockup.gelato_client.get_product",
               side_effect=fake_get_product):
        gelato_product_id = publish_primary_group.create_gelato_product(
            conn, gp_id, candidate, STATIC_CONFIG, "A3", "portrait",
            store_id="store1", api_key="key1", now=datetime(2026, 7, 12, 10, 5, 0),
        )

    assert gelato_product_id == "gelato_prod_a3"

    gp_row = conn.execute("SELECT * FROM group_products WHERE id = ?", (gp_id,)).fetchone()
    assert gp_row["gelato_product_id"] == "gelato_prod_a3"
    assert gp_row["status"] == "created"

    images = conn.execute(
        "SELECT * FROM product_images WHERE group_product_id = ? ORDER BY gallery_order", (gp_id,)
    ).fetchall()
    assert len(images) == 2
    assert images[0]["image_type"] == "flat_mockup"
    assert images[0]["image_url"] == "https://gelato/a3_flat.jpg"
    assert images[1]["image_type"] == "lifestyle"
    conn.close()


def test_create_gelato_product_marks_mockup_failed_on_poll_timeout(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_primary_group(conn, candidate_id)
    gp_id = publish_primary_group.create_group_product_row(
        conn, group_id, "A3", "portrait", "tpl_a3", 35, now=datetime(2026, 7, 12, 10, 0, 0),
    )
    candidate = dict(conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone())

    def fake_create_product_from_template(*args, **kwargs):
        return {"id": "gelato_prod_a3_stuck", "isReadyToPublish": False, "productImages": []}

    def fake_poll_until_ready(*args, **kwargs):
        raise primary_mockup.GelatoMockupTimeoutError("gelato_prod_a3_stuck did not become ready")

    with patch("pipeline.publish_primary_group.gelato_client.create_product_from_template",
               side_effect=fake_create_product_from_template), \
         patch("pipeline.publish_primary_group.primary_mockup.poll_until_ready",
               side_effect=fake_poll_until_ready):
        with pytest.raises(primary_mockup.GelatoMockupTimeoutError):
            publish_primary_group.create_gelato_product(
                conn, gp_id, candidate, STATIC_CONFIG, "A3", "portrait",
                store_id="store1", api_key="key1", now=datetime(2026, 7, 12, 10, 5, 0),
            )

    gp_row = conn.execute("SELECT * FROM group_products WHERE id = ?", (gp_id,)).fetchone()
    assert gp_row["status"] == "mockup_failed"
    assert gp_row["gelato_product_id"] == "gelato_prod_a3_stuck"
    assert conn.execute(
        "SELECT * FROM product_images WHERE group_product_id = ?", (gp_id,)
    ).fetchall() == []
    conn.close()


def test_create_gelato_product_dry_run_skips_polling(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_primary_group(conn, candidate_id)
    gp_id = publish_primary_group.create_group_product_row(
        conn, group_id, "A3", "portrait", "tpl_a3", 35, now=datetime(2026, 7, 12, 10, 0, 0),
    )
    candidate = dict(conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone())

    def fake_create_product_from_template(*args, **kwargs):
        return {"id": "DRY_RUN_PRODUCT_ID", "previewUrl": None, "productImages": [], "_dry_run": True}

    with patch("pipeline.publish_primary_group.gelato_client.create_product_from_template",
               side_effect=fake_create_product_from_template), \
         patch("pipeline.publish_primary_group.primary_mockup.gelato_client.get_product") as mock_get_product:
        publish_primary_group.create_gelato_product(
            conn, gp_id, candidate, STATIC_CONFIG, "A3", "portrait",
            store_id="store1", api_key="key1", now=datetime(2026, 7, 12, 10, 5, 0),
        )

    mock_get_product.assert_not_called()
    images = conn.execute("SELECT * FROM product_images WHERE group_product_id = ?", (gp_id,)).fetchall()
    assert len(images) == 1
    assert images[0]["image_type"] == "flat_mockup"
    gp_row = conn.execute("SELECT status FROM group_products WHERE id = ?", (gp_id,)).fetchone()
    assert gp_row["status"] == "created"
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_publish_primary_group.py -v`
Expected: FAIL — `AttributeError` for `create_group_product_row`/`create_gelato_product`.

- [ ] **Step 3: Implement `create_group_product_row` and `create_gelato_product`**

Add to `pipeline/publish_primary_group.py`:

```python
def create_group_product_row(conn, group_id, size, orientation, template_id, price_eur, *, now=None) -> int:
    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()
    cursor = conn.execute(
        """
        INSERT INTO group_products
          (group_id, size, orientation, gelato_template_id, price_eur, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
        """,
        (group_id, size, orientation, template_id, price_eur, timestamp, timestamp),
    )
    conn.commit()
    return cursor.lastrowid


def create_gelato_product(conn, group_product_id, candidate, static_config, size, orientation, *,
                           store_id=None, api_key=None, now=None) -> str:
    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()
    template = config.get_template_variant(static_config, size, orientation)

    response = gelato_client.create_product_from_template(
        template["template_id"], template["template_variant_id"], template["image_placeholder_name"],
        candidate["base_image_url"], f"{candidate['niche']} - {size} print",
        store_id=store_id, api_key=api_key,
    )
    gelato_product_id = response["id"]
    conn.execute(
        "UPDATE group_products SET gelato_product_id = ?, updated_at = ? WHERE id = ?",
        (gelato_product_id, timestamp, group_product_id),
    )
    conn.commit()

    try:
        if response.get("_dry_run"):
            images = [{"fileUrl": response.get("previewUrl") or "placeholder://dry-run-image", "isPrimary": True}]
        else:
            product = primary_mockup.poll_until_ready(gelato_product_id, store_id=store_id, api_key=api_key)
            images = product["productImages"]

        ordered_images = sorted(images, key=lambda img: not img.get("isPrimary"))
        for order, image in enumerate(ordered_images):
            image_type = "flat_mockup" if image.get("isPrimary") else "lifestyle"
            conn.execute(
                "INSERT INTO product_images (group_product_id, image_url, alt_text, gallery_order, image_type) "
                "VALUES (?, ?, '', ?, ?)",
                (group_product_id, image.get("fileUrl"), order, image_type),
            )
    except Exception:
        conn.execute(
            "UPDATE group_products SET status = 'mockup_failed', updated_at = ? WHERE id = ?",
            (timestamp, group_product_id),
        )
        conn.commit()
        raise

    conn.execute(
        "UPDATE group_products SET status = 'created', updated_at = ? WHERE id = ?",
        (timestamp, group_product_id),
    )
    conn.commit()
    return gelato_product_id
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_publish_primary_group.py -v`
Expected: PASS (all tests in the file).

- [ ] **Step 5: Commit**

```bash
git add pipeline/publish_primary_group.py tests/test_publish_primary_group.py
git commit -m "feat: add per-size Gelato product creation for secondary primary-group sizes"
```

---

### Task 8: publish one size to Etsy

**Files:**
- Modify: `pipeline/publish_primary_group.py`
- Test: `tests/test_publish_primary_group.py`

**Interfaces:**
- Consumes: `build_size_listing_data` (Task 6), `etsy_client.create_draft_listing`, `etsy_client.upload_listing_image`, `etsy_client.update_listing_state` (Task 3), `http.fetch_bytes` (Task 2).
- Produces: `publish_to_etsy(conn, group_product_id, candidate_id, size, price_eur, *, shop_id=None, etsy_api_key=None, etsy_api_secret=None, etsy_access_token=None, dry_run=None, now=None) -> str` — returns the Etsy `listing_id` (as a string), writes it plus `status='published'` onto `group_products`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_publish_primary_group.py`:

```python
def _insert_listing_text(conn, candidate_id, niche="monstera line art"):
    timestamp = "2026-07-12T09:10:00"
    conn.execute(
        """
        INSERT INTO listing_texts (
            candidate_id, title, tags, description, disclosure_text,
            who_made, production_partner_ids, taxonomy_id, shipping_profile_id, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            candidate_id, f"{niche} print", _json.dumps(["botanical", "wall art"]),
            f"A print of {niche}.", "AI disclosure text.",
            "i_did", _json.dumps([5717252]), "1027", "", timestamp,
        ),
    )
    conn.commit()


def _insert_group_product_with_images(conn, group_id, size="A3", *, gelato_product_id="gelato_a3",
                                       image_urls=("https://gelato/a3_flat.jpg", "https://gelato/a3_life.jpg")):
    timestamp = "2026-07-12T10:00:00"
    cursor = conn.execute(
        "INSERT INTO group_products "
        "(group_id, size, orientation, gelato_template_id, gelato_product_id, price_eur, "
        "status, created_at, updated_at) "
        "VALUES (?, ?, 'portrait', 'tpl_x', ?, 35, 'created', ?, ?)",
        (group_id, size, gelato_product_id, timestamp, timestamp),
    )
    gp_id = cursor.lastrowid
    for order, url in enumerate(image_urls):
        image_type = "flat_mockup" if order == 0 else "lifestyle"
        conn.execute(
            "INSERT INTO product_images (group_product_id, image_url, alt_text, gallery_order, image_type) "
            "VALUES (?, ?, '', ?, ?)",
            (gp_id, url, order, image_type),
        )
    conn.commit()
    return gp_id


def test_publish_to_etsy_dry_run_skips_image_download_and_writes_published(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_primary_group(conn, candidate_id)
    _insert_listing_text(conn, candidate_id)
    gp_id = _insert_group_product_with_images(conn, group_id)

    with patch("pipeline.publish_primary_group.etsy_client.create_draft_listing",
               return_value={"listing_id": "DRY_RUN_LISTING_ID", "_dry_run": True}) as mock_draft, \
         patch("pipeline.publish_primary_group.etsy_client.upload_listing_image",
               return_value={"_dry_run": True}) as mock_upload, \
         patch("pipeline.publish_primary_group.etsy_client.update_listing_state",
               return_value={"_dry_run": True}) as mock_state, \
         patch("pipeline.publish_primary_group.http.fetch_bytes") as mock_fetch:
        listing_id = publish_primary_group.publish_to_etsy(
            conn, gp_id, candidate_id, "A3", 35, shop_id="shop1",
            dry_run=True, now=datetime(2026, 7, 12, 10, 10, 0),
        )

    mock_fetch.assert_not_called()
    assert mock_upload.call_count == 2
    for call in mock_upload.call_args_list:
        assert call.args[2] == b""
    assert listing_id == "DRY_RUN_LISTING_ID"

    gp_row = conn.execute("SELECT * FROM group_products WHERE id = ?", (gp_id,)).fetchone()
    assert gp_row["etsy_listing_id"] == "DRY_RUN_LISTING_ID"
    assert gp_row["status"] == "published"
    conn.close()


def test_publish_to_etsy_live_downloads_images_and_activates_listing(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_primary_group(conn, candidate_id)
    _insert_listing_text(conn, candidate_id)
    gp_id = _insert_group_product_with_images(conn, group_id)

    calls = []

    def fake_create_draft_listing(shop_id, listing_data, **kwargs):
        calls.append(("draft", shop_id, listing_data["title"]))
        return {"listing_id": 555}

    def fake_upload(shop_id, listing_id, image_bytes, **kwargs):
        calls.append(("upload", shop_id, listing_id, image_bytes))
        return {"listing_image_id": 1}

    def fake_update_state(shop_id, listing_id, state, **kwargs):
        calls.append(("activate", shop_id, listing_id, state))
        return {"state": "active"}

    with patch("pipeline.publish_primary_group.etsy_client.create_draft_listing",
               side_effect=fake_create_draft_listing), \
         patch("pipeline.publish_primary_group.etsy_client.upload_listing_image",
               side_effect=fake_upload), \
         patch("pipeline.publish_primary_group.etsy_client.update_listing_state",
               side_effect=fake_update_state), \
         patch("pipeline.publish_primary_group.http.fetch_bytes",
               return_value=b"real-image-bytes") as mock_fetch:
        listing_id = publish_primary_group.publish_to_etsy(
            conn, gp_id, candidate_id, "A3", 35, shop_id="shop1",
            dry_run=False, now=datetime(2026, 7, 12, 10, 10, 0),
        )

    assert listing_id == "555"
    assert calls[0] == ("draft", "shop1", "monstera line art print - A3 Print")
    assert calls[1] == ("upload", "shop1", 555, b"real-image-bytes")
    assert calls[2] == ("upload", "shop1", 555, b"real-image-bytes")
    assert calls[3] == ("activate", "shop1", 555, "active")
    assert mock_fetch.call_count == 2

    gp_row = conn.execute("SELECT * FROM group_products WHERE id = ?", (gp_id,)).fetchone()
    assert gp_row["etsy_listing_id"] == "555"
    assert gp_row["status"] == "published"
    conn.close()


def test_publish_to_etsy_raises_when_no_listing_text(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_primary_group(conn, candidate_id)
    gp_id = _insert_group_product_with_images(conn, group_id)

    with pytest.raises(ValueError, match="listing_texts"):
        publish_primary_group.publish_to_etsy(
            conn, gp_id, candidate_id, "A3", 35, shop_id="shop1", dry_run=True,
        )
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_publish_primary_group.py -v`
Expected: FAIL — `AttributeError: module 'pipeline.publish_primary_group' has no attribute 'publish_to_etsy'`.

- [ ] **Step 3: Implement `publish_to_etsy`**

Add to `pipeline/publish_primary_group.py`:

```python
def publish_to_etsy(conn, group_product_id, candidate_id, size, price_eur, *, shop_id=None,
                     etsy_api_key=None, etsy_api_secret=None, etsy_access_token=None,
                     dry_run=None, now=None) -> str:
    if dry_run is None:
        dry_run = not config.is_live_mode("ETSY")
    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()

    listing_text_row = conn.execute(
        "SELECT * FROM listing_texts WHERE candidate_id = ?", (candidate_id,)
    ).fetchone()
    if listing_text_row is None:
        raise ValueError(f"No listing_texts row for candidate {candidate_id}")
    listing_data = build_size_listing_data(dict(listing_text_row), size, price_eur)

    shop_id = shop_id or config.require_env("ETSY_SHOP_ID")
    draft = etsy_client.create_draft_listing(
        shop_id, listing_data, api_key=etsy_api_key, api_secret=etsy_api_secret,
        access_token=etsy_access_token, dry_run=dry_run,
    )
    listing_id = draft["listing_id"]

    image_rows = conn.execute(
        "SELECT image_url FROM product_images WHERE group_product_id = ? ORDER BY gallery_order",
        (group_product_id,),
    ).fetchall()
    for row in image_rows:
        image_bytes = b"" if dry_run else http.fetch_bytes(row["image_url"])
        etsy_client.upload_listing_image(
            shop_id, listing_id, image_bytes, api_key=etsy_api_key, api_secret=etsy_api_secret,
            access_token=etsy_access_token, dry_run=dry_run,
        )

    etsy_client.update_listing_state(
        shop_id, listing_id, "active", api_key=etsy_api_key, api_secret=etsy_api_secret,
        access_token=etsy_access_token, dry_run=dry_run,
    )

    conn.execute(
        "UPDATE group_products SET etsy_listing_id = ?, status = 'published', updated_at = ? WHERE id = ?",
        (str(listing_id), timestamp, group_product_id),
    )
    conn.commit()
    return str(listing_id)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_publish_primary_group.py -v`
Expected: PASS (all tests in the file).

- [ ] **Step 5: Commit**

```bash
git add pipeline/publish_primary_group.py tests/test_publish_primary_group.py
git commit -m "feat: add publish_to_etsy for uploading images, drafting, and activating a listing"
```

---

### Task 9: retry-once wrapper and the 4-size orchestrator

**Files:**
- Modify: `pipeline/publish_primary_group.py`
- Test: `tests/test_publish_primary_group.py`

**Interfaces:**
- Consumes: `create_gelato_product` (Task 7), `publish_to_etsy` (Task 8), `config.load_static_config`, `config.get_template_variant`.
- Produces:
  - `publish_group_product(conn, group_product_id, candidate, static_config, *, store_id=None, gelato_api_key=None, shop_id=None, etsy_api_key=None, etsy_api_secret=None, etsy_access_token=None, dry_run=None, now=None) -> str` — one size end to end; retries the whole sequence once on any exception, then marks `status='publish_failed'` and re-raises.
  - `publish_primary_group(conn, candidate_id, *, static_config=None, store_id=None, gelato_api_key=None, shop_id=None, etsy_api_key=None, etsy_api_secret=None, etsy_access_token=None, dry_run=None, now=None) -> dict` — `{size: "published" | "publish_failed"}` for all four primary-group sizes. Sets `groups.status='approved_published'` and `candidates.status='completed'` once at least one size published.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_publish_primary_group.py`:

```python
def _insert_ready_primary_group(conn, candidate_id, niche="monstera line art"):
    group_id = _insert_primary_group(conn, candidate_id, status="pending_review")
    _insert_group_product_with_images(
        conn, group_id, size="8x12", gelato_product_id="gelato_prod_1",
        image_urls=("https://gelato/flat.jpg", "https://gelato/life.jpg"),
    )
    _insert_listing_text(conn, candidate_id, niche=niche)
    return group_id


def test_publish_group_product_succeeds_first_try(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_ready_primary_group(conn, candidate_id)
    gp_id = conn.execute(
        "SELECT id FROM group_products WHERE group_id = ? AND size = '8x12'", (group_id,)
    ).fetchone()["id"]
    candidate = dict(conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone())

    with patch("pipeline.publish_primary_group.publish_to_etsy",
               return_value="listing_1") as mock_publish:
        result = publish_primary_group.publish_group_product(
            conn, gp_id, candidate, STATIC_CONFIG, dry_run=True, now=datetime(2026, 7, 12, 11, 0, 0),
        )

    assert result == "listing_1"
    mock_publish.assert_called_once()
    conn.close()


def test_publish_group_product_creates_gelato_product_when_missing(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_primary_group(conn, candidate_id)
    _insert_listing_text(conn, candidate_id)
    gp_id = publish_primary_group.create_group_product_row(
        conn, group_id, "A3", "portrait", "tpl_a3", 35, now=datetime(2026, 7, 12, 10, 0, 0),
    )
    candidate = dict(conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone())

    with patch("pipeline.publish_primary_group.create_gelato_product",
               return_value="gelato_prod_new") as mock_create, \
         patch("pipeline.publish_primary_group.publish_to_etsy",
               return_value="listing_2") as mock_publish:
        result = publish_primary_group.publish_group_product(
            conn, gp_id, candidate, STATIC_CONFIG, dry_run=True, now=datetime(2026, 7, 12, 11, 0, 0),
        )

    assert result == "listing_2"
    mock_create.assert_called_once()
    mock_publish.assert_called_once()
    conn.close()


def test_publish_group_product_retries_once_then_succeeds(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_ready_primary_group(conn, candidate_id)
    gp_id = conn.execute(
        "SELECT id FROM group_products WHERE group_id = ? AND size = '8x12'", (group_id,)
    ).fetchone()["id"]
    candidate = dict(conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone())

    attempts = {"n": 0}

    def flaky_publish(*args, **kwargs):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise RuntimeError("Etsy throttled")
        return "listing_after_retry"

    with patch("pipeline.publish_primary_group.publish_to_etsy", side_effect=flaky_publish):
        result = publish_primary_group.publish_group_product(
            conn, gp_id, candidate, STATIC_CONFIG, dry_run=True, now=datetime(2026, 7, 12, 11, 0, 0),
        )

    assert result == "listing_after_retry"
    assert attempts["n"] == 2
    conn.close()


def test_publish_group_product_marks_publish_failed_after_second_failure(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_ready_primary_group(conn, candidate_id)
    gp_id = conn.execute(
        "SELECT id FROM group_products WHERE group_id = ? AND size = '8x12'", (group_id,)
    ).fetchone()["id"]
    candidate = dict(conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone())

    with patch("pipeline.publish_primary_group.publish_to_etsy",
               side_effect=RuntimeError("Etsy down")):
        with pytest.raises(RuntimeError, match="Etsy down"):
            publish_primary_group.publish_group_product(
                conn, gp_id, candidate, STATIC_CONFIG, dry_run=True, now=datetime(2026, 7, 12, 11, 0, 0),
            )

    gp_row = conn.execute("SELECT status FROM group_products WHERE id = ?", (gp_id,)).fetchone()
    assert gp_row["status"] == "publish_failed"
    conn.close()


def test_publish_primary_group_publishes_all_four_sizes(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_ready_primary_group(conn, candidate_id)

    published_sizes = []

    def fake_publish_group_product(conn, group_product_id, candidate, static_config, **kwargs):
        row = conn.execute("SELECT size FROM group_products WHERE id = ?", (group_product_id,)).fetchone()
        published_sizes.append(row["size"])
        return f"listing_{row['size']}"

    with patch("pipeline.publish_primary_group.publish_group_product",
               side_effect=fake_publish_group_product):
        result = publish_primary_group.publish_primary_group(
            conn, candidate_id, static_config=STATIC_CONFIG, dry_run=True,
            now=datetime(2026, 7, 12, 11, 0, 0),
        )

    assert result == {"8x12": "published", "A3": "published", "A2": "published", "A1": "published"}
    assert sorted(published_sizes) == ["8x12", "A1", "A2", "A3"]

    group_row = conn.execute("SELECT status FROM groups WHERE id = ?", (group_id,)).fetchone()
    assert group_row["status"] == "approved_published"
    candidate_row = conn.execute("SELECT status FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    assert candidate_row["status"] == "completed"

    sizes_in_db = {
        row["size"] for row in conn.execute(
            "SELECT size FROM group_products WHERE group_id = ?", (group_id,)
        ).fetchall()
    }
    assert sizes_in_db == {"8x12", "A3", "A2", "A1"}
    conn.close()


def test_publish_primary_group_isolates_per_size_failures(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_ready_primary_group(conn, candidate_id)

    def fake_publish_group_product(conn, group_product_id, candidate, static_config, **kwargs):
        row = conn.execute("SELECT size FROM group_products WHERE id = ?", (group_product_id,)).fetchone()
        if row["size"] == "A2":
            raise RuntimeError("A2 template placeholder")
        return f"listing_{row['size']}"

    with patch("pipeline.publish_primary_group.publish_group_product",
               side_effect=fake_publish_group_product):
        result = publish_primary_group.publish_primary_group(
            conn, candidate_id, static_config=STATIC_CONFIG, dry_run=True,
            now=datetime(2026, 7, 12, 11, 0, 0),
        )

    assert result == {"8x12": "published", "A3": "published", "A2": "publish_failed", "A1": "published"}
    group_row = conn.execute("SELECT status FROM groups WHERE id = ?", (group_id,)).fetchone()
    assert group_row["status"] == "approved_published"
    conn.close()


def test_publish_primary_group_raises_when_no_live_8x12_product(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_primary_group(conn, candidate_id)
    _insert_listing_text(conn, candidate_id)

    with pytest.raises(ValueError, match="8x12"):
        publish_primary_group.publish_primary_group(
            conn, candidate_id, static_config=STATIC_CONFIG, dry_run=True,
        )
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_publish_primary_group.py -v`
Expected: FAIL — `AttributeError` for `publish_group_product`/`publish_primary_group`.

- [ ] **Step 3: Implement `publish_group_product` and `publish_primary_group`**

Add to `pipeline/publish_primary_group.py`:

```python
def publish_group_product(conn, group_product_id, candidate, static_config, *, store_id=None,
                           gelato_api_key=None, shop_id=None, etsy_api_key=None,
                           etsy_api_secret=None, etsy_access_token=None, dry_run=None, now=None) -> str:
    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()

    def attempt():
        row = conn.execute("SELECT * FROM group_products WHERE id = ?", (group_product_id,)).fetchone()
        if row["status"] != "created":
            create_gelato_product(
                conn, group_product_id, candidate, static_config, row["size"], row["orientation"],
                store_id=store_id, api_key=gelato_api_key, now=now,
            )
        return publish_to_etsy(
            conn, group_product_id, candidate["id"], row["size"], row["price_eur"],
            shop_id=shop_id, etsy_api_key=etsy_api_key, etsy_api_secret=etsy_api_secret,
            etsy_access_token=etsy_access_token, dry_run=dry_run, now=now,
        )

    try:
        return attempt()
    except Exception:
        try:
            return attempt()
        except Exception:
            conn.execute(
                "UPDATE group_products SET status = 'publish_failed', updated_at = ? WHERE id = ?",
                (timestamp, group_product_id),
            )
            conn.commit()
            raise


def publish_primary_group(conn, candidate_id, *, static_config=None, store_id=None,
                           gelato_api_key=None, shop_id=None, etsy_api_key=None,
                           etsy_api_secret=None, etsy_access_token=None, dry_run=None, now=None) -> dict:
    static_config = static_config if static_config is not None else config.load_static_config()
    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()

    candidate_row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    if candidate_row is None:
        raise ValueError(f"No candidate with id {candidate_id}")
    candidate = dict(candidate_row)

    group_row = conn.execute(
        "SELECT id FROM groups WHERE candidate_id = ? AND group_type = 'primary'", (candidate_id,)
    ).fetchone()
    if group_row is None:
        raise ValueError(f"No primary group for candidate {candidate_id}")
    group_id = group_row["id"]

    existing_8x12 = conn.execute(
        "SELECT id FROM group_products WHERE group_id = ? AND size = '8x12' AND status = 'created'",
        (group_id,),
    ).fetchone()
    if existing_8x12 is None:
        raise ValueError(f"No live 8x12 group_product for candidate {candidate_id}'s primary group")

    secondary_sizes = [s for s in static_config["aspect_ratio_groups"]["primary"] if s != "8x12"]
    for size in secondary_sizes:
        template = config.get_template_variant(static_config, size, "portrait")
        create_group_product_row(
            conn, group_id, size, "portrait", template["template_id"],
            static_config["prices_eur"][size], now=now,
        )

    group_product_ids = [
        row["id"] for row in conn.execute(
            "SELECT id FROM group_products WHERE group_id = ? AND status != 'deleted' ORDER BY id",
            (group_id,),
        ).fetchall()
    ]

    results = {}
    any_published = False
    for gp_id in group_product_ids:
        size = conn.execute("SELECT size FROM group_products WHERE id = ?", (gp_id,)).fetchone()["size"]
        try:
            publish_group_product(
                conn, gp_id, candidate, static_config, store_id=store_id, gelato_api_key=gelato_api_key,
                shop_id=shop_id, etsy_api_key=etsy_api_key, etsy_api_secret=etsy_api_secret,
                etsy_access_token=etsy_access_token, dry_run=dry_run, now=now,
            )
            results[size] = "published"
            any_published = True
        except Exception as exc:
            results[size] = "publish_failed"
            print(f"publish_group_product failed for candidate {candidate_id} size {size}: {exc}")

    if any_published:
        conn.execute(
            "UPDATE groups SET status = 'approved_published', updated_at = ? WHERE id = ?",
            (timestamp, group_id),
        )
        conn.execute(
            "UPDATE candidates SET status = 'completed', updated_at = ? WHERE id = ?",
            (timestamp, candidate_id),
        )
        conn.commit()

    return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_publish_primary_group.py -v`
Expected: PASS (all tests in the file).

- [ ] **Step 5: Commit**

```bash
git add pipeline/publish_primary_group.py tests/test_publish_primary_group.py
git commit -m "feat: add per-size retry-once publish wrapper and 4-size primary-group orchestrator"
```

---

### Task 10: approve/edit/reject decision routing

**Files:**
- Modify: `pipeline/publish_primary_group.py`
- Test: `tests/test_publish_primary_group.py`

**Interfaces:**
- Consumes: `record_decision` (Task 5), `publish_primary_group` (Task 9), `critic_pass.discard_superseded_attempt(conn, group_product_id, *, store_id=None, api_key=None) -> None` (existing), `generate.generate_for_candidate`, `primary_mockup.create_primary_mockup`, `compliance_draft.build_compliance_draft` (all existing).
- Produces: `handle_decision(conn, candidate_id, group_id, action, decision_notes=None, *, static_config=None, store_id=None, gelato_api_key=None, shop_id=None, etsy_api_key=None, etsy_api_secret=None, etsy_access_token=None, replicate_api_token=None, anthropic_api_key=None, dry_run=None, now=None) -> dict`. Raises `ValueError` for an unrecognized `action`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_publish_primary_group.py`:

```python
def test_handle_decision_approve_records_decision_and_publishes(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_ready_primary_group(conn, candidate_id)

    with patch("pipeline.publish_primary_group.publish_primary_group",
               return_value={"8x12": "published", "A3": "published", "A2": "published", "A1": "published"}
               ) as mock_publish:
        result = publish_primary_group.handle_decision(
            conn, candidate_id, group_id, "approve", static_config=STATIC_CONFIG, dry_run=True,
            now=datetime(2026, 7, 12, 12, 0, 0),
        )

    mock_publish.assert_called_once()
    assert result["action"] == "approve"
    group_row = conn.execute("SELECT decision, decided_at FROM groups WHERE id = ?", (group_id,)).fetchone()
    assert group_row["decision"] == "approved"
    assert group_row["decided_at"] == "2026-07-12T12:00:00"
    conn.close()


def test_handle_decision_reject_marks_group_and_candidate(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_ready_primary_group(conn, candidate_id)

    result = publish_primary_group.handle_decision(
        conn, candidate_id, group_id, "reject", static_config=STATIC_CONFIG,
        now=datetime(2026, 7, 12, 12, 0, 0),
    )

    assert result["action"] == "reject"
    group_row = conn.execute("SELECT decision, status FROM groups WHERE id = ?", (group_id,)).fetchone()
    assert group_row["decision"] == "rejected"
    assert group_row["status"] == "rejected"
    candidate_row = conn.execute(
        "SELECT status, failed_reason FROM candidates WHERE id = ?", (candidate_id,)
    ).fetchone()
    assert candidate_row["status"] == "failed"
    assert candidate_row["failed_reason"] == "primary group rejected"
    conn.close()


def test_handle_decision_edit_discards_old_product_and_regenerates(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_ready_primary_group(conn, candidate_id)
    old_gp_id = conn.execute(
        "SELECT id FROM group_products WHERE group_id = ? AND size = '8x12'", (group_id,)
    ).fetchone()["id"]
    publish_primary_group.critic_pass.record_critic_attempt(
        conn, group_id, 1, {"passed": True, "reason": "meets rubric"}, now=datetime(2026, 7, 12, 9, 20, 0),
    )

    def fake_generate_for_candidate(conn, candidate_id, *, correction_note=None, api_token=None, now=None):
        timestamp = now.isoformat() if now else "2026-07-12T12:05:00"
        conn.execute(
            "UPDATE candidates SET base_image_url = 'https://replicate.delivery/v2.png', "
            "status = 'generating', updated_at = ? WHERE id = ?",
            (timestamp, candidate_id),
        )
        conn.commit()

    def fake_create_primary_mockup(conn, candidate_id, *, static_config=None, store_id=None,
                                    api_key=None, now=None, **kwargs):
        timestamp = now.isoformat() if now else "2026-07-12T12:06:00"
        cursor = conn.execute(
            "INSERT INTO group_products "
            "(group_id, size, orientation, gelato_template_id, gelato_product_id, price_eur, "
            "status, created_at, updated_at) "
            "VALUES (?, '8x12', 'portrait', 'tpl_1', 'gelato_prod_v2', 24, 'created', ?, ?)",
            (group_id, timestamp, timestamp),
        )
        conn.execute(
            "UPDATE groups SET status = 'pending_review', updated_at = ? WHERE id = ?",
            (timestamp, group_id),
        )
        conn.commit()
        return {"group_id": group_id, "group_product_id": cursor.lastrowid}

    def fake_build_compliance_draft(conn, candidate_id, *, static_config=None,
                                     anthropic_api_key=None, now=None):
        _insert_listing_text(conn, candidate_id, niche="monstera line art v2")

    with patch("pipeline.publish_primary_group.critic_pass.gelato_client.delete_product") as mock_delete, \
         patch("pipeline.publish_primary_group.generate.generate_for_candidate",
               side_effect=fake_generate_for_candidate), \
         patch("pipeline.publish_primary_group.primary_mockup.create_primary_mockup",
               side_effect=fake_create_primary_mockup), \
         patch("pipeline.publish_primary_group.compliance_draft.build_compliance_draft",
               side_effect=fake_build_compliance_draft):
        result = publish_primary_group.handle_decision(
            conn, candidate_id, group_id, "edit", "make it more pastel", static_config=STATIC_CONFIG,
            now=datetime(2026, 7, 12, 12, 0, 0),
        )

    assert result["action"] == "edit"
    mock_delete.assert_called_once_with("gelato_prod_1", store_id=None, api_key=None)

    assert conn.execute(
        "SELECT * FROM group_products WHERE id = ?", (old_gp_id,)
    ).fetchone() is None
    assert conn.execute(
        "SELECT * FROM critic_pass_attempts WHERE group_id = ?", (group_id,)
    ).fetchall() == []

    candidate_row = conn.execute(
        "SELECT status, base_image_url FROM candidates WHERE id = ?", (candidate_id,)
    ).fetchone()
    assert candidate_row["status"] == "generating"
    assert candidate_row["base_image_url"] == "https://replicate.delivery/v2.png"

    listing_row = conn.execute(
        "SELECT title FROM listing_texts WHERE candidate_id = ?", (candidate_id,)
    ).fetchone()
    assert listing_row["title"] == "monstera line art v2 print"

    group_row = conn.execute("SELECT decision, decision_notes FROM groups WHERE id = ?", (group_id,)).fetchone()
    assert group_row["decision"] == "edited"
    assert group_row["decision_notes"] == "make it more pastel"
    conn.close()


def test_handle_decision_raises_on_unknown_action(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_ready_primary_group(conn, candidate_id)

    with pytest.raises(ValueError, match="Unknown action"):
        publish_primary_group.handle_decision(conn, candidate_id, group_id, "snooze")
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_publish_primary_group.py -v`
Expected: FAIL — `AttributeError: module 'pipeline.publish_primary_group' has no attribute 'handle_decision'`.

- [ ] **Step 3: Implement `handle_decision`**

Add to `pipeline/publish_primary_group.py`:

```python
def handle_decision(conn, candidate_id, group_id, action, decision_notes=None, *,
                     static_config=None, store_id=None, gelato_api_key=None, shop_id=None,
                     etsy_api_key=None, etsy_api_secret=None, etsy_access_token=None,
                     replicate_api_token=None, anthropic_api_key=None, dry_run=None, now=None) -> dict:
    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()

    if action == "approve":
        record_decision(conn, group_id, "approved", decision_notes, now=now)
        results = publish_primary_group(
            conn, candidate_id, static_config=static_config, store_id=store_id,
            gelato_api_key=gelato_api_key, shop_id=shop_id, etsy_api_key=etsy_api_key,
            etsy_api_secret=etsy_api_secret, etsy_access_token=etsy_access_token,
            dry_run=dry_run, now=now,
        )
        return {"action": "approve", "results": results}

    if action == "edit":
        record_decision(conn, group_id, "edited", decision_notes, now=now)
        resolved_static_config = static_config if static_config is not None else config.load_static_config()

        old_gp_row = conn.execute(
            "SELECT id FROM group_products WHERE group_id = ? AND size = '8x12' AND status = 'created'",
            (group_id,),
        ).fetchone()
        if old_gp_row is not None:
            critic_pass.discard_superseded_attempt(
                conn, old_gp_row["id"], store_id=store_id, api_key=gelato_api_key,
            )
        conn.execute("DELETE FROM critic_pass_attempts WHERE group_id = ?", (group_id,))
        conn.execute("DELETE FROM listing_texts WHERE candidate_id = ?", (candidate_id,))
        conn.commit()

        generate.generate_for_candidate(
            conn, candidate_id, correction_note=decision_notes, api_token=replicate_api_token, now=now,
        )
        primary_mockup.create_primary_mockup(
            conn, candidate_id, static_config=resolved_static_config, store_id=store_id,
            api_key=gelato_api_key, now=now,
        )
        compliance_draft.build_compliance_draft(
            conn, candidate_id, static_config=resolved_static_config,
            anthropic_api_key=anthropic_api_key, now=now,
        )
        return {"action": "edit"}

    if action == "reject":
        record_decision(conn, group_id, "rejected", decision_notes, now=now)
        conn.execute(
            "UPDATE groups SET status = 'rejected', updated_at = ? WHERE id = ?",
            (timestamp, group_id),
        )
        conn.execute(
            "UPDATE candidates SET status = 'failed', failed_reason = 'primary group rejected', "
            "updated_at = ? WHERE id = ?",
            (timestamp, candidate_id),
        )
        conn.commit()
        return {"action": "reject"}

    raise ValueError(f"Unknown action {action!r}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_publish_primary_group.py -v`
Expected: PASS (all tests in the file).

- [ ] **Step 5: Commit**

```bash
git add pipeline/publish_primary_group.py tests/test_publish_primary_group.py
git commit -m "feat: add approve/edit/reject decision routing for the primary group"
```

---

### Task 11: hourly-poll entrypoint

**Files:**
- Modify: `pipeline/publish_primary_group.py`
- Test: `tests/test_publish_primary_group.py`

**Interfaces:**
- Consumes: `resolve_callback`, `is_admin`, `log_telegram_event`, `handle_decision` (all prior tasks), `telegram_client.get_updates`, `telegram_client.answer_callback_query`, schema table `telegram_offset` (Task 1), `group_messages`.
- Produces:
  - `get_telegram_offset(conn) -> int | None`
  - `set_telegram_offset(conn, last_update_id: int) -> None`
  - `process_update(conn, update, *, admin_chat_id=None, bot_token=None, static_config=None, store_id=None, gelato_api_key=None, shop_id=None, etsy_api_key=None, etsy_api_secret=None, etsy_access_token=None, replicate_api_token=None, anthropic_api_key=None, dry_run=None, now=None) -> dict | None`
  - `run_publish_primary_group_cycle(conn, *, admin_chat_id=None, bot_token=None, static_config=None, store_id=None, gelato_api_key=None, shop_id=None, etsy_api_key=None, etsy_api_secret=None, etsy_access_token=None, replicate_api_token=None, anthropic_api_key=None, dry_run=None, now=None) -> list` — the hourly-poll entrypoint.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_publish_primary_group.py`:

```python
def _insert_group_message(conn, group_id, chat_id, telegram_message_id, sent_at="2026-07-12T09:15:00"):
    conn.execute(
        "INSERT INTO group_messages (group_id, telegram_message_id, chat_id, sent_at) VALUES (?, ?, ?, ?)",
        (group_id, telegram_message_id, chat_id, sent_at),
    )
    conn.commit()


def test_get_and_set_telegram_offset_round_trip(tmp_path):
    conn = _fresh_conn(tmp_path)

    assert publish_primary_group.get_telegram_offset(conn) is None

    publish_primary_group.set_telegram_offset(conn, 100)
    assert publish_primary_group.get_telegram_offset(conn) == 100

    publish_primary_group.set_telegram_offset(conn, 105)
    assert publish_primary_group.get_telegram_offset(conn) == 105
    conn.close()


def test_process_update_discards_non_admin_sender(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_ready_primary_group(conn, candidate_id)
    _insert_group_message(conn, group_id, "987654321", 202)
    update = _callback_update(user_id=111111111, data=f"approve:{group_id}", message_id=202, chat_id=987654321)

    with patch("pipeline.publish_primary_group.handle_decision") as mock_handle, \
         patch("pipeline.publish_primary_group.telegram_client.answer_callback_query") as mock_answer:
        result = publish_primary_group.process_update(
            conn, update, admin_chat_id="987654321", now=datetime(2026, 7, 12, 13, 0, 0),
        )

    assert result is None
    mock_handle.assert_not_called()
    mock_answer.assert_not_called()
    log_row = conn.execute("SELECT * FROM telegram_events_log").fetchone()
    assert log_row["accepted"] == 0
    assert log_row["telegram_user_id"] == "111111111"
    conn.close()


def test_process_update_discards_callback_not_matching_group_messages(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_ready_primary_group(conn, candidate_id)
    _insert_group_message(conn, group_id, "987654321", 202)
    # message_id 999 does not match the group_messages row (202)
    update = _callback_update(user_id=987654321, data=f"approve:{group_id}", message_id=999, chat_id=987654321)

    with patch("pipeline.publish_primary_group.handle_decision") as mock_handle:
        result = publish_primary_group.process_update(
            conn, update, admin_chat_id="987654321", now=datetime(2026, 7, 12, 13, 0, 0),
        )

    assert result is None
    mock_handle.assert_not_called()
    conn.close()


def test_process_update_accepts_admin_callback_and_calls_handle_decision(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_ready_primary_group(conn, candidate_id)
    _insert_group_message(conn, group_id, "987654321", 202)
    update = _callback_update(
        user_id=987654321, data=f"approve:{group_id}", message_id=202, chat_id=987654321, callback_id="cbq1",
    )

    with patch("pipeline.publish_primary_group.handle_decision",
               return_value={"action": "approve", "results": {"8x12": "published"}}) as mock_handle, \
         patch("pipeline.publish_primary_group.telegram_client.answer_callback_query") as mock_answer:
        result = publish_primary_group.process_update(
            conn, update, admin_chat_id="987654321", bot_token="tok1", now=datetime(2026, 7, 12, 13, 0, 0),
        )

    assert result == {"candidate_id": candidate_id, "group_id": group_id,
                       "action": "approve", "results": {"8x12": "published"}}
    mock_handle.assert_called_once()
    assert mock_handle.call_args.args[:3] == (conn, candidate_id, group_id)
    assert mock_handle.call_args.args[3] == "approve"
    mock_answer.assert_called_once_with("cbq1", bot_token="tok1")

    log_row = conn.execute("SELECT * FROM telegram_events_log").fetchone()
    assert log_row["accepted"] == 1
    assert log_row["action_taken"] == "approve"
    conn.close()


def test_process_update_returns_none_for_non_callback_update(tmp_path):
    conn = _fresh_conn(tmp_path)
    update = {"update_id": 1, "message": {"text": "/research botanical"}}

    result = publish_primary_group.process_update(conn, update, admin_chat_id="987654321")

    assert result is None
    assert conn.execute("SELECT * FROM telegram_events_log").fetchall() == []
    conn.close()


def test_run_publish_primary_group_cycle_processes_and_advances_offset(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_ready_primary_group(conn, candidate_id)
    _insert_group_message(conn, group_id, "987654321", 202)
    updates = [_callback_update(update_id=500, user_id=987654321, data=f"approve:{group_id}",
                                 message_id=202, chat_id=987654321, callback_id="cbq1")]

    with patch("pipeline.publish_primary_group.telegram_client.get_updates",
               return_value=updates) as mock_get_updates, \
         patch("pipeline.publish_primary_group.telegram_client.answer_callback_query"), \
         patch("pipeline.publish_primary_group.handle_decision",
               return_value={"action": "approve", "results": {"8x12": "published"}}):
        processed = publish_primary_group.run_publish_primary_group_cycle(
            conn, admin_chat_id="987654321", bot_token="tok1", now=datetime(2026, 7, 12, 13, 0, 0),
        )

    assert len(processed) == 1
    assert mock_get_updates.call_args.kwargs["offset"] is None
    assert publish_primary_group.get_telegram_offset(conn) == 500
    conn.close()


def test_run_publish_primary_group_cycle_uses_persisted_offset_on_next_call(tmp_path):
    conn = _fresh_conn(tmp_path)
    publish_primary_group.set_telegram_offset(conn, 500)

    with patch("pipeline.publish_primary_group.telegram_client.get_updates", return_value=[]) as mock_get_updates:
        publish_primary_group.run_publish_primary_group_cycle(conn, admin_chat_id="987654321", bot_token="tok1")

    assert mock_get_updates.call_args.kwargs["offset"] == 501
    conn.close()


def test_run_publish_primary_group_cycle_isolates_per_update_failures(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_ready_primary_group(conn, candidate_id)
    _insert_group_message(conn, group_id, "987654321", 202)
    updates = [
        _callback_update(update_id=600, user_id=987654321, data=f"approve:{group_id}",
                          message_id=202, chat_id=987654321, callback_id="cbq_bad"),
        {"update_id": 601, "message": {"text": "not a callback"}},
    ]

    with patch("pipeline.publish_primary_group.telegram_client.get_updates", return_value=updates), \
         patch("pipeline.publish_primary_group.telegram_client.answer_callback_query"), \
         patch("pipeline.publish_primary_group.handle_decision", side_effect=RuntimeError("boom")):
        processed = publish_primary_group.run_publish_primary_group_cycle(
            conn, admin_chat_id="987654321", bot_token="tok1", now=datetime(2026, 7, 12, 13, 0, 0),
        )

    assert processed == []
    assert publish_primary_group.get_telegram_offset(conn) == 601
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_publish_primary_group.py -v`
Expected: FAIL — `AttributeError` for `get_telegram_offset`/`set_telegram_offset`/`process_update`/`run_publish_primary_group_cycle`.

- [ ] **Step 3: Implement the offset helpers, `process_update`, and `run_publish_primary_group_cycle`**

Add to `pipeline/publish_primary_group.py`:

```python
def get_telegram_offset(conn) -> int | None:
    row = conn.execute("SELECT last_update_id FROM telegram_offset WHERE id = 1").fetchone()
    return row["last_update_id"] if row is not None else None


def set_telegram_offset(conn, last_update_id: int) -> None:
    conn.execute(
        "INSERT INTO telegram_offset (id, last_update_id) VALUES (1, ?) "
        "ON CONFLICT(id) DO UPDATE SET last_update_id = excluded.last_update_id",
        (last_update_id,),
    )
    conn.commit()


def process_update(conn, update, *, admin_chat_id=None, bot_token=None, static_config=None,
                    store_id=None, gelato_api_key=None, shop_id=None, etsy_api_key=None,
                    etsy_api_secret=None, etsy_access_token=None, replicate_api_token=None,
                    anthropic_api_key=None, dry_run=None, now=None) -> dict | None:
    admin_chat_id = admin_chat_id or config.require_env("TELEGRAM_ADMIN_CHAT_ID")
    parsed = resolve_callback(update)
    if parsed is None:
        return None

    if not is_admin(parsed["telegram_user_id"], admin_chat_id):
        log_telegram_event(conn, parsed["telegram_user_id"], update, False,
                            "discarded: not admin", now=now)
        return None

    message_row = conn.execute(
        "SELECT chat_id, telegram_message_id FROM group_messages WHERE group_id = ?",
        (parsed["group_id"],),
    ).fetchone()
    if message_row is None or str(message_row["chat_id"]) != str(parsed["chat_id"]) \
            or message_row["telegram_message_id"] != parsed["message_id"]:
        log_telegram_event(conn, parsed["telegram_user_id"], update, False,
                            "discarded: callback does not match a known group_messages row", now=now)
        return None

    group_row = conn.execute(
        "SELECT candidate_id FROM groups WHERE id = ?", (parsed["group_id"],)
    ).fetchone()
    candidate_id = group_row["candidate_id"]

    log_telegram_event(conn, parsed["telegram_user_id"], update, True, parsed["action"], now=now)
    telegram_client.answer_callback_query(parsed["callback_query_id"], bot_token=bot_token)

    result = handle_decision(
        conn, candidate_id, parsed["group_id"], parsed["action"], static_config=static_config,
        store_id=store_id, gelato_api_key=gelato_api_key, shop_id=shop_id, etsy_api_key=etsy_api_key,
        etsy_api_secret=etsy_api_secret, etsy_access_token=etsy_access_token,
        replicate_api_token=replicate_api_token, anthropic_api_key=anthropic_api_key,
        dry_run=dry_run, now=now,
    )
    return {"candidate_id": candidate_id, "group_id": parsed["group_id"], **result}


def run_publish_primary_group_cycle(conn, *, admin_chat_id=None, bot_token=None, static_config=None,
                                     store_id=None, gelato_api_key=None, shop_id=None,
                                     etsy_api_key=None, etsy_api_secret=None, etsy_access_token=None,
                                     replicate_api_token=None, anthropic_api_key=None,
                                     dry_run=None, now=None) -> list:
    last_offset = get_telegram_offset(conn)
    offset = last_offset + 1 if last_offset is not None else None
    updates = telegram_client.get_updates(offset=offset, bot_token=bot_token)

    processed = []
    max_update_id = last_offset
    for update in updates:
        update_id = update["update_id"]
        max_update_id = update_id if max_update_id is None else max(max_update_id, update_id)
        try:
            result = process_update(
                conn, update, admin_chat_id=admin_chat_id, bot_token=bot_token, static_config=static_config,
                store_id=store_id, gelato_api_key=gelato_api_key, shop_id=shop_id, etsy_api_key=etsy_api_key,
                etsy_api_secret=etsy_api_secret, etsy_access_token=etsy_access_token,
                replicate_api_token=replicate_api_token, anthropic_api_key=anthropic_api_key,
                dry_run=dry_run, now=now,
            )
        except Exception as exc:
            print(f"process_update failed for update {update_id}: {exc}")
            continue
        if result is not None:
            processed.append(result)

    if max_update_id is not None:
        set_telegram_offset(conn, max_update_id)

    return processed
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_publish_primary_group.py -v`
Expected: PASS (all tests in the file).

- [ ] **Step 5: Run the full test suite to confirm no regressions**

Run: `python -m pytest -v`
Expected: PASS (every test in the repo, including all pre-existing suites).

- [ ] **Step 6: Commit**

```bash
git add pipeline/publish_primary_group.py tests/test_publish_primary_group.py
git commit -m "feat: add hourly-poll entrypoint for publish_primary_group with offset tracking"
```

---

## Plan self-review notes

- **Spec coverage:** section 3 step 7 (primary-group publish, 4 sizes, shared metadata, size-title suffix) → Tasks 6–9. Section 4's admin-allowlist requirement on inbound callbacks → Task 4/11. `DELETE`-on-reject-style cleanup semantics reused from `critic_pass.discard_superseded_attempt` for the edit path → Task 10. Operational-failure retry-once-then-isolate → Task 9. Design doc's `update_listing_state`/`fetch_bytes` gaps → Tasks 2–3.
- **Placeholder scan:** no TBD/TODO; every step has runnable code.
- **Type consistency:** `publish_group_product`/`publish_primary_group`/`handle_decision`/`process_update`/`run_publish_primary_group_cycle` signatures match across all tasks that reference them.
