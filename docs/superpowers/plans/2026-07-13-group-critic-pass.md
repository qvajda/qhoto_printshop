# Group Critic Pass (stage 9/12) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `pipeline/group_critic_pass.py` (stage 9/12) — runs the existing critic-pass
rubric against a 5x7 or 10x24 group's gallery, retries up to 3 attempts by recreating the
Gelato product between attempts, and abandons only that group (DELETE Gelato product,
`groups.status='failed_abandoned'`) on the 3rd failure. Also fixes stage 8's known
terminal-guard gap in `group_mockup.create_group_mockup` so an abandoned group can't be
resurrected by a later mockup cycle.

**Architecture:** New module `pipeline/group_critic_pass.py` reuses
`critic_pass.evaluate_critic_pass`, `critic_pass.record_critic_attempt`, and
`critic_pass.discard_superseded_attempt` as-is (all already generic on `group_id`/
`group_product_id`, not primary-specific). It adds `get_group_critic_state` (a
`group_type`-parameterized twin of `critic_pass.get_primary_group_state`), `abandon_group`
(a narrower, group-scoped twin of `critic_pass.abandon_candidate`), and the `run_group_critic_pass`/
`run_group_critic_pass_cycle` orchestration functions. `group_mockup.create_group_mockup`
gets one added guard clause.

**Tech Stack:** Python, sqlite3 (via `pipeline/db.py`), pytest + `unittest.mock.patch`
(project's existing conventions — see `tests/test_critic_pass.py`, `tests/test_group_mockup.py`).

## Global Constraints

- Critic-pass retry cap is exactly 3 attempts per group, then abandon that group only:
  log locally as `failed_abandoned`, DELETE that group's Gelato product via
  `DELETE /v1/stores/{storeId}/products/{productId}` (CLAUDE.md).
- Group-level abandonment does NOT touch `candidates.status`, does NOT trigger Go/Hold/Kill,
  and does NOT touch the candidate's other groups (CLAUDE.md, SPEC section 3 step 7).
- A design is only ever image-generated once — group retry recreates the Gelato mockup from
  the same already-approved `base_image_url`, never a new Replicate/FLUX call (CLAUDE.md).
- One module per pipeline stage (CLAUDE.md) — this stage's logic lives in
  `pipeline/group_critic_pass.py`, not folded into `group_mockup.py` or `critic_pass.py`.
- Runtime is a discrete scheduled batch function (`run_group_critic_pass_cycle`), not called
  inline from `group_mockup.py` (CLAUDE.md, matches stage 8's own cycle-function pattern).

---

### Task 1: Terminal-status guard in `group_mockup.create_group_mockup`

Fixes the resurrection bug flagged in stage 8's review: once this plan introduces
`groups.status='failed_abandoned'` as a real terminal state (Task 3), a later
`run_group_mockup_cycle` run must not recreate the Gelato product for that group. This task
lands the guard first, independently of the rest of the stage, since it's a self-contained
regression fix with its own test.

**Files:**
- Modify: `pipeline/group_mockup.py:32-52` (inside `create_group_mockup`, right after
  `group_id = get_or_create_group(...)`)
- Test: `tests/test_group_mockup.py`

**Interfaces:**
- Consumes: nothing new — reads `groups.status` for the `group_id` already computed by the
  existing `get_or_create_group(conn, candidate_id, group_type, now=now)` call.
- Produces: `create_group_mockup` returns `None` early (no Gelato calls, no row writes) when
  the group's status is `'failed_abandoned'` or `'rejected'`. This is the same early-return
  contract the function already uses for the "already created" idempotency guard a few lines
  below, so callers (`run_group_mockup_cycle`) don't need to change.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_group_mockup.py` (after `test_create_group_mockup_skips_when_already_created`):

```python
def test_create_group_mockup_returns_none_for_failed_abandoned_group(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_published_primary_group(conn, candidate_id)
    group_mockup.get_or_create_group(conn, candidate_id, "5x7", now=datetime(2026, 7, 12, 18, 0, 0))
    conn.execute(
        "UPDATE groups SET status = 'failed_abandoned' WHERE candidate_id = ? AND group_type = '5x7'",
        (candidate_id,),
    )
    conn.commit()

    with patch("pipeline.group_mockup.gelato_client.create_product_from_template") as mock_create:
        result = group_mockup.create_group_mockup(
            conn, candidate_id, "5x7", static_config=STATIC_CONFIG, now=datetime(2026, 7, 12, 19, 0, 0),
        )

    assert result is None
    mock_create.assert_not_called()
    conn.close()


def test_create_group_mockup_returns_none_for_rejected_group(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_published_primary_group(conn, candidate_id)
    group_mockup.get_or_create_group(conn, candidate_id, "10x24", now=datetime(2026, 7, 12, 18, 0, 0))
    conn.execute(
        "UPDATE groups SET status = 'rejected' WHERE candidate_id = ? AND group_type = '10x24'",
        (candidate_id,),
    )
    conn.commit()

    with patch("pipeline.group_mockup.gelato_client.create_product_from_template") as mock_create:
        result = group_mockup.create_group_mockup(
            conn, candidate_id, "10x24", static_config=STATIC_CONFIG, now=datetime(2026, 7, 12, 19, 0, 0),
        )

    assert result is None
    mock_create.assert_not_called()
    conn.close()


def test_run_group_mockup_cycle_does_not_resurrect_abandoned_group(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_published_primary_group(conn, candidate_id)
    group_mockup.get_or_create_group(conn, candidate_id, "5x7", now=datetime(2026, 7, 12, 18, 0, 0))
    conn.execute(
        "UPDATE groups SET status = 'failed_abandoned' WHERE candidate_id = ? AND group_type = '5x7'",
        (candidate_id,),
    )
    conn.commit()

    with patch("pipeline.group_mockup.gelato_client.create_product_from_template",
               side_effect=fake_create_pending), \
         patch("pipeline.group_mockup.primary_mockup.poll_until_ready",
               side_effect=fake_poll_ready):
        processed = group_mockup.run_group_mockup_cycle(
            conn, static_config=STATIC_CONFIG, poll_interval=0, poll_timeout=10,
            now=datetime(2026, 7, 12, 20, 0, 0),
        )

    assert [(p["candidate_id"], p["group_type"]) for p in processed] == [(candidate_id, "10x24")]
    group_row = conn.execute(
        "SELECT status FROM groups WHERE candidate_id = ? AND group_type = '5x7'", (candidate_id,)
    ).fetchone()
    assert group_row["status"] == "failed_abandoned"
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_group_mockup.py -k "failed_abandoned or rejected_group or resurrect" -v`
Expected: FAIL — `test_create_group_mockup_returns_none_for_failed_abandoned_group` and
`test_create_group_mockup_returns_none_for_rejected_group` fail because `mock_create` gets
called (no guard yet, `result` is not `None`); `test_run_group_mockup_cycle_does_not_resurrect_abandoned_group`
fails because the processed list still includes `(candidate_id, "5x7")`.

- [ ] **Step 3: Add the guard clause**

In `pipeline/group_mockup.py`, inside `create_group_mockup`, right after the
`group_id = get_or_create_group(conn, candidate_id, group_type, now=now)` line:

```python
    group_id = get_or_create_group(conn, candidate_id, group_type, now=now)

    group_status_row = conn.execute(
        "SELECT status FROM groups WHERE id = ?", (group_id,)
    ).fetchone()
    if group_status_row["status"] in ("failed_abandoned", "rejected"):
        return None

    size = _group_size(static_config, group_type)
```

(This replaces the existing `size = _group_size(static_config, group_type)` line — insert
the guard between it and the `group_id = ...` line above it.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_group_mockup.py -v`
Expected: all tests PASS (full file, to confirm no regression on existing group_mockup tests).

- [ ] **Step 5: Commit**

```bash
git add pipeline/group_mockup.py tests/test_group_mockup.py
git commit -m "fix: guard create_group_mockup against resurrecting abandoned/rejected groups"
```

---

### Task 2: `get_group_critic_state` and `abandon_group`

The two new building blocks `run_group_critic_pass` (Task 3) will call. Both are narrow
twins of existing `critic_pass.py` functions, generalized/scoped as described in the design
doc.

**Files:**
- Create: `pipeline/group_critic_pass.py`
- Test: `tests/test_group_critic_pass.py`

**Interfaces:**
- Consumes: `pipeline.db` (`db.get_connection`, `db.init_db`, matching every other test
  file's `_fresh_conn` helper); schema tables `groups`, `group_products`, `product_images`,
  `listing_texts`, `candidates`.
- Produces:
  - `get_group_critic_state(conn, candidate_id: int, group_type: str) -> dict` returning
    `{"group_id": int, "group_product_id": int, "image_urls": list[str], "listing_text": dict}`.
  - `abandon_group(conn, group_id: int, reason: str, *, now=None) -> None`, used by Task 3.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_group_critic_pass.py`:

```python
import json as _json
from datetime import datetime
from unittest.mock import patch

import pytest

import pipeline.db as db
import pipeline.group_critic_pass as group_critic_pass


def _fresh_conn(tmp_path):
    conn = db.get_connection(tmp_path / "test.sqlite3")
    db.init_db(conn)
    return conn


def _insert_candidate(conn, niche="monstera line art", *, status="primary_review",
                       base_image_url="https://replicate.delivery/out.png"):
    timestamp = "2026-07-13T09:00:00"
    cursor = conn.execute(
        """
        INSERT INTO candidates (created_at, niche, go_hold_kill, status, base_image_url, updated_at)
        VALUES (?, ?, 'go', ?, ?, ?)
        """,
        (timestamp, niche, status, base_image_url, timestamp),
    )
    conn.commit()
    return cursor.lastrowid


def _insert_group_gallery(conn, candidate_id, group_type, size, *,
                           image_urls=("https://gelato/flat.jpg", "https://gelato/life.jpg"),
                           gelato_product_id="gelato_prod_1", group_status="pending_review",
                           group_product_status="created"):
    timestamp = "2026-07-13T09:05:00"
    group_cursor = conn.execute(
        "INSERT INTO groups (candidate_id, group_type, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (candidate_id, group_type, group_status, timestamp, timestamp),
    )
    group_id = group_cursor.lastrowid
    gp_cursor = conn.execute(
        "INSERT INTO group_products "
        "(group_id, size, orientation, gelato_template_id, gelato_product_id, price_eur, "
        "status, created_at, updated_at) "
        "VALUES (?, ?, 'portrait', 'tpl_1', ?, 19, ?, ?, ?)",
        (group_id, size, gelato_product_id, group_product_status, timestamp, timestamp),
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
    timestamp = "2026-07-13T09:10:00"
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


def test_get_group_critic_state_returns_gallery_and_listing_text(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_group_gallery(conn, candidate_id, "5x7", "5x7")
    _insert_listing_text(conn, candidate_id)

    state = group_critic_pass.get_group_critic_state(conn, candidate_id, "5x7")

    assert state["image_urls"] == ["https://gelato/flat.jpg", "https://gelato/life.jpg"]
    assert state["listing_text"]["title"] == "monstera line art print"
    conn.close()


def test_get_group_critic_state_raises_when_no_group(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)

    with pytest.raises(ValueError, match="5x7 group"):
        group_critic_pass.get_group_critic_state(conn, candidate_id, "5x7")
    conn.close()


def test_get_group_critic_state_raises_when_no_live_group_product(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_group_gallery(conn, candidate_id, "10x24", "10x24", group_product_status="mockup_failed")

    with pytest.raises(ValueError, match="group_products"):
        group_critic_pass.get_group_critic_state(conn, candidate_id, "10x24")
    conn.close()


def test_get_group_critic_state_raises_when_no_listing_text(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_group_gallery(conn, candidate_id, "5x7", "5x7")

    with pytest.raises(ValueError, match="listing_texts"):
        group_critic_pass.get_group_critic_state(conn, candidate_id, "5x7")
    conn.close()


def test_abandon_group_marks_only_that_group_failed(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id, _ = _insert_group_gallery(conn, candidate_id, "5x7", "5x7")
    other_group_id, _ = _insert_group_gallery(conn, candidate_id, "10x24", "10x24",
                                               gelato_product_id="gelato_prod_2")

    group_critic_pass.abandon_group(
        conn, group_id, "exhausted 3 attempts: off-center crop",
        now=datetime(2026, 7, 13, 12, 0, 0),
    )

    group_row = conn.execute(
        "SELECT status, failed_reason FROM groups WHERE id = ?", (group_id,)
    ).fetchone()
    assert group_row["status"] == "failed_abandoned"
    assert group_row["failed_reason"] == "exhausted 3 attempts: off-center crop"

    other_group_row = conn.execute(
        "SELECT status FROM groups WHERE id = ?", (other_group_id,)
    ).fetchone()
    assert other_group_row["status"] == "pending_review"

    candidate_row = conn.execute(
        "SELECT status FROM candidates WHERE id = ?", (candidate_id,)
    ).fetchone()
    assert candidate_row["status"] == "primary_review"
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_group_critic_pass.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.group_critic_pass'`.

- [ ] **Step 3: Write the implementation**

Create `pipeline/group_critic_pass.py`:

```python
from datetime import datetime, timezone

import pipeline.critic_pass as critic_pass
import pipeline.config as config
import pipeline.group_mockup as group_mockup


def get_group_critic_state(conn, candidate_id: int, group_type: str) -> dict:
    group_row = conn.execute(
        "SELECT id FROM groups WHERE candidate_id = ? AND group_type = ?",
        (candidate_id, group_type),
    ).fetchone()
    if group_row is None:
        raise ValueError(f"No {group_type} group for candidate {candidate_id}")
    group_id = group_row["id"]

    group_product_row = conn.execute(
        "SELECT id FROM group_products WHERE group_id = ? AND status = 'created'",
        (group_id,),
    ).fetchone()
    if group_product_row is None:
        raise ValueError(
            f"No live group_products row for candidate {candidate_id}'s {group_type} group"
        )
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


def abandon_group(conn, group_id: int, reason: str, *, now=None) -> None:
    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()
    conn.execute(
        "UPDATE groups SET status = 'failed_abandoned', failed_reason = ?, updated_at = ? WHERE id = ?",
        (reason, timestamp, group_id),
    )
    conn.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_group_critic_pass.py -v`
Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/group_critic_pass.py tests/test_group_critic_pass.py
git commit -m "feat: add get_group_critic_state and abandon_group to group_critic_pass"
```

---

### Task 3: `run_group_critic_pass` — retry loop and abandon-on-3rd-failure

**Files:**
- Modify: `pipeline/group_critic_pass.py` (add `run_group_critic_pass`)
- Test: `tests/test_group_critic_pass.py`

**Interfaces:**
- Consumes: `get_group_critic_state`, `abandon_group` (Task 2, this module);
  `critic_pass.evaluate_critic_pass(image_urls, listing_text, *, api_key=None) -> dict`,
  `critic_pass.record_critic_attempt(conn, group_id, attempt_number, result, correction_notes=None, *, now=None) -> int`,
  `critic_pass.discard_superseded_attempt(conn, group_product_id, *, store_id=None, api_key=None) -> None`
  (all pre-existing, unmodified); `group_mockup.create_group_mockup(conn, candidate_id, group_type, *, static_config=None, store_id=None, api_key=None, poll_interval=3.0, poll_timeout=90.0, now=None) -> dict | None`
  (pre-existing, unmodified — used here purely for its recreate-the-product side effect, its
  return value isn't used since the next loop iteration re-fetches state via
  `get_group_critic_state`); `config.load_static_config()`.
- Produces: `run_group_critic_pass(conn, candidate_id: int, group_type: str, *, static_config=None, anthropic_api_key=None, store_id=None, gelato_api_key=None, now=None) -> dict`
  returning `{"group_id": int, "passed": bool, "attempts": int}` — the shape Task 4's cycle
  function and (later) stage 10's digest logic will rely on.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_group_critic_pass.py`:

```python
STATIC_CONFIG = {
    "gelato_templates": {
        "5x7_portrait": {
            "template_id": "tpl_5x7",
            "template_variant_id": "variant_5x7",
            "image_placeholder_name": "slot_5x7.jpg",
        },
    },
    "prices_eur": {"5x7": 19},
    "aspect_ratio_groups": {"5x7": ["5x7"], "10x24": ["10x24"]},
}


def test_run_group_critic_pass_passes_on_first_attempt(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_group_gallery(conn, candidate_id, "5x7", "5x7")
    _insert_listing_text(conn, candidate_id)

    fake_response = {"text": _json.dumps({"passed": True, "reason": "meets rubric"})}
    with patch("pipeline.critic_pass.anthropic_client.complete_with_images", return_value=fake_response):
        result = group_critic_pass.run_group_critic_pass(
            conn, candidate_id, "5x7", static_config=STATIC_CONFIG, anthropic_api_key="key1",
            store_id="store1", gelato_api_key="key2", now=datetime(2026, 7, 13, 12, 0, 0),
        )

    assert result["passed"] is True
    assert result["attempts"] == 1

    group_row = conn.execute(
        "SELECT status FROM groups WHERE candidate_id = ? AND group_type = '5x7'", (candidate_id,)
    ).fetchone()
    assert group_row["status"] == "pending_review"

    attempts = conn.execute(
        "SELECT * FROM critic_pass_attempts WHERE group_id = ?", (result["group_id"],)
    ).fetchall()
    assert len(attempts) == 1
    assert attempts[0]["passed"] == 1
    conn.close()


def test_run_group_critic_pass_retries_once_then_passes(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_group_gallery(conn, candidate_id, "5x7", "5x7", gelato_product_id="gelato_prod_v1")
    _insert_listing_text(conn, candidate_id)

    critic_responses = iter([
        {"text": _json.dumps({"passed": False, "reason": "crop cuts off the composition"})},
        {"text": _json.dumps({"passed": True, "reason": "meets rubric"})},
    ])

    def fake_create_product_from_template(*args, **kwargs):
        return {"id": "gelato_prod_v2", "isReadyToPublish": False, "productImages": []}

    ready_product = {"isReadyToPublish": True,
                      "productImages": [{"fileUrl": "https://gelato/flat_v2.jpg", "isPrimary": True}]}

    with patch("pipeline.critic_pass.anthropic_client.complete_with_images",
               side_effect=lambda *a, **k: next(critic_responses)), \
         patch("pipeline.critic_pass.gelato_client.delete_product") as mock_delete, \
         patch("pipeline.group_mockup.gelato_client.create_product_from_template",
               side_effect=fake_create_product_from_template), \
         patch("pipeline.group_mockup.primary_mockup.poll_until_ready", return_value=ready_product):
        result = group_critic_pass.run_group_critic_pass(
            conn, candidate_id, "5x7", static_config=STATIC_CONFIG, anthropic_api_key="key1",
            store_id="store1", gelato_api_key="key2", now=datetime(2026, 7, 13, 12, 0, 0),
        )

    assert result["passed"] is True
    assert result["attempts"] == 2
    mock_delete.assert_called_once_with("gelato_prod_v1", store_id="store1", api_key="key2")

    group_row = conn.execute(
        "SELECT status FROM groups WHERE candidate_id = ? AND group_type = '5x7'", (candidate_id,)
    ).fetchone()
    assert group_row["status"] == "pending_review"

    gp_rows = conn.execute(
        "SELECT * FROM group_products WHERE group_id = ?", (result["group_id"],)
    ).fetchall()
    assert len(gp_rows) == 1
    assert gp_rows[0]["gelato_product_id"] == "gelato_prod_v2"
    assert gp_rows[0]["status"] == "created"

    attempts = conn.execute(
        "SELECT * FROM critic_pass_attempts WHERE group_id = ? ORDER BY attempt_number",
        (result["group_id"],),
    ).fetchall()
    assert len(attempts) == 2
    assert attempts[0]["passed"] == 0
    assert attempts[0]["failure_reason"] == "crop cuts off the composition"
    assert attempts[1]["passed"] == 1
    conn.close()


def test_run_group_critic_pass_abandons_only_this_group_after_three_failures(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_group_gallery(conn, candidate_id, "5x7", "5x7", gelato_product_id="gelato_prod_v1")
    _insert_group_gallery(conn, candidate_id, "10x24", "10x24", gelato_product_id="gelato_prod_other")
    _insert_listing_text(conn, candidate_id)

    critic_responses = iter([
        {"text": _json.dumps({"passed": False, "reason": "reason one"})},
        {"text": _json.dumps({"passed": False, "reason": "reason two"})},
        {"text": _json.dumps({"passed": False, "reason": "reason three"})},
    ])

    def fake_create_product_from_template(*args, **kwargs):
        return {"id": "gelato_prod_retry", "isReadyToPublish": False, "productImages": []}

    ready_product = {"isReadyToPublish": True,
                      "productImages": [{"fileUrl": "https://gelato/flat_retry.jpg", "isPrimary": True}]}

    with patch("pipeline.critic_pass.anthropic_client.complete_with_images",
               side_effect=lambda *a, **k: next(critic_responses)), \
         patch("pipeline.critic_pass.gelato_client.delete_product") as mock_delete, \
         patch("pipeline.group_mockup.gelato_client.create_product_from_template",
               side_effect=fake_create_product_from_template), \
         patch("pipeline.group_mockup.primary_mockup.poll_until_ready", return_value=ready_product):
        result = group_critic_pass.run_group_critic_pass(
            conn, candidate_id, "5x7", static_config=STATIC_CONFIG, anthropic_api_key="key1",
            store_id="store1", gelato_api_key="key2", now=datetime(2026, 7, 13, 12, 0, 0),
        )

    assert result["passed"] is False
    assert result["attempts"] == 3
    assert mock_delete.call_count == 3

    group_row = conn.execute(
        "SELECT status, failed_reason FROM groups WHERE candidate_id = ? AND group_type = '5x7'",
        (candidate_id,),
    ).fetchone()
    assert group_row["status"] == "failed_abandoned"
    assert group_row["failed_reason"] == "reason three"

    # Untouched: candidate itself, and the sibling 10x24 group.
    candidate_row = conn.execute("SELECT status FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    assert candidate_row["status"] == "primary_review"

    other_group_row = conn.execute(
        "SELECT status FROM groups WHERE candidate_id = ? AND group_type = '10x24'", (candidate_id,)
    ).fetchone()
    assert other_group_row["status"] == "pending_review"
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_group_critic_pass.py -k run_group_critic_pass -v`
Expected: FAIL with `AttributeError: module 'pipeline.group_critic_pass' has no attribute 'run_group_critic_pass'`.

- [ ] **Step 3: Write the implementation**

Append to `pipeline/group_critic_pass.py`:

```python
def run_group_critic_pass(conn, candidate_id: int, group_type: str, *, static_config: dict = None,
                           anthropic_api_key: str = None, store_id: str = None,
                           gelato_api_key: str = None, now=None) -> dict:
    static_config = static_config if static_config is not None else config.load_static_config()

    group_row = conn.execute(
        "SELECT id FROM groups WHERE candidate_id = ? AND group_type = ?",
        (candidate_id, group_type),
    ).fetchone()
    if group_row is None:
        raise ValueError(f"No {group_type} group for candidate {candidate_id}")
    group_id = group_row["id"]

    max_attempt_row = conn.execute(
        "SELECT MAX(attempt_number) AS max_attempt FROM critic_pass_attempts WHERE group_id = ?",
        (group_id,),
    ).fetchone()
    attempt_number = (max_attempt_row["max_attempt"] or 0) + 1

    while True:
        state = get_group_critic_state(conn, candidate_id, group_type)
        result = critic_pass.evaluate_critic_pass(
            state["image_urls"], state["listing_text"], api_key=anthropic_api_key
        )
        critic_pass.record_critic_attempt(conn, group_id, attempt_number, result, now=now)

        if result["passed"]:
            return {"group_id": group_id, "passed": True, "attempts": attempt_number}

        critic_pass.discard_superseded_attempt(
            conn, state["group_product_id"], store_id=store_id, api_key=gelato_api_key
        )

        if attempt_number >= 3:
            abandon_group(conn, group_id, result["reason"], now=now)
            return {"group_id": group_id, "passed": False, "attempts": attempt_number}

        group_mockup.create_group_mockup(
            conn, candidate_id, group_type, static_config=static_config,
            store_id=store_id, api_key=gelato_api_key, now=now,
        )
        attempt_number += 1
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_group_critic_pass.py -v`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/group_critic_pass.py tests/test_group_critic_pass.py
git commit -m "feat: add run_group_critic_pass retry-then-abandon loop"
```

---

### Task 4: `run_group_critic_pass_cycle` — batch entrypoint

**Files:**
- Modify: `pipeline/group_critic_pass.py` (add `run_group_critic_pass_cycle`)
- Test: `tests/test_group_critic_pass.py`

**Interfaces:**
- Consumes: `run_group_critic_pass` (Task 3, this module).
- Produces: `run_group_critic_pass_cycle(conn, *, static_config=None, anthropic_api_key=None, store_id=None, gelato_api_key=None, now=None) -> list[dict]`,
  returning `[{"candidate_id": int, "group_type": str, "passed": bool}, ...]` for every
  `(candidate_id, group_type)` pair it attempted (whether that attempt ultimately passed or
  abandoned the group) — mirrors `critic_pass.run_critic_pass_cycle`'s "processed regardless
  of pass/fail, skipped only on exception" convention. This is the function the twice-daily
  batch cron calls for stage 9.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_group_critic_pass.py`:

```python
def test_run_group_critic_pass_cycle_processes_ready_groups_and_skips_uncreated(tmp_path):
    conn = _fresh_conn(tmp_path)
    ready_id = _insert_candidate(conn, niche="monstera line art")
    _insert_group_gallery(conn, ready_id, "5x7", "5x7")
    _insert_listing_text(conn, ready_id, niche="monstera line art")

    not_ready_id = _insert_candidate(conn, niche="moon phase print")
    _insert_group_gallery(conn, not_ready_id, "10x24", "10x24", group_product_status="mockup_failed")
    _insert_listing_text(conn, not_ready_id, niche="moon phase print")

    fake_response = {"text": _json.dumps({"passed": True, "reason": "meets rubric"})}
    with patch("pipeline.critic_pass.anthropic_client.complete_with_images", return_value=fake_response):
        processed = group_critic_pass.run_group_critic_pass_cycle(
            conn, anthropic_api_key="key1", store_id="store1", gelato_api_key="key2",
            now=datetime(2026, 7, 13, 20, 0, 0),
        )

    assert processed == [{"candidate_id": ready_id, "group_type": "5x7", "passed": True}]
    conn.close()


def test_run_group_critic_pass_cycle_skips_groups_already_passed(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_group_gallery(conn, candidate_id, "5x7", "5x7")
    _insert_listing_text(conn, candidate_id)

    fake_response = {"text": _json.dumps({"passed": True, "reason": "meets rubric"})}
    with patch("pipeline.critic_pass.anthropic_client.complete_with_images", return_value=fake_response):
        first_run = group_critic_pass.run_group_critic_pass_cycle(
            conn, anthropic_api_key="key1", store_id="store1", gelato_api_key="key2",
            now=datetime(2026, 7, 13, 20, 0, 0),
        )
        second_run = group_critic_pass.run_group_critic_pass_cycle(
            conn, anthropic_api_key="key1", store_id="store1", gelato_api_key="key2",
            now=datetime(2026, 7, 13, 21, 0, 0),
        )

    assert first_run == [{"candidate_id": candidate_id, "group_type": "5x7", "passed": True}]
    assert second_run == []
    conn.close()


def test_run_group_critic_pass_cycle_excludes_abandoned_group_from_rerun(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_group_gallery(conn, candidate_id, "5x7", "5x7", gelato_product_id="gelato_prod_v1")
    _insert_listing_text(conn, candidate_id)

    fail_response = {"text": _json.dumps({"passed": False, "reason": "reason"})}

    def fake_create_product_from_template(*args, **kwargs):
        return {"id": "gelato_prod_retry", "isReadyToPublish": False, "productImages": []}

    ready_product = {"isReadyToPublish": True,
                      "productImages": [{"fileUrl": "https://gelato/flat_retry.jpg", "isPrimary": True}]}

    with patch("pipeline.critic_pass.anthropic_client.complete_with_images", return_value=fail_response), \
         patch("pipeline.critic_pass.gelato_client.delete_product"), \
         patch("pipeline.group_mockup.gelato_client.create_product_from_template",
               side_effect=fake_create_product_from_template), \
         patch("pipeline.group_mockup.primary_mockup.poll_until_ready", return_value=ready_product):
        first_run = group_critic_pass.run_group_critic_pass_cycle(
            conn, anthropic_api_key="key1", store_id="store1", gelato_api_key="key2",
            now=datetime(2026, 7, 13, 20, 0, 0),
        )
        second_run = group_critic_pass.run_group_critic_pass_cycle(
            conn, anthropic_api_key="key1", store_id="store1", gelato_api_key="key2",
            now=datetime(2026, 7, 13, 22, 0, 0),
        )

    assert first_run == [{"candidate_id": candidate_id, "group_type": "5x7", "passed": False}]
    # After abandonment, groups.status is 'failed_abandoned', not 'pending_review' — excluded.
    assert second_run == []
    conn.close()


def test_run_group_critic_pass_cycle_isolates_per_group_operational_failures(tmp_path):
    conn = _fresh_conn(tmp_path)
    failing_id = _insert_candidate(conn, niche="saturated term")
    _insert_group_gallery(conn, failing_id, "5x7", "5x7")
    _insert_listing_text(conn, failing_id, niche="saturated term")

    succeeding_id = _insert_candidate(conn, niche="moon phase print")
    _insert_group_gallery(conn, succeeding_id, "10x24", "10x24")
    _insert_listing_text(conn, succeeding_id, niche="moon phase print")

    def fake_complete_with_images(prompt, image_urls, *, api_key=None, max_tokens=1024):
        if "saturated term" in prompt:
            raise RuntimeError("Anthropic throttled")
        return {"text": _json.dumps({"passed": True, "reason": "meets rubric"})}

    with patch("pipeline.critic_pass.anthropic_client.complete_with_images",
               side_effect=fake_complete_with_images):
        processed = group_critic_pass.run_group_critic_pass_cycle(
            conn, anthropic_api_key="key1", store_id="store1", gelato_api_key="key2",
            now=datetime(2026, 7, 13, 20, 0, 0),
        )

    assert processed == [{"candidate_id": succeeding_id, "group_type": "10x24", "passed": True}]

    failing_group_row = conn.execute(
        "SELECT status FROM groups WHERE candidate_id = ? AND group_type = '5x7'", (failing_id,)
    ).fetchone()
    assert failing_group_row["status"] == "pending_review"  # untouched — exception before any write
    conn.close()


def test_run_group_critic_pass_cycle_returns_empty_list_when_nothing_ready(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_group_gallery(conn, candidate_id, "5x7", "5x7", group_product_status="mockup_failed")

    processed = group_critic_pass.run_group_critic_pass_cycle(conn)

    assert processed == []
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_group_critic_pass.py -k cycle -v`
Expected: FAIL with `AttributeError: module 'pipeline.group_critic_pass' has no attribute 'run_group_critic_pass_cycle'`.

- [ ] **Step 3: Write the implementation**

Append to `pipeline/group_critic_pass.py`:

```python
GROUP_TYPES = ("5x7", "10x24")


def run_group_critic_pass_cycle(conn, *, static_config: dict = None, anthropic_api_key: str = None,
                                 store_id: str = None, gelato_api_key: str = None, now=None) -> list:
    static_config = static_config if static_config is not None else config.load_static_config()

    pairs = conn.execute(
        """
        SELECT DISTINCT g.candidate_id, g.group_type
        FROM groups g
        JOIN group_products gp ON gp.group_id = g.id
        WHERE g.group_type IN ('5x7', '10x24')
          AND g.status = 'pending_review'
          AND gp.status = 'created'
          AND g.id NOT IN (SELECT group_id FROM critic_pass_attempts WHERE passed = 1)
        ORDER BY g.candidate_id, g.group_type
        """
    ).fetchall()

    processed = []
    for row in pairs:
        candidate_id, group_type = row["candidate_id"], row["group_type"]
        try:
            result = run_group_critic_pass(
                conn, candidate_id, group_type, static_config=static_config,
                anthropic_api_key=anthropic_api_key, store_id=store_id,
                gelato_api_key=gelato_api_key, now=now,
            )
        except Exception as exc:
            print(f"run_group_critic_pass failed for candidate {candidate_id} "
                  f"group_type {group_type}: {exc}")
            continue
        processed.append({
            "candidate_id": candidate_id, "group_type": group_type, "passed": result["passed"],
        })
    return processed
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_group_critic_pass.py -v`
Expected: all tests PASS.

- [ ] **Step 5: Run the full test suite**

Run: `python -m pytest -v`
Expected: all tests PASS (no regressions in `critic_pass.py`, `group_mockup.py`, or any
other stage's suite).

- [ ] **Step 6: Commit**

```bash
git add pipeline/group_critic_pass.py tests/test_group_critic_pass.py
git commit -m "feat: add run_group_critic_pass_cycle batch entrypoint for stage 9/12"
```

---

## Post-plan: whole-branch review

After Task 4's commit, do a final whole-branch review (per CLAUDE.md conventions:
"Commit after each stage passes its manual M1 test") before considering stage 9 done —
same closing step stage 7 and stage 8 each went through.
