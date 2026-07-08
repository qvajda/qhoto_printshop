# Design Generation Stage (generate.py) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `pipeline/generate.py`, the second of 12 M1 pipeline stage modules — one Replicate (FLUX.1 [schnell]) image-generation call per `pending` candidate, writing the result back onto the `candidates` row, per SPEC_v4.10.md section 3 step 2.

**Architecture:** Three layered functions in one module: `build_prompt()` is a pure string-builder (niche + fixed style scaffold + hard no-go list + optional retry correction note), `generate_for_candidate()` reads one candidate row, calls the already-merged `replicate_client.generate_image()`, and writes the result back, and `run_generate_cycle()` is the batch entry point that finds every `status='pending'` candidate and calls `generate_for_candidate()` on each. No new DB tables or columns.

**Tech Stack:** Python 3, `sqlite3` (stdlib, via existing `pipeline/db.py`), `pytest` + `unittest.mock` for tests — same conventions as `pipeline/research.py`.

## Global Constraints

- **No schema changes.** `db/schema.sql` is not touched. Per the approved design (`docs/superpowers/specs/2026-07-09-generate-stage-design.md`, section 4):
  - Base images are generated **portrait only** for M1 — no per-candidate orientation column, no orientation parameter anywhere in this module. Deferred as a future feature, not solved here.
  - No new `candidates.status` value is added. `generate_for_candidate` sets `status='generating'`; the future `primary_mockup.py` is expected to select on `status='generating' AND base_image_url IS NOT NULL`.
  - `style_theme_tags` stays NULL — this module never reads or writes it.
  - `rationale` (research.py's raw-candidate field) is not persisted anywhere and is not used by this module's prompt.
- **A design is only ever image-generated once per approved candidate** (CLAUDE.md hard constraint) — enforced by construction: `generate_for_candidate` is the only thing in the whole pipeline that ever calls `replicate_client.generate_image`, and nothing later than the primary-group approval is allowed to call it again. This plan does not build that later guard (no `critic_pass.py` yet) — it only builds the function the future retry loop will call.
- **`generate_for_candidate` always makes a fresh Replicate call and overwrites `base_image_url`/`base_replicate_prediction_id`** — no per-attempt image history is kept on the candidate row (see design doc section 2).
- Every stage module in this pipeline is independently testable and gets its own commit per passing test group, per CLAUDE.md's "commit after each stage passes its manual M1 test."

---

## Task 1: `build_prompt()` — prompt construction

**Files:**
- Create: `pipeline/generate.py`
- Create: `tests/test_generate.py`

**Interfaces:**
- Produces: `build_prompt(candidate: dict, *, correction_note: str = None) -> str`. Consumed by Task 2's `generate_for_candidate`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_generate.py`:

```python
import pipeline.generate as generate


def test_build_prompt_includes_niche_and_no_go_list():
    candidate = {"niche": "monstera line art"}

    prompt = generate.build_prompt(candidate)

    assert "monstera line art" in prompt
    assert "named artist" in prompt
    assert "recognizable characters, franchises, or logos" in prompt
    assert "celebrity likeness" in prompt
    assert "hand-painted" in prompt


def test_build_prompt_appends_correction_note_when_retrying():
    candidate = {"niche": "moon phase print"}

    prompt = generate.build_prompt(candidate, correction_note="composition was off-center")

    assert "moon phase print" in prompt
    assert "Previous attempt was rejected for: composition was off-center" in prompt


def test_build_prompt_omits_correction_note_when_not_retrying():
    candidate = {"niche": "moon phase print"}

    prompt = generate.build_prompt(candidate)

    assert "Previous attempt was rejected" not in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_generate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.generate'`.

- [ ] **Step 3: Implement `pipeline/generate.py`**

```python
NICHE_STYLE_SCAFFOLD = (
    "A minimalist botanical/nature wall art print: {niche}. Clean composition, soft "
    "muted natural color palette, print-ready poster art, no text or watermarks."
)

# Hard no-go list per SPEC_v4.10.md section 2 / CLAUDE.md - baked into generation
# prompts as best-effort steering, not a guarantee. The critic pass (future stage)
# is the authoritative compliance gate that checks the rendered image itself.
NO_GO_LIST = (
    "Do not depict any named artist's style, recognizable characters, franchises, or "
    "logos. Do not imply celebrity likeness. Do not claim or resemble hand-painted or "
    "one-of-a-kind original artwork - this is a print reproduction."
)


def build_prompt(candidate: dict, *, correction_note: str = None) -> str:
    prompt = f"{NICHE_STYLE_SCAFFOLD.format(niche=candidate['niche'])} {NO_GO_LIST}"
    if correction_note:
        prompt += f" Previous attempt was rejected for: {correction_note}. Avoid this issue in the new image."
    return prompt
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_generate.py -v`
Expected: all 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/generate.py tests/test_generate.py
git commit -m "feat: add generate.py build_prompt with niche scaffold and no-go list"
```

---

## Task 2: `generate_for_candidate()` — single-candidate generation + DB write-back

**Files:**
- Modify: `pipeline/generate.py`
- Modify: `tests/test_generate.py`

**Interfaces:**
- Consumes: `build_prompt(candidate, correction_note=None)` (Task 1), `replicate_client.generate_image(prompt, api_token=None) -> {"image_url": str, "prediction_id": str}` (already merged, `pipeline/replicate_client.py`), `db.get_connection`/`db.init_db` (already merged, `pipeline/db.py`).
- Produces: `generate_for_candidate(conn, candidate_id: int, *, correction_note: str = None, api_token: str = None, now=None) -> dict` — returns `{"image_url": ..., "prediction_id": ...}`. Consumed by Task 3's `run_generate_cycle` and, later, `critic_pass.py`'s retry loop (not built in this plan).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_generate.py`:

```python
from datetime import datetime
from unittest.mock import patch

import pytest

import pipeline.db as db


def _fresh_conn(tmp_path):
    conn = db.get_connection(tmp_path / "test.sqlite3")
    db.init_db(conn)
    return conn


def _insert_pending_candidate(conn, niche="monstera line art", *, status="pending"):
    timestamp = "2026-07-09T09:00:00"
    cursor = conn.execute(
        """
        INSERT INTO candidates (created_at, niche, go_hold_kill, status, updated_at)
        VALUES (?, ?, 'go', ?, ?)
        """,
        (timestamp, niche, status, timestamp),
    )
    conn.commit()
    return cursor.lastrowid


def test_generate_for_candidate_calls_replicate_and_writes_image_back(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_pending_candidate(conn, niche="monstera line art")
    captured = {}

    def fake_generate_image(prompt, *, api_token=None):
        captured["prompt"] = prompt
        captured["api_token"] = api_token
        return {"image_url": "https://replicate.delivery/out.png", "prediction_id": "pred123"}

    with patch("pipeline.generate.replicate_client.generate_image", side_effect=fake_generate_image):
        result = generate.generate_for_candidate(
            conn, candidate_id, api_token="test-token", now=datetime(2026, 7, 9, 10, 0, 0)
        )

    assert result == {"image_url": "https://replicate.delivery/out.png", "prediction_id": "pred123"}
    assert "monstera line art" in captured["prompt"]
    assert captured["api_token"] == "test-token"

    row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    assert row["base_image_url"] == "https://replicate.delivery/out.png"
    assert row["base_replicate_prediction_id"] == "pred123"
    assert row["status"] == "generating"
    assert row["updated_at"] == "2026-07-09T10:00:00"
    conn.close()


def test_generate_for_candidate_passes_correction_note_into_prompt(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_pending_candidate(conn, niche="moon phase print", status="generating")
    captured = {}

    def fake_generate_image(prompt, *, api_token=None):
        captured["prompt"] = prompt
        return {"image_url": "https://replicate.delivery/retry.png", "prediction_id": "pred456"}

    with patch("pipeline.generate.replicate_client.generate_image", side_effect=fake_generate_image):
        generate.generate_for_candidate(
            conn, candidate_id, correction_note="composition was off-center",
            now=datetime(2026, 7, 9, 11, 0, 0),
        )

    assert "Previous attempt was rejected for: composition was off-center" in captured["prompt"]

    row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    assert row["base_image_url"] == "https://replicate.delivery/retry.png"
    conn.close()


def test_generate_for_candidate_raises_on_unknown_candidate_id(tmp_path):
    conn = _fresh_conn(tmp_path)

    with pytest.raises(ValueError, match="999"):
        generate.generate_for_candidate(conn, 999)

    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_generate.py -v`
Expected: FAIL — `generate_for_candidate` doesn't exist yet (`AttributeError`).

- [ ] **Step 3: Implement**

Add to `pipeline/generate.py` (add these imports at the top of the file):

```python
from datetime import datetime

import pipeline.replicate_client as replicate_client
```

Add the function:

```python
def generate_for_candidate(conn, candidate_id: int, *, correction_note: str = None,
                            api_token: str = None, now=None) -> dict:
    row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    if row is None:
        raise ValueError(f"No candidate with id {candidate_id}")

    prompt = build_prompt(dict(row), correction_note=correction_note)
    result = replicate_client.generate_image(prompt, api_token=api_token)

    timestamp = (now or datetime.utcnow()).isoformat()
    conn.execute(
        """
        UPDATE candidates
        SET base_image_url = ?, base_replicate_prediction_id = ?, status = 'generating', updated_at = ?
        WHERE id = ?
        """,
        (result["image_url"], result["prediction_id"], timestamp, candidate_id),
    )
    conn.commit()
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_generate.py -v`
Expected: all 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/generate.py tests/test_generate.py
git commit -m "feat: add generate.py generate_for_candidate DB read/write around Replicate call"
```

---

## Task 3: `run_generate_cycle()` — batch orchestrator

**Files:**
- Modify: `pipeline/generate.py`
- Modify: `tests/test_generate.py`

**Interfaces:**
- Consumes: `generate_for_candidate(conn, candidate_id, ...)` (Task 2).
- Produces: `run_generate_cycle(conn, *, api_token: str = None, now=None) -> list[int]` — the module's public entry point, to be called by the not-yet-built twice-daily batch orchestrator after `research.run_research_cycle`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_generate.py`:

```python
def test_run_generate_cycle_processes_all_pending_candidates_and_skips_others(tmp_path):
    conn = _fresh_conn(tmp_path)
    pending_id_1 = _insert_pending_candidate(conn, niche="monstera line art", status="pending")
    pending_id_2 = _insert_pending_candidate(conn, niche="moon phase print", status="pending")
    abandoned_id = _insert_pending_candidate(conn, niche="saturated term", status="abandoned")

    call_count = {"n": 0}

    def fake_generate_image(prompt, *, api_token=None):
        call_count["n"] += 1
        return {"image_url": f"https://replicate.delivery/out{call_count['n']}.png", "prediction_id": f"pred{call_count['n']}"}

    with patch("pipeline.generate.replicate_client.generate_image", side_effect=fake_generate_image):
        processed_ids = generate.run_generate_cycle(conn, now=datetime(2026, 7, 9, 12, 0, 0))

    assert sorted(processed_ids) == sorted([pending_id_1, pending_id_2])
    assert call_count["n"] == 2

    row_1 = conn.execute("SELECT * FROM candidates WHERE id = ?", (pending_id_1,)).fetchone()
    row_2 = conn.execute("SELECT * FROM candidates WHERE id = ?", (pending_id_2,)).fetchone()
    abandoned_row = conn.execute("SELECT * FROM candidates WHERE id = ?", (abandoned_id,)).fetchone()

    assert row_1["status"] == "generating"
    assert row_1["base_image_url"] is not None
    assert row_2["status"] == "generating"
    assert row_2["base_image_url"] is not None
    assert abandoned_row["status"] == "abandoned"
    assert abandoned_row["base_image_url"] is None
    conn.close()


def test_run_generate_cycle_returns_empty_list_when_no_pending_candidates(tmp_path):
    conn = _fresh_conn(tmp_path)
    _insert_pending_candidate(conn, niche="saturated term", status="abandoned")

    processed_ids = generate.run_generate_cycle(conn)

    assert processed_ids == []
    conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_generate.py -v`
Expected: FAIL — `run_generate_cycle` doesn't exist yet (`AttributeError`).

- [ ] **Step 3: Implement**

Add to `pipeline/generate.py`:

```python
def run_generate_cycle(conn, *, api_token: str = None, now=None) -> list:
    pending_ids = [
        row["id"] for row in conn.execute(
            "SELECT id FROM candidates WHERE status = 'pending' ORDER BY id"
        ).fetchall()
    ]
    for candidate_id in pending_ids:
        generate_for_candidate(conn, candidate_id, api_token=api_token, now=now)
    return pending_ids
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_generate.py -v`
Expected: all 8 PASS.

- [ ] **Step 5: Run the full test suite to confirm nothing else broke**

Run: `python -m pytest -v`
Expected: all PASS (db, config, http, gelato, replicate, telegram, etsy, anthropic, research, generate suites).

- [ ] **Step 6: Commit**

```bash
git add pipeline/generate.py tests/test_generate.py
git commit -m "feat: add generate.py run_generate_cycle batch orchestrator"
```

---

## Self-Review Notes

- **Spec coverage:** function signatures (Task 1 + 2 + 3), research.py consumption via `status='pending'` selection (Task 3), the future critic-pass retry hook — `generate_for_candidate` callable directly with `correction_note`, always a fresh Replicate call (Task 2) — prompt construction and no-go-list enforcement split (Task 1) are all covered, matching `docs/superpowers/specs/2026-07-09-generate-stage-design.md` sections 1-3. Section 4's four decisions (portrait-only, combined status check, rationale left out, style_theme_tags deferred) are all either directly implemented (no orientation/status/column code exists) or explicitly not built, per the design doc — no task contradicts them.
- **Placeholder scan:** no TBD/"add error handling"/"similar to Task N" language. Every step has concrete, runnable code.
- **Type consistency:** `build_prompt(candidate: dict, ...)` (Task 1) is called identically in Task 2 with `dict(row)` from a `sqlite3.Row` (works because `db.get_connection` sets `conn.row_factory = sqlite3.Row`, confirmed in `pipeline/db.py:9`). `generate_for_candidate`'s signature (Task 2) matches its only call site in Task 3 (`run_generate_cycle`) exactly — same keyword names (`api_token`, `now`).
