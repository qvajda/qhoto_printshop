# Critic Pass Stage (critic_pass.py) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `pipeline/critic_pass.py`, the fifth of 12 M1 pipeline stage modules — a vision-capable Claude call reviewing the primary group's rendered gallery plus draft listing text against a fixed rubric, owning the up-to-3-attempt regenerate-retry loop across `generate.py`/`primary_mockup.py`/`compliance_draft.py`, and abandoning the candidate (with Gelato cleanup and a Go/Hold/Kill fallback) on exhaustion, per SPEC_v4.10.md section 3 step 5.

**Architecture:** Nine functions in `critic_pass.py`, layered like the prior stages: `build_critic_prompt()` is pure; `get_primary_group_state()` reads the candidate's current live gallery + draft text; `evaluate_critic_pass()` builds and parses a single vision-capable Claude call (via a new `anthropic_client.complete_with_images()`); `record_critic_attempt()`, `discard_superseded_attempt()`, and `abandon_candidate()` are the three DB-mutation helpers; `run_critic_pass()` orchestrates one candidate's full retry loop, directly calling `generate.generate_for_candidate`, `primary_mockup.create_primary_mockup`, and `compliance_draft.build_compliance_draft` between attempts; `run_critic_pass_cycle()` is the batch entry point. A new `research.trigger_fallback_if_needed()` handles the Go/Hold/Kill fallback on final abandonment.

**Tech Stack:** Python 3, `sqlite3` (stdlib, via `pipeline/db.py`), `pytest` + `unittest.mock` — same conventions as every prior stage module.

## Global Constraints

Per the approved design (`docs/superpowers/specs/2026-07-10-critic-pass-stage-design.md`):

- **`critic_pass.py` directly drives `generate.py`/`primary_mockup.py`/`compliance_draft.py`'s single-candidate functions in its own retry loop** — not a separate orchestrator stage. SPEC section 3 step 5 spells the sequence explicitly ("generate → primary_mockup → compliance_draft → critic_pass, repeated") and no orchestrator stage exists in CLAUDE.md's 12-stage list.
- **`discard_superseded_attempt` physically `DELETE`s the superseded `group_products` row and its `product_images` children from SQLite** (plus the Gelato-side `DELETE`) — not a soft `status='deleted'` flag. This is necessary, not a style choice: `compliance_draft.get_primary_gallery`'s query has no status filter, so a second live `group_products` row for the same group would make it return a mixed/duplicated gallery.
- **Before re-drafting on retry, the stale `listing_texts` row is physically deleted** by `critic_pass.py` itself (not a change to the already-merged `compliance_draft.py`) — `write_listing_texts` always `INSERT`s with no upsert, and `listing_texts` has no `UNIQUE(candidate_id)`.
- **No schema changes.** `candidates.status` already has `'primary_review'`/`'failed'`, `groups.status` already has `'failed_abandoned'`, and `critic_pass_attempts` (group_id, attempt_number 1-3, passed, failure_reason, correction_notes) already exists in `db/schema.sql`. `group_products.status`'s existing `'deleted'` value is *not* used by this plan (physical delete is used instead) — left as-is for a future stage that may still want it.
- **Vision call shape verified live against Anthropic's current API docs**, not guessed: an `image` content block with `source: {"type": "url", "url": ...}` is real and documented, images ordered before the text block in the content array.
- **`trigger_fallback_if_needed`'s "the pool" reading:** any other candidate system-wide with `status NOT IN ('failed', 'abandoned', 'completed')` — not scoped to a batch/research-cycle, since the schema has no `batch_id` concept and adding one was explicitly rejected as scope creep beyond this stage.
- **Group-level (5x7/10x24) critic pass is out of scope** — that's the future `group_critic_pass.py` stage.
- Every stage module in this pipeline is independently testable and gets its own commit per passing test group, per CLAUDE.md's "commit after each stage passes its manual M1 test."

---

## Task 1: `anthropic_client.complete_with_images()` — vision-capable completion

**Files:**
- Modify: `pipeline/anthropic_client.py`
- Modify: `tests/test_anthropic_client.py`

**Interfaces:**
- Consumes: `config.require_env`, `http.send`, `ANTHROPIC_MODEL`, `ANTHROPIC_API_BASE`, `_headers` (all already merged, unchanged).
- Produces: `complete_with_images(prompt: str, image_urls: list, *, api_key: str = None, max_tokens: int = 1024) -> dict` — returns `{"text": str, "raw": dict}`. Consumed by Task 4's `evaluate_critic_pass`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_anthropic_client.py`:

```python
def test_complete_with_images_builds_correct_request_with_image_blocks_before_text():
    captured = {}

    def fake_send(request, timeout=30):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["body"] = json.loads(request.data)
        return {"content": [{"type": "text", "text": '{"passed": true, "reason": "ok"}'}]}

    with patch("pipeline.anthropic_client.http.send", side_effect=fake_send):
        result = anthropic_client.complete_with_images(
            "review these images", ["https://gelato/a.jpg", "https://gelato/b.jpg"], api_key="key1"
        )

    assert captured["url"] == "https://api.anthropic.com/v1/messages"
    assert captured["method"] == "POST"
    assert captured["body"]["model"] == anthropic_client.ANTHROPIC_MODEL
    assert captured["body"]["max_tokens"] == 1024
    content = captured["body"]["messages"][0]["content"]
    assert content == [
        {"type": "image", "source": {"type": "url", "url": "https://gelato/a.jpg"}},
        {"type": "image", "source": {"type": "url", "url": "https://gelato/b.jpg"}},
        {"type": "text", "text": "review these images"},
    ]
    assert result["text"] == '{"passed": true, "reason": "ok"}'


def test_complete_with_images_concatenates_multiple_text_blocks():
    def fake_send(request, timeout=30):
        return {"content": [{"type": "text", "text": "line one"}, {"type": "text", "text": "line two"}]}

    with patch("pipeline.anthropic_client.http.send", side_effect=fake_send):
        result = anthropic_client.complete_with_images("prompt", ["https://gelato/a.jpg"], api_key="key1")

    assert result["text"] == "line one\nline two"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_anthropic_client.py -v`
Expected: FAIL — `complete_with_images` doesn't exist yet (`AttributeError`).

- [ ] **Step 3: Implement**

Add to `pipeline/anthropic_client.py`, after `complete`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_anthropic_client.py -v`
Expected: all 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/anthropic_client.py tests/test_anthropic_client.py
git commit -m "feat: add anthropic_client.py complete_with_images for vision calls"
```

---

## Task 2: `critic_pass.py` skeleton — rubric template + `build_critic_prompt()`

**Files:**
- Create: `pipeline/critic_pass.py`
- Create: `tests/test_critic_pass.py`

**Interfaces:**
- Produces: `CRITIC_RUBRIC_PROMPT_TEMPLATE: str` (module constant), `build_critic_prompt(listing_text: dict, image_count: int) -> str`. Consumed by Task 4's `evaluate_critic_pass`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_critic_pass.py`:

```python
import json as _json
from datetime import datetime
from unittest.mock import patch

import pytest

import pipeline.critic_pass as critic_pass
import pipeline.db as db


def test_build_critic_prompt_includes_rubric_and_listing_text():
    listing_text = {
        "title": "Monstera Line Art Botanical Print",
        "description": "A minimalist botanical print.",
    }

    prompt = critic_pass.build_critic_prompt(listing_text, 3)

    assert "Monstera Line Art Botanical Print" in prompt
    assert "A minimalist botanical print." in prompt
    assert "named artist's style" in prompt
    assert "watermark-like elements" in prompt
    assert "off-center or cut-off composition" in prompt
    assert "3 gallery images" in prompt
    assert "'passed' (boolean)" in prompt
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_critic_pass.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.critic_pass'`.

- [ ] **Step 3: Implement `pipeline/critic_pass.py`**

```python
import json
from datetime import datetime, timezone

import pipeline.anthropic_client as anthropic_client
import pipeline.compliance_draft as compliance_draft
import pipeline.config as config
import pipeline.gelato_client as gelato_client
import pipeline.generate as generate
import pipeline.primary_mockup as primary_mockup
import pipeline.research as research


CRITIC_RUBRIC_PROMPT_TEMPLATE = (
    "You are the compliance and quality critic for an Etsy AI-generated wall art listing. "
    "Review the {image_count} gallery images above against this rubric:\n"
    "1. Hard no-go list: no named artist's style, no recognizable characters, franchises, or "
    "logos, no implied celebrity likeness, no claims of hand-painted or one-of-a-kind original "
    "artwork - this is a print reproduction.\n"
    "2. Image quality: no obvious artifacts, no garbled or watermark-like elements, no "
    "off-center or cut-off composition, in any image.\n"
    "3. Text match: does this draft title and description actually match what's shown in the "
    "images and fit the niche?\n\n"
    "Title: {title}\n"
    "Description: {description}\n\n"
    "Reply with ONLY a JSON object with keys 'passed' (boolean) and 'reason' (string explaining "
    "the verdict - cite the specific rubric point if failing), no other text."
)


def build_critic_prompt(listing_text: dict, image_count: int) -> str:
    return CRITIC_RUBRIC_PROMPT_TEMPLATE.format(
        image_count=image_count,
        title=listing_text["title"],
        description=listing_text["description"],
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_critic_pass.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/critic_pass.py tests/test_critic_pass.py
git commit -m "feat: add critic_pass.py build_critic_prompt"
```

---

## Task 3: `get_primary_group_state()` — read the current live gallery + draft text

**Files:**
- Modify: `pipeline/critic_pass.py`
- Modify: `tests/test_critic_pass.py`

**Interfaces:**
- Consumes: `pipeline/db.py`'s `get_connection`/`init_db` (already merged).
- Produces: `get_primary_group_state(conn, candidate_id: int) -> dict` — returns `{"group_id", "group_product_id", "image_urls": list[str], "listing_text": dict}`. Raises `ValueError` if the primary group, its live `group_products` row, or its `listing_texts` row is missing. Consumed by Task 9's `run_critic_pass`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_critic_pass.py`:

```python
def _fresh_conn(tmp_path):
    conn = db.get_connection(tmp_path / "test.sqlite3")
    db.init_db(conn)
    return conn


def _insert_candidate(conn, niche="monstera line art", *, status="generating",
                       base_image_url="https://replicate.delivery/out.png"):
    timestamp = "2026-07-10T11:00:00"
    cursor = conn.execute(
        """
        INSERT INTO candidates (created_at, niche, go_hold_kill, status, base_image_url, updated_at)
        VALUES (?, ?, 'go', ?, ?, ?)
        """,
        (timestamp, niche, status, base_image_url, timestamp),
    )
    conn.commit()
    return cursor.lastrowid


def _insert_primary_gallery(conn, candidate_id,
                             image_urls=("https://gelato/flat.jpg", "https://gelato/life.jpg"),
                             *, gelato_product_id="gelato_prod_1", group_product_status="created"):
    timestamp = "2026-07-10T11:05:00"
    group_cursor = conn.execute(
        "INSERT INTO groups (candidate_id, group_type, status, created_at, updated_at) "
        "VALUES (?, 'primary', 'pending_review', ?, ?)",
        (candidate_id, timestamp, timestamp),
    )
    group_id = group_cursor.lastrowid
    gp_cursor = conn.execute(
        "INSERT INTO group_products "
        "(group_id, size, orientation, gelato_template_id, gelato_product_id, price_eur, "
        "status, created_at, updated_at) "
        "VALUES (?, '8x12', 'portrait', 'tpl_1', ?, 24, ?, ?, ?)",
        (group_id, gelato_product_id, group_product_status, timestamp, timestamp),
    )
    group_product_id = gp_cursor.lastrowid
    for order, image_url in enumerate(image_urls):
        image_type = "flat_mockup" if order == 0 else "lifestyle"
        conn.execute(
            "INSERT INTO product_images (group_product_id, image_url, alt_text, gallery_order, image_type) "
            "VALUES (?, ?, 'placeholder alt', ?, ?)",
            (group_product_id, image_url, order, image_type),
        )
    conn.commit()
    return group_id, group_product_id


def _insert_listing_text(conn, candidate_id, niche="monstera line art"):
    timestamp = "2026-07-10T11:10:00"
    conn.execute(
        """
        INSERT INTO listing_texts (
            candidate_id, title, tags, description, disclosure_text,
            who_made, production_partner_ids, taxonomy_id, shipping_profile_id, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            candidate_id, f"{niche} print", _json.dumps(["botanical", "wall art"]),
            f"A print of {niche}.", "disclosure text",
            "i_did", _json.dumps([5717252]), "1027", "", timestamp,
        ),
    )
    conn.commit()


def _insert_ready_candidate(conn, niche="monstera line art"):
    candidate_id = _insert_candidate(conn, niche=niche)
    _insert_primary_gallery(conn, candidate_id)
    _insert_listing_text(conn, candidate_id, niche=niche)
    return candidate_id


def test_get_primary_group_state_returns_gallery_and_listing_text(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_ready_candidate(conn, niche="monstera line art")

    state = critic_pass.get_primary_group_state(conn, candidate_id)

    assert state["image_urls"] == ["https://gelato/flat.jpg", "https://gelato/life.jpg"]
    assert state["listing_text"]["title"] == "monstera line art print"
    assert state["listing_text"]["description"] == "A print of monstera line art."
    conn.close()


def test_get_primary_group_state_raises_when_no_primary_group(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)

    with pytest.raises(ValueError, match="primary group"):
        critic_pass.get_primary_group_state(conn, candidate_id)
    conn.close()


def test_get_primary_group_state_raises_when_no_listing_text(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_primary_gallery(conn, candidate_id)

    with pytest.raises(ValueError, match="listing_texts"):
        critic_pass.get_primary_group_state(conn, candidate_id)
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_critic_pass.py -v`
Expected: FAIL — `get_primary_group_state` doesn't exist yet (`AttributeError`).

- [ ] **Step 3: Implement**

Add to `pipeline/critic_pass.py`:

```python
def get_primary_group_state(conn, candidate_id: int) -> dict:
    group_row = conn.execute(
        "SELECT id FROM groups WHERE candidate_id = ? AND group_type = 'primary'",
        (candidate_id,),
    ).fetchone()
    if group_row is None:
        raise ValueError(f"No primary group for candidate {candidate_id}")
    group_id = group_row["id"]

    group_product_row = conn.execute(
        "SELECT id FROM group_products WHERE group_id = ? AND status = 'created'",
        (group_id,),
    ).fetchone()
    if group_product_row is None:
        raise ValueError(f"No live group_products row for candidate {candidate_id}'s primary group")
    group_product_id = group_product_row["id"]

    image_rows = conn.execute(
        "SELECT image_url FROM product_images WHERE group_product_id = ? ORDER BY gallery_order",
        (group_product_id,),
    ).fetchall()
    image_urls = [row["image_url"] for row in image_rows]

    listing_row = conn.execute(
        "SELECT title, tags, description FROM listing_texts WHERE candidate_id = ?",
        (candidate_id,),
    ).fetchone()
    if listing_row is None:
        raise ValueError(f"No listing_texts row for candidate {candidate_id}")

    return {
        "group_id": group_id,
        "group_product_id": group_product_id,
        "image_urls": image_urls,
        "listing_text": dict(listing_row),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_critic_pass.py -v`
Expected: all 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/critic_pass.py tests/test_critic_pass.py
git commit -m "feat: add critic_pass.py get_primary_group_state"
```

---

## Task 4: `evaluate_critic_pass()` — the vision call + response parsing

**Files:**
- Modify: `pipeline/critic_pass.py`
- Modify: `tests/test_critic_pass.py`

**Interfaces:**
- Consumes: `anthropic_client.complete_with_images(prompt, image_urls, *, api_key=None, max_tokens=1024) -> dict` (Task 1), `build_critic_prompt` (Task 2).
- Produces: `evaluate_critic_pass(gallery_image_urls: list, listing_text: dict, *, api_key: str = None) -> dict` — returns `{"passed": bool, "reason": str}`, raises `ValueError` on a missing key. Consumed by Task 9's `run_critic_pass`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_critic_pass.py`:

```python
def test_evaluate_critic_pass_returns_parsed_result():
    listing_text = {"title": "Monstera Line Art Botanical Print", "description": "A minimalist botanical print."}
    fake_response = {"text": _json.dumps({"passed": True, "reason": "meets rubric"})}

    with patch("pipeline.critic_pass.anthropic_client.complete_with_images",
               return_value=fake_response) as mock_call:
        result = critic_pass.evaluate_critic_pass(
            ["https://gelato/a.jpg", "https://gelato/b.jpg"], listing_text, api_key="key1"
        )

    mock_call.assert_called_once()
    called_prompt, called_images = mock_call.call_args.args
    assert "Monstera Line Art Botanical Print" in called_prompt
    assert called_images == ["https://gelato/a.jpg", "https://gelato/b.jpg"]
    assert mock_call.call_args.kwargs["api_key"] == "key1"
    assert result == {"passed": True, "reason": "meets rubric"}


def test_evaluate_critic_pass_raises_on_missing_key():
    listing_text = {"title": "A title", "description": "A description."}
    fake_response = {"text": _json.dumps({"passed": False})}

    with patch("pipeline.critic_pass.anthropic_client.complete_with_images", return_value=fake_response):
        with pytest.raises(ValueError, match="reason"):
            critic_pass.evaluate_critic_pass(["https://gelato/a.jpg"], listing_text, api_key="key1")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_critic_pass.py -v`
Expected: FAIL — `evaluate_critic_pass` doesn't exist yet (`AttributeError`).

- [ ] **Step 3: Implement**

Add to `pipeline/critic_pass.py`:

```python
def evaluate_critic_pass(gallery_image_urls: list, listing_text: dict, *, api_key: str = None) -> dict:
    prompt = build_critic_prompt(listing_text, len(gallery_image_urls))
    result = anthropic_client.complete_with_images(prompt, gallery_image_urls, api_key=api_key)
    parsed = json.loads(result["text"])
    for key in ("passed", "reason"):
        if key not in parsed:
            raise ValueError(f"Claude critic response missing required key {key!r}: {parsed!r}")
    return {"passed": parsed["passed"], "reason": parsed["reason"]}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_critic_pass.py -v`
Expected: all 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/critic_pass.py tests/test_critic_pass.py
git commit -m "feat: add critic_pass.py evaluate_critic_pass"
```

---

## Task 5: `record_critic_attempt()` — persist one attempt

**Files:**
- Modify: `pipeline/critic_pass.py`
- Modify: `tests/test_critic_pass.py`

**Interfaces:**
- Produces: `record_critic_attempt(conn, group_id: int, attempt_number: int, result: dict, correction_notes: str = None, *, now=None) -> int` — returns the new `critic_pass_attempts.id`. Consumed by Task 9's `run_critic_pass`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_critic_pass.py`:

```python
def test_record_critic_attempt_stores_pass(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id, _ = _insert_primary_gallery(conn, candidate_id)

    attempt_id = critic_pass.record_critic_attempt(
        conn, group_id, 1, {"passed": True, "reason": "meets rubric"},
        now=datetime(2026, 7, 10, 12, 0, 0),
    )

    row = conn.execute("SELECT * FROM critic_pass_attempts WHERE id = ?", (attempt_id,)).fetchone()
    assert row["group_id"] == group_id
    assert row["attempt_number"] == 1
    assert row["passed"] == 1
    assert row["failure_reason"] is None
    assert row["created_at"] == "2026-07-10T12:00:00"
    conn.close()


def test_record_critic_attempt_stores_failure_with_reason_and_correction_notes(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id, _ = _insert_primary_gallery(conn, candidate_id)

    attempt_id = critic_pass.record_critic_attempt(
        conn, group_id, 1, {"passed": False, "reason": "composition is off-center"},
        correction_notes="composition is off-center", now=datetime(2026, 7, 10, 12, 0, 0),
    )

    row = conn.execute("SELECT * FROM critic_pass_attempts WHERE id = ?", (attempt_id,)).fetchone()
    assert row["passed"] == 0
    assert row["failure_reason"] == "composition is off-center"
    assert row["correction_notes"] == "composition is off-center"
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_critic_pass.py -v`
Expected: FAIL — `record_critic_attempt` doesn't exist yet (`AttributeError`).

- [ ] **Step 3: Implement**

Add to `pipeline/critic_pass.py`:

```python
def record_critic_attempt(conn, group_id: int, attempt_number: int, result: dict,
                           correction_notes: str = None, *, now=None) -> int:
    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()
    cursor = conn.execute(
        """
        INSERT INTO critic_pass_attempts (
            group_id, attempt_number, passed, failure_reason, correction_notes, created_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            group_id, attempt_number, 1 if result["passed"] else 0,
            None if result["passed"] else result["reason"],
            correction_notes, timestamp,
        ),
    )
    conn.commit()
    return cursor.lastrowid
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_critic_pass.py -v`
Expected: all 8 PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/critic_pass.py tests/test_critic_pass.py
git commit -m "feat: add critic_pass.py record_critic_attempt"
```

---

## Task 6: `discard_superseded_attempt()` — Gelato delete + physical row cleanup

**Files:**
- Modify: `pipeline/critic_pass.py`
- Modify: `tests/test_critic_pass.py`

**Interfaces:**
- Consumes: `gelato_client.delete_product(product_id, *, store_id=None, api_key=None, dry_run=None) -> None` (already merged).
- Produces: `discard_superseded_attempt(conn, group_product_id: int, *, store_id: str = None, api_key: str = None) -> None`. Consumed by Task 9's `run_critic_pass`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_critic_pass.py`:

```python
def test_discard_superseded_attempt_deletes_gelato_product_and_rows(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _group_id, group_product_id = _insert_primary_gallery(conn, candidate_id)

    with patch("pipeline.critic_pass.gelato_client.delete_product") as mock_delete:
        critic_pass.discard_superseded_attempt(
            conn, group_product_id, store_id="store1", api_key="key2"
        )

    mock_delete.assert_called_once_with("gelato_prod_1", store_id="store1", api_key="key2")

    assert conn.execute(
        "SELECT * FROM group_products WHERE id = ?", (group_product_id,)
    ).fetchone() is None
    assert conn.execute(
        "SELECT * FROM product_images WHERE group_product_id = ?", (group_product_id,)
    ).fetchall() == []
    conn.close()


def test_discard_superseded_attempt_skips_gelato_call_when_no_product_id(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _group_id, group_product_id = _insert_primary_gallery(
        conn, candidate_id, gelato_product_id=None, group_product_status="pending"
    )

    with patch("pipeline.critic_pass.gelato_client.delete_product") as mock_delete:
        critic_pass.discard_superseded_attempt(conn, group_product_id, store_id="store1", api_key="key2")

    mock_delete.assert_not_called()
    assert conn.execute(
        "SELECT * FROM group_products WHERE id = ?", (group_product_id,)
    ).fetchone() is None
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_critic_pass.py -v`
Expected: FAIL — `discard_superseded_attempt` doesn't exist yet (`AttributeError`).

- [ ] **Step 3: Implement**

Add to `pipeline/critic_pass.py`:

```python
def discard_superseded_attempt(conn, group_product_id: int, *, store_id: str = None, api_key: str = None) -> None:
    row = conn.execute(
        "SELECT gelato_product_id FROM group_products WHERE id = ?", (group_product_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"No group_products row with id {group_product_id}")
    if row["gelato_product_id"]:
        gelato_client.delete_product(row["gelato_product_id"], store_id=store_id, api_key=api_key)
    conn.execute("DELETE FROM product_images WHERE group_product_id = ?", (group_product_id,))
    conn.execute("DELETE FROM group_products WHERE id = ?", (group_product_id,))
    conn.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_critic_pass.py -v`
Expected: all 10 PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/critic_pass.py tests/test_critic_pass.py
git commit -m "feat: add critic_pass.py discard_superseded_attempt"
```

---

## Task 7: `abandon_candidate()` — mark candidate + group failed

**Files:**
- Modify: `pipeline/critic_pass.py`
- Modify: `tests/test_critic_pass.py`

**Interfaces:**
- Produces: `abandon_candidate(conn, candidate_id: int, group_id: int, reason: str, *, now=None) -> None`. Consumed by Task 9's `run_critic_pass`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_critic_pass.py`:

```python
def test_abandon_candidate_marks_candidate_and_group_failed(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id, _ = _insert_primary_gallery(conn, candidate_id)

    critic_pass.abandon_candidate(
        conn, candidate_id, group_id, "exhausted 3 attempts: off-center composition",
        now=datetime(2026, 7, 10, 12, 30, 0),
    )

    candidate_row = conn.execute(
        "SELECT status, failed_reason, updated_at FROM candidates WHERE id = ?", (candidate_id,)
    ).fetchone()
    assert candidate_row["status"] == "failed"
    assert candidate_row["failed_reason"] == "exhausted 3 attempts: off-center composition"
    assert candidate_row["updated_at"] == "2026-07-10T12:30:00"

    group_row = conn.execute(
        "SELECT status, failed_reason FROM groups WHERE id = ?", (group_id,)
    ).fetchone()
    assert group_row["status"] == "failed_abandoned"
    assert group_row["failed_reason"] == "exhausted 3 attempts: off-center composition"
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_critic_pass.py -v`
Expected: FAIL — `abandon_candidate` doesn't exist yet (`AttributeError`).

- [ ] **Step 3: Implement**

Add to `pipeline/critic_pass.py`:

```python
def abandon_candidate(conn, candidate_id: int, group_id: int, reason: str, *, now=None) -> None:
    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()
    conn.execute(
        "UPDATE candidates SET status = 'failed', failed_reason = ?, updated_at = ? WHERE id = ?",
        (reason, timestamp, candidate_id),
    )
    conn.execute(
        "UPDATE groups SET status = 'failed_abandoned', failed_reason = ?, updated_at = ? WHERE id = ?",
        (reason, timestamp, group_id),
    )
    conn.commit()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_critic_pass.py -v`
Expected: all 11 PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/critic_pass.py tests/test_critic_pass.py
git commit -m "feat: add critic_pass.py abandon_candidate"
```

---

## Task 8: `research.trigger_fallback_if_needed()` — Go/Hold/Kill fallback

**Files:**
- Modify: `pipeline/research.py`
- Modify: `tests/test_research.py`

**Interfaces:**
- Consumes: `pick_safe_evergreen_fallback()`, `classify()`, `_insert_candidate()` (all already merged, in `pipeline/research.py`).
- Produces: `trigger_fallback_if_needed(conn, *, now=None) -> int | None` — inserts one safe-evergreen candidate and returns its id only if no other candidate is currently non-terminal; otherwise returns `None`. Consumed by Task 9's `run_critic_pass`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_research.py`:

```python
def test_trigger_fallback_if_needed_noops_when_another_candidate_is_alive(tmp_path):
    conn = _fresh_conn(tmp_path)
    conn.execute(
        "INSERT INTO candidates (created_at, niche, go_hold_kill, status, updated_at) "
        "VALUES ('2026-07-10T09:00:00', 'moon phase print', 'go', 'generating', '2026-07-10T09:00:00')"
    )
    conn.commit()

    result = research.trigger_fallback_if_needed(conn, now=datetime(2026, 7, 10, 12, 0, 0))

    assert result is None
    rows = conn.execute("SELECT * FROM candidates").fetchall()
    assert len(rows) == 1  # no fallback candidate inserted
    conn.close()


def test_trigger_fallback_if_needed_inserts_fallback_when_nothing_alive(tmp_path):
    conn = _fresh_conn(tmp_path)
    conn.execute(
        "INSERT INTO candidates (created_at, niche, go_hold_kill, status, updated_at) "
        "VALUES ('2026-07-10T09:00:00', 'saturated term', 'go', 'failed', '2026-07-10T09:00:00')"
    )
    conn.commit()

    new_id = research.trigger_fallback_if_needed(conn, now=datetime(2026, 7, 10, 12, 0, 0))

    assert new_id is not None
    row = conn.execute("SELECT * FROM candidates WHERE id = ?", (new_id,)).fetchone()
    assert row["status"] == "pending"
    assert row["trend_source"].startswith("safe_evergreen_fallback:")
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_research.py -v`
Expected: FAIL — `trigger_fallback_if_needed` doesn't exist yet (`AttributeError`).

- [ ] **Step 3: Implement**

Add to `pipeline/research.py`, after `run_research_cycle`:

```python
def trigger_fallback_if_needed(conn, *, now=None) -> int:
    other_alive = conn.execute(
        "SELECT 1 FROM candidates WHERE status NOT IN ('failed', 'abandoned', 'completed') LIMIT 1"
    ).fetchone()
    if other_alive is not None:
        return None

    fallback_raw = pick_safe_evergreen_fallback()
    classification = classify(fallback_raw, now=(now.date() if now else date.today()))
    return _insert_candidate(conn, fallback_raw, classification, now=now)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_research.py -v`
Expected: all 19 PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/research.py tests/test_research.py
git commit -m "feat: add research.py trigger_fallback_if_needed"
```

---

## Task 9: `run_critic_pass()` — happy path

**Files:**
- Modify: `pipeline/critic_pass.py`
- Modify: `tests/test_critic_pass.py`

**Interfaces:**
- Consumes: `get_primary_group_state` (Task 3), `evaluate_critic_pass` (Task 4), `record_critic_attempt` (Task 5), `discard_superseded_attempt` (Task 6), `abandon_candidate` (Task 7), `research.trigger_fallback_if_needed` (Task 8), `generate.generate_for_candidate`, `primary_mockup.create_primary_mockup`, `compliance_draft.build_compliance_draft`, `config.load_static_config` (all already merged).
- Produces: `run_critic_pass(conn, candidate_id: int, *, static_config: dict = None, anthropic_api_key: str = None, store_id: str = None, gelato_api_key: str = None, replicate_api_token: str = None, now=None) -> dict` — returns `{"candidate_id", "passed": bool, "attempts": int}`. Consumed by Task 12's `run_critic_pass_cycle`.

This task writes the **complete** retry-loop implementation (pass / fail-and-retry / fail-and-abandon branches) — Tasks 10 and 11 add test coverage for the retry and abandon branches this same implementation already contains, the same pattern `compliance_draft.py`'s plan used for its failure-path coverage.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_critic_pass.py`:

```python
STATIC_CONFIG = {
    "gelato_templates": {
        "8x12_portrait": {
            "template_id": "tpl_real_8x12",
            "template_variant_id": "variant_real_8x12",
            "image_placeholder_name": "real_image_slot.jpg",
        }
    },
    "prices_eur": {"8x12": 24},
    "etsy_who_made": "i_did",
    "etsy_production_partner_ids": [5717252],
    "etsy_taxonomy_id": "1027",
    "etsy_shipping_profile_id": "",
}


def test_run_critic_pass_happy_path_sets_primary_review_on_first_pass(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_ready_candidate(conn, niche="monstera line art")

    fake_response = {"text": _json.dumps({"passed": True, "reason": "meets rubric"})}
    with patch("pipeline.critic_pass.anthropic_client.complete_with_images", return_value=fake_response):
        result = critic_pass.run_critic_pass(
            conn, candidate_id, static_config=STATIC_CONFIG, anthropic_api_key="key1",
            store_id="store1", gelato_api_key="key2", now=datetime(2026, 7, 10, 12, 0, 0),
        )

    assert result == {"candidate_id": candidate_id, "passed": True, "attempts": 1}

    candidate_row = conn.execute("SELECT status FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    assert candidate_row["status"] == "primary_review"

    attempts = conn.execute(
        "SELECT * FROM critic_pass_attempts WHERE group_id = "
        "(SELECT id FROM groups WHERE candidate_id = ? AND group_type = 'primary')",
        (candidate_id,),
    ).fetchall()
    assert len(attempts) == 1
    assert attempts[0]["passed"] == 1
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_critic_pass.py -v`
Expected: FAIL — `run_critic_pass` doesn't exist yet (`AttributeError`).

- [ ] **Step 3: Implement**

Add to `pipeline/critic_pass.py`:

```python
def run_critic_pass(conn, candidate_id: int, *, static_config: dict = None,
                     anthropic_api_key: str = None, store_id: str = None,
                     gelato_api_key: str = None, replicate_api_token: str = None,
                     now=None) -> dict:
    static_config = static_config if static_config is not None else config.load_static_config()

    attempt_number = 1
    while True:
        state = get_primary_group_state(conn, candidate_id)
        result = evaluate_critic_pass(
            state["image_urls"], state["listing_text"], api_key=anthropic_api_key
        )
        record_critic_attempt(conn, state["group_id"], attempt_number, result, now=now)

        if result["passed"]:
            timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()
            conn.execute(
                "UPDATE candidates SET status = 'primary_review', updated_at = ? WHERE id = ?",
                (timestamp, candidate_id),
            )
            conn.commit()
            return {"candidate_id": candidate_id, "passed": True, "attempts": attempt_number}

        discard_superseded_attempt(
            conn, state["group_product_id"], store_id=store_id, api_key=gelato_api_key
        )

        if attempt_number >= 3:
            abandon_candidate(conn, candidate_id, state["group_id"], result["reason"], now=now)
            research.trigger_fallback_if_needed(conn, now=now)
            return {"candidate_id": candidate_id, "passed": False, "attempts": attempt_number}

        conn.execute("DELETE FROM listing_texts WHERE candidate_id = ?", (candidate_id,))
        conn.commit()

        generate.generate_for_candidate(
            conn, candidate_id, correction_note=result["reason"],
            api_token=replicate_api_token, now=now,
        )
        primary_mockup.create_primary_mockup(
            conn, candidate_id, static_config=static_config, store_id=store_id,
            api_key=gelato_api_key, now=now,
        )
        compliance_draft.build_compliance_draft(
            conn, candidate_id, static_config=static_config,
            anthropic_api_key=anthropic_api_key, now=now,
        )
        attempt_number += 1
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_critic_pass.py -v`
Expected: all 12 PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/critic_pass.py tests/test_critic_pass.py
git commit -m "feat: add critic_pass.py run_critic_pass happy path"
```

---

## Task 10: `run_critic_pass()` — retry-then-pass coverage

**Files:**
- Modify: `tests/test_critic_pass.py`

**Interfaces:**
- Consumes/Produces: same `run_critic_pass` from Task 9 — this task adds test coverage for the fail-then-retry-then-pass branch the implementation already contains.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_critic_pass.py`:

```python
def test_run_critic_pass_retries_once_then_passes(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_ready_candidate(conn, niche="monstera line art")

    critic_responses = iter([
        {"text": _json.dumps({"passed": False, "reason": "composition is off-center"})},
        {"text": _json.dumps({"passed": True, "reason": "meets rubric"})},
    ])

    def fake_create_product_from_template(*args, **kwargs):
        return {"id": "gelato_prod_retry", "isReadyToPublish": True,
                "productImages": [{"fileUrl": "https://gelato/flat_v2.jpg", "isPrimary": True}]}

    def fake_get_product(product_id, *, store_id=None, api_key=None):
        return {"id": product_id, "isReadyToPublish": True,
                "productImages": [{"fileUrl": "https://gelato/flat_v2.jpg", "isPrimary": True}]}

    def fake_generate_image(prompt, *, api_token=None):
        assert "composition is off-center" in prompt
        return {"image_url": "https://replicate.delivery/retry.png", "prediction_id": "pred_retry"}

    fake_draft_response = {
        "text": _json.dumps({
            "title": "Monstera Line Art Botanical Print v2",
            "tags": ["botanical"], "description": "Retried description.",
            "alt_texts": ["retry alt one"],
        })
    }

    with patch("pipeline.critic_pass.anthropic_client.complete_with_images",
               side_effect=lambda *a, **k: next(critic_responses)), \
         patch("pipeline.critic_pass.gelato_client.delete_product") as mock_delete, \
         patch("pipeline.generate.replicate_client.generate_image", side_effect=fake_generate_image), \
         patch("pipeline.primary_mockup.gelato_client.create_product_from_template",
               side_effect=fake_create_product_from_template), \
         patch("pipeline.primary_mockup.gelato_client.get_product", side_effect=fake_get_product), \
         patch("pipeline.compliance_draft.anthropic_client.complete", return_value=fake_draft_response):
        result = critic_pass.run_critic_pass(
            conn, candidate_id, static_config=STATIC_CONFIG, anthropic_api_key="key1",
            store_id="store1", gelato_api_key="key2", replicate_api_token="tok1",
            now=datetime(2026, 7, 10, 12, 0, 0),
        )

    assert result == {"candidate_id": candidate_id, "passed": True, "attempts": 2}
    mock_delete.assert_called_once_with("gelato_prod_1", store_id="store1", api_key="key2")

    candidate_row = conn.execute("SELECT status FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    assert candidate_row["status"] == "primary_review"

    listing_rows = conn.execute(
        "SELECT * FROM listing_texts WHERE candidate_id = ?", (candidate_id,)
    ).fetchall()
    assert len(listing_rows) == 1
    assert listing_rows[0]["title"] == "Monstera Line Art Botanical Print v2"

    attempts = conn.execute(
        "SELECT * FROM critic_pass_attempts WHERE group_id = "
        "(SELECT id FROM groups WHERE candidate_id = ? AND group_type = 'primary') "
        "ORDER BY attempt_number",
        (candidate_id,),
    ).fetchall()
    assert len(attempts) == 2
    assert attempts[0]["passed"] == 0
    assert attempts[0]["failure_reason"] == "composition is off-center"
    assert attempts[1]["passed"] == 1
    conn.close()
```

- [ ] **Step 2: Run test to verify it passes**

Run: `python -m pytest tests/test_critic_pass.py -v`
Expected: all 13 PASS — Task 9's implementation already handles this branch. (If it fails, the retry branch in Task 9's code needs fixing before continuing — do not proceed with a red test.)

- [ ] **Step 3: Commit**

```bash
git add tests/test_critic_pass.py
git commit -m "test: cover critic_pass.py run_critic_pass retry-then-pass path"
```

---

## Task 11: `run_critic_pass()` — exhaustion + fallback coverage

**Files:**
- Modify: `tests/test_critic_pass.py`

**Interfaces:**
- Consumes/Produces: same `run_critic_pass` from Task 9 — this task adds test coverage for the 3-failure exhaustion branch (abandon + Go/Hold/Kill fallback trigger) the implementation already contains.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_critic_pass.py`:

```python
def test_run_critic_pass_abandons_after_three_failures_and_triggers_fallback(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_ready_candidate(conn, niche="monstera line art")

    critic_responses = iter([
        {"text": _json.dumps({"passed": False, "reason": "reason one"})},
        {"text": _json.dumps({"passed": False, "reason": "reason two"})},
        {"text": _json.dumps({"passed": False, "reason": "reason three"})},
    ])

    def fake_create_product_from_template(*args, **kwargs):
        return {"id": "gelato_prod_new", "isReadyToPublish": True,
                "productImages": [{"fileUrl": "https://gelato/flat_new.jpg", "isPrimary": True}]}

    def fake_get_product(product_id, *, store_id=None, api_key=None):
        return {"id": product_id, "isReadyToPublish": True,
                "productImages": [{"fileUrl": "https://gelato/flat_new.jpg", "isPrimary": True}]}

    def fake_generate_image(prompt, *, api_token=None):
        return {"image_url": "https://replicate.delivery/retry.png", "prediction_id": "pred_retry"}

    fake_draft_response = {
        "text": _json.dumps({
            "title": "Retried Title", "tags": ["botanical"], "description": "Retried description.",
            "alt_texts": ["retry alt"],
        })
    }

    with patch("pipeline.critic_pass.anthropic_client.complete_with_images",
               side_effect=lambda *a, **k: next(critic_responses)), \
         patch("pipeline.critic_pass.gelato_client.delete_product") as mock_delete, \
         patch("pipeline.generate.replicate_client.generate_image", side_effect=fake_generate_image), \
         patch("pipeline.primary_mockup.gelato_client.create_product_from_template",
               side_effect=fake_create_product_from_template), \
         patch("pipeline.primary_mockup.gelato_client.get_product", side_effect=fake_get_product), \
         patch("pipeline.compliance_draft.anthropic_client.complete", return_value=fake_draft_response):
        result = critic_pass.run_critic_pass(
            conn, candidate_id, static_config=STATIC_CONFIG, anthropic_api_key="key1",
            store_id="store1", gelato_api_key="key2", replicate_api_token="tok1",
            now=datetime(2026, 7, 10, 12, 0, 0),
        )

    assert result == {"candidate_id": candidate_id, "passed": False, "attempts": 3}
    assert mock_delete.call_count == 3

    candidate_row = conn.execute(
        "SELECT status, failed_reason FROM candidates WHERE id = ?", (candidate_id,)
    ).fetchone()
    assert candidate_row["status"] == "failed"
    assert candidate_row["failed_reason"] == "reason three"

    group_row = conn.execute(
        "SELECT status, failed_reason FROM groups WHERE candidate_id = ? AND group_type = 'primary'",
        (candidate_id,),
    ).fetchone()
    assert group_row["status"] == "failed_abandoned"
    assert group_row["failed_reason"] == "reason three"

    fallback_row = conn.execute(
        "SELECT * FROM candidates WHERE trend_source LIKE 'safe_evergreen_fallback:%'"
    ).fetchone()
    assert fallback_row is not None
    assert fallback_row["status"] == "pending"
    conn.close()
```

- [ ] **Step 2: Run test to verify it passes**

Run: `python -m pytest tests/test_critic_pass.py -v`
Expected: all 14 PASS — Task 9's implementation already handles this branch. (If it fails, the exhaustion branch in Task 9's code needs fixing before continuing — do not proceed with a red test.)

- [ ] **Step 3: Commit**

```bash
git add tests/test_critic_pass.py
git commit -m "test: cover critic_pass.py run_critic_pass exhaustion and fallback path"
```

---

## Task 12: `run_critic_pass_cycle()` — batch orchestrator

**Files:**
- Modify: `pipeline/critic_pass.py`
- Modify: `tests/test_critic_pass.py`

**Interfaces:**
- Consumes: `run_critic_pass(conn, candidate_id, ...)` (Tasks 9-11).
- Produces: `run_critic_pass_cycle(conn, *, static_config: dict = None, anthropic_api_key: str = None, store_id: str = None, gelato_api_key: str = None, replicate_api_token: str = None, now=None) -> list[int]` — the module's public batch entry point, to be called by the not-yet-built twice-daily batch orchestrator after `compliance_draft.run_compliance_draft_cycle`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_critic_pass.py`:

```python
def test_run_critic_pass_cycle_processes_ready_candidates_and_skips_undrafted(tmp_path):
    conn = _fresh_conn(tmp_path)
    ready_id = _insert_ready_candidate(conn, niche="monstera line art")
    undrafted_id = _insert_candidate(conn, niche="pending one", status="generating")
    _insert_primary_gallery(conn, undrafted_id)  # gallery exists but no listing_texts row yet

    fake_response = {"text": _json.dumps({"passed": True, "reason": "meets rubric"})}
    with patch("pipeline.critic_pass.anthropic_client.complete_with_images", return_value=fake_response):
        processed_ids = critic_pass.run_critic_pass_cycle(
            conn, static_config=STATIC_CONFIG, anthropic_api_key="key1",
            store_id="store1", gelato_api_key="key2", now=datetime(2026, 7, 10, 12, 0, 0),
        )

    assert processed_ids == [ready_id]
    assert undrafted_id not in processed_ids
    conn.close()


def test_run_critic_pass_cycle_skips_candidates_already_passed(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_ready_candidate(conn, niche="monstera line art")

    fake_response = {"text": _json.dumps({"passed": True, "reason": "meets rubric"})}
    with patch("pipeline.critic_pass.anthropic_client.complete_with_images", return_value=fake_response):
        first_run = critic_pass.run_critic_pass_cycle(
            conn, static_config=STATIC_CONFIG, anthropic_api_key="key1",
            store_id="store1", gelato_api_key="key2", now=datetime(2026, 7, 10, 12, 0, 0),
        )
        second_run = critic_pass.run_critic_pass_cycle(
            conn, static_config=STATIC_CONFIG, anthropic_api_key="key1",
            store_id="store1", gelato_api_key="key2", now=datetime(2026, 7, 10, 13, 0, 0),
        )

    assert first_run == [candidate_id]
    assert second_run == []
    conn.close()


def test_run_critic_pass_cycle_isolates_per_candidate_operational_failures(tmp_path):
    conn = _fresh_conn(tmp_path)
    failing_id = _insert_ready_candidate(conn, niche="saturated term")
    succeeding_id = _insert_ready_candidate(conn, niche="moon phase print")

    def fake_complete_with_images(prompt, image_urls, *, api_key=None, max_tokens=1024):
        if "saturated term" in prompt:
            raise RuntimeError("Anthropic throttled")
        return {"text": _json.dumps({"passed": True, "reason": "meets rubric"})}

    with patch("pipeline.critic_pass.anthropic_client.complete_with_images",
               side_effect=fake_complete_with_images):
        processed_ids = critic_pass.run_critic_pass_cycle(
            conn, static_config=STATIC_CONFIG, anthropic_api_key="key1",
            store_id="store1", gelato_api_key="key2", now=datetime(2026, 7, 10, 12, 0, 0),
        )

    assert processed_ids == [succeeding_id]

    failing_row = conn.execute("SELECT status FROM candidates WHERE id = ?", (failing_id,)).fetchone()
    assert failing_row["status"] == "generating"  # exception happened before any status write
    conn.close()


def test_run_critic_pass_cycle_returns_empty_list_when_nothing_ready(tmp_path):
    conn = _fresh_conn(tmp_path)
    _insert_candidate(conn, niche="pending one", status="pending")

    processed_ids = critic_pass.run_critic_pass_cycle(conn, static_config=STATIC_CONFIG)

    assert processed_ids == []
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_critic_pass.py -v`
Expected: FAIL — `run_critic_pass_cycle` doesn't exist yet (`AttributeError`).

- [ ] **Step 3: Implement**

Add to `pipeline/critic_pass.py`:

```python
def run_critic_pass_cycle(conn, *, static_config: dict = None, anthropic_api_key: str = None,
                           store_id: str = None, gelato_api_key: str = None,
                           replicate_api_token: str = None, now=None) -> list:
    candidate_ids = [
        row["id"] for row in conn.execute(
            """
            SELECT DISTINCT c.id FROM candidates c
            JOIN groups g ON g.candidate_id = c.id AND g.group_type = 'primary'
            JOIN listing_texts lt ON lt.candidate_id = c.id
            WHERE c.status = 'generating'
              AND g.id NOT IN (SELECT group_id FROM critic_pass_attempts WHERE passed = 1)
            ORDER BY c.id
            """
        ).fetchall()
    ]
    processed_ids = []
    for candidate_id in candidate_ids:
        try:
            run_critic_pass(
                conn, candidate_id, static_config=static_config, anthropic_api_key=anthropic_api_key,
                store_id=store_id, gelato_api_key=gelato_api_key,
                replicate_api_token=replicate_api_token, now=now,
            )
        except Exception as exc:
            print(f"run_critic_pass failed for candidate {candidate_id}: {exc}")
            continue
        processed_ids.append(candidate_id)
    return processed_ids
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_critic_pass.py -v`
Expected: all 18 PASS.

- [ ] **Step 5: Run the full test suite to confirm nothing else broke**

Run: `python -m pytest -v`
Expected: all PASS (db, config, http, gelato, replicate, telegram, etsy, anthropic, research, generate, primary_mockup, compliance_draft, critic_pass suites).

- [ ] **Step 6: Commit**

```bash
git add pipeline/critic_pass.py tests/test_critic_pass.py
git commit -m "feat: add critic_pass.py run_critic_pass_cycle batch orchestrator"
```

---

## Self-Review Notes

- **Spec coverage:** all 9 `critic_pass.py` function signatures (Tasks 2-12), the new vision-capable `anthropic_client.complete_with_images` (Task 1, verified against live Anthropic docs), the rubric prompt covering all three checks from SPEC section 3 step 5 (Task 2), the "one live attempt at a time" gallery/draft-text read (Task 3), the pass/fail-plus-reason vision evaluation with fail-loud shape checks (Task 4), permanent per-attempt history (Task 5), the physical-delete supersession cleanup that both satisfies "delete the Gelato product created during each failed attempt" and keeps `get_primary_group_state`/`compliance_draft.get_primary_gallery` correct (Task 6), the abandon-on-exhaustion status flips (Task 7), the Go/Hold/Kill fallback with its explicitly-scoped "any other non-terminal candidate" reading (Task 8), the full retry loop directly driving `generate`/`primary_mockup`/`compliance_draft` with the stale-`listing_texts` cleanup before each redraft (Task 9), retry-then-pass coverage (Task 10), 3-attempt exhaustion coverage (Task 11), and the combined-check selection predicate excluding both undrafted and already-passed candidates (Task 12) are all covered, matching `docs/superpowers/specs/2026-07-10-critic-pass-stage-design.md` sections 1-7.
- **Placeholder scan:** no TBD/"add error handling"/"similar to Task N" language. Every step has concrete, runnable code.
- **Type consistency:** `run_critic_pass`'s keyword signature (Task 9) is called identically by `run_critic_pass_cycle` (Task 12) — same parameter names (`static_config`, `anthropic_api_key`, `store_id`, `gelato_api_key`, `replicate_api_token`, `now`). `get_primary_group_state`'s return dict keys (`group_id`, `group_product_id`, `image_urls`, `listing_text`, Task 3) match exactly what `run_critic_pass` reads off `state` (Task 9). `evaluate_critic_pass`'s return dict keys (`passed`, `reason`, Task 4) match what `record_critic_attempt`/`discard_superseded_attempt`/`abandon_candidate` consume (Tasks 5-7) and what `run_critic_pass` branches on (Task 9). `trigger_fallback_if_needed`'s signature (Task 8) matches its call site in `run_critic_pass` (Task 9) exactly (`conn, now=now`).
