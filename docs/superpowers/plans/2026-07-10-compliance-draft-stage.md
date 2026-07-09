# Compliance Draft Stage (compliance_draft.py) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `pipeline/compliance_draft.py`, the fourth of 12 M1 pipeline stage modules — auto-fills disclosure text, Etsy compliance metadata, a title/tags/description draft, and gallery alt text for the primary-size listing, per SPEC_v4.10.md section 3 step 4.

**Architecture:** Nine functions in one module, layered like `primary_mockup.py`: `resolve_compliance_metadata()` and `validate_listing_text()` are pure; `get_primary_gallery()` reads the primary group's `product_images`; `build_draft_prompt()`/`generate_draft_text()` build and parse a single text-only Claude call (via a new `anthropic_client.complete()`); `write_listing_texts()` and `update_gallery_alt_text()` are the two DB writes; `build_compliance_draft()` orchestrates one candidate's full flow, marking `candidates.status='compliance_failed'` on any error; `run_compliance_draft_cycle()` is the batch entry point.

**Tech Stack:** Python 3, `sqlite3` (stdlib, via `pipeline/db.py`), `pytest` + `unittest.mock` — same conventions as `pipeline/primary_mockup.py`/`pipeline/generate.py`.

## Global Constraints

Per the approved design (`docs/superpowers/specs/2026-07-10-compliance-draft-stage-design.md`):

- **Text-only, no vision.** Alt text comes from the same single Claude call as title/tags/description, keyed only to each image's `image_type` (`'flat_mockup'`/`'lifestyle'`) — never from inspecting the actual rendered image. The critic pass (future stage) is the vision-capable one.
- **Only the primary group's gallery is in scope.** `get_primary_gallery` always filters `group_type = 'primary'` — the 5x7/10x24 groups don't exist yet at this point in the pipeline.
- **`candidates.status` stays `'generating'` on success** — this stage never sets `'primary_review'` (that's `critic_pass.py`'s job, confirmed in the prior stage's design review). On failure it's set to the new `'compliance_failed'` value (Task 1) plus `failed_reason`, which — via this module's own selection predicate — also keeps the batch cycle from retrying it forever.
- **Blank `etsy_shipping_profile_id` is passed through as-is**, not fail-loud. `resolve_compliance_metadata` reads `static_config["etsy_shipping_profile_id"]` directly, even while it's still `""`. The real fail-loud check belongs to the future `publish_primary_group.py` stage, which is the one that actually calls Etsy's `create_draft_listing`.
- **`listing_texts.tags` and `.production_partner_ids` are stored `json.dumps()`-encoded** — no prior module writes to this table, so this stage sets the convention. `publish_primary_group.py` will `json.loads()` them back later.
- **Schema change required:** `candidates.status`'s CHECK constraint gains `'compliance_failed'` (Task 1) — the only schema change in this plan. Distinct from the existing `'failed'` value, which stays reserved for critic-pass exhaustion (Gelato cleanup + Go/Hold/Kill fallback) — a compliance-draft failure has neither of those implications.
- **Known accepted limitation** (same class as `primary_mockup.py`'s stuck-`'pending'` edge case): if `write_listing_texts` commits but `update_gallery_alt_text` then raises, the `listing_texts` row is already persisted, so `run_compliance_draft_cycle`'s `NOT IN (SELECT candidate_id FROM listing_texts)` predicate treats the candidate as done even though alt text wasn't fully updated. Not fixed in this plan — Task 10 has a test that documents this exact scenario rather than silently missing it.
- Every stage module in this pipeline is independently testable and gets its own commit per passing test group, per CLAUDE.md's "commit after each stage passes its manual M1 test."

---

## Task 1: Schema change — `candidates.status` gains `'compliance_failed'`

**Files:**
- Modify: `db/schema.sql`
- Modify: `tests/test_db.py`

**Interfaces:**
- Produces: `candidates.status` now accepts `'compliance_failed'` as a valid value, alongside the existing `'pending'/'generating'/'primary_review'/'failed'/'abandoned'/'completed'`. Consumed by Task 10's failure-handling code.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_db.py`:

```python
def test_candidates_accepts_compliance_failed_status(tmp_path):
    db_path = tmp_path / "test.sqlite3"
    conn = db.get_connection(db_path)
    db.init_db(conn)

    conn.execute(
        "INSERT INTO candidates (id, created_at, niche, go_hold_kill, status, updated_at) "
        "VALUES (1, '2026-07-10', 'botanical', 'go', 'compliance_failed', '2026-07-10')"
    )
    conn.commit()

    row = conn.execute("SELECT status FROM candidates WHERE id = 1").fetchone()
    assert row["status"] == "compliance_failed"
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_db.py::test_candidates_accepts_compliance_failed_status -v`
Expected: FAIL with `sqlite3.IntegrityError: CHECK constraint failed: candidates`.

- [ ] **Step 3: Update the schema**

In `db/schema.sql`, find the `candidates` table's `status` CHECK constraint:

```sql
  status TEXT NOT NULL CHECK(status IN (
    'pending','generating','primary_review','failed','abandoned','completed'
  )),
```

Replace it with:

```sql
  status TEXT NOT NULL CHECK(status IN (
    'pending','generating','primary_review','compliance_failed','failed','abandoned','completed'
  )),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_db.py -v`
Expected: all PASS, including the new test.

- [ ] **Step 5: Commit**

```bash
git add db/schema.sql tests/test_db.py
git commit -m "feat: add compliance_failed status to candidates for compliance_draft.py"
```

---

## Task 2: `anthropic_client.complete()` — plain completion, no tools

**Files:**
- Modify: `pipeline/anthropic_client.py`
- Modify: `tests/test_anthropic_client.py`

**Interfaces:**
- Consumes: `config.require_env`, `http.send` (already merged, unchanged).
- Produces: `complete(prompt: str, *, api_key: str = None, max_tokens: int = 1024) -> dict` — returns `{"text": str, "raw": dict}`. Consumed by Task 6's `generate_draft_text`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_anthropic_client.py`:

```python
def test_complete_builds_correct_request_without_tools():
    captured = {}

    def fake_send(request, timeout=30):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["body"] = json.loads(request.data)
        return {"content": [{"type": "text", "text": '{"title": "Botanical Wall Art"}'}]}

    with patch("pipeline.anthropic_client.http.send", side_effect=fake_send):
        result = anthropic_client.complete("draft some listing text", api_key="key1")

    assert captured["url"] == "https://api.anthropic.com/v1/messages"
    assert captured["method"] == "POST"
    assert captured["body"]["model"] == anthropic_client.ANTHROPIC_MODEL
    assert captured["body"]["max_tokens"] == 1024
    assert captured["body"]["messages"] == [{"role": "user", "content": "draft some listing text"}]
    assert "tools" not in captured["body"]
    assert result["text"] == '{"title": "Botanical Wall Art"}'


def test_complete_concatenates_multiple_text_blocks():
    def fake_send(request, timeout=30):
        return {"content": [{"type": "text", "text": "line one"}, {"type": "text", "text": "line two"}]}

    with patch("pipeline.anthropic_client.http.send", side_effect=fake_send):
        result = anthropic_client.complete("prompt", api_key="key1")

    assert result["text"] == "line one\nline two"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_anthropic_client.py -v`
Expected: FAIL — `complete` doesn't exist yet (`AttributeError`).

- [ ] **Step 3: Implement**

Add to `pipeline/anthropic_client.py`, after `research_web_search`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_anthropic_client.py -v`
Expected: all 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/anthropic_client.py tests/test_anthropic_client.py
git commit -m "feat: add anthropic_client.py complete for plain text completions"
```

---

## Task 3: `compliance_draft.py` skeleton — `DISCLOSURE_TEXT` + `resolve_compliance_metadata()`

**Files:**
- Create: `pipeline/compliance_draft.py`
- Create: `tests/test_compliance_draft.py`

**Interfaces:**
- Produces: `DISCLOSURE_TEXT: str` (module constant), `resolve_compliance_metadata(static_config: dict) -> dict`. Consumed by Task 9's `build_compliance_draft` and Task 7's `write_listing_texts`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_compliance_draft.py`:

```python
import pipeline.compliance_draft as compliance_draft


STATIC_CONFIG = {
    "etsy_who_made": "i_did",
    "etsy_production_partner_ids": [5717252],
    "etsy_taxonomy_id": "1027",
    "etsy_shipping_profile_id": "",
}


def test_resolve_compliance_metadata_reads_static_config_fields():
    metadata = compliance_draft.resolve_compliance_metadata(STATIC_CONFIG)

    assert metadata == {
        "who_made": "i_did",
        "production_partner_ids": [5717252],
        "taxonomy_id": "1027",
        "shipping_profile_id": "",
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_compliance_draft.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.compliance_draft'`.

- [ ] **Step 3: Implement `pipeline/compliance_draft.py`**

```python
import json
from datetime import datetime, timezone

import pipeline.anthropic_client as anthropic_client
import pipeline.config as config


DISCLOSURE_TEXT = (
    "This design was created using AI image generation from the seller's own prompts, "
    "then selected, edited, and prepared for print by the seller. Printed and shipped "
    "by our production partner, Gelato."
)


def resolve_compliance_metadata(static_config: dict) -> dict:
    return {
        "who_made": static_config["etsy_who_made"],
        "production_partner_ids": static_config["etsy_production_partner_ids"],
        "taxonomy_id": static_config["etsy_taxonomy_id"],
        "shipping_profile_id": static_config["etsy_shipping_profile_id"],
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_compliance_draft.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/compliance_draft.py tests/test_compliance_draft.py
git commit -m "feat: add compliance_draft.py resolve_compliance_metadata"
```

---

## Task 4: `validate_listing_text()` — Etsy format-limit validation

**Files:**
- Modify: `pipeline/compliance_draft.py`
- Modify: `tests/test_compliance_draft.py`

**Interfaces:**
- Produces: `MAX_TAGS = 13`, `MAX_TAG_LENGTH = 20`, `MAX_TITLE_LENGTH = 140` (module constants), `validate_listing_text(title: str, tags: list[str]) -> None` — raises `ValueError` on any limit violation. Consumed by Task 9's `build_compliance_draft`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_compliance_draft.py`:

```python
import pytest


def test_validate_listing_text_accepts_valid_input():
    compliance_draft.validate_listing_text("Botanical Wall Art Print", ["botanical", "wall art", "minimalist"])


def test_validate_listing_text_rejects_title_over_140_chars():
    long_title = "x" * 141

    with pytest.raises(ValueError, match="140"):
        compliance_draft.validate_listing_text(long_title, ["botanical"])


def test_validate_listing_text_rejects_more_than_13_tags():
    too_many_tags = [f"tag{i}" for i in range(14)]

    with pytest.raises(ValueError, match="13"):
        compliance_draft.validate_listing_text("A short title", too_many_tags)


def test_validate_listing_text_rejects_tag_over_20_chars():
    long_tag = "x" * 21

    with pytest.raises(ValueError, match="20"):
        compliance_draft.validate_listing_text("A short title", [long_tag])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_compliance_draft.py -v`
Expected: FAIL — `validate_listing_text` doesn't exist yet (`AttributeError`).

- [ ] **Step 3: Implement**

Add to `pipeline/compliance_draft.py`:

```python
MAX_TAGS = 13
MAX_TAG_LENGTH = 20
MAX_TITLE_LENGTH = 140


def validate_listing_text(title: str, tags: list) -> None:
    if len(title) > MAX_TITLE_LENGTH:
        raise ValueError(
            f"title is {len(title)} chars, exceeds Etsy's {MAX_TITLE_LENGTH}-char limit: {title!r}"
        )
    if len(tags) > MAX_TAGS:
        raise ValueError(f"{len(tags)} tags exceeds Etsy's {MAX_TAGS}-tag limit: {tags!r}")
    for tag in tags:
        if len(tag) > MAX_TAG_LENGTH:
            raise ValueError(
                f"tag {tag!r} is {len(tag)} chars, exceeds Etsy's {MAX_TAG_LENGTH}-char limit"
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_compliance_draft.py -v`
Expected: all 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/compliance_draft.py tests/test_compliance_draft.py
git commit -m "feat: add compliance_draft.py validate_listing_text"
```

---

## Task 5: `get_primary_gallery()` — read the primary group's image rows

**Files:**
- Modify: `pipeline/compliance_draft.py`
- Modify: `tests/test_compliance_draft.py`

**Interfaces:**
- Consumes: `pipeline/db.py`'s `get_connection`/`init_db` (already merged).
- Produces: `get_primary_gallery(conn, candidate_id: int) -> list[dict]` — rows with `id`, `gallery_order`, `image_type`, ordered by `gallery_order`. Consumed by Task 8's `update_gallery_alt_text` and Task 9's `build_compliance_draft`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_compliance_draft.py`:

```python
import pipeline.db as db


def _fresh_conn(tmp_path):
    conn = db.get_connection(tmp_path / "test.sqlite3")
    db.init_db(conn)
    return conn


def _insert_candidate(conn, niche="monstera line art", *, status="generating"):
    timestamp = "2026-07-10T09:00:00"
    cursor = conn.execute(
        """
        INSERT INTO candidates (created_at, niche, go_hold_kill, status, updated_at)
        VALUES (?, ?, 'go', ?, ?)
        """,
        (timestamp, niche, status, timestamp),
    )
    conn.commit()
    return cursor.lastrowid


def _insert_primary_gallery(conn, candidate_id, image_types=("flat_mockup", "lifestyle"),
                             *, group_product_status="created"):
    timestamp = "2026-07-10T09:05:00"
    group_cursor = conn.execute(
        "INSERT INTO groups (candidate_id, group_type, status, created_at, updated_at) "
        "VALUES (?, 'primary', 'pending_review', ?, ?)",
        (candidate_id, timestamp, timestamp),
    )
    group_id = group_cursor.lastrowid
    gp_cursor = conn.execute(
        "INSERT INTO group_products "
        "(group_id, size, orientation, gelato_template_id, price_eur, status, created_at, updated_at) "
        "VALUES (?, '8x12', 'portrait', 'tpl_1', 24, ?, ?, ?)",
        (group_id, group_product_status, timestamp, timestamp),
    )
    group_product_id = gp_cursor.lastrowid
    for order, image_type in enumerate(image_types):
        conn.execute(
            "INSERT INTO product_images (group_product_id, image_url, alt_text, gallery_order, image_type) "
            "VALUES (?, ?, '', ?, ?)",
            (group_product_id, f"https://gelato/img{order}.jpg", order, image_type),
        )
    conn.commit()
    return group_product_id


def _insert_ready_candidate(conn, niche="monstera line art", image_types=("flat_mockup", "lifestyle")):
    candidate_id = _insert_candidate(conn, niche=niche, status="generating")
    _insert_primary_gallery(conn, candidate_id, image_types=image_types)
    return candidate_id


def test_get_primary_gallery_returns_images_in_order(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_ready_candidate(
        conn, image_types=("flat_mockup", "lifestyle", "lifestyle")
    )

    gallery = compliance_draft.get_primary_gallery(conn, candidate_id)

    assert [image["image_type"] for image in gallery] == ["flat_mockup", "lifestyle", "lifestyle"]
    assert [image["gallery_order"] for image in gallery] == [0, 1, 2]
    conn.close()


def test_get_primary_gallery_returns_empty_list_when_no_gallery(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)

    gallery = compliance_draft.get_primary_gallery(conn, candidate_id)

    assert gallery == []
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_compliance_draft.py -v`
Expected: FAIL — `get_primary_gallery` doesn't exist yet (`AttributeError`).

- [ ] **Step 3: Implement**

Add to `pipeline/compliance_draft.py`:

```python
def get_primary_gallery(conn, candidate_id: int) -> list:
    rows = conn.execute(
        """
        SELECT pi.id, pi.gallery_order, pi.image_type
        FROM product_images pi
        JOIN group_products gp ON gp.id = pi.group_product_id
        JOIN groups g ON g.id = gp.group_id
        WHERE g.candidate_id = ? AND g.group_type = 'primary'
        ORDER BY pi.gallery_order
        """,
        (candidate_id,),
    ).fetchall()
    return [dict(row) for row in rows]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_compliance_draft.py -v`
Expected: all 7 PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/compliance_draft.py tests/test_compliance_draft.py
git commit -m "feat: add compliance_draft.py get_primary_gallery"
```

---

## Task 6: `build_draft_prompt()` + `generate_draft_text()` — Claude draft generation

**Files:**
- Modify: `pipeline/compliance_draft.py`
- Modify: `tests/test_compliance_draft.py`

**Interfaces:**
- Consumes: `anthropic_client.complete(prompt, *, api_key=None, max_tokens=1024) -> dict` (Task 2), `DISCLOSURE_TEXT` (Task 3).
- Produces: `build_draft_prompt(candidate: dict, image_types: list[str]) -> str` (pure); `generate_draft_text(candidate: dict, image_types: list[str], *, api_key: str = None) -> dict` — returns `{"title", "tags", "description", "alt_texts"}`, raises `ValueError` on a missing key or an `alt_texts` length mismatch. Both consumed by Task 9's `build_compliance_draft`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_compliance_draft.py`:

```python
import json as _json
from unittest.mock import patch


def test_build_draft_prompt_includes_niche_disclosure_and_limits():
    candidate = {"niche": "monstera line art"}

    prompt = compliance_draft.build_draft_prompt(candidate, ["flat_mockup", "lifestyle"])

    assert "monstera line art" in prompt
    assert compliance_draft.DISCLOSURE_TEXT in prompt
    assert "140" in prompt
    assert "13" in prompt
    assert "20" in prompt
    assert "flat_mockup, lifestyle" in prompt


def test_generate_draft_text_returns_parsed_draft():
    candidate = {"niche": "monstera line art"}
    fake_response = {
        "text": _json.dumps({
            "title": "Monstera Line Art Botanical Print",
            "tags": ["botanical", "wall art"],
            "description": "A minimalist botanical print.",
            "alt_texts": ["Flat mockup of monstera line art print", "Monstera print shown in a living room"],
        })
    }

    with patch("pipeline.compliance_draft.anthropic_client.complete", return_value=fake_response) as mock_complete:
        draft = compliance_draft.generate_draft_text(
            candidate, ["flat_mockup", "lifestyle"], api_key="key1"
        )

    mock_complete.assert_called_once()
    assert mock_complete.call_args.kwargs["api_key"] == "key1"
    assert draft["title"] == "Monstera Line Art Botanical Print"
    assert draft["tags"] == ["botanical", "wall art"]
    assert len(draft["alt_texts"]) == 2


def test_generate_draft_text_raises_on_missing_key():
    candidate = {"niche": "monstera line art"}
    fake_response = {"text": _json.dumps({"title": "A title", "tags": [], "description": "desc"})}

    with patch("pipeline.compliance_draft.anthropic_client.complete", return_value=fake_response):
        with pytest.raises(ValueError, match="alt_texts"):
            compliance_draft.generate_draft_text(candidate, ["flat_mockup"], api_key="key1")


def test_generate_draft_text_raises_on_alt_text_count_mismatch():
    candidate = {"niche": "monstera line art"}
    fake_response = {
        "text": _json.dumps({
            "title": "A title", "tags": ["botanical"], "description": "desc",
            "alt_texts": ["only one alt text"],
        })
    }

    with patch("pipeline.compliance_draft.anthropic_client.complete", return_value=fake_response):
        with pytest.raises(ValueError, match="alt_texts"):
            compliance_draft.generate_draft_text(
                candidate, ["flat_mockup", "lifestyle"], api_key="key1"
            )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_compliance_draft.py -v`
Expected: FAIL — `build_draft_prompt`/`generate_draft_text` don't exist yet (`AttributeError`).

- [ ] **Step 3: Implement**

Add to `pipeline/compliance_draft.py`:

```python
DRAFT_TEXT_PROMPT_TEMPLATE = (
    "You are writing an Etsy listing draft for an AI-generated botanical/minimalist wall "
    "art poster print, niche: {niche}. This listing must comply with Etsy's format limits: "
    "the title must be at most 140 characters, there must be at most 13 tags and each tag "
    "at most 20 characters, and the description must mention the following AI disclosure: "
    "\"{disclosure}\"\n\n"
    "The product gallery has {image_count} images in this order: {image_types}. Write one "
    "short, descriptive alt text per image, in the same order, distinguishing a flat print "
    "mockup shot from a lifestyle/room-context shot.\n\n"
    "Reply with ONLY a JSON object with keys 'title' (string), 'tags' (list of strings), "
    "'description' (string), and 'alt_texts' (list of strings, same length and order as the "
    "gallery), no other text."
)


def build_draft_prompt(candidate: dict, image_types: list) -> str:
    return DRAFT_TEXT_PROMPT_TEMPLATE.format(
        niche=candidate["niche"],
        disclosure=DISCLOSURE_TEXT,
        image_count=len(image_types),
        image_types=", ".join(image_types),
    )


def generate_draft_text(candidate: dict, image_types: list, *, api_key: str = None) -> dict:
    result = anthropic_client.complete(build_draft_prompt(candidate, image_types), api_key=api_key)
    draft = json.loads(result["text"])
    for key in ("title", "tags", "description", "alt_texts"):
        if key not in draft:
            raise ValueError(f"Claude draft response missing required key {key!r}: {draft!r}")
    if len(draft["alt_texts"]) != len(image_types):
        raise ValueError(
            f"Claude draft response has {len(draft['alt_texts'])} alt_texts, "
            f"expected {len(image_types)} to match the gallery: {draft!r}"
        )
    return draft
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_compliance_draft.py -v`
Expected: all 11 PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/compliance_draft.py tests/test_compliance_draft.py
git commit -m "feat: add compliance_draft.py build_draft_prompt and generate_draft_text"
```

---

## Task 7: `write_listing_texts()` — persist the draft + metadata

**Files:**
- Modify: `pipeline/compliance_draft.py`
- Modify: `tests/test_compliance_draft.py`

**Interfaces:**
- Consumes: `DISCLOSURE_TEXT` (Task 3).
- Produces: `write_listing_texts(conn, candidate_id: int, draft: dict, metadata: dict, *, now=None) -> int` — returns the new `listing_texts.id`. Consumed by Task 9's `build_compliance_draft`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_compliance_draft.py`:

```python
from datetime import datetime


def test_write_listing_texts_inserts_row_with_json_encoded_lists(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    draft = {
        "title": "Monstera Line Art Botanical Print",
        "tags": ["botanical", "wall art"],
        "description": "A minimalist botanical print.",
        "alt_texts": ["alt one", "alt two"],
    }
    metadata = {
        "who_made": "i_did",
        "production_partner_ids": [5717252],
        "taxonomy_id": "1027",
        "shipping_profile_id": "",
    }

    listing_text_id = compliance_draft.write_listing_texts(
        conn, candidate_id, draft, metadata, now=datetime(2026, 7, 10, 9, 30, 0)
    )

    row = conn.execute("SELECT * FROM listing_texts WHERE id = ?", (listing_text_id,)).fetchone()
    assert row["candidate_id"] == candidate_id
    assert row["title"] == "Monstera Line Art Botanical Print"
    assert _json.loads(row["tags"]) == ["botanical", "wall art"]
    assert row["description"] == "A minimalist botanical print."
    assert row["disclosure_text"] == compliance_draft.DISCLOSURE_TEXT
    assert row["who_made"] == "i_did"
    assert _json.loads(row["production_partner_ids"]) == [5717252]
    assert row["taxonomy_id"] == "1027"
    assert row["shipping_profile_id"] == ""
    assert row["created_at"] == "2026-07-10T09:30:00"
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_compliance_draft.py -v`
Expected: FAIL — `write_listing_texts` doesn't exist yet (`AttributeError`).

- [ ] **Step 3: Implement**

Add to `pipeline/compliance_draft.py`:

```python
def write_listing_texts(conn, candidate_id: int, draft: dict, metadata: dict, *, now=None) -> int:
    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()
    cursor = conn.execute(
        """
        INSERT INTO listing_texts (
            candidate_id, title, tags, description, disclosure_text,
            who_made, production_partner_ids, taxonomy_id, shipping_profile_id, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            candidate_id, draft["title"], json.dumps(draft["tags"]), draft["description"], DISCLOSURE_TEXT,
            metadata["who_made"], json.dumps(metadata["production_partner_ids"]),
            metadata["taxonomy_id"], metadata["shipping_profile_id"], timestamp,
        ),
    )
    conn.commit()
    return cursor.lastrowid
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_compliance_draft.py -v`
Expected: all 12 PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/compliance_draft.py tests/test_compliance_draft.py
git commit -m "feat: add compliance_draft.py write_listing_texts"
```

---

## Task 8: `update_gallery_alt_text()` — write alt text onto `product_images`

**Files:**
- Modify: `pipeline/compliance_draft.py`
- Modify: `tests/test_compliance_draft.py`

**Interfaces:**
- Consumes: `get_primary_gallery(conn, candidate_id) -> list[dict]` (Task 5).
- Produces: `update_gallery_alt_text(conn, candidate_id: int, alt_texts: list[str]) -> None` — raises `ValueError` on a count mismatch. Consumed by Task 9's `build_compliance_draft`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_compliance_draft.py`:

```python
def test_update_gallery_alt_text_updates_rows_in_order(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_ready_candidate(conn, image_types=("flat_mockup", "lifestyle"))

    compliance_draft.update_gallery_alt_text(
        conn, candidate_id, ["Flat mockup alt text", "Lifestyle alt text"]
    )

    gallery = conn.execute(
        """
        SELECT pi.alt_text FROM product_images pi
        JOIN group_products gp ON gp.id = pi.group_product_id
        JOIN groups g ON g.id = gp.group_id
        WHERE g.candidate_id = ? ORDER BY pi.gallery_order
        """,
        (candidate_id,),
    ).fetchall()
    assert [row["alt_text"] for row in gallery] == ["Flat mockup alt text", "Lifestyle alt text"]
    conn.close()


def test_update_gallery_alt_text_raises_on_count_mismatch(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_ready_candidate(conn, image_types=("flat_mockup", "lifestyle"))

    with pytest.raises(ValueError, match="2"):
        compliance_draft.update_gallery_alt_text(conn, candidate_id, ["only one alt text"])

    gallery = conn.execute(
        """
        SELECT pi.alt_text FROM product_images pi
        JOIN group_products gp ON gp.id = pi.group_product_id
        JOIN groups g ON g.id = gp.group_id
        WHERE g.candidate_id = ?
        """,
        (candidate_id,),
    ).fetchall()
    assert all(row["alt_text"] == "" for row in gallery)
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_compliance_draft.py -v`
Expected: FAIL — `update_gallery_alt_text` doesn't exist yet (`AttributeError`).

- [ ] **Step 3: Implement**

Add to `pipeline/compliance_draft.py`:

```python
def update_gallery_alt_text(conn, candidate_id: int, alt_texts: list) -> None:
    gallery = get_primary_gallery(conn, candidate_id)
    if len(alt_texts) != len(gallery):
        raise ValueError(
            f"{len(alt_texts)} alt_texts provided but candidate {candidate_id}'s primary "
            f"gallery has {len(gallery)} images"
        )
    for image, alt_text in zip(gallery, alt_texts):
        conn.execute(
            "UPDATE product_images SET alt_text = ? WHERE id = ?",
            (alt_text, image["id"]),
        )
    conn.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_compliance_draft.py -v`
Expected: all 14 PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/compliance_draft.py tests/test_compliance_draft.py
git commit -m "feat: add compliance_draft.py update_gallery_alt_text"
```

---

## Task 9: `build_compliance_draft()` — happy path

**Files:**
- Modify: `pipeline/compliance_draft.py`
- Modify: `tests/test_compliance_draft.py`

**Interfaces:**
- Consumes: `get_primary_gallery` (Task 5), `resolve_compliance_metadata` (Task 3), `generate_draft_text` (Task 6), `validate_listing_text` (Task 4), `write_listing_texts` (Task 7), `update_gallery_alt_text` (Task 8), `config.load_static_config()` (already merged, `pipeline/config.py`).
- Produces: `build_compliance_draft(conn, candidate_id: int, *, static_config: dict = None, anthropic_api_key: str = None, now=None) -> dict` — returns `{"listing_text_id", "candidate_id"}`. Consumed by Task 11's `run_compliance_draft_cycle`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_compliance_draft.py`:

```python
def _fake_draft_response(alt_text_count=2):
    return {
        "text": _json.dumps({
            "title": "Monstera Line Art Botanical Print",
            "tags": ["botanical", "wall art"],
            "description": "A minimalist botanical print.",
            "alt_texts": [f"alt text {i}" for i in range(alt_text_count)],
        })
    }


def test_build_compliance_draft_happy_path_writes_listing_text_and_alt_text(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_ready_candidate(conn, image_types=("flat_mockup", "lifestyle"))

    with patch("pipeline.compliance_draft.anthropic_client.complete",
               return_value=_fake_draft_response(2)):
        result = compliance_draft.build_compliance_draft(
            conn, candidate_id, static_config=STATIC_CONFIG, anthropic_api_key="key1",
            now=datetime(2026, 7, 10, 10, 0, 0),
        )

    listing_row = conn.execute(
        "SELECT * FROM listing_texts WHERE id = ?", (result["listing_text_id"],)
    ).fetchone()
    assert listing_row["candidate_id"] == candidate_id
    assert listing_row["title"] == "Monstera Line Art Botanical Print"
    assert listing_row["who_made"] == "i_did"

    gallery = conn.execute(
        """
        SELECT pi.alt_text FROM product_images pi
        JOIN group_products gp ON gp.id = pi.group_product_id
        JOIN groups g ON g.id = gp.group_id
        WHERE g.candidate_id = ? ORDER BY pi.gallery_order
        """,
        (candidate_id,),
    ).fetchall()
    assert [row["alt_text"] for row in gallery] == ["alt text 0", "alt text 1"]

    candidate_row = conn.execute("SELECT status FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    assert candidate_row["status"] == "generating"
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_compliance_draft.py -v`
Expected: FAIL — `build_compliance_draft` doesn't exist yet (`AttributeError`).

- [ ] **Step 3: Implement**

Add to `pipeline/compliance_draft.py`:

```python
def build_compliance_draft(conn, candidate_id: int, *, static_config: dict = None,
                            anthropic_api_key: str = None, now=None) -> dict:
    row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    if row is None:
        raise ValueError(f"No candidate with id {candidate_id}")
    candidate = dict(row)

    static_config = static_config if static_config is not None else config.load_static_config()
    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()

    gallery = get_primary_gallery(conn, candidate_id)
    image_types = [image["image_type"] for image in gallery]
    metadata = resolve_compliance_metadata(static_config)

    try:
        draft = generate_draft_text(candidate, image_types, api_key=anthropic_api_key)
        validate_listing_text(draft["title"], draft["tags"])
        listing_text_id = write_listing_texts(conn, candidate_id, draft, metadata, now=now)
        update_gallery_alt_text(conn, candidate_id, draft["alt_texts"])
    except Exception as exc:
        conn.execute(
            "UPDATE candidates SET status = 'compliance_failed', failed_reason = ?, updated_at = ? WHERE id = ?",
            (str(exc), timestamp, candidate_id),
        )
        conn.commit()
        raise

    return {"listing_text_id": listing_text_id, "candidate_id": candidate_id}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_compliance_draft.py -v`
Expected: all 15 PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/compliance_draft.py tests/test_compliance_draft.py
git commit -m "feat: add compliance_draft.py build_compliance_draft happy path"
```

---

## Task 10: `build_compliance_draft()` — failure handling (`compliance_failed`)

**Files:**
- Modify: `tests/test_compliance_draft.py`

**Interfaces:**
- Consumes/Produces: same `build_compliance_draft` from Task 9 — its `try/except` already marks `candidates.status='compliance_failed'` on any error; this task adds the test coverage for that path across three distinct failure points (Claude call, validation, alt-text write).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_compliance_draft.py`:

```python
def test_build_compliance_draft_marks_compliance_failed_when_claude_call_raises(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_ready_candidate(conn, image_types=("flat_mockup", "lifestyle"))

    with patch("pipeline.compliance_draft.anthropic_client.complete",
               side_effect=RuntimeError("Anthropic 500")):
        with pytest.raises(RuntimeError, match="Anthropic 500"):
            compliance_draft.build_compliance_draft(
                conn, candidate_id, static_config=STATIC_CONFIG, anthropic_api_key="key1",
                now=datetime(2026, 7, 10, 10, 0, 0),
            )

    candidate_row = conn.execute(
        "SELECT status, failed_reason FROM candidates WHERE id = ?", (candidate_id,)
    ).fetchone()
    assert candidate_row["status"] == "compliance_failed"
    assert "Anthropic 500" in candidate_row["failed_reason"]

    listing_rows = conn.execute(
        "SELECT * FROM listing_texts WHERE candidate_id = ?", (candidate_id,)
    ).fetchall()
    assert listing_rows == []
    conn.close()


def test_build_compliance_draft_marks_compliance_failed_on_validation_error(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_ready_candidate(conn, image_types=("flat_mockup", "lifestyle"))
    over_limit_title = "x" * 141
    fake_response = {
        "text": _json.dumps({
            "title": over_limit_title, "tags": ["botanical"], "description": "desc",
            "alt_texts": ["alt one", "alt two"],
        })
    }

    with patch("pipeline.compliance_draft.anthropic_client.complete", return_value=fake_response):
        with pytest.raises(ValueError, match="140"):
            compliance_draft.build_compliance_draft(
                conn, candidate_id, static_config=STATIC_CONFIG, anthropic_api_key="key1",
                now=datetime(2026, 7, 10, 10, 0, 0),
            )

    candidate_row = conn.execute("SELECT status FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    assert candidate_row["status"] == "compliance_failed"
    conn.close()


def test_build_compliance_draft_marks_compliance_failed_on_alt_text_mismatch_but_keeps_listing_text(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_ready_candidate(conn, image_types=("flat_mockup", "lifestyle"))

    with patch("pipeline.compliance_draft.anthropic_client.complete",
               return_value=_fake_draft_response(2)), \
         patch("pipeline.compliance_draft.update_gallery_alt_text",
               side_effect=ValueError("alt_texts count mismatch")):
        with pytest.raises(ValueError, match="alt_texts count mismatch"):
            compliance_draft.build_compliance_draft(
                conn, candidate_id, static_config=STATIC_CONFIG, anthropic_api_key="key1",
                now=datetime(2026, 7, 10, 10, 0, 0),
            )

    candidate_row = conn.execute("SELECT status FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    assert candidate_row["status"] == "compliance_failed"

    # Known accepted limitation (see plan's Global Constraints): write_listing_texts already
    # committed before update_gallery_alt_text raised, so the row persists.
    listing_rows = conn.execute(
        "SELECT * FROM listing_texts WHERE candidate_id = ?", (candidate_id,)
    ).fetchall()
    assert len(listing_rows) == 1
    conn.close()
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `python -m pytest tests/test_compliance_draft.py -v`
Expected: all 18 PASS — Task 9's implementation already handles every one of these branches. (If any fails, the `try/except` in Task 9's code needs fixing before continuing — do not proceed with a red test.)

- [ ] **Step 3: Commit**

```bash
git add tests/test_compliance_draft.py
git commit -m "test: cover compliance_draft.py compliance_failed failure paths"
```

---

## Task 11: `run_compliance_draft_cycle()` — batch orchestrator

**Files:**
- Modify: `pipeline/compliance_draft.py`
- Modify: `tests/test_compliance_draft.py`

**Interfaces:**
- Consumes: `build_compliance_draft(conn, candidate_id, ...)` (Task 9/10).
- Produces: `run_compliance_draft_cycle(conn, *, static_config: dict = None, anthropic_api_key: str = None, now=None) -> list[int]` — the module's public entry point, to be called by the not-yet-built twice-daily batch orchestrator after `primary_mockup.run_primary_mockup_cycle`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_compliance_draft.py`:

```python
def test_run_compliance_draft_cycle_processes_ready_candidates_and_skips_others(tmp_path):
    conn = _fresh_conn(tmp_path)
    ready_id = _insert_ready_candidate(conn, niche="monstera line art")
    not_yet_mocked_id = _insert_candidate(conn, niche="pending one", status="generating")

    with patch("pipeline.compliance_draft.anthropic_client.complete",
               return_value=_fake_draft_response(2)):
        processed_ids = compliance_draft.run_compliance_draft_cycle(
            conn, static_config=STATIC_CONFIG, anthropic_api_key="key1",
            now=datetime(2026, 7, 10, 10, 0, 0),
        )

    assert processed_ids == [ready_id]
    assert not_yet_mocked_id not in processed_ids
    conn.close()


def test_run_compliance_draft_cycle_skips_already_drafted_candidates(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_ready_candidate(conn, niche="monstera line art")

    with patch("pipeline.compliance_draft.anthropic_client.complete",
               return_value=_fake_draft_response(2)):
        first_run = compliance_draft.run_compliance_draft_cycle(
            conn, static_config=STATIC_CONFIG, anthropic_api_key="key1",
            now=datetime(2026, 7, 10, 10, 0, 0),
        )
        second_run = compliance_draft.run_compliance_draft_cycle(
            conn, static_config=STATIC_CONFIG, anthropic_api_key="key1",
            now=datetime(2026, 7, 10, 11, 0, 0),
        )

    assert first_run == [candidate_id]
    assert second_run == []
    conn.close()


def test_run_compliance_draft_cycle_skips_already_failed_candidates_on_next_run(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_ready_candidate(conn, niche="monstera line art")

    with patch("pipeline.compliance_draft.anthropic_client.complete",
               side_effect=RuntimeError("Anthropic 500")):
        first_run = compliance_draft.run_compliance_draft_cycle(
            conn, static_config=STATIC_CONFIG, anthropic_api_key="key1",
            now=datetime(2026, 7, 10, 10, 0, 0),
        )

    with patch("pipeline.compliance_draft.anthropic_client.complete",
               return_value=_fake_draft_response(2)):
        second_run = compliance_draft.run_compliance_draft_cycle(
            conn, static_config=STATIC_CONFIG, anthropic_api_key="key1",
            now=datetime(2026, 7, 10, 11, 0, 0),
        )

    assert first_run == []
    assert second_run == []  # candidate stayed 'compliance_failed', not auto-retried
    candidate_row = conn.execute("SELECT status FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    assert candidate_row["status"] == "compliance_failed"
    conn.close()


def test_run_compliance_draft_cycle_isolates_per_candidate_failures(tmp_path):
    conn = _fresh_conn(tmp_path)
    failing_id = _insert_ready_candidate(conn, niche="saturated term")
    succeeding_id = _insert_ready_candidate(conn, niche="moon phase print")

    def fake_complete(prompt, *, api_key=None, max_tokens=1024):
        if "saturated term" in prompt:
            raise RuntimeError("Anthropic throttled")
        return _fake_draft_response(2)

    with patch("pipeline.compliance_draft.anthropic_client.complete", side_effect=fake_complete):
        processed_ids = compliance_draft.run_compliance_draft_cycle(
            conn, static_config=STATIC_CONFIG, anthropic_api_key="key1",
            now=datetime(2026, 7, 10, 10, 0, 0),
        )

    assert processed_ids == [succeeding_id]

    failing_row = conn.execute("SELECT status FROM candidates WHERE id = ?", (failing_id,)).fetchone()
    assert failing_row["status"] == "compliance_failed"
    conn.close()


def test_run_compliance_draft_cycle_returns_empty_list_when_nothing_ready(tmp_path):
    conn = _fresh_conn(tmp_path)
    _insert_candidate(conn, niche="pending one", status="pending")

    processed_ids = compliance_draft.run_compliance_draft_cycle(conn, static_config=STATIC_CONFIG)

    assert processed_ids == []
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_compliance_draft.py -v`
Expected: FAIL — `run_compliance_draft_cycle` doesn't exist yet (`AttributeError`).

- [ ] **Step 3: Implement**

Add to `pipeline/compliance_draft.py`:

```python
def run_compliance_draft_cycle(conn, *, static_config: dict = None,
                                anthropic_api_key: str = None, now=None) -> list:
    candidate_ids = [
        row["id"] for row in conn.execute(
            """
            SELECT DISTINCT c.id FROM candidates c
            JOIN groups g ON g.candidate_id = c.id AND g.group_type = 'primary'
            JOIN group_products gp ON gp.group_id = g.id
            WHERE c.status = 'generating'
              AND gp.status = 'created'
              AND c.id NOT IN (SELECT candidate_id FROM listing_texts)
            ORDER BY c.id
            """
        ).fetchall()
    ]
    processed_ids = []
    for candidate_id in candidate_ids:
        try:
            build_compliance_draft(
                conn, candidate_id, static_config=static_config,
                anthropic_api_key=anthropic_api_key, now=now,
            )
        except Exception as exc:
            print(f"build_compliance_draft failed for candidate {candidate_id}: {exc}")
            continue
        processed_ids.append(candidate_id)
    return processed_ids
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_compliance_draft.py -v`
Expected: all 23 PASS.

- [ ] **Step 5: Run the full test suite to confirm nothing else broke**

Run: `python -m pytest -v`
Expected: all PASS (db, config, http, gelato, replicate, telegram, etsy, anthropic, research, generate, primary_mockup, compliance_draft suites).

- [ ] **Step 6: Commit**

```bash
git add pipeline/compliance_draft.py tests/test_compliance_draft.py
git commit -m "feat: add compliance_draft.py run_compliance_draft_cycle batch orchestrator"
```

---

## Self-Review Notes

- **Spec coverage:** all 9 function signatures (Tasks 3-11), the schema addition (Task 1), the new `anthropic_client.complete()` (Task 2), the disclosure text + metadata resolution (Task 3), the 13-tag/20-char/140-char validation (Task 4), the primary-gallery read (Task 5), the text-only draft+alt-text generation with fail-loud shape checks (Task 6), the `json.dumps()` serialization convention (Task 7), the alt-text write with count-mismatch protection (Task 8), the full happy-path orchestration that leaves `candidates.status` untouched (Task 9), the `compliance_failed` failure path across all three failure points including the documented accepted limitation (Task 10), and the combined-check selection predicate that excludes both already-drafted and already-failed candidates (Task 11) are all covered, matching `docs/superpowers/specs/2026-07-10-compliance-draft-stage-design.md` sections 1-10.
- **Placeholder scan:** no TBD/"add error handling"/"similar to Task N" language. Every step has concrete, runnable code.
- **Type consistency:** `build_compliance_draft`'s signature (Task 9) is called identically by `run_compliance_draft_cycle` (Task 11) — same keyword names (`static_config`, `anthropic_api_key`, `now`). `generate_draft_text`'s return dict keys (`title`, `tags`, `description`, `alt_texts`, Task 6) match exactly what `build_compliance_draft` reads off `draft` (Task 9) and what `write_listing_texts`/`update_gallery_alt_text` consume (Tasks 7-8). `resolve_compliance_metadata`'s return dict keys (`who_made`, `production_partner_ids`, `taxonomy_id`, `shipping_profile_id`, Task 3) match exactly what `write_listing_texts` reads off `metadata` (Task 7).
