# Primary Mockup Stage (primary_mockup.py) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `pipeline/primary_mockup.py`, the third of 12 M1 pipeline stage modules — renders one Gelato poster product at the candidate's primary size (21x29.7cm/8x12″, portrait only for M1), per SPEC_v4.10.md section 3 step 3.

**Architecture:** Five layered functions in one module: `build_mockup_title()` is a pure string-builder, `get_or_create_primary_group()` find-or-creates the `groups` row, `poll_until_ready()` polls `gelato_client.get_product()` until Gelato's async render finishes, `create_primary_mockup()` orchestrates one candidate's full mockup flow (creates a fresh `group_products` row every call, writes `product_images`, transitions `group_products`/`groups` status), and `run_primary_mockup_cycle()` is the batch entry point that finds every ready-and-not-yet-mocked-up candidate and calls `create_primary_mockup()` on each, isolating per-candidate failures.

**Tech Stack:** Python 3, `sqlite3` (stdlib, via existing `pipeline/db.py`), `pytest` + `unittest.mock` for tests — same conventions as `pipeline/generate.py`.

## Global Constraints

Per the approved design (`docs/superpowers/specs/2026-07-09-primary-mockup-stage-design.md`):

- **Orientation is portrait-only for M1** — always `"8x12"` / `"portrait"`, no per-candidate orientation logic anywhere in this module.
- **`candidates.status` is never touched by this module.** It stays `'generating'` throughout. The selection predicate for the next stage (`compliance_draft.py`, not built here) will need its own combined check against `group_products`, same pattern as this module's own selection predicate (Task 8).
- **`create_primary_mockup` always inserts a fresh `group_products` row** — never finds-or-reuses one, even on a second call for the same candidate. Only `get_or_create_primary_group`'s `groups` row is find-or-create (schema `UNIQUE(candidate_id, group_type)` backs this).
- **Schema change required:** `group_products.status`'s CHECK constraint gains `'mockup_failed'` (Task 1) — the only schema change in this plan.
- **No compliance-draft text, no alt text generation, no critic-pass evaluation, no group-level (5x7/10x24) work** — all out of scope, later stages' jobs. `product_images.alt_text` is written as `''` here, to be `UPDATE`d later by `compliance_draft.py`.
- **Dry-run polling:** `gelato_client.get_product()` has no `dry_run` awareness. When `create_product_from_template`'s response carries `_dry_run: True`, `create_primary_mockup` skips `poll_until_ready` entirely and synthesizes one placeholder `product_images` row instead.
- Every stage module in this pipeline is independently testable and gets its own commit per passing test group, per CLAUDE.md's "commit after each stage passes its manual M1 test."

---

## Task 1: Schema change — `group_products.status` gains `'mockup_failed'`

**Files:**
- Modify: `db/schema.sql`
- Modify: `tests/test_db.py`

**Interfaces:**
- Produces: `group_products.status` now accepts `'mockup_failed'` as a valid value, alongside the existing `'pending'/'created'/'publish_failed'/'published'/'deleted'`. Consumed by Task 7's failure-handling code.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_db.py`:

```python
def test_group_products_accepts_mockup_failed_status(tmp_path):
    db_path = tmp_path / "test.sqlite3"
    conn = db.get_connection(db_path)
    db.init_db(conn)

    conn.execute(
        "INSERT INTO candidates (id, created_at, niche, go_hold_kill, status, updated_at) "
        "VALUES (1, '2026-07-06', 'botanical', 'go', 'pending', '2026-07-06')"
    )
    conn.execute(
        "INSERT INTO groups (id, candidate_id, group_type, status, created_at, updated_at) "
        "VALUES (1, 1, 'primary', 'pending_generation', '2026-07-06', '2026-07-06')"
    )
    conn.execute(
        "INSERT INTO group_products "
        "(group_id, size, orientation, gelato_template_id, price_eur, status, created_at, updated_at) "
        "VALUES (1, '8x12', 'portrait', 'tpl_1', 24, 'mockup_failed', '2026-07-06', '2026-07-06')"
    )
    conn.commit()

    row = conn.execute("SELECT status FROM group_products WHERE group_id = 1").fetchone()
    assert row["status"] == "mockup_failed"
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_db.py::test_group_products_accepts_mockup_failed_status -v`
Expected: FAIL with `sqlite3.IntegrityError: CHECK constraint failed: group_products`.

- [ ] **Step 3: Update the schema**

In `db/schema.sql`, find the `group_products` table's `status` CHECK constraint:

```sql
  status TEXT NOT NULL CHECK(status IN (
    'pending','created','publish_failed','published','deleted'
  )),
```

Replace it with:

```sql
  status TEXT NOT NULL CHECK(status IN (
    'pending','created','mockup_failed','publish_failed','published','deleted'
  )),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_db.py -v`
Expected: all PASS, including the new test.

- [ ] **Step 5: Commit**

```bash
git add db/schema.sql tests/test_db.py
git commit -m "feat: add mockup_failed status to group_products for primary_mockup.py"
```

---

## Task 2: `build_mockup_title()` — module skeleton + pure title construction

**Files:**
- Create: `pipeline/primary_mockup.py`
- Create: `tests/test_primary_mockup.py`

**Interfaces:**
- Produces: `build_mockup_title(candidate: dict) -> str`. Consumed by Task 5's `create_primary_mockup`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_primary_mockup.py`:

```python
import pipeline.primary_mockup as primary_mockup


def test_build_mockup_title_includes_niche():
    candidate = {"niche": "monstera line art"}

    title = primary_mockup.build_mockup_title(candidate)

    assert "monstera line art" in title
    assert "primary mockup" in title.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_primary_mockup.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.primary_mockup'`.

- [ ] **Step 3: Implement `pipeline/primary_mockup.py`**

```python
import time
from datetime import datetime, timezone

import pipeline.config as config
import pipeline.gelato_client as gelato_client


class GelatoMockupTimeoutError(Exception):
    pass


def build_mockup_title(candidate: dict) -> str:
    return f"{candidate['niche']} - primary mockup"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_primary_mockup.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/primary_mockup.py tests/test_primary_mockup.py
git commit -m "feat: add primary_mockup.py build_mockup_title"
```

---

## Task 3: `get_or_create_primary_group()` — find-or-create the `groups` row

**Files:**
- Modify: `pipeline/primary_mockup.py`
- Modify: `tests/test_primary_mockup.py`

**Interfaces:**
- Consumes: `pipeline/db.py`'s `get_connection`/`init_db` (already merged).
- Produces: `get_or_create_primary_group(conn, candidate_id: int, *, now=None) -> int` — returns `group_id`. Consumed by Task 5's `create_primary_mockup`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_primary_mockup.py`:

```python
from datetime import datetime

import pipeline.db as db


def _fresh_conn(tmp_path):
    conn = db.get_connection(tmp_path / "test.sqlite3")
    db.init_db(conn)
    return conn


def _insert_candidate(conn, niche="monstera line art", *, status="generating",
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


def test_get_or_create_primary_group_creates_new_row(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)

    group_id = primary_mockup.get_or_create_primary_group(
        conn, candidate_id, now=datetime(2026, 7, 9, 10, 0, 0)
    )

    row = conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone()
    assert row["candidate_id"] == candidate_id
    assert row["group_type"] == "primary"
    assert row["status"] == "pending_generation"
    assert row["created_at"] == "2026-07-09T10:00:00"
    conn.close()


def test_get_or_create_primary_group_returns_existing_row(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    first_id = primary_mockup.get_or_create_primary_group(
        conn, candidate_id, now=datetime(2026, 7, 9, 10, 0, 0)
    )

    second_id = primary_mockup.get_or_create_primary_group(
        conn, candidate_id, now=datetime(2026, 7, 9, 11, 0, 0)
    )

    assert second_id == first_id
    rows = conn.execute(
        "SELECT * FROM groups WHERE candidate_id = ? AND group_type = 'primary'", (candidate_id,)
    ).fetchall()
    assert len(rows) == 1
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_primary_mockup.py -v`
Expected: FAIL — `get_or_create_primary_group` doesn't exist yet (`AttributeError`).

- [ ] **Step 3: Implement**

Add to `pipeline/primary_mockup.py`:

```python
def get_or_create_primary_group(conn, candidate_id: int, *, now=None) -> int:
    row = conn.execute(
        "SELECT id FROM groups WHERE candidate_id = ? AND group_type = 'primary'",
        (candidate_id,),
    ).fetchone()
    if row is not None:
        return row["id"]

    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()
    cursor = conn.execute(
        """
        INSERT INTO groups (candidate_id, group_type, status, created_at, updated_at)
        VALUES (?, 'primary', 'pending_generation', ?, ?)
        """,
        (candidate_id, timestamp, timestamp),
    )
    conn.commit()
    return cursor.lastrowid
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_primary_mockup.py -v`
Expected: all 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/primary_mockup.py tests/test_primary_mockup.py
git commit -m "feat: add primary_mockup.py get_or_create_primary_group"
```

---

## Task 4: `poll_until_ready()` — Gelato async-render poll loop

**Files:**
- Modify: `pipeline/primary_mockup.py`
- Modify: `tests/test_primary_mockup.py`

**Interfaces:**
- Consumes: `gelato_client.get_product(product_id, *, store_id=None, api_key=None) -> dict` (already merged, `pipeline/gelato_client.py`).
- Produces: `poll_until_ready(product_id: str, *, store_id=None, api_key=None, poll_interval=3.0, timeout=90.0, sleep_fn=time.sleep, now_fn=time.monotonic) -> dict`. Consumed by Task 5's `create_primary_mockup`. Raises `GelatoMockupTimeoutError` (defined in Task 2) on timeout.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_primary_mockup.py`:

```python
from unittest.mock import patch

import pytest


def test_poll_until_ready_returns_product_once_ready():
    call_count = {"n": 0}

    def fake_get_product(product_id, *, store_id=None, api_key=None):
        call_count["n"] += 1
        if call_count["n"] < 3:
            return {"id": product_id, "isReadyToPublish": False, "productImages": []}
        return {
            "id": product_id, "isReadyToPublish": True,
            "productImages": [{"fileUrl": "https://img/1.jpg", "isPrimary": True}],
        }

    sleeps = []

    with patch("pipeline.primary_mockup.gelato_client.get_product", side_effect=fake_get_product):
        result = primary_mockup.poll_until_ready(
            "prod_1", store_id="store1", api_key="key1",
            poll_interval=3.0, timeout=90.0,
            sleep_fn=sleeps.append, now_fn=lambda: 0.0,
        )

    assert result["isReadyToPublish"] is True
    assert call_count["n"] == 3
    assert sleeps == [3.0, 3.0]


def test_poll_until_ready_raises_after_timeout():
    def fake_get_product(product_id, *, store_id=None, api_key=None):
        return {"id": product_id, "isReadyToPublish": False, "productImages": []}

    now_values = iter([0.0, 10.0, 95.0])

    with patch("pipeline.primary_mockup.gelato_client.get_product", side_effect=fake_get_product):
        with pytest.raises(primary_mockup.GelatoMockupTimeoutError, match="prod_1"):
            primary_mockup.poll_until_ready(
                "prod_1", store_id="store1", api_key="key1",
                poll_interval=3.0, timeout=90.0,
                sleep_fn=lambda seconds: None, now_fn=lambda: next(now_values),
            )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_primary_mockup.py -v`
Expected: FAIL — `poll_until_ready` doesn't exist yet (`AttributeError`).

- [ ] **Step 3: Implement**

Add to `pipeline/primary_mockup.py`:

```python
def poll_until_ready(product_id: str, *, store_id: str = None, api_key: str = None,
                      poll_interval: float = 3.0, timeout: float = 90.0,
                      sleep_fn=time.sleep, now_fn=time.monotonic) -> dict:
    deadline = now_fn() + timeout
    while True:
        product = gelato_client.get_product(product_id, store_id=store_id, api_key=api_key)
        if product.get("isReadyToPublish"):
            return product
        if now_fn() >= deadline:
            raise GelatoMockupTimeoutError(
                f"Gelato product {product_id} did not become ready to publish within "
                f"{timeout:.0f}s. The one observed real render took ~9s for a 4-image "
                f"gallery - this likely indicates a Gelato-side delay or outage, not a "
                f"pipeline bug."
            )
        sleep_fn(poll_interval)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_primary_mockup.py -v`
Expected: all 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/primary_mockup.py tests/test_primary_mockup.py
git commit -m "feat: add primary_mockup.py poll_until_ready"
```

---

## Task 5: `create_primary_mockup()` — happy path

**Files:**
- Modify: `pipeline/primary_mockup.py`
- Modify: `tests/test_primary_mockup.py`

**Interfaces:**
- Consumes: `build_mockup_title` (Task 2), `get_or_create_primary_group` (Task 3), `poll_until_ready` (Task 4), `config.get_template_variant(static_config, size, orientation) -> dict` (already merged, `pipeline/config.py`), `gelato_client.create_product_from_template(template_id, template_variant_id, image_placeholder_name, image_url, title, *, store_id=None, api_key=None, dry_run=None) -> dict` (already merged, `pipeline/gelato_client.py`).
- Produces: `create_primary_mockup(conn, candidate_id: int, *, static_config: dict = None, store_id: str = None, api_key: str = None, poll_interval: float = 3.0, poll_timeout: float = 90.0, now=None) -> dict` — returns `{"group_id", "group_product_id", "gelato_product_id"}`. Consumed by Task 8's `run_primary_mockup_cycle` and, later, `critic_pass.py`'s retry loop (not built in this plan).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_primary_mockup.py`:

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
}


def test_create_primary_mockup_happy_path_writes_group_product_and_images(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn, niche="monstera line art")

    def fake_create_product_from_template(template_id, template_variant_id, image_placeholder_name,
                                           image_url, title, *, store_id=None, api_key=None, **kwargs):
        assert template_id == "tpl_real_8x12"
        assert template_variant_id == "variant_real_8x12"
        assert image_placeholder_name == "real_image_slot.jpg"
        assert image_url == "https://replicate.delivery/out.png"
        assert "monstera line art" in title
        return {"id": "gelato_prod_1", "isReadyToPublish": False, "productImages": []}

    def fake_get_product(product_id, *, store_id=None, api_key=None):
        assert product_id == "gelato_prod_1"
        return {
            "id": "gelato_prod_1",
            "isReadyToPublish": True,
            "productImages": [
                {"fileUrl": "https://gelato/lifestyle1.jpg", "isPrimary": False},
                {"fileUrl": "https://gelato/flat.jpg", "isPrimary": True},
                {"fileUrl": "https://gelato/lifestyle2.jpg", "isPrimary": False},
            ],
        }

    with patch("pipeline.primary_mockup.gelato_client.create_product_from_template",
               side_effect=fake_create_product_from_template), \
         patch("pipeline.primary_mockup.gelato_client.get_product", side_effect=fake_get_product):
        result = primary_mockup.create_primary_mockup(
            conn, candidate_id, static_config=STATIC_CONFIG, store_id="store1", api_key="key1",
            poll_interval=0, poll_timeout=10, now=datetime(2026, 7, 9, 12, 0, 0),
        )

    assert result["gelato_product_id"] == "gelato_prod_1"

    group_row = conn.execute("SELECT * FROM groups WHERE id = ?", (result["group_id"],)).fetchone()
    assert group_row["status"] == "pending_review"

    gp_row = conn.execute("SELECT * FROM group_products WHERE id = ?", (result["group_product_id"],)).fetchone()
    assert gp_row["status"] == "created"
    assert gp_row["gelato_product_id"] == "gelato_prod_1"
    assert gp_row["size"] == "8x12"
    assert gp_row["orientation"] == "portrait"
    assert gp_row["price_eur"] == 24

    images = conn.execute(
        "SELECT * FROM product_images WHERE group_product_id = ? ORDER BY gallery_order",
        (result["group_product_id"],),
    ).fetchall()
    assert len(images) == 3
    assert images[0]["image_type"] == "flat_mockup"
    assert images[0]["image_url"] == "https://gelato/flat.jpg"
    assert images[0]["alt_text"] == ""
    assert [img["image_type"] for img in images[1:]] == ["lifestyle", "lifestyle"]
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_primary_mockup.py -v`
Expected: FAIL — `create_primary_mockup` doesn't exist yet (`AttributeError`).

- [ ] **Step 3: Implement**

Add to `pipeline/primary_mockup.py`:

```python
def create_primary_mockup(conn, candidate_id: int, *, static_config: dict = None,
                           store_id: str = None, api_key: str = None,
                           poll_interval: float = 3.0, poll_timeout: float = 90.0,
                           now=None) -> dict:
    row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    if row is None:
        raise ValueError(f"No candidate with id {candidate_id}")
    candidate = dict(row)

    static_config = static_config if static_config is not None else config.load_static_config()
    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()

    group_id = get_or_create_primary_group(conn, candidate_id, now=now)

    template = config.get_template_variant(static_config, "8x12", "portrait")
    price_eur = static_config["prices_eur"]["8x12"]

    cursor = conn.execute(
        """
        INSERT INTO group_products
          (group_id, size, orientation, gelato_template_id, price_eur, status, created_at, updated_at)
        VALUES (?, '8x12', 'portrait', ?, ?, 'pending', ?, ?)
        """,
        (group_id, template["template_id"], price_eur, timestamp, timestamp),
    )
    conn.commit()
    group_product_id = cursor.lastrowid

    response = gelato_client.create_product_from_template(
        template["template_id"], template["template_variant_id"],
        template["image_placeholder_name"], candidate["base_image_url"],
        build_mockup_title(candidate), store_id=store_id, api_key=api_key,
    )
    gelato_product_id = response["id"]
    conn.execute(
        "UPDATE group_products SET gelato_product_id = ?, updated_at = ? WHERE id = ?",
        (gelato_product_id, timestamp, group_product_id),
    )
    conn.commit()

    if response.get("_dry_run"):
        images = [{"fileUrl": response.get("previewUrl"), "isPrimary": True}]
    else:
        product = poll_until_ready(
            gelato_product_id, store_id=store_id, api_key=api_key,
            poll_interval=poll_interval, timeout=poll_timeout,
        )
        images = product["productImages"]

    ordered_images = sorted(images, key=lambda img: not img.get("isPrimary"))
    for order, image in enumerate(ordered_images):
        image_type = "flat_mockup" if image.get("isPrimary") else "lifestyle"
        conn.execute(
            """
            INSERT INTO product_images (group_product_id, image_url, alt_text, gallery_order, image_type)
            VALUES (?, ?, '', ?, ?)
            """,
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

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_primary_mockup.py -v`
Expected: all 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/primary_mockup.py tests/test_primary_mockup.py
git commit -m "feat: add primary_mockup.py create_primary_mockup happy path"
```

---

## Task 6: `create_primary_mockup()` — dry-run short-circuit

**Files:**
- Modify: `pipeline/primary_mockup.py`
- Modify: `tests/test_primary_mockup.py`

**Interfaces:**
- Consumes/Produces: same `create_primary_mockup` from Task 5 — this task adds the dry-run branch's test coverage (the implementation code was already written in Task 5's `if response.get("_dry_run")` branch; this task verifies it).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_primary_mockup.py`:

```python
def test_create_primary_mockup_dry_run_skips_polling(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn, niche="moon phase print")

    def fake_create_product_from_template(*args, **kwargs):
        return {
            "id": "DRY_RUN_PRODUCT_ID", "previewUrl": None, "productImages": [],
            "isReadyToPublish": False, "_dry_run": True,
        }

    with patch("pipeline.primary_mockup.gelato_client.create_product_from_template",
               side_effect=fake_create_product_from_template), \
         patch("pipeline.primary_mockup.gelato_client.get_product") as mock_get_product:
        result = primary_mockup.create_primary_mockup(
            conn, candidate_id, static_config=STATIC_CONFIG, store_id="store1", api_key="key1",
            now=datetime(2026, 7, 9, 12, 0, 0),
        )

    mock_get_product.assert_not_called()

    images = conn.execute(
        "SELECT * FROM product_images WHERE group_product_id = ?",
        (result["group_product_id"],),
    ).fetchall()
    assert len(images) == 1
    assert images[0]["image_type"] == "flat_mockup"
    assert images[0]["gallery_order"] == 0

    gp_row = conn.execute("SELECT * FROM group_products WHERE id = ?", (result["group_product_id"],)).fetchone()
    assert gp_row["status"] == "created"
    conn.close()
```

- [ ] **Step 2: Run test to verify it currently passes or fails**

Run: `python -m pytest tests/test_primary_mockup.py::test_create_primary_mockup_dry_run_skips_polling -v`
Expected: PASS — Task 5's implementation already handles this branch. (If it fails, the dry-run branch in Task 5's code needs fixing before continuing — do not proceed with a red test.)

- [ ] **Step 3: Run the full test file to confirm nothing broke**

Run: `python -m pytest tests/test_primary_mockup.py -v`
Expected: all 7 PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/test_primary_mockup.py
git commit -m "test: cover primary_mockup.py dry-run polling short-circuit"
```

---

## Task 7: `create_primary_mockup()` — failure handling (`mockup_failed`)

**Files:**
- Modify: `pipeline/primary_mockup.py`
- Modify: `tests/test_primary_mockup.py`

**Interfaces:**
- Consumes/Produces: same `create_primary_mockup` from Task 5 — this task adds a `try/except` around the Gelato create-and-poll block so failures mark `group_products.status = 'mockup_failed'` (Task 1's schema addition) before re-raising.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_primary_mockup.py`:

```python
def test_create_primary_mockup_marks_mockup_failed_when_create_call_raises(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn, niche="saturated term")

    def fake_create_product_from_template(*args, **kwargs):
        raise RuntimeError("Gelato 500")

    with patch("pipeline.primary_mockup.gelato_client.create_product_from_template",
               side_effect=fake_create_product_from_template):
        with pytest.raises(RuntimeError, match="Gelato 500"):
            primary_mockup.create_primary_mockup(
                conn, candidate_id, static_config=STATIC_CONFIG, store_id="store1", api_key="key1",
                now=datetime(2026, 7, 9, 12, 0, 0),
            )

    gp_row = conn.execute(
        "SELECT gp.* FROM group_products gp JOIN groups g ON g.id = gp.group_id "
        "WHERE g.candidate_id = ?", (candidate_id,)
    ).fetchone()
    assert gp_row["status"] == "mockup_failed"
    conn.close()


def test_create_primary_mockup_marks_mockup_failed_on_poll_timeout(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn, niche="fern print")

    def fake_create_product_from_template(*args, **kwargs):
        return {"id": "gelato_prod_2", "isReadyToPublish": False, "productImages": []}

    def fake_get_product(product_id, *, store_id=None, api_key=None):
        return {"id": product_id, "isReadyToPublish": False, "productImages": []}

    with patch("pipeline.primary_mockup.gelato_client.create_product_from_template",
               side_effect=fake_create_product_from_template), \
         patch("pipeline.primary_mockup.gelato_client.get_product", side_effect=fake_get_product):
        with pytest.raises(primary_mockup.GelatoMockupTimeoutError):
            primary_mockup.create_primary_mockup(
                conn, candidate_id, static_config=STATIC_CONFIG, store_id="store1", api_key="key1",
                poll_interval=0, poll_timeout=0,
                now=datetime(2026, 7, 9, 12, 0, 0),
            )

    gp_row = conn.execute(
        "SELECT gp.* FROM group_products gp JOIN groups g ON g.id = gp.group_id "
        "WHERE g.candidate_id = ?", (candidate_id,)
    ).fetchone()
    assert gp_row["status"] == "mockup_failed"
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_primary_mockup.py -v`
Expected: FAIL — both new tests raise the expected exception, but `group_products.status` is still `'pending'` (no failure-handling code exists yet), so the `assert gp_row["status"] == "mockup_failed"` assertion fails.

- [ ] **Step 3: Implement**

In `pipeline/primary_mockup.py`, wrap the Gelato create-and-poll block inside `create_primary_mockup` in a `try/except`. Replace this section:

```python
    response = gelato_client.create_product_from_template(
        template["template_id"], template["template_variant_id"],
        template["image_placeholder_name"], candidate["base_image_url"],
        build_mockup_title(candidate), store_id=store_id, api_key=api_key,
    )
    gelato_product_id = response["id"]
    conn.execute(
        "UPDATE group_products SET gelato_product_id = ?, updated_at = ? WHERE id = ?",
        (gelato_product_id, timestamp, group_product_id),
    )
    conn.commit()

    if response.get("_dry_run"):
        images = [{"fileUrl": response.get("previewUrl"), "isPrimary": True}]
    else:
        product = poll_until_ready(
            gelato_product_id, store_id=store_id, api_key=api_key,
            poll_interval=poll_interval, timeout=poll_timeout,
        )
        images = product["productImages"]
```

with:

```python
    try:
        response = gelato_client.create_product_from_template(
            template["template_id"], template["template_variant_id"],
            template["image_placeholder_name"], candidate["base_image_url"],
            build_mockup_title(candidate), store_id=store_id, api_key=api_key,
        )
        gelato_product_id = response["id"]
        conn.execute(
            "UPDATE group_products SET gelato_product_id = ?, updated_at = ? WHERE id = ?",
            (gelato_product_id, timestamp, group_product_id),
        )
        conn.commit()

        if response.get("_dry_run"):
            images = [{"fileUrl": response.get("previewUrl"), "isPrimary": True}]
        else:
            product = poll_until_ready(
                gelato_product_id, store_id=store_id, api_key=api_key,
                poll_interval=poll_interval, timeout=poll_timeout,
            )
            images = product["productImages"]
    except Exception:
        conn.execute(
            "UPDATE group_products SET status = 'mockup_failed', updated_at = ? WHERE id = ?",
            (timestamp, group_product_id),
        )
        conn.commit()
        raise
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_primary_mockup.py -v`
Expected: all 9 PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/primary_mockup.py tests/test_primary_mockup.py
git commit -m "feat: mark group_products mockup_failed on create/poll failure"
```

---

## Task 8: `run_primary_mockup_cycle()` — batch orchestrator

**Files:**
- Modify: `pipeline/primary_mockup.py`
- Modify: `tests/test_primary_mockup.py`

**Interfaces:**
- Consumes: `create_primary_mockup(conn, candidate_id, ...)` (Task 5/7).
- Produces: `run_primary_mockup_cycle(conn, *, static_config=None, store_id=None, api_key=None, poll_interval=3.0, poll_timeout=90.0, now=None) -> list[int]` — the module's public entry point, to be called by the not-yet-built twice-daily batch orchestrator after `generate.run_generate_cycle`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_primary_mockup.py`:

```python
def test_run_primary_mockup_cycle_processes_ready_candidates_and_skips_others(tmp_path):
    conn = _fresh_conn(tmp_path)
    ready_id = _insert_candidate(conn, niche="monstera line art", status="generating",
                                  base_image_url="https://replicate.delivery/a.png")
    _insert_candidate(conn, niche="pending one", status="pending", base_image_url=None)

    def fake_create_product_from_template(*args, **kwargs):
        return {"id": "gelato_prod_x", "isReadyToPublish": True,
                "productImages": [{"fileUrl": "https://gelato/flat.jpg", "isPrimary": True}]}

    def fake_get_product(product_id, *, store_id=None, api_key=None):
        return {"id": product_id, "isReadyToPublish": True,
                "productImages": [{"fileUrl": "https://gelato/flat.jpg", "isPrimary": True}]}

    with patch("pipeline.primary_mockup.gelato_client.create_product_from_template",
               side_effect=fake_create_product_from_template), \
         patch("pipeline.primary_mockup.gelato_client.get_product", side_effect=fake_get_product):
        processed_ids = primary_mockup.run_primary_mockup_cycle(
            conn, static_config=STATIC_CONFIG, store_id="store1", api_key="key1",
            now=datetime(2026, 7, 9, 12, 0, 0),
        )

    assert processed_ids == [ready_id]
    conn.close()


def test_run_primary_mockup_cycle_skips_candidates_already_mocked_up(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn, niche="monstera line art", status="generating")

    def fake_create_product_from_template(*args, **kwargs):
        return {"id": "gelato_prod_y", "isReadyToPublish": True,
                "productImages": [{"fileUrl": "https://gelato/flat.jpg", "isPrimary": True}]}

    def fake_get_product(product_id, *, store_id=None, api_key=None):
        return {"id": product_id, "isReadyToPublish": True,
                "productImages": [{"fileUrl": "https://gelato/flat.jpg", "isPrimary": True}]}

    with patch("pipeline.primary_mockup.gelato_client.create_product_from_template",
               side_effect=fake_create_product_from_template), \
         patch("pipeline.primary_mockup.gelato_client.get_product", side_effect=fake_get_product):
        first_run = primary_mockup.run_primary_mockup_cycle(
            conn, static_config=STATIC_CONFIG, store_id="store1", api_key="key1",
            now=datetime(2026, 7, 9, 12, 0, 0),
        )
        second_run = primary_mockup.run_primary_mockup_cycle(
            conn, static_config=STATIC_CONFIG, store_id="store1", api_key="key1",
            now=datetime(2026, 7, 9, 13, 0, 0),
        )

    assert first_run == [candidate_id]
    assert second_run == []
    conn.close()


def test_run_primary_mockup_cycle_isolates_per_candidate_failures(tmp_path):
    conn = _fresh_conn(tmp_path)
    failing_id = _insert_candidate(conn, niche="monstera line art", status="generating",
                                    base_image_url="https://replicate.delivery/fail.png")
    succeeding_id = _insert_candidate(conn, niche="moon phase print", status="generating",
                                       base_image_url="https://replicate.delivery/ok.png")

    def fake_create_product_from_template(template_id, template_variant_id, image_placeholder_name,
                                           image_url, title, *, store_id=None, api_key=None, **kwargs):
        if image_url == "https://replicate.delivery/fail.png":
            raise RuntimeError("Gelato throttled")
        return {"id": "gelato_prod_ok", "isReadyToPublish": True,
                "productImages": [{"fileUrl": "https://gelato/flat.jpg", "isPrimary": True}]}

    def fake_get_product(product_id, *, store_id=None, api_key=None):
        return {"id": product_id, "isReadyToPublish": True,
                "productImages": [{"fileUrl": "https://gelato/flat.jpg", "isPrimary": True}]}

    with patch("pipeline.primary_mockup.gelato_client.create_product_from_template",
               side_effect=fake_create_product_from_template), \
         patch("pipeline.primary_mockup.gelato_client.get_product", side_effect=fake_get_product):
        processed_ids = primary_mockup.run_primary_mockup_cycle(
            conn, static_config=STATIC_CONFIG, store_id="store1", api_key="key1",
            now=datetime(2026, 7, 9, 12, 0, 0),
        )

    assert processed_ids == [succeeding_id]

    failing_gp = conn.execute(
        "SELECT gp.* FROM group_products gp JOIN groups g ON g.id = gp.group_id "
        "WHERE g.candidate_id = ?", (failing_id,)
    ).fetchone()
    assert failing_gp["status"] == "mockup_failed"
    conn.close()


def test_run_primary_mockup_cycle_returns_empty_list_when_nothing_ready(tmp_path):
    conn = _fresh_conn(tmp_path)
    _insert_candidate(conn, niche="pending one", status="pending", base_image_url=None)

    processed_ids = primary_mockup.run_primary_mockup_cycle(conn, static_config=STATIC_CONFIG)

    assert processed_ids == []
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_primary_mockup.py -v`
Expected: FAIL — `run_primary_mockup_cycle` doesn't exist yet (`AttributeError`).

- [ ] **Step 3: Implement**

Add to `pipeline/primary_mockup.py`:

```python
def run_primary_mockup_cycle(conn, *, static_config: dict = None, store_id: str = None,
                              api_key: str = None, poll_interval: float = 3.0,
                              poll_timeout: float = 90.0, now=None) -> list:
    candidate_ids = [
        row["id"] for row in conn.execute(
            """
            SELECT id FROM candidates
            WHERE status = 'generating'
              AND base_image_url IS NOT NULL
              AND id NOT IN (
                SELECT g.candidate_id FROM groups g
                JOIN group_products gp ON gp.group_id = g.id
                WHERE g.group_type = 'primary'
              )
            ORDER BY id
            """
        ).fetchall()
    ]
    processed_ids = []
    for candidate_id in candidate_ids:
        try:
            create_primary_mockup(
                conn, candidate_id, static_config=static_config, store_id=store_id,
                api_key=api_key, poll_interval=poll_interval, poll_timeout=poll_timeout, now=now,
            )
        except Exception as exc:
            print(f"create_primary_mockup failed for candidate {candidate_id}: {exc}")
            continue
        processed_ids.append(candidate_id)
    return processed_ids
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_primary_mockup.py -v`
Expected: all 13 PASS.

- [ ] **Step 5: Run the full test suite to confirm nothing else broke**

Run: `python -m pytest -v`
Expected: all PASS (db, config, http, gelato, replicate, telegram, etsy, anthropic, research, generate, primary_mockup suites).

- [ ] **Step 6: Commit**

```bash
git add pipeline/primary_mockup.py tests/test_primary_mockup.py
git commit -m "feat: add primary_mockup.py run_primary_mockup_cycle batch orchestrator"
```

---

## Self-Review Notes

- **Spec coverage:** all 5 function signatures (Tasks 2-5, 8), the schema addition (Task 1), the poll-loop shape with real-timing-calibrated defaults (Task 4), gallery ordering (`isPrimary` first, Task 5), the `alt_text=''` placeholder (Task 5), the dry-run short-circuit (Task 6, code written in Task 5), the `mockup_failed` failure path (Task 7), and the combined-check selection predicate that excludes already-mocked and `mockup_failed` candidates alike (Task 8) are all covered, matching `docs/superpowers/specs/2026-07-09-primary-mockup-stage-design.md` sections 1-9. Section 5's status-semantics table (`candidates` untouched, `groups` → `'pending_review'`, `group_products` → `'created'`/`'mockup_failed'`) is directly implemented with no contradicting code.
- **Placeholder scan:** no TBD/"add error handling"/"similar to Task N" language. Every step has concrete, runnable code.
- **Type consistency:** `create_primary_mockup`'s signature (Task 5) is called identically by `run_primary_mockup_cycle` (Task 8) — same keyword names (`static_config`, `store_id`, `api_key`, `poll_interval`, `poll_timeout`, `now`). `poll_until_ready`'s `sleep_fn`/`now_fn` injection points (Task 4) are exercised directly in its own tests but left at their real (`time.sleep`/`time.monotonic`) defaults everywhere `create_primary_mockup` calls it — acceptable since every `create_primary_mockup` test either resolves on the first poll (no sleep) or uses `poll_timeout=0` (raises before any sleep), so no test actually blocks on a real sleep.
