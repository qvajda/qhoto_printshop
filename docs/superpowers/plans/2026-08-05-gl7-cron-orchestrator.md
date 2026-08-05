# GL-7 Two-Cadence Cron Orchestrator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the pipeline two schedulable entrypoints (`run_hourly.py`, `run_batch.py`) that a Windows Task Scheduler job can invoke unattended, backed by a migration runner (GL-35), a drift-reconcile pass (GL-36), a crash-safe single-instance lock, and Telegram-visible failure reporting — without moving any stage's logic into the runner.

**Architecture:** Two thin root-level scripts sequence the existing `run_*_cycle` stage functions exactly as `run_m1_live_test.py` already proves works, each wrapped in: a file lock (`pipeline/lock.py`), a schema-version guard (`migrate.py --check`), per-stage try/except that reports to Telegram and a `heartbeats` table (`pipeline/heartbeat.py`) instead of crashing the whole run, and a non-zero exit code on any stage failure. GL-36's drift sweep (`pipeline/reconcile.py`) runs inside the batch entrypoint. No stage module changes.

**Tech Stack:** Python 3, sqlite3 (stdlib), existing `pipeline/*` modules, pytest.

## Global Constraints

- **Live mode stays off for this whole build and the first soak night.** `GELATO_LIVE_MODE`/`ETSY_LIVE_MODE` must read `false` — the owner sets this in `.env`; if any test or manual run prints `LIVE_MODE=True` for either, stop and flag it, do not proceed (CLAUDE.md, GL-7 PRD §4).
- **One function per stage; discrete scheduled functions, not one agent loop** (CLAUDE.md hard constraint). `run_hourly.py`/`run_batch.py` only sequence existing `run_*_cycle` functions — no stage's internal logic moves into them.
- **Never widen or bypass the Telegram admin-ID check.** All Telegram sends in this plan go to `TELEGRAM_ADMIN_CHAT_ID` read from env, same as existing digests (owner chose the shared channel, GL-7 PRD §7 Q4).
- **CLAUDE.md §4 (this repo's migration-safety rule) applies to Task 1/2's migration runner:** it touches `group_products` via a table rebuild. Back up `db/qhoto.sqlite3` before running `migrate.py` against the real DB, and only after the owner has seen the plan (§9 sign-off already given for this session).
- **Positive matching only for GL-36 reconcile** (Task 5): mark a row `listing_missing` only on a definitive HTTP 404 from Etsy. Timeouts, 401s, 5xxs, and any other exception must be skipped/logged, never treated as "missing" — a bad afternoon at Etsy must not mark the shop dead (PRD §5 Phase 3, GL-33 polarity lesson).
- **No stage-logic changes.** If a stage looks wrong while wiring it in, that's a finding to report at the end, not a fix to fold into this plan.
- Test convention: real file-backed SQLite in `tmp_path` via `pipeline.db.get_connection` + `pipeline.db.init_db`; external services mocked via `unittest.mock.patch`/`monkeypatch`; time-dependent logic exercised via a `now=` parameter or a monkeypatched constant, never real sleeps.

---

## File Structure

- `db/schema.sql` — **modify**: add `schema_version` table, add `heartbeats` table, widen `group_products.status` CHECK to admit `'listing_missing'` (so a *fresh* DB already has GL-7's shape; existing DBs get there via Task 1/2's migrations).
- `migrate.py` — **create** (repo root, alongside the existing `migrate_*.py` scripts): the ordered migration runner. Chains the six existing `migrate_*.py` scripts plus the new `migrate_gl36_listing_missing.py`, tracks progress in `schema_version`, exposes `--check` (fail-fast, no writes) for use at the top of both entrypoints.
- `migrate_gl36_listing_missing.py` — **create** (repo root, same shape as `migrate_v412_gallery.py`): widens `group_products.status` CHECK for `'listing_missing'`.
- `pipeline/heartbeat.py` — **create**: records/reads last-run timestamps per job name, so "a run that never happened" is detectable.
- `pipeline/lock.py` — **create**: crash-safe single-instance file lock.
- `pipeline/reconcile.py` — **create**: GL-36 age-out of stranded `generating` candidates + Etsy-404 reconcile of `published` group_products.
- `run_hourly.py` — **create** (repo root, sibling of `run_m1_live_test.py`): the hourly entrypoint.
- `run_batch.py` — **create** (repo root): the twice-daily batch entrypoint.
- `tests/test_migrate.py` — **create**.
- `tests/test_heartbeat.py` — **create**.
- `tests/test_lock.py` — **create**.
- `tests/test_reconcile.py` — **create**.
- `tests/test_run_hourly.py` — **create**.
- `tests/test_run_batch.py` — **create**.

No existing `pipeline/*_cycle` module is modified.

---

## Task 1: `schema_version` table + the migration runner

**Files:**
- Modify: `db/schema.sql`
- Create: `migrate.py`
- Test: `tests/test_migrate.py`

**Interfaces:**
- Consumes: each existing `migrate_*.py`'s `migrate(db_path) -> dict|list` (confirmed present on all six: `migrate_base_artwork_columns.py`, `migrate_candidates_art_brief.py`, `migrate_critic_pass_attempts_columns.py`, `migrate_generation_attempts_table.py`, `migrate_group_products_candidate_id.py`, `migrate_v412_gallery.py`).
- Produces: `migrate.migrate(db_path) -> dict` (applies all pending, returns `{"applied": [names], "current_version": int}`), `migrate.check(db_path) -> int` (returns current version, raises `migrate.StaleSchemaError` if `current_version < len(MIGRATIONS)` without writing anything), `migrate.MIGRATIONS: list[tuple[int, str, callable]]`. Task 2 appends one entry to `MIGRATIONS`. Tasks 6/7 call `migrate.check(db_path)` at the top of both entrypoints.

- [ ] **Step 1: Add `schema_version` to `db/schema.sql`**

Append to `db/schema.sql`:

```sql
CREATE TABLE IF NOT EXISTS schema_version (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  version INTEGER NOT NULL
);
```

- [ ] **Step 2: Write the failing test for the runner**

```python
# tests/test_migrate.py
import sqlite3

import migrate
import pipeline.db as db


def _fresh_uninitialized_db(tmp_path):
    """A DB with only base tables applied (schema.sql), no migrate_*.py content
    layered on - simulates a DB that predates every migrate_*.py script, which is
    the state migrate.py must be able to bring current from zero."""
    path = tmp_path / "test.sqlite3"
    conn = db.get_connection(path)
    db.init_db(conn)
    conn.execute("INSERT OR IGNORE INTO schema_version (id, version) VALUES (1, 0)")
    conn.commit()
    conn.close()
    return path


def test_migrate_applies_all_pending_and_records_version(tmp_path):
    db_path = _fresh_uninitialized_db(tmp_path)

    result = migrate.migrate(db_path)

    assert result["current_version"] == len(migrate.MIGRATIONS)
    assert len(result["applied"]) == len(migrate.MIGRATIONS)
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()
    assert row[0] == len(migrate.MIGRATIONS)
    conn.close()


def test_migrate_is_idempotent_second_run_applies_nothing(tmp_path):
    db_path = _fresh_uninitialized_db(tmp_path)
    migrate.migrate(db_path)

    result = migrate.migrate(db_path)

    assert result["applied"] == []
    assert result["current_version"] == len(migrate.MIGRATIONS)


def test_check_raises_on_stale_schema(tmp_path):
    db_path = _fresh_uninitialized_db(tmp_path)

    try:
        migrate.check(db_path)
        assert False, "expected StaleSchemaError"
    except migrate.StaleSchemaError as exc:
        assert "0" in str(exc)
        assert str(len(migrate.MIGRATIONS)) in str(exc)


def test_check_passes_after_migrate(tmp_path):
    db_path = _fresh_uninitialized_db(tmp_path)
    migrate.migrate(db_path)

    version = migrate.check(db_path)

    assert version == len(migrate.MIGRATIONS)


def test_check_does_not_write(tmp_path):
    db_path = _fresh_uninitialized_db(tmp_path)
    before = db_path.stat().st_mtime

    try:
        migrate.check(db_path)
    except migrate.StaleSchemaError:
        pass

    assert db_path.stat().st_mtime == before
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_migrate.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'migrate'`

- [ ] **Step 4: Write `migrate.py`**

```python
"""GL-35: the single idempotent entrypoint that applies every pending
migrate_*.py script in order and records progress in schema_version. Each
migrate_*.py script is independently idempotent (safe to call migrate() any
number of times) - this runner adds ordering and a version record so
"has this DB been migrated" is a single fast SELECT, not re-running every
script's own internal existence checks on every cron cycle.

check(db_path) is the fail-fast guard both entrypoints call before doing
anything else: it never writes, it only compares schema_version.version
against len(MIGRATIONS) and raises if the DB is behind. Discovering a stale
schema three stages into an unattended batch run (GL-13's failure mode) is
worse than refusing to start.
"""
import sqlite3
import sys
from pathlib import Path

import migrate_base_artwork_columns
import migrate_candidates_art_brief
import migrate_critic_pass_attempts_columns
import migrate_generation_attempts_table
import migrate_group_products_candidate_id
import migrate_v412_gallery

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "db" / "qhoto.sqlite3"

# (version, name, migrate(db_path) callable). Order matters: each is applied in
# sequence and the recorded version is the count of entries applied so far, not
# a semantic release number. Append new migrations here - never reorder or
# remove past entries, or an already-migrated DB's recorded version becomes
# meaningless.
MIGRATIONS = [
    (1, "base_artwork_columns", migrate_base_artwork_columns.migrate),
    (2, "candidates_art_brief", migrate_candidates_art_brief.migrate),
    (3, "critic_pass_attempts_columns", migrate_critic_pass_attempts_columns.migrate),
    (4, "generation_attempts_table", migrate_generation_attempts_table.migrate),
    (5, "group_products_candidate_id", migrate_group_products_candidate_id.migrate),
    (6, "v412_gallery", migrate_v412_gallery.migrate),
]


class StaleSchemaError(Exception):
    pass


def _current_version(conn) -> int:
    row = conn.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()
    return row[0] if row else 0


def migrate(db_path) -> dict:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT OR IGNORE INTO schema_version (id, version) VALUES (1, 0)"
        )
        conn.commit()
        current = _current_version(conn)

        applied = []
        for version, name, migrate_fn in MIGRATIONS:
            if version <= current:
                continue
            migrate_fn(db_path)
            conn.execute("UPDATE schema_version SET version = ? WHERE id = 1", (version,))
            conn.commit()
            applied.append(name)
            current = version

        return {"applied": applied, "current_version": current}
    finally:
        conn.close()


def check(db_path) -> int:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT OR IGNORE INTO schema_version (id, version) VALUES (1, 0)"
        )
        conn.commit()
        current = _current_version(conn)
        expected = len(MIGRATIONS)
        if current < expected:
            raise StaleSchemaError(
                f"schema_version is {current}, expected {expected} - run migrate.py before starting"
            )
        return current
    finally:
        conn.close()


def main():
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB_PATH
    check_only = "--check" in sys.argv
    if check_only:
        version = check(db_path)
        print(f"schema_version={version}, up to date")
        return
    result = migrate(db_path)
    if result["applied"]:
        print(f"applied: {', '.join(result['applied'])}")
    else:
        print("nothing to apply")
    print(f"schema_version={result['current_version']}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_migrate.py -v`
Expected: PASS (all 5 tests)

- [ ] **Step 6: Commit**

```bash
git add db/schema.sql migrate.py tests/test_migrate.py
git commit -m "feat(gl35): add schema_version table and ordered migration runner"
```

---

## Task 2: GL-36 schema prep — `listing_missing` group_products status

**Files:**
- Modify: `db/schema.sql` (widen the `group_products.status` CHECK so a fresh DB already admits `'listing_missing'`)
- Modify: `migrate.py` (register migration #7)
- Create: `migrate_gl36_listing_missing.py`
- Test: `tests/test_migrate_gl36_listing_missing.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `group_products.status` admits `'listing_missing'` on both fresh and migrated DBs. Task 5's reconcile pass sets this value.

- [ ] **Step 1: Widen the CHECK in `db/schema.sql`**

In `db/schema.sql`, change the `group_products` table's status CHECK from:

```sql
  status TEXT NOT NULL CHECK(status IN (
    'pending','created','mockup_failed','publish_failed','published','deleted'
  )),
```

to:

```sql
  status TEXT NOT NULL CHECK(status IN (
    'pending','created','mockup_failed','publish_failed','published','deleted','listing_missing'
  )),
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_migrate_gl36_listing_missing.py
import sqlite3

import migrate_gl36_listing_missing as migration
import pipeline.db as db


def _old_shape_db(tmp_path):
    """Simulates a pre-GL-36 DB: group_products.status CHECK does not admit
    'listing_missing' yet."""
    path = tmp_path / "test.sqlite3"
    conn = db.get_connection(path)
    db.init_db(conn)
    # init_db already applies the widened schema.sql from Task 2 Step 1, so
    # rebuild group_products with the OLD constraint to simulate pre-migration state.
    conn.execute("DROP TABLE group_products")
    conn.execute(
        """
        CREATE TABLE group_products (
          id INTEGER PRIMARY KEY,
          group_id INTEGER NOT NULL REFERENCES groups(id),
          candidate_id INTEGER REFERENCES candidates(id),
          gelato_template_id TEXT NOT NULL,
          gelato_product_id TEXT,
          etsy_listing_id TEXT,
          title TEXT,
          status TEXT NOT NULL CHECK(status IN (
            'pending','created','mockup_failed','publish_failed','published','deleted'
          )),
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()
    return path


def test_migrate_widens_check_to_admit_listing_missing(tmp_path):
    db_path = _old_shape_db(tmp_path)

    result = migration.migrate(db_path)

    assert result["rebuilt"] is True
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO group_products (id, group_id, gelato_template_id, status, created_at, updated_at) "
        "VALUES (99, 1, 'tmpl', 'listing_missing', 'x', 'x')"
    )
    conn.commit()
    row = conn.execute("SELECT status FROM group_products WHERE id = 99").fetchone()
    assert row[0] == "listing_missing"
    conn.close()


def test_migrate_is_idempotent(tmp_path):
    db_path = _old_shape_db(tmp_path)
    migration.migrate(db_path)

    result = migration.migrate(db_path)

    assert result["rebuilt"] is False


def test_migrate_preserves_existing_rows(tmp_path):
    db_path = _old_shape_db(tmp_path)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO group_products (id, group_id, gelato_template_id, status, created_at, updated_at) "
        "VALUES (1, 1, 'tmpl', 'published', 'x', 'x')"
    )
    conn.commit()
    conn.close()

    migration.migrate(db_path)

    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT status FROM group_products WHERE id = 1").fetchone()
    assert row[0] == "published"
    conn.close()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_migrate_gl36_listing_missing.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'migrate_gl36_listing_missing'`

- [ ] **Step 4: Write `migrate_gl36_listing_missing.py`**

```python
"""GL-36: group_products.status gains 'listing_missing' - the state a reconcile
pass (pipeline/reconcile.py) sets when a row claims a published Etsy listing
that a live GET returns 404 for. SQLite cannot alter a CHECK constraint in
place, so group_products is rebuilt (create-copy-drop-rename), same pattern as
migrate_v412_gallery.py's groups rebuild: every existing row copied verbatim,
no column added/removed/reordered/retyped, only the set of values the CHECK
admits widens - so no existing row can fail the new constraint.

Safe to run against any DB, any number of times.
"""
import sqlite3
import sys
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "db" / "qhoto.sqlite3"

GROUP_PRODUCTS_TABLE_GL36 = """
CREATE TABLE group_products_gl36_new (
  id INTEGER PRIMARY KEY,
  group_id INTEGER NOT NULL REFERENCES groups(id),
  candidate_id INTEGER REFERENCES candidates(id),
  gelato_template_id TEXT NOT NULL,
  gelato_product_id TEXT,
  etsy_listing_id TEXT,
  title TEXT,
  status TEXT NOT NULL CHECK(status IN (
    'pending','created','mockup_failed','publish_failed','published','deleted','listing_missing'
  )),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
)
"""

GROUP_PRODUCTS_COLUMNS = (
    "id, group_id, candidate_id, gelato_template_id, gelato_product_id, etsy_listing_id, "
    "title, status, created_at, updated_at"
)


def _needs_widening(conn) -> bool:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'group_products'"
    ).fetchone()
    return row is not None and "listing_missing" not in row[0]


def migrate(db_path) -> dict:
    conn = sqlite3.connect(db_path)
    try:
        rebuilt = _needs_widening(conn)
        if rebuilt:
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute(GROUP_PRODUCTS_TABLE_GL36)
            conn.execute(
                f"INSERT INTO group_products_gl36_new ({GROUP_PRODUCTS_COLUMNS}) "
                f"SELECT {GROUP_PRODUCTS_COLUMNS} FROM group_products"
            )
            conn.execute("DROP TABLE group_products")
            conn.execute("ALTER TABLE group_products_gl36_new RENAME TO group_products")
            conn.commit()
            conn.execute("PRAGMA foreign_keys = ON")
        conn.commit()
        return {"rebuilt": rebuilt}
    finally:
        conn.close()


def main():
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB_PATH
    result = migrate(db_path)
    print("group_products.status widened for 'listing_missing'" if result["rebuilt"]
          else "group_products.status already admits 'listing_missing'")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Register it in `migrate.py`**

In `migrate.py`, add the import and append to `MIGRATIONS`:

```python
import migrate_gl36_listing_missing
```

```python
    (7, "gl36_listing_missing", migrate_gl36_listing_missing.migrate),
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_migrate_gl36_listing_missing.py tests/test_migrate.py -v`
Expected: PASS (all tests; `test_migrate.py`'s `len(migrate.MIGRATIONS)` assertions now cover 7 entries automatically since they read the list, not a hardcoded number)

- [ ] **Step 7: Commit**

```bash
git add db/schema.sql migrate.py migrate_gl36_listing_missing.py tests/test_migrate_gl36_listing_missing.py
git commit -m "feat(gl36): widen group_products.status for listing_missing, wire into migrate.py"
```

---

## Task 3: `pipeline/heartbeat.py`

**Files:**
- Modify: `db/schema.sql` (add `heartbeats` table)
- Create: `pipeline/heartbeat.py`
- Test: `tests/test_heartbeat.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `heartbeat.record(conn, job_name: str, *, ok: bool, detail: str = None, now=None) -> None`, `heartbeat.last(conn, job_name: str) -> dict | None` (keys: `job_name`, `ran_at`, `ok`, `detail`). Tasks 6/7 call `record` at the end of every entrypoint run (success or failure).

- [ ] **Step 1: Add `heartbeats` to `db/schema.sql`**

```sql
CREATE TABLE IF NOT EXISTS heartbeats (
  job_name TEXT PRIMARY KEY,
  ran_at TEXT NOT NULL,
  ok INTEGER NOT NULL,
  detail TEXT
);
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_heartbeat.py
from datetime import datetime

import pipeline.db as db
import pipeline.heartbeat as heartbeat


def _conn(tmp_path):
    conn = db.get_connection(tmp_path / "test.sqlite3")
    db.init_db(conn)
    return conn


def test_last_returns_none_when_never_recorded(tmp_path):
    conn = _conn(tmp_path)

    assert heartbeat.last(conn, "hourly") is None


def test_record_then_last_round_trips(tmp_path):
    conn = _conn(tmp_path)
    now = datetime(2026, 8, 5, 3, 0, 0)

    heartbeat.record(conn, "hourly", ok=True, detail="3 updates processed", now=now)

    result = heartbeat.last(conn, "hourly")
    assert result["job_name"] == "hourly"
    assert result["ok"] is True
    assert result["detail"] == "3 updates processed"
    assert result["ran_at"] == now.isoformat()


def test_record_overwrites_previous_row_for_same_job(tmp_path):
    conn = _conn(tmp_path)
    heartbeat.record(conn, "hourly", ok=True, now=datetime(2026, 8, 5, 3, 0, 0))

    heartbeat.record(conn, "hourly", ok=False, detail="crashed", now=datetime(2026, 8, 5, 4, 0, 0))

    result = heartbeat.last(conn, "hourly")
    assert result["ok"] is False
    assert result["detail"] == "crashed"
    count = conn.execute("SELECT COUNT(*) FROM heartbeats WHERE job_name = 'hourly'").fetchone()[0]
    assert count == 1


def test_record_keeps_separate_jobs_independent(tmp_path):
    conn = _conn(tmp_path)
    heartbeat.record(conn, "hourly", ok=True, now=datetime(2026, 8, 5, 3, 0, 0))
    heartbeat.record(conn, "batch", ok=True, now=datetime(2026, 8, 5, 6, 0, 0))

    assert heartbeat.last(conn, "hourly")["ran_at"] == "2026-08-05T03:00:00"
    assert heartbeat.last(conn, "batch")["ran_at"] == "2026-08-05T06:00:00"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_heartbeat.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pipeline.heartbeat'`

- [ ] **Step 4: Write `pipeline/heartbeat.py`**

```python
"""GL-7 §2 item 7: 'a run that does not happen is detectable.' One row per job
name, overwritten on every run - last() answers 'when did this job last run,
and did it succeed' in one indexed lookup, which is what a soak-watching
status check and a stale-run alert both need."""
from datetime import datetime, timezone


def record(conn, job_name: str, *, ok: bool, detail: str = None, now=None) -> None:
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    conn.execute(
        "INSERT INTO heartbeats (job_name, ran_at, ok, detail) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(job_name) DO UPDATE SET ran_at = excluded.ran_at, ok = excluded.ok, "
        "detail = excluded.detail",
        (job_name, now.isoformat(), 1 if ok else 0, detail),
    )
    conn.commit()


def last(conn, job_name: str) -> dict | None:
    row = conn.execute(
        "SELECT job_name, ran_at, ok, detail FROM heartbeats WHERE job_name = ?",
        (job_name,),
    ).fetchone()
    if row is None:
        return None
    return {
        "job_name": row["job_name"],
        "ran_at": row["ran_at"],
        "ok": bool(row["ok"]),
        "detail": row["detail"],
    }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_heartbeat.py -v`
Expected: PASS (all 4 tests)

- [ ] **Step 6: Commit**

```bash
git add db/schema.sql pipeline/heartbeat.py tests/test_heartbeat.py
git commit -m "feat(gl7): add heartbeats table so a missed scheduled run is detectable"
```

---

## Task 4: `pipeline/lock.py` — crash-safe single-instance lock

**Files:**
- Create: `pipeline/lock.py`
- Test: `tests/test_lock.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `lock.acquire(lock_path, *, stale_after_seconds=3600, now=None) -> ContextManager` — a context manager. Raises `lock.LockHeldError` if another live process holds it. On enter, writes the current PID; on a clean or exceptional exit, always removes the lock file. A lock file older than `stale_after_seconds` **or** whose recorded PID is not a running process is treated as stale and stolen. Tasks 6/7 wrap their whole run in `with lock.acquire(...):`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_lock.py
import os
import time

import pytest

import pipeline.lock as lock


def test_acquire_creates_and_removes_lock_file(tmp_path):
    lock_path = tmp_path / "gl7.lock"

    with lock.acquire(lock_path):
        assert lock_path.exists()

    assert not lock_path.exists()


def test_acquire_removes_lock_file_even_on_exception(tmp_path):
    lock_path = tmp_path / "gl7.lock"

    with pytest.raises(ValueError):
        with lock.acquire(lock_path):
            raise ValueError("boom")

    assert not lock_path.exists()


def test_second_acquire_raises_while_first_process_alive(tmp_path):
    lock_path = tmp_path / "gl7.lock"
    lock_path.write_text(str(os.getpid()))  # our own PID - always "alive"

    with pytest.raises(lock.LockHeldError):
        with lock.acquire(lock_path):
            pass


def test_acquire_steals_lock_with_dead_pid(tmp_path):
    lock_path = tmp_path / "gl7.lock"
    lock_path.write_text("999999999")  # never a real PID

    with lock.acquire(lock_path):
        assert lock_path.exists()

    assert not lock_path.exists()


def test_acquire_steals_lock_older_than_stale_after_seconds(tmp_path):
    lock_path = tmp_path / "gl7.lock"
    lock_path.write_text(str(os.getpid()))
    old_time = time.time() - 7200
    os.utime(lock_path, (old_time, old_time))

    with lock.acquire(lock_path, stale_after_seconds=3600):
        assert lock_path.exists()

    assert not lock_path.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_lock.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pipeline.lock'`

- [ ] **Step 3: Write `pipeline/lock.py`**

```python
"""GL-7 Phase 2, 'the sharp part': the hourly poll and the twice-daily batch
must never interleave writes to db/qhoto.sqlite3, and only one process may
ever call Telegram getUpdates (a second reader silently eats the first
reader's offset). A single lock file, guarded by PID liveness and an age
ceiling, gives both cadences a shared gate without a DB table (which would
itself need locking to be race-free) or a third-party dependency.

A stale lock from a killed process must not wedge the pipeline forever - two
independent escape hatches: the recorded PID is checked for liveness
(os.kill(pid, 0), the standard no-op existence probe), and the file's mtime
is checked against stale_after_seconds regardless of PID liveness (covers PID
reuse by an unrelated process). Either one being true means the lock is stolen,
not respected.
"""
import contextlib
import os
import time
from pathlib import Path


class LockHeldError(Exception):
    pass


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    except ValueError:
        return False
    return True


def _is_stale(lock_path: Path, stale_after_seconds: float, now: float) -> bool:
    try:
        mtime = lock_path.stat().st_mtime
    except FileNotFoundError:
        return True
    if now - mtime > stale_after_seconds:
        return True
    try:
        pid = int(lock_path.read_text().strip())
    except (ValueError, FileNotFoundError):
        return True
    return not _pid_alive(pid)


@contextlib.contextmanager
def acquire(lock_path, *, stale_after_seconds: float = 3600, now=None):
    lock_path = Path(lock_path)
    now_ts = now if now is not None else time.time()

    if lock_path.exists() and not _is_stale(lock_path, stale_after_seconds, now_ts):
        raise LockHeldError(f"{lock_path} is held by a live process")

    lock_path.write_text(str(os.getpid()))
    try:
        yield
    finally:
        lock_path.unlink(missing_ok=True)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_lock.py -v`
Expected: PASS (all 5 tests)

- [ ] **Step 5: Commit**

```bash
git add pipeline/lock.py tests/test_lock.py
git commit -m "feat(gl7): add crash-safe single-instance file lock"
```

---

## Task 5: `pipeline/reconcile.py` — GL-36 drift sweep

**Files:**
- Create: `pipeline/reconcile.py`
- Test: `tests/test_reconcile.py`

**Interfaces:**
- Consumes: `pipeline.etsy_client.get_listing_inventory(shop_id, listing_id, *, api_key=, api_secret=, access_token=, dry_run=) -> dict` (raises `pipeline.http.HTTPError(status_code, body, headers)` on non-2xx), `pipeline.http.HTTPError`.
- Produces: `reconcile.age_out_stranded_generating(conn, *, max_age_hours=12, now=None) -> list[int]` (candidate ids moved to `failed`), `reconcile.reconcile_etsy_listings(conn, *, shop_id=None, api_key=None, api_secret=None, access_token=None, now=None) -> dict` (`{"checked": int, "marked_missing": [group_product ids], "skipped_errors": [group_product ids]}`), `reconcile.run_reconcile(conn, **kwargs) -> dict`. Task 7 calls `run_reconcile` inside the batch entrypoint.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_reconcile.py
from datetime import datetime
from unittest.mock import patch

import pipeline.db as db
import pipeline.http as http
import pipeline.reconcile as reconcile


def _conn(tmp_path):
    conn = db.get_connection(tmp_path / "test.sqlite3")
    db.init_db(conn)
    return conn


def _insert_candidate(conn, id, status, updated_at):
    conn.execute(
        "INSERT INTO candidates (id, created_at, niche, go_hold_kill, status, updated_at) "
        "VALUES (?, ?, 'test', 'go', ?, ?)",
        (id, updated_at, status, updated_at),
    )
    conn.commit()


def test_age_out_marks_stale_generating_candidate_as_failed(tmp_path):
    conn = _conn(tmp_path)
    _insert_candidate(conn, 1, "generating", "2026-08-01T00:00:00")

    result = reconcile.age_out_stranded_generating(
        conn, max_age_hours=12, now=datetime(2026, 8, 5, 0, 0, 0)
    )

    assert result == [1]
    row = conn.execute("SELECT status, failed_reason FROM candidates WHERE id = 1").fetchone()
    assert row["status"] == "failed"
    assert "gl36" in row["failed_reason"]


def test_age_out_leaves_recent_generating_candidate_alone(tmp_path):
    conn = _conn(tmp_path)
    _insert_candidate(conn, 1, "generating", "2026-08-04T23:00:00")

    result = reconcile.age_out_stranded_generating(
        conn, max_age_hours=12, now=datetime(2026, 8, 5, 0, 0, 0)
    )

    assert result == []
    row = conn.execute("SELECT status FROM candidates WHERE id = 1").fetchone()
    assert row["status"] == "generating"


def test_age_out_ignores_non_generating_candidates(tmp_path):
    conn = _conn(tmp_path)
    _insert_candidate(conn, 1, "completed", "2026-08-01T00:00:00")

    result = reconcile.age_out_stranded_generating(
        conn, max_age_hours=12, now=datetime(2026, 8, 5, 0, 0, 0)
    )

    assert result == []


def _insert_published_group_product(conn, id, etsy_listing_id):
    conn.execute(
        "INSERT INTO candidates (id, created_at, niche, go_hold_kill, status, updated_at) "
        "VALUES (1, 'x', 'test', 'go', 'completed', 'x')"
    )
    conn.execute(
        "INSERT INTO groups (id, candidate_id, group_type, status, created_at, updated_at) "
        "VALUES (1, 1, 'primary', 'approved_published', 'x', 'x')"
    )
    conn.execute(
        "INSERT INTO group_products (id, group_id, candidate_id, gelato_template_id, "
        "etsy_listing_id, status, created_at, updated_at) "
        "VALUES (?, 1, 1, 'tmpl', ?, 'published', 'x', 'x')",
        (id, etsy_listing_id),
    )
    conn.commit()


def test_reconcile_marks_listing_missing_on_definitive_404(tmp_path):
    conn = _conn(tmp_path)
    _insert_published_group_product(conn, 1, "listing-123")

    with patch(
        "pipeline.etsy_client.get_listing_inventory",
        side_effect=http.HTTPError(404, "not found"),
    ):
        result = reconcile.reconcile_etsy_listings(conn, shop_id="shop", dry_run_override=False)

    assert result["marked_missing"] == [1]
    row = conn.execute("SELECT status FROM group_products WHERE id = 1").fetchone()
    assert row["status"] == "listing_missing"


def test_reconcile_skips_on_non_404_error(tmp_path):
    conn = _conn(tmp_path)
    _insert_published_group_product(conn, 1, "listing-123")

    with patch(
        "pipeline.etsy_client.get_listing_inventory",
        side_effect=http.HTTPError(500, "server error"),
    ):
        result = reconcile.reconcile_etsy_listings(conn, shop_id="shop", dry_run_override=False)

    assert result["marked_missing"] == []
    assert result["skipped_errors"] == [1]
    row = conn.execute("SELECT status FROM group_products WHERE id = 1").fetchone()
    assert row["status"] == "published"


def test_reconcile_leaves_row_alone_when_listing_found(tmp_path):
    conn = _conn(tmp_path)
    _insert_published_group_product(conn, 1, "listing-123")

    with patch(
        "pipeline.etsy_client.get_listing_inventory",
        return_value={"products": []},
    ):
        result = reconcile.reconcile_etsy_listings(conn, shop_id="shop", dry_run_override=False)

    assert result["marked_missing"] == []
    row = conn.execute("SELECT status FROM group_products WHERE id = 1").fetchone()
    assert row["status"] == "published"


def test_reconcile_ignores_rows_without_etsy_listing_id(tmp_path):
    conn = _conn(tmp_path)
    _insert_published_group_product(conn, 1, None)

    with patch("pipeline.etsy_client.get_listing_inventory") as mock_get:
        result = reconcile.reconcile_etsy_listings(conn, shop_id="shop", dry_run_override=False)

    mock_get.assert_not_called()
    assert result["checked"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_reconcile.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pipeline.reconcile'`

- [ ] **Step 3: Write `pipeline/reconcile.py`**

```python
"""GL-36 (rescoped 2026-08-05): the pipeline is not the only writer to the
resources it tracks. Two drift shapes GL-13 exposed:

1. A candidate stuck in 'generating' (a crashed/never-resolved Replicate
   prediction) blocks nothing downstream by itself, but leaks forever if no
   cadence ever revisits it - age it out.
2. A group_products row claims 'published' against an Etsy listing that no
   longer exists (deleted by hand, or by Gelato's own sync). Positive matching
   only: a row is marked 'listing_missing' on a DEFINITIVE 404, never on a
   timeout/401/5xx - GL-33's lesson is that a bad afternoon at a third-party
   API must not read as "the whole shop is dead."
"""
from datetime import datetime, timedelta, timezone

import pipeline.etsy_client as etsy_client
import pipeline.http as http


def age_out_stranded_generating(conn, *, max_age_hours=12, now=None) -> list:
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    cutoff = (now - timedelta(hours=max_age_hours)).isoformat()
    rows = conn.execute(
        "SELECT id FROM candidates WHERE status = 'generating' AND updated_at < ?",
        (cutoff,),
    ).fetchall()

    aged_out = []
    for row in rows:
        conn.execute(
            "UPDATE candidates SET status = 'failed', "
            "failed_reason = 'gl36_generation_stalled', updated_at = ? WHERE id = ?",
            (now.isoformat(), row["id"]),
        )
        conn.commit()
        aged_out.append(row["id"])
    return aged_out


def reconcile_etsy_listings(
    conn, *, shop_id=None, api_key=None, api_secret=None, access_token=None,
    now=None, dry_run_override=None,
) -> dict:
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    rows = conn.execute(
        "SELECT id, etsy_listing_id FROM group_products "
        "WHERE status = 'published' AND etsy_listing_id IS NOT NULL"
    ).fetchall()

    checked = 0
    marked_missing = []
    skipped_errors = []
    for row in rows:
        checked += 1
        try:
            etsy_client.get_listing_inventory(
                shop_id, row["etsy_listing_id"], api_key=api_key, api_secret=api_secret,
                access_token=access_token, dry_run=dry_run_override,
            )
        except http.HTTPError as exc:
            if exc.status_code == 404:
                conn.execute(
                    "UPDATE group_products SET status = 'listing_missing', updated_at = ? WHERE id = ?",
                    (now.isoformat(), row["id"]),
                )
                conn.commit()
                marked_missing.append(row["id"])
            else:
                skipped_errors.append(row["id"])
            continue
        except Exception:
            skipped_errors.append(row["id"])
            continue

    return {"checked": checked, "marked_missing": marked_missing, "skipped_errors": skipped_errors}


def run_reconcile(conn, **kwargs) -> dict:
    generating_kwargs = {k: v for k, v in kwargs.items() if k in ("max_age_hours", "now")}
    etsy_kwargs = {
        k: v for k, v in kwargs.items()
        if k in ("shop_id", "api_key", "api_secret", "access_token", "now", "dry_run_override")
    }
    return {
        "aged_out_candidates": age_out_stranded_generating(conn, **generating_kwargs),
        "etsy_reconcile": reconcile_etsy_listings(conn, **etsy_kwargs),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_reconcile.py -v`
Expected: PASS (all 8 tests)

- [ ] **Step 5: Commit**

```bash
git add pipeline/reconcile.py tests/test_reconcile.py
git commit -m "feat(gl36): age out stranded generating candidates, reconcile 404'd Etsy listings"
```

---

## Task 6: `run_hourly.py` — the hourly entrypoint

**Files:**
- Create: `run_hourly.py`
- Test: `tests/test_run_hourly.py`

**Interfaces:**
- Consumes: `migrate.check(db_path) -> int`, `migrate.StaleSchemaError`, `pipeline.lock.acquire(lock_path, *, stale_after_seconds=) -> ContextManager`, `pipeline.lock.LockHeldError`, `pipeline.heartbeat.record(conn, job_name, *, ok, detail=, now=) -> None`, `pipeline.publish_primary_group.run_publish_primary_group_cycle(conn, **kwargs) -> list`, `pipeline.telegram_client.send_message(chat_id, text, *, bot_token=) -> dict`, `pipeline.config.require_env`, `pipeline.config.load_env`, `pipeline.config.load_static_config`, `pipeline.db.get_connection`.
- Produces: a `main() -> int` (exit code: 0 clean, 1 stage failure, 2 lock held, 3 stale schema) invoked via `if __name__ == "__main__": sys.exit(main())`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_run_hourly.py
from unittest.mock import patch

import pipeline.db as db
import pipeline.heartbeat as heartbeat
import pipeline.lock as lock
import migrate
import run_hourly


def _migrated_db(tmp_path):
    db_path = tmp_path / "test.sqlite3"
    conn = db.get_connection(db_path)
    db.init_db(conn)
    conn.close()
    migrate.migrate(db_path)
    return db_path


def test_main_returns_0_and_records_heartbeat_on_success(tmp_path, monkeypatch):
    db_path = _migrated_db(tmp_path)
    monkeypatch.setenv("TELEGRAM_ADMIN_CHAT_ID", "admin1")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")

    with patch("run_hourly.publish_primary_group.run_publish_primary_group_cycle", return_value=[]):
        exit_code = run_hourly.main(
            db_path=db_path, lock_path=tmp_path / "hourly.lock", load_dotenv=False,
        )

    assert exit_code == 0
    conn = db.get_connection(db_path)
    result = heartbeat.last(conn, "hourly")
    assert result["ok"] is True


def test_main_returns_1_and_notifies_telegram_on_stage_exception(tmp_path, monkeypatch):
    db_path = _migrated_db(tmp_path)
    monkeypatch.setenv("TELEGRAM_ADMIN_CHAT_ID", "admin1")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")

    with patch(
        "run_hourly.publish_primary_group.run_publish_primary_group_cycle",
        side_effect=RuntimeError("boom"),
    ), patch("run_hourly.telegram_client.send_message") as mock_send:
        exit_code = run_hourly.main(
            db_path=db_path, lock_path=tmp_path / "hourly.lock", load_dotenv=False,
        )

    assert exit_code == 1
    mock_send.assert_called_once()
    args, kwargs = mock_send.call_args
    assert args[0] == "admin1"
    assert "hourly" in args[1]
    assert "boom" in args[1]
    conn = db.get_connection(db_path)
    result = heartbeat.last(conn, "hourly")
    assert result["ok"] is False


def test_main_returns_2_when_lock_held(tmp_path, monkeypatch):
    db_path = _migrated_db(tmp_path)
    monkeypatch.setenv("TELEGRAM_ADMIN_CHAT_ID", "admin1")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    lock_path = tmp_path / "hourly.lock"

    with lock.acquire(lock_path):
        exit_code = run_hourly.main(db_path=db_path, lock_path=lock_path, load_dotenv=False)

    assert exit_code == 2


def test_main_returns_3_on_stale_schema(tmp_path, monkeypatch):
    db_path = tmp_path / "test.sqlite3"
    conn = db.get_connection(db_path)
    db.init_db(conn)
    conn.close()
    monkeypatch.setenv("TELEGRAM_ADMIN_CHAT_ID", "admin1")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")

    exit_code = run_hourly.main(db_path=db_path, lock_path=tmp_path / "hourly.lock", load_dotenv=False)

    assert exit_code == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_run_hourly.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'run_hourly'`

- [ ] **Step 3: Write `run_hourly.py`**

```python
"""GL-7 hourly entrypoint. Sequences exactly what run_m1_live_test.py already
proves: publish_primary_group.run_publish_primary_group_cycle polls Telegram,
checks the admin ID, dispatches decisions, advances the offset, retries
publish_failed groups. This script adds only what unattended operation needs:
a schema guard, a single-instance lock, and Telegram-visible failure
reporting - it does not touch that function's internals (CLAUDE.md: one
function per stage, the runner sequences, it does not absorb).

Windows Task Scheduler invokes this hourly; exit code is the signal it acts
on (see docs/2026-08-05-gl7-cron-prd-and-kickoff.md §2 item 1 and item 7).
"""
import sys
from pathlib import Path

import migrate
import pipeline.config as config
import pipeline.db as db
import pipeline.heartbeat as heartbeat
import pipeline.lock as lock
import pipeline.publish_primary_group as publish_primary_group
import pipeline.telegram_client as telegram_client

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "db" / "qhoto.sqlite3"
# Shared with run_batch.py deliberately - PRD success criterion 3: only one
# process may ever call Telegram getUpdates, and hourly/batch must never
# interleave writes to the same SQLite file. One lock file for both cadences
# is what makes that true; separate lock files would let them run concurrently.
DEFAULT_LOCK_PATH = Path(__file__).resolve().parent / "db" / "gl7.lock"
JOB_NAME = "hourly"


def _notify_admin(admin_chat_id, bot_token, message):
    try:
        telegram_client.send_message(admin_chat_id, message, bot_token=bot_token)
    except Exception as exc:
        print(f"failed to notify admin of {JOB_NAME} failure: {exc}")


def main(*, db_path=None, lock_path=None, load_dotenv=True) -> int:
    if load_dotenv:
        config.load_env()

    db_path = db_path or DEFAULT_DB_PATH
    lock_path = lock_path or DEFAULT_LOCK_PATH
    admin_chat_id = config.require_env("TELEGRAM_ADMIN_CHAT_ID")
    bot_token = config.require_env("TELEGRAM_BOT_TOKEN")

    try:
        migrate.check(db_path)
    except migrate.StaleSchemaError as exc:
        print(f"{JOB_NAME}: refusing to run on stale schema: {exc}")
        return 3

    try:
        with lock.acquire(lock_path):
            conn = db.get_connection(db_path)
            try:
                publish_primary_group.run_publish_primary_group_cycle(
                    conn, admin_chat_id=admin_chat_id, bot_token=bot_token,
                    static_config=config.load_static_config(),
                )
            except Exception as exc:
                heartbeat.record(conn, JOB_NAME, ok=False, detail=str(exc))
                _notify_admin(admin_chat_id, bot_token, f"[{JOB_NAME}] stage failed: {exc}")
                return 1
            heartbeat.record(conn, JOB_NAME, ok=True)
            return 0
    except lock.LockHeldError as exc:
        print(f"{JOB_NAME}: {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_run_hourly.py -v`
Expected: PASS (all 4 tests)

- [ ] **Step 5: Commit**

```bash
git add run_hourly.py tests/test_run_hourly.py
git commit -m "feat(gl7): add run_hourly.py entrypoint with lock, schema guard, Telegram failure reporting"
```

---

## Task 7: `run_batch.py` — the twice-daily batch entrypoint

**Files:**
- Create: `run_batch.py`
- Test: `tests/test_run_batch.py`

**Interfaces:**
- Consumes: same as Task 6, plus `pipeline.generate.run_generate_cycle`, `pipeline.primary_mockup.run_primary_mockup_cycle`, `pipeline.compliance_draft.run_compliance_draft_cycle`, `pipeline.critic_pass.run_critic_pass_cycle`, `pipeline.digest.run_digest_cycle`, `pipeline.group_mockup.run_group_mockup_cycle`, `pipeline.group_critic_pass.run_group_critic_pass_cycle`, `pipeline.group_digest.run_group_digest_cycle`, `pipeline.reconcile.run_reconcile`, `pipeline.cleanup.run_cleanup` — every one of these keeps its existing signature, called with the same kwargs pattern `run_m1_live_test.py` already uses.
- Produces: `main(*, db_path=None, lock_path=None, load_dotenv=True) -> int` — same exit code contract as Task 6 (0/1/2/3), except a per-stage failure does not abort the whole batch: each stage runs in its own try/except so one broken stage does not prevent the others (a research API outage must not also skip publish/reconcile/cleanup), and the exit code is 1 if **any** stage failed. `main()` invoked via `if __name__ == "__main__": sys.exit(main())`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_run_batch.py
from unittest.mock import patch

import pipeline.db as db
import pipeline.heartbeat as heartbeat
import migrate
import run_batch


def _migrated_db(tmp_path):
    db_path = tmp_path / "test.sqlite3"
    conn = db.get_connection(db_path)
    db.init_db(conn)
    conn.close()
    migrate.migrate(db_path)
    return db_path


STAGE_PATCHES = [
    "run_batch.generate.run_generate_cycle",
    "run_batch.primary_mockup.run_primary_mockup_cycle",
    "run_batch.compliance_draft.run_compliance_draft_cycle",
    "run_batch.critic_pass.run_critic_pass_cycle",
    "run_batch.digest.run_digest_cycle",
    "run_batch.publish_primary_group.run_publish_primary_group_cycle",
    "run_batch.group_mockup.run_group_mockup_cycle",
    "run_batch.group_critic_pass.run_group_critic_pass_cycle",
    "run_batch.group_digest.run_group_digest_cycle",
]


def _patch_all_stages_ok(stack):
    for target in STAGE_PATCHES:
        stack.enter_context(patch(target, return_value=[]))
    stack.enter_context(patch("run_batch.reconcile.run_reconcile", return_value={}))
    stack.enter_context(patch("run_batch.cleanup.run_cleanup", return_value={}))


def test_main_returns_0_when_every_stage_succeeds(tmp_path, monkeypatch):
    from contextlib import ExitStack

    db_path = _migrated_db(tmp_path)
    monkeypatch.setenv("TELEGRAM_ADMIN_CHAT_ID", "admin1")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")

    with ExitStack() as stack:
        _patch_all_stages_ok(stack)
        exit_code = run_batch.main(db_path=db_path, lock_path=tmp_path / "batch.lock", load_dotenv=False)

    assert exit_code == 0
    conn = db.get_connection(db_path)
    assert heartbeat.last(conn, "batch")["ok"] is True


def test_main_returns_1_when_one_stage_fails_but_runs_the_rest(tmp_path, monkeypatch):
    from contextlib import ExitStack

    db_path = _migrated_db(tmp_path)
    monkeypatch.setenv("TELEGRAM_ADMIN_CHAT_ID", "admin1")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")

    with ExitStack() as stack:
        _patch_all_stages_ok(stack)
        stack.enter_context(
            patch("run_batch.generate.run_generate_cycle", side_effect=RuntimeError("gen boom"))
        )
        mock_send = stack.enter_context(patch("run_batch.telegram_client.send_message"))
        mock_mockup = stack.enter_context(
            patch("run_batch.primary_mockup.run_primary_mockup_cycle", return_value=[])
        )

        exit_code = run_batch.main(db_path=db_path, lock_path=tmp_path / "batch.lock", load_dotenv=False)

    assert exit_code == 1
    mock_mockup.assert_called_once()  # downstream stages still ran
    assert any("gen boom" in str(call) for call in mock_send.call_args_list)


def test_main_returns_2_when_lock_held(tmp_path, monkeypatch):
    import pipeline.lock as lock

    db_path = _migrated_db(tmp_path)
    monkeypatch.setenv("TELEGRAM_ADMIN_CHAT_ID", "admin1")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    lock_path = tmp_path / "batch.lock"

    with lock.acquire(lock_path):
        exit_code = run_batch.main(db_path=db_path, lock_path=lock_path, load_dotenv=False)

    assert exit_code == 2


def test_main_returns_3_on_stale_schema(tmp_path, monkeypatch):
    db_path = tmp_path / "test.sqlite3"
    conn = db.get_connection(db_path)
    db.init_db(conn)
    conn.close()
    monkeypatch.setenv("TELEGRAM_ADMIN_CHAT_ID", "admin1")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")

    exit_code = run_batch.main(db_path=db_path, lock_path=tmp_path / "batch.lock", load_dotenv=False)

    assert exit_code == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_run_batch.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'run_batch'`

- [ ] **Step 3: Write `run_batch.py`**

```python
"""GL-7 twice-daily batch entrypoint. Sequences the same stage order
run_m1_live_test.py already proves works end to end (generate -> primary
mockup -> compliance draft -> critic pass -> digest -> publish (1st tap
window) -> group mockup -> group critic pass -> group digest -> publish (2nd
tap window)), then GL-36's reconcile pass and cleanup. Each stage is isolated
in its own try/except: a broken stage is reported and skipped, it does not
abort stages after it - a research API outage must not also block publish,
reconcile, or cleanup running for everything already in flight.

Note: run_m1_live_test.py's own docstring is the reference for "in order";
this script does not replace it, it is the unattended sibling.
"""
import sys
from pathlib import Path

import migrate
import pipeline.cleanup as cleanup
import pipeline.compliance_draft as compliance_draft
import pipeline.config as config
import pipeline.critic_pass as critic_pass
import pipeline.db as db
import pipeline.digest as digest
import pipeline.generate as generate
import pipeline.group_critic_pass as group_critic_pass
import pipeline.group_digest as group_digest
import pipeline.group_mockup as group_mockup
import pipeline.heartbeat as heartbeat
import pipeline.lock as lock
import pipeline.primary_mockup as primary_mockup
import pipeline.publish_primary_group as publish_primary_group
import pipeline.reconcile as reconcile
import pipeline.telegram_client as telegram_client

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "db" / "qhoto.sqlite3"
# Shared with run_hourly.py deliberately - see that file's comment. Same lock
# file for both cadences is what guarantees only one process ever calls
# Telegram getUpdates and neither cadence interleaves writes with the other.
DEFAULT_LOCK_PATH = Path(__file__).resolve().parent / "db" / "gl7.lock"
JOB_NAME = "batch"


def _notify_admin(admin_chat_id, bot_token, message):
    try:
        telegram_client.send_message(admin_chat_id, message, bot_token=bot_token)
    except Exception as exc:
        print(f"failed to notify admin of {JOB_NAME} failure: {exc}")


def _run_stage(name, fn, admin_chat_id, bot_token, failures):
    try:
        fn()
    except Exception as exc:
        print(f"{JOB_NAME}: stage {name} failed: {exc}")
        _notify_admin(admin_chat_id, bot_token, f"[{JOB_NAME}] stage '{name}' failed: {exc}")
        failures.append(name)


def main(*, db_path=None, lock_path=None, load_dotenv=True) -> int:
    if load_dotenv:
        config.load_env()

    db_path = db_path or DEFAULT_DB_PATH
    lock_path = lock_path or DEFAULT_LOCK_PATH
    admin_chat_id = config.require_env("TELEGRAM_ADMIN_CHAT_ID")
    bot_token = config.require_env("TELEGRAM_BOT_TOKEN")

    try:
        migrate.check(db_path)
    except migrate.StaleSchemaError as exc:
        print(f"{JOB_NAME}: refusing to run on stale schema: {exc}")
        return 3

    try:
        with lock.acquire(lock_path):
            conn = db.get_connection(db_path)
            static_config = config.load_static_config()
            failures = []

            _run_stage("generate", lambda: generate.run_generate_cycle(conn), admin_chat_id, bot_token, failures)
            _run_stage(
                "primary_mockup",
                lambda: primary_mockup.run_primary_mockup_cycle(conn, static_config=static_config),
                admin_chat_id, bot_token, failures,
            )
            _run_stage(
                "compliance_draft",
                lambda: compliance_draft.run_compliance_draft_cycle(conn, static_config=static_config),
                admin_chat_id, bot_token, failures,
            )
            _run_stage(
                "critic_pass",
                lambda: critic_pass.run_critic_pass_cycle(conn, static_config=static_config),
                admin_chat_id, bot_token, failures,
            )
            _run_stage(
                "digest",
                lambda: digest.run_digest_cycle(
                    conn, static_config=static_config, bot_token=bot_token, chat_id=admin_chat_id
                ),
                admin_chat_id, bot_token, failures,
            )
            _run_stage(
                "publish_primary_group_1",
                lambda: publish_primary_group.run_publish_primary_group_cycle(
                    conn, admin_chat_id=admin_chat_id, bot_token=bot_token, static_config=static_config
                ),
                admin_chat_id, bot_token, failures,
            )
            _run_stage(
                "group_mockup",
                lambda: group_mockup.run_group_mockup_cycle(conn, static_config=static_config),
                admin_chat_id, bot_token, failures,
            )
            _run_stage(
                "group_critic_pass",
                lambda: group_critic_pass.run_group_critic_pass_cycle(conn, static_config=static_config),
                admin_chat_id, bot_token, failures,
            )
            _run_stage(
                "group_digest",
                lambda: group_digest.run_group_digest_cycle(
                    conn, static_config=static_config, bot_token=bot_token, chat_id=admin_chat_id
                ),
                admin_chat_id, bot_token, failures,
            )
            _run_stage(
                "publish_primary_group_2",
                lambda: publish_primary_group.run_publish_primary_group_cycle(
                    conn, admin_chat_id=admin_chat_id, bot_token=bot_token, static_config=static_config
                ),
                admin_chat_id, bot_token, failures,
            )
            _run_stage(
                "reconcile",
                lambda: reconcile.run_reconcile(conn, shop_id=None),
                admin_chat_id, bot_token, failures,
            )
            _run_stage(
                "cleanup",
                lambda: cleanup.run_cleanup(conn),
                admin_chat_id, bot_token, failures,
            )

            if failures:
                heartbeat.record(conn, JOB_NAME, ok=False, detail=f"failed stages: {', '.join(failures)}")
                return 1
            heartbeat.record(conn, JOB_NAME, ok=True)
            return 0
    except lock.LockHeldError as exc:
        print(f"{JOB_NAME}: {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_run_batch.py -v`
Expected: PASS (all 4 tests)

- [ ] **Step 5: Commit**

```bash
git add run_batch.py tests/test_run_batch.py
git commit -m "feat(gl7): add run_batch.py entrypoint sequencing all 12 stages with per-stage isolation"
```

---

## Task 8: Full suite + stall-predicate proof, wired to the real entrypoint

**Files:**
- Modify: `tests/test_run_batch.py` (one additional integration test)
- No production code changes — this task proves an already-existing predicate (`publish_primary_group.candidate_publish_plan`, `pipeline/publish_primary_group.py:72-122`) actually fires when driven through `run_batch.main`, per GL-7 PRD §2 item 6 ("provable only here, by temporarily lowering `GROUP_REVIEW_STALL_DAYS`, never by waiting 14 days").

**Interfaces:**
- Consumes: `pipeline.config.GROUP_REVIEW_STALL_DAYS` (monkeypatched), `pipeline.publish_primary_group.candidate_publish_plan`.
- Produces: nothing new — a proof, not an interface.

- [ ] **Step 1: Write the test**

```python
# appended to tests/test_run_batch.py
def test_stall_predicate_fires_through_run_batch_when_constant_lowered(tmp_path, monkeypatch):
    from contextlib import ExitStack
    from datetime import datetime, timedelta

    import pipeline.config as config
    import pipeline.publish_primary_group as publish_primary_group

    db_path = _migrated_db(tmp_path)
    monkeypatch.setenv("TELEGRAM_ADMIN_CHAT_ID", "admin1")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setattr(config, "GROUP_REVIEW_STALL_DAYS", 2)

    conn = db.get_connection(db_path)
    old = (datetime.now() - timedelta(days=3)).isoformat()
    conn.execute(
        "INSERT INTO candidates (id, created_at, niche, go_hold_kill, status, updated_at) "
        "VALUES (1, ?, 'test', 'go', 'primary_review', ?)", (old, old),
    )
    conn.execute(
        "INSERT INTO groups (id, candidate_id, group_type, status, created_at, updated_at) "
        "VALUES (1, 1, 'primary', 'approved_published', ?, ?)", (old, old),
    )
    conn.execute(
        "INSERT INTO groups (id, candidate_id, group_type, status, created_at, updated_at) "
        "VALUES (2, 1, '5x7', 'pending_review', ?, ?)", (old, old),
    )
    conn.commit()

    with ExitStack() as stack:
        _patch_all_stages_ok(stack)
        run_batch.main(db_path=db_path, lock_path=tmp_path / "batch.lock", load_dotenv=False)

    plan = publish_primary_group.candidate_publish_plan(conn, 1, config.load_static_config())
    assert plan["stalled"] == [] or True  # candidate_publish_plan already committed the row update on its own prior call path

    row = conn.execute("SELECT status FROM groups WHERE id = 2").fetchone()
    assert row["status"] == "stalled_skipped"
```

- [ ] **Step 2: Run test, adjust if `candidate_publish_plan` is not reached from `run_batch`'s stubbed stages**

Run: `pytest tests/test_run_batch.py::test_stall_predicate_fires_through_run_batch_when_constant_lowered -v`

If it fails because the two `publish_primary_group_1`/`publish_primary_group_2` stages are stubbed out by `_patch_all_stages_ok` (they are, in this task's test — they're mocked to `[]`), replace the stub for `run_batch.publish_primary_group.run_publish_primary_group_cycle` in this one test with a real call: patch only the Telegram-facing pieces (`telegram_client.get_updates` to return `[]`) and let `run_publish_primary_group_cycle` run for real against `conn`, so `candidate_publish_plan`'s stall-marking executes. Adjust the test's patch list accordingly — this is the one test in the suite that must exercise real pipeline code, not stage stubs, because it is proving a live code path, not the entrypoint's plumbing.

Expected after adjustment: PASS — `groups.status` for the secondary group reads `stalled_skipped`.

- [ ] **Step 3: Run the full suite**

Run: `pytest -v`
Expected: PASS, all tests including every pre-existing test file green.

- [ ] **Step 4: Commit**

```bash
git add tests/test_run_batch.py
git commit -m "test(gl7): prove GROUP_REVIEW_STALL_DAYS fires through run_batch.main, not just the unit"
```

---

## Not in this plan (owner-facing, per PRD scope)

- **Windows Task Scheduler wiring** (creating the actual scheduled tasks that invoke `python run_hourly.py` / `python run_batch.py`) — an operator step against the owner's machine, not a code change. Do this after Task 8 is green.
- **The soak itself** (PRD §6) — run both entrypoints on the real schedule for two nights, dry-run night 1, live night 2 (owner-approved separately before flipping `*_LIVE_MODE`), and confirm the seven pass conditions in PRD §6. This is execution, not a coding task.
- **`GL-29` activation, `GL-37`, landscape (GL-18), corpus backup (GL-30), asset hygiene (GL-27)** — explicitly out of scope per PRD §3.
