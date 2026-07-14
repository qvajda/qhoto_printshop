# publish_group.py Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `pipeline/publish_group.py` (stage 11/12) — the Approve/Edit/Reject handler for a
single 5x7 or 10x24 group's Telegram callback — and wire `publish_primary_group.py`'s existing
poll/dispatch to route non-primary-group callbacks into it.

**Architecture:** `publish_group.py` owns one function, `handle_decision`, the group-scoped
analog of `publish_primary_group.handle_decision`. It reuses `publish_primary_group.record_decision`
and `publish_primary_group.publish_group_product` directly (both already generic on
`group_id`/`group_product_id`) rather than reimplementing Gelato/Etsy publish logic.
`publish_primary_group.process_update` gains one extra `SELECT group_type` and an if/else that
calls either its own `handle_decision` (group_type == 'primary') or
`publish_group.handle_decision` (group_type in ('5x7', '10x24')). No new poll loop, no new
`telegram_offset` row, no new Telegram-callback-parsing code.

**Tech Stack:** Python 3.12, sqlite3 (stdlib), pytest, unittest.mock.patch for Gelato/Etsy/Telegram
client seams — same stack and test style as `pipeline/publish_primary_group.py` and
`pipeline/group_critic_pass.py`.

## Global Constraints

- Design generation happens exactly once per candidate — this stage never triggers a new
  Replicate/FLUX call. (CLAUDE.md hard constraints)
- Critic-pass retry cap is exactly 3 attempts per group — already enforced upstream in
  `group_critic_pass.py`; this stage only reacts to a group that already passed. (CLAUDE.md)
- A rejected/abandoned group's Gelato product must be deleted via
  `DELETE /v1/stores/{storeId}/products/{productId}` — never left dangling. (CLAUDE.md)
- Rejecting or abandoning one non-primary group must never touch `candidates` or the other
  non-primary group's rows — narrow blast radius. (CLAUDE.md, SPEC_v4.10.md section 3 step 7)
- Static config (Gelato template IDs, prices, etc.) is read from `static_config`/`config.py` —
  never discovered at runtime. (CLAUDE.md)
- Python must be invoked via its absolute path on this machine —
  `C:\Users\QVajd\AppData\Local\Programs\Python\Python312\python.exe` — bare `python`/`python3`
  hits a dead Windows Store stub.

---

## File Structure

- Create: `pipeline/publish_group.py` — `handle_decision(conn, candidate_id, group_id, action,
  decision_notes=None, ...)` for a non-primary group. No poll loop, no Telegram-parsing code.
- Create: `tests/test_publish_group.py` — TDD suite for `handle_decision`'s three actions.
- Modify: `pipeline/publish_primary_group.py`
  - `SIZE_TITLE_SUFFIXES` gains `"5x7"` and `"10x24"` entries.
  - `process_update` gains a group_type lookup + dispatch branch.
  - Top-level `import pipeline.publish_group as publish_group` added (safe despite
    `publish_group.py` importing `publish_primary_group` back — both use `import ... as`,
    not `from ... import name`, and only touch each other's attributes inside function
    bodies, never at module-load time, so the cycle resolves fine).
- Modify: `tests/test_publish_primary_group.py` — two new dispatch-routing tests for
  `process_update`.

---

### Task 1: Extend SIZE_TITLE_SUFFIXES for 5x7/10x24

**Files:**
- Modify: `pipeline/publish_primary_group.py:20-25`
- Test: `tests/test_publish_primary_group.py` (add near existing
  `test_build_size_listing_data_appends_size_suffix_for_secondary_sizes`, around line 174)

**Interfaces:**
- Consumes: nothing new.
- Produces: `SIZE_TITLE_SUFFIXES["5x7"]` and `SIZE_TITLE_SUFFIXES["10x24"]`, consumed by
  `build_size_listing_data` — Task 2 relies on these existing before `publish_group.py` can
  build a listing for either size.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_publish_primary_group.py` (near the other `build_size_listing_data` tests,
after line 194):

```python
def test_build_size_listing_data_appends_size_suffix_for_5x7_and_10x24():
    listing_text = {
        "title": "monstera line art print", "tags": _json.dumps(["botanical", "wall art"]),
        "description": "desc", "who_made": "i_did", "taxonomy_id": "1027",
        "shipping_profile_id": "", "production_partner_ids": _json.dumps([5717252]),
    }

    data_5x7 = publish_primary_group.build_size_listing_data(listing_text, "5x7", 19)
    data_10x24 = publish_primary_group.build_size_listing_data(listing_text, "10x24", 45)

    assert data_5x7["title"] == "monstera line art print - 5x7 Print"
    assert data_5x7["price"] == 19
    assert data_10x24["title"] == "monstera line art print - 10x24 Panoramic Print"
    assert data_10x24["price"] == 45
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:\Users\QVajd\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/test_publish_primary_group.py::test_build_size_listing_data_appends_size_suffix_for_5x7_and_10x24 -v`
Expected: FAIL with `KeyError: '5x7'`

- [ ] **Step 3: Write minimal implementation**

In `pipeline/publish_primary_group.py`, replace lines 20-25:

```python
SIZE_TITLE_SUFFIXES = {
    "8x12": "",
    "A3": " - A3 Print",
    "A2": " - A2 Print",
    "A1": " - A1 Print",
    "5x7": " - 5x7 Print",
    "10x24": " - 10x24 Panoramic Print",
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `C:\Users\QVajd\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/test_publish_primary_group.py::test_build_size_listing_data_appends_size_suffix_for_5x7_and_10x24 -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/publish_primary_group.py tests/test_publish_primary_group.py
git commit -m "feat: add 5x7/10x24 title suffixes for group listings"
```

---

### Task 2: publish_group.py — approve action

**Files:**
- Create: `pipeline/publish_group.py`
- Create: `tests/test_publish_group.py`

**Interfaces:**
- Consumes: `publish_primary_group.record_decision(conn, group_id, decision, decision_notes=None, *,
  now=None) -> None`; `publish_primary_group.publish_group_product(conn, group_product_id,
  candidate, static_config, *, store_id=None, gelato_api_key=None, shop_id=None,
  etsy_api_key=None, etsy_api_secret=None, etsy_access_token=None, dry_run=None, now=None) ->
  str` (both already exist in `pipeline/publish_primary_group.py`); `pipeline.config.load_static_config()`.
- Produces: `handle_decision(conn, candidate_id, group_id, action, decision_notes=None, *,
  static_config=None, store_id=None, gelato_api_key=None, shop_id=None, etsy_api_key=None,
  etsy_api_secret=None, etsy_access_token=None, dry_run=None, now=None) -> dict` — Task 6's
  dispatch code calls this exact signature.

- [ ] **Step 1: Write the failing test**

Create `tests/test_publish_group.py`:

```python
import json as _json
from datetime import datetime
from unittest.mock import patch

import pytest

import pipeline.db as db
import pipeline.publish_group as publish_group
import pipeline.publish_primary_group as publish_primary_group


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


def _insert_group(conn, candidate_id, group_type, *, status="pending_review"):
    timestamp = "2026-07-13T09:05:00"
    cursor = conn.execute(
        "INSERT INTO groups (candidate_id, group_type, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (candidate_id, group_type, status, timestamp, timestamp),
    )
    conn.commit()
    return cursor.lastrowid


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


def _insert_group_product_with_images(conn, group_id, size, *, gelato_product_id="gelato_5x7",
                                       price_eur=19,
                                       image_urls=("https://gelato/flat.jpg", "https://gelato/life.jpg")):
    timestamp = "2026-07-13T10:00:00"
    cursor = conn.execute(
        "INSERT INTO group_products "
        "(group_id, size, orientation, gelato_template_id, gelato_product_id, price_eur, "
        "status, created_at, updated_at) "
        "VALUES (?, ?, 'portrait', 'tpl_x', ?, ?, 'created', ?, ?)",
        (group_id, size, gelato_product_id, price_eur, timestamp, timestamp),
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


def _insert_ready_5x7_group(conn, candidate_id):
    group_id = _insert_group(conn, candidate_id, "5x7", status="pending_review")
    gp_id = _insert_group_product_with_images(conn, group_id, "5x7")
    _insert_listing_text(conn, candidate_id)
    return group_id, gp_id


STATIC_CONFIG = {
    "gelato_templates": {
        "5x7_portrait": {
            "template_id": "tpl_5x7", "template_variant_id": "variant_5x7",
            "image_placeholder_name": "slot_5x7.jpg",
        },
    },
    "prices_eur": {"5x7": 19},
    "aspect_ratio_groups": {"primary": ["8x12", "A3", "A2", "A1"], "5x7": ["5x7"], "10x24": ["10x24"]},
}


def test_handle_decision_approve_publishes_group_and_sets_status(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id, gp_id = _insert_ready_5x7_group(conn, candidate_id)

    with patch("pipeline.publish_group.publish_primary_group.publish_group_product",
               return_value="listing_777") as mock_publish:
        result = publish_group.handle_decision(
            conn, candidate_id, group_id, "approve", static_config=STATIC_CONFIG, dry_run=True,
            now=datetime(2026, 7, 13, 12, 0, 0),
        )

    mock_publish.assert_called_once()
    assert mock_publish.call_args.args[1] == gp_id
    assert result["action"] == "approve"
    assert result["listing_id"] == "listing_777"

    group_row = conn.execute(
        "SELECT decision, status, decided_at FROM groups WHERE id = ?", (group_id,)
    ).fetchone()
    assert group_row["decision"] == "approved"
    assert group_row["status"] == "approved_published"
    assert group_row["decided_at"] == "2026-07-13T12:00:00"

    candidate_row = conn.execute(
        "SELECT status FROM candidates WHERE id = ?", (candidate_id,)
    ).fetchone()
    assert candidate_row["status"] == "primary_review"  # untouched
    conn.close()


def test_handle_decision_approve_raises_when_no_live_group_product(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_group(conn, candidate_id, "5x7", status="pending_review")

    with pytest.raises(ValueError, match="No live group_product"):
        publish_group.handle_decision(
            conn, candidate_id, group_id, "approve", static_config=STATIC_CONFIG,
        )
    conn.close()


def test_handle_decision_approve_leaves_status_pending_review_on_publish_failure(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id, gp_id = _insert_ready_5x7_group(conn, candidate_id)

    with patch("pipeline.publish_group.publish_primary_group.publish_group_product",
               side_effect=RuntimeError("etsy down")):
        with pytest.raises(RuntimeError, match="etsy down"):
            publish_group.handle_decision(
                conn, candidate_id, group_id, "approve", static_config=STATIC_CONFIG, dry_run=True,
                now=datetime(2026, 7, 13, 12, 0, 0),
            )

    group_row = conn.execute("SELECT status FROM groups WHERE id = ?", (group_id,)).fetchone()
    assert group_row["status"] == "pending_review"
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:\Users\QVajd\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/test_publish_group.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.publish_group'`

- [ ] **Step 3: Write minimal implementation**

Create `pipeline/publish_group.py`:

```python
from datetime import datetime, timezone

import pipeline.config as config
import pipeline.critic_pass as critic_pass
import pipeline.publish_primary_group as publish_primary_group


def get_live_group_product(conn, group_id: int) -> dict:
    row = conn.execute(
        "SELECT * FROM group_products WHERE group_id = ? AND status IN ('created', 'published') "
        "ORDER BY id LIMIT 1",
        (group_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"No live group_product for group {group_id}")
    return dict(row)


def handle_decision(conn, candidate_id, group_id, action, decision_notes=None, *,
                     static_config=None, store_id=None, gelato_api_key=None, shop_id=None,
                     etsy_api_key=None, etsy_api_secret=None, etsy_access_token=None,
                     dry_run=None, now=None) -> dict:
    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()

    if action == "approve":
        publish_primary_group.record_decision(conn, group_id, "approved", decision_notes, now=now)
        static_config = static_config if static_config is not None else config.load_static_config()

        group_product = get_live_group_product(conn, group_id)
        candidate = dict(
            conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
        )

        listing_id = publish_primary_group.publish_group_product(
            conn, group_product["id"], candidate, static_config, store_id=store_id,
            gelato_api_key=gelato_api_key, shop_id=shop_id, etsy_api_key=etsy_api_key,
            etsy_api_secret=etsy_api_secret, etsy_access_token=etsy_access_token,
            dry_run=dry_run, now=now,
        )

        conn.execute(
            "UPDATE groups SET status = 'approved_published', updated_at = ? WHERE id = ?",
            (timestamp, group_id),
        )
        conn.commit()
        return {"action": "approve", "listing_id": listing_id}

    raise ValueError(f"Unknown action {action!r}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `C:\Users\QVajd\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/test_publish_group.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add pipeline/publish_group.py tests/test_publish_group.py
git commit -m "feat: add publish_group.py approve action for 5x7/10x24 groups"
```

---

### Task 3: publish_group.py — reject action

**Files:**
- Modify: `pipeline/publish_group.py`
- Test: `tests/test_publish_group.py`

**Interfaces:**
- Consumes: `critic_pass.discard_superseded_attempt(conn, group_product_id, *, store_id=None,
  api_key=None) -> None` (already exists, deletes the Gelato product + `product_images`/
  `group_products` rows for that id).
- Produces: `handle_decision(..., action="reject", ...)` returns `{"action": "reject"}`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_publish_group.py`:

```python
def test_handle_decision_reject_deletes_product_and_marks_group_rejected(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id, gp_id = _insert_ready_5x7_group(conn, candidate_id)

    with patch("pipeline.publish_group.critic_pass.gelato_client.delete_product") as mock_delete:
        result = publish_group.handle_decision(
            conn, candidate_id, group_id, "reject", "not vibing with this crop",
            now=datetime(2026, 7, 13, 12, 0, 0),
        )

    mock_delete.assert_called_once_with("gelato_5x7", store_id=None, api_key=None)
    assert result["action"] == "reject"

    group_row = conn.execute(
        "SELECT decision, decision_notes, status FROM groups WHERE id = ?", (group_id,)
    ).fetchone()
    assert group_row["decision"] == "rejected"
    assert group_row["decision_notes"] == "not vibing with this crop"
    assert group_row["status"] == "rejected"

    assert conn.execute(
        "SELECT * FROM group_products WHERE id = ?", (gp_id,)
    ).fetchone() is None

    candidate_row = conn.execute(
        "SELECT status FROM candidates WHERE id = ?", (candidate_id,)
    ).fetchone()
    assert candidate_row["status"] == "primary_review"  # untouched
    conn.close()


def test_handle_decision_reject_with_no_live_product_still_marks_rejected(tmp_path):
    # e.g. the group's product already failed publish earlier and was never recreated —
    # reject should still record the decision without requiring a live Gelato product to delete.
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_group(conn, candidate_id, "5x7", status="pending_review")

    with patch("pipeline.publish_group.critic_pass.gelato_client.delete_product") as mock_delete:
        result = publish_group.handle_decision(conn, candidate_id, group_id, "reject")

    mock_delete.assert_not_called()
    assert result["action"] == "reject"
    group_row = conn.execute("SELECT status FROM groups WHERE id = ?", (group_id,)).fetchone()
    assert group_row["status"] == "rejected"
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:\Users\QVajd\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/test_publish_group.py -k reject -v`
Expected: FAIL with `ValueError: Unknown action 'reject'`

- [ ] **Step 3: Write minimal implementation**

In `pipeline/publish_group.py`, insert before the final `raise ValueError(...)` line:

```python
    if action == "reject":
        publish_primary_group.record_decision(conn, group_id, "rejected", decision_notes, now=now)

        live_row = conn.execute(
            "SELECT id FROM group_products WHERE group_id = ? AND status IN ('created', 'published') "
            "ORDER BY id LIMIT 1",
            (group_id,),
        ).fetchone()
        if live_row is not None:
            critic_pass.discard_superseded_attempt(
                conn, live_row["id"], store_id=store_id, api_key=gelato_api_key,
            )

        conn.execute(
            "UPDATE groups SET status = 'rejected', updated_at = ? WHERE id = ?",
            (timestamp, group_id),
        )
        conn.commit()
        return {"action": "reject"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `C:\Users\QVajd\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/test_publish_group.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add pipeline/publish_group.py tests/test_publish_group.py
git commit -m "feat: add publish_group.py reject action"
```

---

### Task 4: publish_group.py — edit action

**Files:**
- Modify: `pipeline/publish_group.py`
- Test: `tests/test_publish_group.py`

**Interfaces:**
- Consumes: same `critic_pass.discard_superseded_attempt` as Task 3.
- Produces: `handle_decision(..., action="edit", ...)` returns `{"action": "edit"}`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_publish_group.py`:

```python
def test_handle_decision_edit_discards_product_and_attempts_leaves_status_alone(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id, gp_id = _insert_ready_5x7_group(conn, candidate_id)
    publish_primary_group.critic_pass.record_critic_attempt(
        conn, group_id, 1, {"passed": True, "reason": "meets rubric"},
        now=datetime(2026, 7, 13, 9, 20, 0),
    )
    conn.execute(
        "INSERT INTO group_messages (group_id, telegram_message_id, chat_id, sent_at) "
        "VALUES (?, 202, '987654321', '2026-07-13T09:15:00')",
        (group_id,),
    )
    conn.commit()

    with patch("pipeline.publish_group.critic_pass.gelato_client.delete_product") as mock_delete:
        result = publish_group.handle_decision(
            conn, candidate_id, group_id, "edit", "crop feels too tight",
            now=datetime(2026, 7, 13, 12, 0, 0),
        )

    mock_delete.assert_called_once_with("gelato_5x7", store_id=None, api_key=None)
    assert result["action"] == "edit"

    assert conn.execute("SELECT * FROM group_products WHERE id = ?", (gp_id,)).fetchone() is None
    assert conn.execute(
        "SELECT * FROM critic_pass_attempts WHERE group_id = ?", (group_id,)
    ).fetchall() == []
    assert conn.execute(
        "SELECT * FROM group_messages WHERE group_id = ?", (group_id,)
    ).fetchall() == []

    group_row = conn.execute(
        "SELECT decision, decision_notes, status FROM groups WHERE id = ?", (group_id,)
    ).fetchone()
    assert group_row["decision"] == "edited"
    assert group_row["decision_notes"] == "crop feels too tight"
    assert group_row["status"] == "pending_review"  # left as-is, confirmed with user
    conn.close()


def test_handle_decision_edit_with_no_live_product_still_clears_attempts_and_messages(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_group(conn, candidate_id, "5x7", status="pending_review")
    publish_primary_group.critic_pass.record_critic_attempt(
        conn, group_id, 1, {"passed": False, "reason": "off-center"},
        now=datetime(2026, 7, 13, 9, 20, 0),
    )

    with patch("pipeline.publish_group.critic_pass.gelato_client.delete_product") as mock_delete:
        result = publish_group.handle_decision(conn, candidate_id, group_id, "edit")

    mock_delete.assert_not_called()
    assert result["action"] == "edit"
    assert conn.execute(
        "SELECT * FROM critic_pass_attempts WHERE group_id = ?", (group_id,)
    ).fetchall() == []
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:\Users\QVajd\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/test_publish_group.py -k edit -v`
Expected: FAIL with `ValueError: Unknown action 'edit'`

- [ ] **Step 3: Write minimal implementation**

In `pipeline/publish_group.py`, insert before the final `raise ValueError(...)` line:

```python
    if action == "edit":
        publish_primary_group.record_decision(conn, group_id, "edited", decision_notes, now=now)

        live_row = conn.execute(
            "SELECT id FROM group_products WHERE group_id = ? AND status IN ('created', 'published') "
            "ORDER BY id LIMIT 1",
            (group_id,),
        ).fetchone()
        if live_row is not None:
            critic_pass.discard_superseded_attempt(
                conn, live_row["id"], store_id=store_id, api_key=gelato_api_key,
            )

        conn.execute("DELETE FROM critic_pass_attempts WHERE group_id = ?", (group_id,))
        conn.execute("DELETE FROM group_messages WHERE group_id = ?", (group_id,))
        conn.commit()
        return {"action": "edit"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `C:\Users\QVajd\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/test_publish_group.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add pipeline/publish_group.py tests/test_publish_group.py
git commit -m "feat: add publish_group.py edit action"
```

---

### Task 5: publish_group.py — unknown action

**Files:**
- Test: `tests/test_publish_group.py`
- (no implementation change — the `raise ValueError` fallthrough from Task 2 already covers this)

**Interfaces:**
- Consumes: `handle_decision` as built in Tasks 2-4.
- Produces: nothing new.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_publish_group.py`:

```python
def test_handle_decision_raises_on_unknown_action(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id, _ = _insert_ready_5x7_group(conn, candidate_id)

    with pytest.raises(ValueError, match="Unknown action"):
        publish_group.handle_decision(conn, candidate_id, group_id, "snooze")
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:\Users\QVajd\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/test_publish_group.py::test_handle_decision_raises_on_unknown_action -v`
Expected: This should actually already PASS, since Task 2's fallthrough `raise ValueError`
already handles it — run it to confirm rather than to see it fail.

- [ ] **Step 3: Confirm no implementation change needed**

If Step 2 passed, there is nothing to implement — the existing fallthrough already covers this
case. Skip to Step 5.

- [ ] **Step 4: Run full file to verify no regressions**

Run: `C:\Users\QVajd\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/test_publish_group.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add tests/test_publish_group.py
git commit -m "test: cover unknown action in publish_group.handle_decision"
```

---

### Task 6: Dispatch — route non-primary callbacks from publish_primary_group.process_update

**Files:**
- Modify: `pipeline/publish_primary_group.py:1-12` (imports), `:403-442` (`process_update`)
- Test: `tests/test_publish_primary_group.py`

**Interfaces:**
- Consumes: `publish_group.handle_decision(conn, candidate_id, group_id, action,
  decision_notes=None, *, static_config=None, store_id=None, gelato_api_key=None, shop_id=None,
  etsy_api_key=None, etsy_api_secret=None, etsy_access_token=None, dry_run=None, now=None) ->
  dict` (built in Tasks 2-5).
- Produces: `process_update` now returns the same shape for either group type:
  `{"candidate_id": ..., "group_id": ..., **result}`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_publish_primary_group.py` (near
`test_process_update_accepts_admin_callback_and_calls_handle_decision`, after line 1002):

```python
def test_process_update_routes_5x7_group_to_publish_group_handle_decision(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = conn.execute(
        "INSERT INTO groups (candidate_id, group_type, status, created_at, updated_at) "
        "VALUES (?, '5x7', 'pending_review', '2026-07-13T09:05:00', '2026-07-13T09:05:00')",
        (candidate_id,),
    ).lastrowid
    conn.commit()
    _insert_group_message(conn, group_id, "987654321", 202)
    update = _callback_update(
        user_id=987654321, data=f"approve:{group_id}", message_id=202, chat_id=987654321,
        callback_id="cbq2",
    )

    with patch("pipeline.publish_group.handle_decision",
               return_value={"action": "approve", "listing_id": "listing_999"}) as mock_group_handle, \
         patch("pipeline.publish_primary_group.handle_decision") as mock_primary_handle, \
         patch("pipeline.publish_primary_group.telegram_client.answer_callback_query"):
        result = publish_primary_group.process_update(
            conn, update, admin_chat_id="987654321", now=datetime(2026, 7, 13, 13, 0, 0),
        )

    mock_primary_handle.assert_not_called()
    mock_group_handle.assert_called_once()
    assert mock_group_handle.call_args.args[:3] == (conn, candidate_id, group_id)
    assert mock_group_handle.call_args.args[3] == "approve"
    assert result == {"candidate_id": candidate_id, "group_id": group_id,
                       "action": "approve", "listing_id": "listing_999"}
    conn.close()


def test_process_update_still_routes_primary_group_to_own_handle_decision(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_ready_primary_group(conn, candidate_id)
    _insert_group_message(conn, group_id, "987654321", 202)
    update = _callback_update(
        user_id=987654321, data=f"approve:{group_id}", message_id=202, chat_id=987654321,
        callback_id="cbq3",
    )

    with patch("pipeline.publish_group.handle_decision") as mock_group_handle, \
         patch("pipeline.publish_primary_group.handle_decision",
               return_value={"action": "approve", "results": {"8x12": "published"}}) as mock_primary_handle, \
         patch("pipeline.publish_primary_group.telegram_client.answer_callback_query"):
        result = publish_primary_group.process_update(
            conn, update, admin_chat_id="987654321", now=datetime(2026, 7, 13, 13, 0, 0),
        )

    mock_group_handle.assert_not_called()
    mock_primary_handle.assert_called_once()
    assert result == {"candidate_id": candidate_id, "group_id": group_id,
                       "action": "approve", "results": {"8x12": "published"}}
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:\Users\QVajd\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/test_publish_primary_group.py -k routes -v`
Expected: FAIL — `test_process_update_routes_5x7_group_to_publish_group_handle_decision` fails
because `process_update` currently always calls the module's own `handle_decision` (assertion on
`mock_primary_handle`/result shape mismatches, or an exception if `pipeline.publish_group` isn't
imported yet and the patch target doesn't exist).

- [ ] **Step 3: Write minimal implementation**

In `pipeline/publish_primary_group.py`, add the import after the existing `pipeline.primary_mockup`
import (line 11):

```python
import pipeline.publish_group as publish_group
```

Then replace the `group_row`/`candidate_id` lookup and `handle_decision` call inside
`process_update` (originally lines 427-442):

```python
    group_row = conn.execute(
        "SELECT candidate_id, group_type FROM groups WHERE id = ?", (parsed["group_id"],)
    ).fetchone()
    candidate_id = group_row["candidate_id"]

    log_telegram_event(conn, parsed["telegram_user_id"], update, True, parsed["action"], now=now)
    telegram_client.answer_callback_query(parsed["callback_query_id"], bot_token=bot_token)

    if group_row["group_type"] == "primary":
        result = handle_decision(
            conn, candidate_id, parsed["group_id"], parsed["action"], static_config=static_config,
            store_id=store_id, gelato_api_key=gelato_api_key, shop_id=shop_id, etsy_api_key=etsy_api_key,
            etsy_api_secret=etsy_api_secret, etsy_access_token=etsy_access_token,
            replicate_api_token=replicate_api_token, anthropic_api_key=anthropic_api_key,
            dry_run=dry_run, now=now,
        )
    else:
        result = publish_group.handle_decision(
            conn, candidate_id, parsed["group_id"], parsed["action"], static_config=static_config,
            store_id=store_id, gelato_api_key=gelato_api_key, shop_id=shop_id, etsy_api_key=etsy_api_key,
            etsy_api_secret=etsy_api_secret, etsy_access_token=etsy_access_token,
            dry_run=dry_run, now=now,
        )
    return {"candidate_id": candidate_id, "group_id": parsed["group_id"], **result}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `C:\Users\QVajd\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/test_publish_primary_group.py -v`
Expected: PASS (all tests in this file, including the two new ones)

- [ ] **Step 5: Commit**

```bash
git add pipeline/publish_primary_group.py tests/test_publish_primary_group.py
git commit -m "feat: dispatch non-primary group callbacks to publish_group.handle_decision"
```

---

### Task 7: Whole-suite regression run

**Files:** none (verification only)

**Interfaces:** none.

- [ ] **Step 1: Run the full test suite**

Run: `C:\Users\QVajd\AppData\Local\Programs\Python\Python312\python.exe -m pytest -v`
Expected: all tests PASS (no regressions in `test_publish_primary_group.py`,
`test_group_mockup.py`, `test_group_critic_pass.py`, `test_group_digest.py`, or any other
existing suite).

- [ ] **Step 2: If anything fails, fix forward and re-run**

Diagnose against the specific failing test's assertion — do not weaken assertions to make them
pass. Re-run Step 1 until green.

- [ ] **Step 3: Commit if any fixes were made**

```bash
git add -A
git commit -m "fix: address regressions found in publish_group whole-suite run"
```

(Skip this step entirely if Step 1 was already green with no changes.)

---

## Self-Review Notes

- **Spec coverage:** Approve (SPEC step 7 sub-bullet "Approving one publishes that group's
  single listing the same way as the primary group") → Task 2. Reject (SPEC "rejecting ...
  behaves the same as it does for the primary group, scoped to that one group") → Task 3. Edit
  (confirmed with user during brainstorming: discard + leave `groups.status` alone) → Task 4.
  Dispatch/routing (task brief's shared poll+dispatch architecture decision) → Task 6.
- **Placeholder scan:** no TBD/TODO; every step has concrete code.
- **Type consistency:** `handle_decision` signature matches across Tasks 2-6 and the dispatch
  call site in Task 6; `get_live_group_product` is internal to `publish_group.py` and not
  referenced by name from `publish_primary_group.py`.
