# Group Mockup (stage 8/12) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `pipeline/group_mockup.py`, the batch-scan stage that creates Gelato products
(and their `group_products`/`product_images` rows) for the 5x7 and 10x24 aspect-ratio groups,
once a candidate's primary group has published.

**Architecture:** One new module, `pipeline/group_mockup.py`, following the exact
per-item-function + cycle-function shape already used by `pipeline/primary_mockup.py`. Three
functions: `get_or_create_group` (generalizes `primary_mockup.get_or_create_primary_group` to
any `group_type`), `create_group_mockup` (one group_type for one candidate, with retry-once on
Gelato operational failure), `run_group_mockup_cycle` (batch selection + per-item error
isolation, mirroring `primary_mockup.run_primary_mockup_cycle`).

**Tech Stack:** Python, sqlite3 (stdlib), pytest, `unittest.mock.patch`. No new dependencies.

## Post-Task-2-review correction

Task 2's review (see `.superpowers/sdd/progress.md`) found every `fake_create_product_from_template`
fixture below that returns `"isReadyToPublish": True` directly from the *create* call is wrong —
the real Gelato create-from-template response never reports ready immediately (see
`docs/gelato_call_response_example_from_manual_tests.txt`); `create_group_mockup` always polls via
`primary_mockup.poll_until_ready` for non-dry-run responses, matching `create_primary_mockup`
exactly (no short-circuit). Every task below whose fixture returns `isReadyToPublish: True` from
`create_product_from_template` must instead return `isReadyToPublish: False, productImages: []`
from create, and separately mock `pipeline.group_mockup.primary_mockup.poll_until_ready` to supply
the ready state and gallery. This was corrected in the Task 3 dispatch brief directly; this note
exists so the plan file itself isn't misleading if read later.

## Global Constraints

- Image generation happens once per design — this stage never calls Replicate/FLUX; it only
  calls `gelato_client.create_product_from_template` against `candidates.base_image_url`
  (CLAUDE.md hard constraint).
- No new DB tables/columns — `groups.group_type` and `group_products.size` already accept
  `'5x7'`/`'10x24'` per `db/schema.sql`.
- Orientation is hardcoded `'portrait'` (no orientation field on `candidates`, matches every
  existing stage).
- `dry_run` behavior for `create_product_from_template` is already implemented in
  `gelato_client.py` (returns `{"_dry_run": True, "previewUrl": ..., ...}` when
  `dry_run`/non-live) — this stage must handle that response shape exactly like
  `primary_mockup.create_primary_mockup` does.
- Operational failure (Gelato create/poll raises) retries the whole create-then-poll sequence
  once; if it still fails, `group_products.status='mockup_failed'` and `groups.status` stays
  `'pending_generation'` (not terminal) so the next cycle retries it. This is a different
  failure semantics from `primary_mockup.create_primary_mockup`, which does NOT retry — group
  mockup must retry per SPEC_v4.10.md section 3 step 7's "retry once automatically" rule for
  operational failures.
- One failing group_type/candidate must never block another (per-item try/except in the
  cycle function, same convention as `run_primary_mockup_cycle`).

---

## File Structure

- Create: `pipeline/group_mockup.py` — the whole stage.
- Create: `tests/test_group_mockup.py` — full test suite.
- No other files modified. `db/schema.sql`, `config/static_config.json`, and
  `pipeline/config.py` already support everything this stage needs
  (`aspect_ratio_groups.5x7 = ["5x7"]`, `aspect_ratio_groups.10x24 = ["10x24"]`,
  `get_template_variant`, `prices_eur`).

---

### Task 1: `get_or_create_group` — generalized group lookup/creation

**Files:**
- Create: `pipeline/group_mockup.py`
- Test: `tests/test_group_mockup.py`

**Interfaces:**
- Consumes: `db.get_connection`, `db.init_db` (test helpers only); no other pipeline module.
- Produces: `get_or_create_group(conn, candidate_id: int, group_type: str, *, now=None) -> int`
  — returns the `groups.id` for `(candidate_id, group_type)`, inserting a new row with
  `status='pending_generation'` if none exists. Used by Task 2's `create_group_mockup`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_group_mockup.py
from datetime import datetime
from unittest.mock import patch

import pytest

import pipeline.db as db
import pipeline.group_mockup as group_mockup


def _fresh_conn(tmp_path):
    conn = db.get_connection(tmp_path / "test.sqlite3")
    db.init_db(conn)
    return conn


def _insert_candidate(conn, niche="monstera line art", *, status="completed",
                       base_image_url="https://replicate.delivery/out.png"):
    timestamp = "2026-07-09T09:00:00"
    cursor = conn.execute(
        """
        INSERT INTO candidates (created_at, niche, go_hold_kill, status, base_image_url, updated_at)
        VALUES (?, ?, 'go', ?, ?, ?)
        """,
        (timestamp, niche, status, base_image_url, timestamp),
    )
    conn.commit()
    return cursor.lastrowid


def _insert_published_primary_group(conn, candidate_id):
    timestamp = "2026-07-12T09:00:00"
    cursor = conn.execute(
        """
        INSERT INTO groups (candidate_id, group_type, status, created_at, updated_at)
        VALUES (?, 'primary', 'approved_published', ?, ?)
        """,
        (candidate_id, timestamp, timestamp),
    )
    conn.commit()
    return cursor.lastrowid


def test_get_or_create_group_creates_new_row(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)

    group_id = group_mockup.get_or_create_group(
        conn, candidate_id, "5x7", now=datetime(2026, 7, 12, 18, 0, 0)
    )

    row = conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone()
    assert row["candidate_id"] == candidate_id
    assert row["group_type"] == "5x7"
    assert row["status"] == "pending_generation"
    assert row["created_at"] == "2026-07-12T18:00:00"
    conn.close()


def test_get_or_create_group_returns_existing_row(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    first_id = group_mockup.get_or_create_group(
        conn, candidate_id, "10x24", now=datetime(2026, 7, 12, 18, 0, 0)
    )

    second_id = group_mockup.get_or_create_group(
        conn, candidate_id, "10x24", now=datetime(2026, 7, 12, 19, 0, 0)
    )

    assert second_id == first_id
    rows = conn.execute(
        "SELECT * FROM groups WHERE candidate_id = ? AND group_type = '10x24'", (candidate_id,)
    ).fetchall()
    assert len(rows) == 1
    conn.close()


def test_get_or_create_group_keeps_5x7_and_10x24_separate(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)

    id_5x7 = group_mockup.get_or_create_group(conn, candidate_id, "5x7", now=datetime(2026, 7, 12, 18, 0, 0))
    id_10x24 = group_mockup.get_or_create_group(conn, candidate_id, "10x24", now=datetime(2026, 7, 12, 18, 0, 0))

    assert id_5x7 != id_10x24
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_group_mockup.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.group_mockup'`

- [ ] **Step 3: Write minimal implementation**

```python
# pipeline/group_mockup.py
from datetime import datetime, timezone

import pipeline.config as config
import pipeline.gelato_client as gelato_client
import pipeline.primary_mockup as primary_mockup


def get_or_create_group(conn, candidate_id: int, group_type: str, *, now=None) -> int:
    row = conn.execute(
        "SELECT id FROM groups WHERE candidate_id = ? AND group_type = ?",
        (candidate_id, group_type),
    ).fetchone()
    if row is not None:
        return row["id"]

    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()
    cursor = conn.execute(
        """
        INSERT INTO groups (candidate_id, group_type, status, created_at, updated_at)
        VALUES (?, ?, 'pending_generation', ?, ?)
        """,
        (candidate_id, group_type, timestamp, timestamp),
    )
    conn.commit()
    return cursor.lastrowid
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_group_mockup.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add pipeline/group_mockup.py tests/test_group_mockup.py
git commit -m "feat: add get_or_create_group to group_mockup stage"
```

---

### Task 2: `create_group_mockup` — one group_type, one candidate, retry-once

**Files:**
- Modify: `pipeline/group_mockup.py`
- Modify: `tests/test_group_mockup.py`

**Interfaces:**
- Consumes: `get_or_create_group` (Task 1); `config.get_template_variant(static_config, size,
  orientation) -> dict` (existing, returns `{"template_id", "template_variant_id",
  "image_placeholder_name"}`); `config.load_static_config() -> dict` (existing);
  `gelato_client.create_product_from_template(template_id, template_variant_id,
  image_placeholder_name, image_url, title, *, store_id=None, api_key=None, dry_run=None) ->
  dict` (existing); `primary_mockup.poll_until_ready(product_id, *, store_id=None,
  api_key=None, poll_interval=3.0, timeout=90.0, sleep_fn=time.sleep,
  now_fn=time.monotonic) -> dict` (existing).
- Produces: `GROUP_SIZE_BY_TYPE = {"5x7": "5x7", "10x24": "10x24"}` module constant (the single
  size each of these two group_types maps to — read from
  `static_config["aspect_ratio_groups"][group_type][0]` at call time, not hardcoded, so it
  stays in sync with `config/static_config.json`). `create_group_mockup(conn, candidate_id:
  int, group_type: str, *, static_config=None, store_id=None, api_key=None,
  poll_interval=3.0, poll_timeout=90.0, now=None) -> dict | None` — returns `{"group_id":
  int, "group_product_id": int, "gelato_product_id": str}` on success, or `None` if the group
  already has a `created`/`published` `group_products` row (idempotent skip). Raises on
  failure after retry (caller in Task 3 catches). Used by Task 3's `run_group_mockup_cycle`.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_group_mockup.py

STATIC_CONFIG = {
    "gelato_templates": {
        "5x7_portrait": {
            "template_id": "tpl_5x7",
            "template_variant_id": "variant_5x7",
            "image_placeholder_name": "slot_5x7.jpg",
        },
        "10x24_portrait": {
            "template_id": "tpl_10x24",
            "template_variant_id": "variant_10x24",
            "image_placeholder_name": "slot_10x24.jpg",
        },
    },
    "prices_eur": {"5x7": 19, "10x24": 45},
    "aspect_ratio_groups": {"primary": ["8x12", "A3", "A2", "A1"], "5x7": ["5x7"], "10x24": ["10x24"]},
}


def test_create_group_mockup_happy_path_writes_group_product_and_images(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn, niche="monstera line art")
    _insert_published_primary_group(conn, candidate_id)

    def fake_create_product_from_template(template_id, template_variant_id, image_placeholder_name,
                                           image_url, title, *, store_id=None, api_key=None, **kwargs):
        assert template_id == "tpl_5x7"
        assert template_variant_id == "variant_5x7"
        assert image_placeholder_name == "slot_5x7.jpg"
        assert image_url == "https://replicate.delivery/out.png"
        return {"id": "gelato_prod_5x7", "isReadyToPublish": True,
                "productImages": [
                    {"fileUrl": "https://gelato/flat.jpg", "isPrimary": True},
                    {"fileUrl": "https://gelato/lifestyle.jpg", "isPrimary": False},
                ]}

    with patch("pipeline.group_mockup.gelato_client.create_product_from_template",
               side_effect=fake_create_product_from_template):
        result = group_mockup.create_group_mockup(
            conn, candidate_id, "5x7", static_config=STATIC_CONFIG, store_id="store1",
            api_key="key1", poll_interval=0, poll_timeout=10, now=datetime(2026, 7, 12, 18, 0, 0),
        )

    assert result["gelato_product_id"] == "gelato_prod_5x7"

    group_row = conn.execute("SELECT * FROM groups WHERE id = ?", (result["group_id"],)).fetchone()
    assert group_row["group_type"] == "5x7"
    assert group_row["status"] == "pending_review"

    gp_row = conn.execute(
        "SELECT * FROM group_products WHERE id = ?", (result["group_product_id"],)
    ).fetchone()
    assert gp_row["status"] == "created"
    assert gp_row["size"] == "5x7"
    assert gp_row["orientation"] == "portrait"
    assert gp_row["price_eur"] == 19

    images = conn.execute(
        "SELECT * FROM product_images WHERE group_product_id = ? ORDER BY gallery_order",
        (result["group_product_id"],),
    ).fetchall()
    assert len(images) == 2
    assert images[0]["image_type"] == "flat_mockup"
    assert images[1]["image_type"] == "lifestyle"
    conn.close()


def test_create_group_mockup_dry_run_skips_polling(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn, niche="moon phase print")
    _insert_published_primary_group(conn, candidate_id)

    def fake_create_product_from_template(*args, **kwargs):
        return {"id": "DRY_RUN_PRODUCT_ID", "previewUrl": None, "productImages": [], "_dry_run": True}

    with patch("pipeline.group_mockup.gelato_client.create_product_from_template",
               side_effect=fake_create_product_from_template), \
         patch("pipeline.group_mockup.primary_mockup.poll_until_ready") as mock_poll:
        result = group_mockup.create_group_mockup(
            conn, candidate_id, "10x24", static_config=STATIC_CONFIG, store_id="store1",
            api_key="key1", now=datetime(2026, 7, 12, 18, 0, 0),
        )

    mock_poll.assert_not_called()
    gp_row = conn.execute(
        "SELECT * FROM group_products WHERE id = ?", (result["group_product_id"],)
    ).fetchone()
    assert gp_row["status"] == "created"
    assert gp_row["size"] == "10x24"
    conn.close()


def test_create_group_mockup_skips_when_already_created(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_published_primary_group(conn, candidate_id)

    def fake_create_product_from_template(*args, **kwargs):
        return {"id": "gelato_prod_once", "isReadyToPublish": True,
                "productImages": [{"fileUrl": "https://gelato/flat.jpg", "isPrimary": True}]}

    with patch("pipeline.group_mockup.gelato_client.create_product_from_template",
               side_effect=fake_create_product_from_template) as mock_create:
        first = group_mockup.create_group_mockup(
            conn, candidate_id, "5x7", static_config=STATIC_CONFIG,
            poll_interval=0, poll_timeout=10, now=datetime(2026, 7, 12, 18, 0, 0),
        )
        second = group_mockup.create_group_mockup(
            conn, candidate_id, "5x7", static_config=STATIC_CONFIG,
            poll_interval=0, poll_timeout=10, now=datetime(2026, 7, 12, 19, 0, 0),
        )

    assert first is not None
    assert second is None
    mock_create.assert_called_once()
    conn.close()


def test_create_group_mockup_retries_once_then_succeeds(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_published_primary_group(conn, candidate_id)

    attempts = {"n": 0}

    def flaky_create(*args, **kwargs):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise RuntimeError("Gelato throttled")
        return {"id": "gelato_prod_retry", "isReadyToPublish": True,
                "productImages": [{"fileUrl": "https://gelato/flat.jpg", "isPrimary": True}]}

    with patch("pipeline.group_mockup.gelato_client.create_product_from_template",
               side_effect=flaky_create):
        result = group_mockup.create_group_mockup(
            conn, candidate_id, "5x7", static_config=STATIC_CONFIG,
            poll_interval=0, poll_timeout=10, now=datetime(2026, 7, 12, 18, 0, 0),
        )

    assert result["gelato_product_id"] == "gelato_prod_retry"
    assert attempts["n"] == 2
    conn.close()


def test_create_group_mockup_marks_mockup_failed_after_second_failure(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_published_primary_group(conn, candidate_id)

    with patch("pipeline.group_mockup.gelato_client.create_product_from_template",
               side_effect=RuntimeError("Gelato down")):
        with pytest.raises(RuntimeError, match="Gelato down"):
            group_mockup.create_group_mockup(
                conn, candidate_id, "10x24", static_config=STATIC_CONFIG,
                poll_interval=0, poll_timeout=10, now=datetime(2026, 7, 12, 18, 0, 0),
            )

    gp_row = conn.execute(
        "SELECT gp.* FROM group_products gp JOIN groups g ON g.id = gp.group_id "
        "WHERE g.candidate_id = ? AND g.group_type = '10x24'", (candidate_id,)
    ).fetchone()
    assert gp_row["status"] == "mockup_failed"

    group_row = conn.execute(
        "SELECT status FROM groups WHERE candidate_id = ? AND group_type = '10x24'", (candidate_id,)
    ).fetchone()
    assert group_row["status"] == "pending_generation"
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_group_mockup.py -v`
Expected: FAIL — `AttributeError: module 'pipeline.group_mockup' has no attribute 'create_group_mockup'`

- [ ] **Step 3: Write minimal implementation**

```python
# append to pipeline/group_mockup.py

def _group_size(static_config: dict, group_type: str) -> str:
    return static_config["aspect_ratio_groups"][group_type][0]


def create_group_mockup(conn, candidate_id: int, group_type: str, *, static_config: dict = None,
                         store_id: str = None, api_key: str = None,
                         poll_interval: float = 3.0, poll_timeout: float = 90.0,
                         now=None) -> dict | None:
    candidate_row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    if candidate_row is None:
        raise ValueError(f"No candidate with id {candidate_id}")
    candidate = dict(candidate_row)

    static_config = static_config if static_config is not None else config.load_static_config()
    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()

    group_id = get_or_create_group(conn, candidate_id, group_type, now=now)
    size = _group_size(static_config, group_type)

    existing = conn.execute(
        "SELECT id FROM group_products WHERE group_id = ? AND size = ? AND status IN ('created', 'published')",
        (group_id, size),
    ).fetchone()
    if existing is not None:
        return None

    row = conn.execute(
        "SELECT id FROM group_products WHERE group_id = ? AND size = ? AND status != 'deleted'",
        (group_id, size),
    ).fetchone()
    if row is not None:
        group_product_id = row["id"]
    else:
        template = config.get_template_variant(static_config, size, "portrait")
        cursor = conn.execute(
            """
            INSERT INTO group_products
              (group_id, size, orientation, gelato_template_id, price_eur, status, created_at, updated_at)
            VALUES (?, ?, 'portrait', ?, ?, 'pending', ?, ?)
            """,
            (group_id, size, template["template_id"], static_config["prices_eur"][size], timestamp, timestamp),
        )
        conn.commit()
        group_product_id = cursor.lastrowid

    template = config.get_template_variant(static_config, size, "portrait")

    def attempt():
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

        if response.get("_dry_run"):
            images = [{"fileUrl": response.get("previewUrl") or "placeholder://dry-run-image", "isPrimary": True}]
        else:
            product = primary_mockup.poll_until_ready(
                gelato_product_id, store_id=store_id, api_key=api_key,
                poll_interval=poll_interval, timeout=poll_timeout,
            )
            images = product["productImages"]
        return gelato_product_id, images

    try:
        try:
            gelato_product_id, images = attempt()
        except Exception:
            gelato_product_id, images = attempt()
    except Exception:
        conn.execute(
            "UPDATE group_products SET status = 'mockup_failed', updated_at = ? WHERE id = ?",
            (timestamp, group_product_id),
        )
        conn.commit()
        raise

    ordered_images = sorted(images, key=lambda img: not img.get("isPrimary"))
    for order, image in enumerate(ordered_images):
        image_type = "flat_mockup" if image.get("isPrimary") else "lifestyle"
        conn.execute(
            "INSERT INTO product_images (group_product_id, image_url, alt_text, gallery_order, image_type) "
            "VALUES (?, ?, '', ?, ?)",
            (group_product_id, image.get("fileUrl"), order, image_type),
        )

    conn.execute(
        "UPDATE group_products SET status = 'created', updated_at = ? WHERE id = ?",
        (timestamp, group_product_id),
    )
    conn.execute(
        "UPDATE groups SET status = 'pending_review', updated_at = ? WHERE id = ?",
        (timestamp, group_id),
    )
    conn.commit()

    return {"group_id": group_id, "group_product_id": group_product_id, "gelato_product_id": gelato_product_id}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_group_mockup.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add pipeline/group_mockup.py tests/test_group_mockup.py
git commit -m "feat: add create_group_mockup with retry-once-then-mockup_failed"
```

---

### Task 3: `run_group_mockup_cycle` — batch selection across candidates and group_types

**Files:**
- Modify: `pipeline/group_mockup.py`
- Modify: `tests/test_group_mockup.py`

**Interfaces:**
- Consumes: `create_group_mockup` (Task 2).
- Produces: `run_group_mockup_cycle(conn, *, static_config=None, store_id=None, api_key=None,
  poll_interval=3.0, poll_timeout=90.0, now=None) -> list[dict]` — the batch entrypoint for
  the twice-daily-batch cron. Returns one `{"candidate_id": int, "group_type": str,
  "gelato_product_id": str}` entry per group actually created this run (skips are omitted,
  failures are logged and omitted, matching `primary_mockup.run_primary_mockup_cycle`'s
  return-list convention).

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_group_mockup.py

GROUP_TYPES = ("5x7", "10x24")


def test_run_group_mockup_cycle_processes_both_group_types_for_ready_candidate(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn, niche="monstera line art")
    _insert_published_primary_group(conn, candidate_id)

    def fake_create_product_from_template(template_id, *args, **kwargs):
        return {"id": f"gelato_prod_{template_id}", "isReadyToPublish": True,
                "productImages": [{"fileUrl": "https://gelato/flat.jpg", "isPrimary": True}]}

    with patch("pipeline.group_mockup.gelato_client.create_product_from_template",
               side_effect=fake_create_product_from_template):
        processed = group_mockup.run_group_mockup_cycle(
            conn, static_config=STATIC_CONFIG, poll_interval=0, poll_timeout=10,
            now=datetime(2026, 7, 12, 20, 0, 0),
        )

    assert {(p["candidate_id"], p["group_type"]) for p in processed} == {
        (candidate_id, "5x7"), (candidate_id, "10x24"),
    }
    conn.close()


def test_run_group_mockup_cycle_skips_candidates_without_published_primary(tmp_path):
    conn = _fresh_conn(tmp_path)
    _insert_candidate(conn, niche="unreviewed one", status="primary_review")

    processed = group_mockup.run_group_mockup_cycle(conn, static_config=STATIC_CONFIG)

    assert processed == []
    conn.close()


def test_run_group_mockup_cycle_skips_group_types_already_created(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_published_primary_group(conn, candidate_id)

    def fake_create_product_from_template(template_id, *args, **kwargs):
        return {"id": f"gelato_prod_{template_id}", "isReadyToPublish": True,
                "productImages": [{"fileUrl": "https://gelato/flat.jpg", "isPrimary": True}]}

    with patch("pipeline.group_mockup.gelato_client.create_product_from_template",
               side_effect=fake_create_product_from_template):
        first_run = group_mockup.run_group_mockup_cycle(
            conn, static_config=STATIC_CONFIG, poll_interval=0, poll_timeout=10,
            now=datetime(2026, 7, 12, 20, 0, 0),
        )
        second_run = group_mockup.run_group_mockup_cycle(
            conn, static_config=STATIC_CONFIG, poll_interval=0, poll_timeout=10,
            now=datetime(2026, 7, 12, 21, 0, 0),
        )

    assert len(first_run) == 2
    assert second_run == []
    conn.close()


def test_run_group_mockup_cycle_isolates_per_group_type_failures(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_published_primary_group(conn, candidate_id)

    def fake_create_product_from_template(template_id, *args, **kwargs):
        if template_id == "tpl_5x7":
            raise RuntimeError("Gelato throttled")
        return {"id": f"gelato_prod_{template_id}", "isReadyToPublish": True,
                "productImages": [{"fileUrl": "https://gelato/flat.jpg", "isPrimary": True}]}

    with patch("pipeline.group_mockup.gelato_client.create_product_from_template",
               side_effect=fake_create_product_from_template):
        processed = group_mockup.run_group_mockup_cycle(
            conn, static_config=STATIC_CONFIG, poll_interval=0, poll_timeout=10,
            now=datetime(2026, 7, 12, 20, 0, 0),
        )

    assert [(p["candidate_id"], p["group_type"]) for p in processed] == [(candidate_id, "10x24")]

    failing_gp = conn.execute(
        "SELECT gp.* FROM group_products gp JOIN groups g ON g.id = gp.group_id "
        "WHERE g.candidate_id = ? AND g.group_type = '5x7'", (candidate_id,)
    ).fetchone()
    assert failing_gp["status"] == "mockup_failed"
    conn.close()


def test_run_group_mockup_cycle_returns_empty_list_when_nothing_ready(tmp_path):
    conn = _fresh_conn(tmp_path)

    processed = group_mockup.run_group_mockup_cycle(conn, static_config=STATIC_CONFIG)

    assert processed == []
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_group_mockup.py -v`
Expected: FAIL — `AttributeError: module 'pipeline.group_mockup' has no attribute 'run_group_mockup_cycle'`

- [ ] **Step 3: Write minimal implementation**

```python
# append to pipeline/group_mockup.py

GROUP_TYPES = ("5x7", "10x24")


def run_group_mockup_cycle(conn, *, static_config: dict = None, store_id: str = None,
                            api_key: str = None, poll_interval: float = 3.0,
                            poll_timeout: float = 90.0, now=None) -> list:
    static_config = static_config if static_config is not None else config.load_static_config()

    candidate_ids = [
        row["id"] for row in conn.execute(
            """
            SELECT c.id FROM candidates c
            JOIN groups g ON g.candidate_id = c.id AND g.group_type = 'primary'
                          AND g.status = 'approved_published'
            ORDER BY c.id
            """
        ).fetchall()
    ]

    processed = []
    for candidate_id in candidate_ids:
        for group_type in GROUP_TYPES:
            try:
                result = create_group_mockup(
                    conn, candidate_id, group_type, static_config=static_config,
                    store_id=store_id, api_key=api_key, poll_interval=poll_interval,
                    poll_timeout=poll_timeout, now=now,
                )
            except Exception as exc:
                print(f"create_group_mockup failed for candidate {candidate_id} "
                      f"group_type {group_type}: {exc}")
                continue
            if result is not None:
                processed.append({
                    "candidate_id": candidate_id,
                    "group_type": group_type,
                    "gelato_product_id": result["gelato_product_id"],
                })
    return processed
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_group_mockup.py -v`
Expected: 13 passed

- [ ] **Step 5: Commit**

```bash
git add pipeline/group_mockup.py tests/test_group_mockup.py
git commit -m "feat: add run_group_mockup_cycle batch entrypoint for stage 8/12"
```

---

### Task 4: Full-suite regression check

**Files:**
- None modified — verification only.

**Interfaces:**
- Consumes: entire test suite.
- Produces: confirmation that stage 8 doesn't regress stages 1-7.

- [ ] **Step 1: Run the full test suite**

Run: `python -m pytest tests/ -v`
Expected: all tests pass (206 pre-existing + 13 new = 219), 0 failures.

- [ ] **Step 2: If green, no commit needed (nothing changed in this task)**

If anything fails, fix the regression in `pipeline/group_mockup.py` (this stage is additive —
it should not touch any existing file), re-run, and commit the fix with message
`fix: <describe>`.

---

## Self-Review Notes

- **Spec coverage:** design doc's `get_or_create_group`, `create_group_mockup` (idempotent
  skip, retry-once, dry_run passthrough, mockup_failed-then-`pending_generation` semantics),
  and `run_group_mockup_cycle` (selection query, per-item isolation) are each covered by a
  task. No gaps found against `docs/superpowers/specs/2026-07-12-group-mockup-design.md`.
- **Placeholder scan:** none — every step has runnable code and exact expected output.
- **Type consistency:** `create_group_mockup` returns `dict | None` consistently across Tasks
  2 and 3; `GROUP_TYPES` tuple defined once in Task 3 and reused by no other function (no
  duplicate constant); `_group_size` reads from `static_config["aspect_ratio_groups"]` so
  Task 2/3 tests' `STATIC_CONFIG` fixture must include that key (it does).
