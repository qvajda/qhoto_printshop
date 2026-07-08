# Qhoto Pipeline — Foundation Layer Implementation Plan (Part 1 of M1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the shared foundation every pipeline stage depends on — the SQLite schema/connection layer and the config loader (env vars + static config + placeholder detection) — so that Step 1 of the M1 build plan is complete and stage modules (research, generate, primary-mockup, ...) have something real to import.

**Architecture:** Two independent modules, `pipeline/db.py` and `pipeline/config.py`, each with no dependency on the other. `db.py` owns schema init against `db/schema.sql`. `config.py` owns `.env` parsing and `config/static_config.json` loading, plus the `is_placeholder`/`get_template_id` helpers that later Gelato-calling stages will use to fail loud on placeholder template IDs.

**Tech Stack:** Python 3, stdlib `sqlite3` (no ORM), stdlib `json`/`os`/`pathlib` (no `python-dotenv` — a 15-line parser is simpler than a dependency for `KEY=value` parsing), `pytest`.

## Global Constraints

These apply project-wide, not just to this plan's two tasks:
- Image generation: Replicate + FLUX.1 [schnell] only. Never FLUX.1 [dev] without explicitly raising it. A design is only ever image-generated once per candidate lifecycle — primary-group critic-pass retries (≤3) never call generate again, they only redo mockup/crop + compliance + critic pass against the same base image. A new generation call only happens for a *different* candidate pulled in via Go/Hold/Kill fallback after abandonment.
- Runtime is discrete scheduled functions on two cron cadences — not a persistent service, not one agent loop. One function per pipeline stage.
- Telegram digest = `sendMediaGroup` + separate `sendMessage`, never combined. Up to three digest entries per design (primary, 5x7, 10x24 groups).
- Critic-pass retry cap is exactly 3 attempts per group, then abandon that group: log `failed`, `DELETE` its Gelato product(s). At primary-group level this also triggers Go/Hold/Kill fallback; at 5x7/10x24-group level it only abandons that group.
- Data storage is SQLite — one row per candidate, one row per aspect-ratio group per candidate (primary, 5x7, 10x24).
- Static config (Gelato template IDs, Etsy taxonomy_id/shipping_profile_id/production_partner_ids/who_made, Telegram admin ID) is resolved once and read from config — never discovered dynamically at runtime.
- Telegram admin/allowlist user ID is read from `.env` (`TELEGRAM_ADMIN_CHAT_ID` / `ALLOWED_TELEGRAM_USER_ID`), never hardcoded in source or in CLAUDE.md.
- Placeholder policy: a still-placeholder `templateId` reaching a real (non-mocked) `products:create-from-template` call must fail loudly — never silently skip or proceed with a fake ID. Building/testing against placeholders is otherwise fine.

---

## Task 1: SQLite schema and connection layer

**Files:**
- Create: `db/schema.sql`
- Create: `pipeline/__init__.py` (empty)
- Create: `pipeline/db.py`
- Create: `conftest.py` (repo root, empty — makes `pipeline` importable from `tests/` without a src-layout)
- Create: `requirements-dev.txt`
- Test: `tests/test_db.py`

**Interfaces:**
- Produces: `pipeline.db.get_connection(db_path) -> sqlite3.Connection` (row_factory set to `sqlite3.Row`, foreign keys ON). `pipeline.db.init_db(conn: sqlite3.Connection) -> None` (idempotent — safe to call more than once on the same connection/file).

- [ ] **Step 1: Add pytest as a dev dependency**

Create `requirements-dev.txt`:

```
pytest==8.3.3
```

Run: `pip install -r requirements-dev.txt`

- [ ] **Step 2: Create the root conftest.py so `pipeline` is importable from tests**

Create `conftest.py` at the repo root (empty file — its presence is what matters, it anchors pytest's rootdir insertion so `pipeline/` becomes importable):

```python
```

- [ ] **Step 3: Write the failing test**

Create `tests/test_db.py`:

```python
import pipeline.db as db


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
}


def test_init_db_creates_all_tables(tmp_path):
    db_path = tmp_path / "test.sqlite3"
    conn = db.get_connection(db_path)
    db.init_db(conn)

    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = {row[0] for row in cursor.fetchall()}

    assert EXPECTED_TABLES.issubset(tables)
    conn.close()


def test_init_db_is_idempotent(tmp_path):
    db_path = tmp_path / "test.sqlite3"
    conn = db.get_connection(db_path)
    db.init_db(conn)
    db.init_db(conn)  # must not raise on second call
    conn.close()


def test_get_connection_enables_foreign_keys(tmp_path):
    db_path = tmp_path / "test.sqlite3"
    conn = db.get_connection(db_path)

    result = conn.execute("PRAGMA foreign_keys").fetchone()[0]

    assert result == 1
    conn.close()


def test_groups_unique_constraint_on_candidate_and_group_type(tmp_path):
    db_path = tmp_path / "test.sqlite3"
    conn = db.get_connection(db_path)
    db.init_db(conn)

    conn.execute(
        "INSERT INTO candidates (id, created_at, niche, go_hold_kill, status, updated_at) "
        "VALUES (1, '2026-07-06', 'botanical', 'go', 'pending', '2026-07-06')"
    )
    conn.execute(
        "INSERT INTO groups (candidate_id, group_type, status, created_at, updated_at) "
        "VALUES (1, 'primary', 'pending_generation', '2026-07-06', '2026-07-06')"
    )
    conn.commit()

    import sqlite3
    import pytest as _pytest
    with _pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO groups (candidate_id, group_type, status, created_at, updated_at) "
            "VALUES (1, 'primary', 'pending_generation', '2026-07-06', '2026-07-06')"
        )
    conn.close()
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `pytest tests/test_db.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline'` (or `pipeline.db`)

- [ ] **Step 5: Write schema.sql**

Create `db/schema.sql`:

```sql
CREATE TABLE IF NOT EXISTS candidates (
  id INTEGER PRIMARY KEY,
  created_at TEXT NOT NULL,
  niche TEXT NOT NULL,
  style_theme_tags TEXT,
  trend_source TEXT,
  go_hold_kill TEXT NOT NULL CHECK(go_hold_kill IN ('go','hold','kill')),
  hold_recheck_date TEXT,
  kill_reason TEXT,
  base_image_url TEXT,
  base_replicate_prediction_id TEXT,
  status TEXT NOT NULL CHECK(status IN (
    'pending','generating','primary_review','failed','abandoned','completed'
  )),
  failed_reason TEXT,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS listing_texts (
  id INTEGER PRIMARY KEY,
  candidate_id INTEGER NOT NULL REFERENCES candidates(id),
  title TEXT NOT NULL,
  tags TEXT NOT NULL,
  description TEXT NOT NULL,
  disclosure_text TEXT NOT NULL,
  who_made TEXT NOT NULL,
  production_partner_ids TEXT NOT NULL,
  taxonomy_id TEXT NOT NULL,
  shipping_profile_id TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS groups (
  id INTEGER PRIMARY KEY,
  candidate_id INTEGER NOT NULL REFERENCES candidates(id),
  group_type TEXT NOT NULL CHECK(group_type IN ('primary','5x7','10x24')),
  decision TEXT CHECK(decision IN ('approved','edited','rejected')),
  decision_notes TEXT,
  decided_at TEXT,
  status TEXT NOT NULL CHECK(status IN (
    'pending_generation','pending_review','approved_published','rejected','failed_abandoned'
  )),
  failed_reason TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(candidate_id, group_type)
);

CREATE TABLE IF NOT EXISTS critic_pass_attempts (
  id INTEGER PRIMARY KEY,
  group_id INTEGER NOT NULL REFERENCES groups(id),
  attempt_number INTEGER NOT NULL CHECK(attempt_number BETWEEN 1 AND 3),
  passed INTEGER NOT NULL,
  failure_reason TEXT,
  correction_notes TEXT,
  created_at TEXT NOT NULL,
  UNIQUE(group_id, attempt_number)
);

CREATE TABLE IF NOT EXISTS group_products (
  id INTEGER PRIMARY KEY,
  group_id INTEGER NOT NULL REFERENCES groups(id),
  size TEXT NOT NULL CHECK(size IN ('5x7','8x12','A3','A2','10x24','A1')),
  orientation TEXT NOT NULL CHECK(orientation IN ('portrait','landscape')),
  gelato_template_id TEXT NOT NULL,
  gelato_product_id TEXT,
  etsy_listing_id TEXT,
  price_eur REAL NOT NULL,
  title TEXT,
  status TEXT NOT NULL CHECK(status IN (
    'pending','created','publish_failed','published','deleted'
  )),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS product_images (
  id INTEGER PRIMARY KEY,
  group_product_id INTEGER NOT NULL REFERENCES group_products(id),
  image_url TEXT NOT NULL,
  alt_text TEXT NOT NULL,
  gallery_order INTEGER NOT NULL,
  image_type TEXT NOT NULL CHECK(image_type IN ('flat_mockup','lifestyle'))
);

CREATE TABLE IF NOT EXISTS group_messages (
  id INTEGER PRIMARY KEY,
  group_id INTEGER NOT NULL REFERENCES groups(id),
  telegram_message_id INTEGER NOT NULL,
  chat_id TEXT NOT NULL,
  sent_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS telegram_events_log (
  id INTEGER PRIMARY KEY,
  received_at TEXT NOT NULL,
  telegram_user_id TEXT NOT NULL,
  raw_payload TEXT NOT NULL,
  accepted INTEGER NOT NULL,
  action_taken TEXT
);

CREATE TABLE IF NOT EXISTS listing_metrics_snapshots (
  id INTEGER PRIMARY KEY,
  group_product_id INTEGER NOT NULL REFERENCES group_products(id),
  snapshot_date TEXT NOT NULL,
  views INTEGER NOT NULL,
  num_favorers INTEGER NOT NULL,
  orders_count INTEGER NOT NULL
);
```

- [ ] **Step 6: Write pipeline/db.py**

Create `pipeline/__init__.py` (empty).

Create `pipeline/db.py`:

```python
import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "db" / "schema.sql"


def get_connection(db_path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    schema_sql = SCHEMA_PATH.read_text()
    conn.executescript(schema_sql)
    conn.commit()
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest tests/test_db.py -v`
Expected: PASS (4 passed)

- [ ] **Step 8: Add the runtime db file to .gitignore**

Edit `.gitignore`, add under a new section:

```
# Local runtime data
db/*.sqlite3
```

- [ ] **Step 9: Commit**

```bash
git add db/schema.sql pipeline/__init__.py pipeline/db.py conftest.py requirements-dev.txt tests/test_db.py .gitignore
git commit -m "feat: add SQLite schema and connection layer"
```

---

## Task 2: Config loader (.env + static config + placeholder detection)

**Files:**
- Create: `config/static_config.json`
- Create: `pipeline/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: nothing from Task 1 — fully independent module.
- Produces: `pipeline.config.MissingConfigError` (exception class), `parse_env_file(path) -> dict[str, str]`, `load_env(env_path=None) -> None`, `require_env(key: str) -> str`, `load_static_config(path=None) -> dict`, `is_placeholder(template_id: str) -> bool`, `get_template_id(static_config: dict, size: str, orientation: str) -> str`. Later tasks (`gelato_client.py`) will call `is_placeholder` before any real `products:create-from-template` call and raise if `True`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_config.py`:

```python
import json
import os

import pytest

import pipeline.config as config


def test_parse_env_file_parses_key_value_pairs(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# comment\n"
        "FOO=bar\n"
        "\n"
        "BAZ=qux\n"
    )

    result = config.parse_env_file(env_file)

    assert result == {"FOO": "bar", "BAZ": "qux"}


def test_load_env_sets_os_environ_without_overwriting_existing(tmp_path, monkeypatch):
    monkeypatch.delenv("QHOTO_TEST_VAR", raising=False)
    monkeypatch.setenv("QHOTO_TEST_VAR_EXISTING", "already_set")
    env_file = tmp_path / ".env"
    env_file.write_text(
        "QHOTO_TEST_VAR=from_file\n"
        "QHOTO_TEST_VAR_EXISTING=from_file\n"
    )

    config.load_env(env_file)

    assert os.environ["QHOTO_TEST_VAR"] == "from_file"
    assert os.environ["QHOTO_TEST_VAR_EXISTING"] == "already_set"


def test_require_env_raises_when_missing(monkeypatch):
    monkeypatch.delenv("QHOTO_MISSING_VAR", raising=False)

    with pytest.raises(config.MissingConfigError):
        config.require_env("QHOTO_MISSING_VAR")


def test_require_env_returns_value_when_present(monkeypatch):
    monkeypatch.setenv("QHOTO_PRESENT_VAR", "hello")

    assert config.require_env("QHOTO_PRESENT_VAR") == "hello"


def test_load_static_config_reads_json(tmp_path):
    static_path = tmp_path / "static_config.json"
    static_path.write_text(json.dumps({
        "gelato_templates": {"8x12_portrait": "PLACEHOLDER_8x12_PORTRAIT"},
        "primary_size": "8x12",
    }))

    result = config.load_static_config(static_path)

    assert result["primary_size"] == "8x12"


def test_is_placeholder_detects_placeholder_ids():
    assert config.is_placeholder("PLACEHOLDER_8x12_PORTRAIT") is True
    assert config.is_placeholder("tpl_real_abc123") is False


def test_get_template_id_returns_configured_value():
    static_config = {"gelato_templates": {"8x12_portrait": "tpl_real_abc123"}}

    result = config.get_template_id(static_config, "8x12", "portrait")

    assert result == "tpl_real_abc123"


def test_get_template_id_raises_on_unknown_size_orientation():
    static_config = {"gelato_templates": {"8x12_portrait": "tpl_real_abc123"}}

    with pytest.raises(KeyError):
        config.get_template_id(static_config, "5x7", "landscape")


def test_repo_static_config_has_all_twelve_template_slots():
    static_config = config.load_static_config()

    sizes = ["5x7", "8x12", "A3", "A2", "10x24", "A1"]
    for size in sizes:
        for orientation in ("portrait", "landscape"):
            key = f"{size}_{orientation}"
            assert key in static_config["gelato_templates"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.config'`

- [ ] **Step 3: Write config/static_config.json**

Create `config/static_config.json` — mirrors the static-config block in `CLAUDE.md`; keep both in sync by hand when a template ID or Etsy field is resolved:

```json
{
  "gelato_templates": {
    "5x7_portrait": "PLACEHOLDER_5x7_PORTRAIT",
    "5x7_landscape": "PLACEHOLDER_5x7_LANDSCAPE",
    "8x12_portrait": "PLACEHOLDER_8x12_PORTRAIT",
    "8x12_landscape": "PLACEHOLDER_8x12_LANDSCAPE",
    "A3_portrait": "PLACEHOLDER_A3_PORTRAIT",
    "A3_landscape": "PLACEHOLDER_A3_LANDSCAPE",
    "A2_portrait": "PLACEHOLDER_A2_PORTRAIT",
    "A2_landscape": "PLACEHOLDER_A2_LANDSCAPE",
    "10x24_portrait": "PLACEHOLDER_10x24_PORTRAIT",
    "10x24_landscape": "PLACEHOLDER_10x24_LANDSCAPE",
    "A1_portrait": "PLACEHOLDER_A1_PORTRAIT",
    "A1_landscape": "PLACEHOLDER_A1_LANDSCAPE"
  },
  "prices_eur": {
    "5x7": 19,
    "8x12": 24,
    "A3": 35,
    "A2": 39,
    "10x24": 45,
    "A1": 49
  },
  "aspect_ratio_groups": {
    "primary": ["8x12", "A3", "A2", "A1"],
    "5x7": ["5x7"],
    "10x24": ["10x24"]
  },
  "primary_size": "8x12",
  "etsy_taxonomy_id": "",
  "etsy_shipping_profile_id": "",
  "etsy_production_partner_ids": [],
  "etsy_who_made": ""
}
```

- [ ] **Step 4: Write pipeline/config.py**

Create `pipeline/config.py`:

```python
import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ENV_PATH = REPO_ROOT / ".env"
DEFAULT_STATIC_CONFIG_PATH = REPO_ROOT / "config" / "static_config.json"


class MissingConfigError(Exception):
    pass


def parse_env_file(path) -> dict:
    values = {}
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def load_env(env_path=None) -> None:
    env_path = Path(env_path) if env_path else DEFAULT_ENV_PATH
    if not env_path.exists():
        return
    for key, value in parse_env_file(env_path).items():
        os.environ.setdefault(key, value)


def require_env(key: str) -> str:
    value = os.environ.get(key)
    if not value:
        raise MissingConfigError(f"Missing required environment variable: {key}")
    return value


def load_static_config(path=None) -> dict:
    path = Path(path) if path else DEFAULT_STATIC_CONFIG_PATH
    return json.loads(Path(path).read_text())


def is_placeholder(template_id: str) -> bool:
    return template_id.startswith("PLACEHOLDER_")


def get_template_id(static_config: dict, size: str, orientation: str) -> str:
    key = f"{size}_{orientation}"
    return static_config["gelato_templates"][key]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_config.py -v`
Expected: PASS (9 passed)

- [ ] **Step 6: Run the full test suite**

Run: `pytest -v`
Expected: PASS (13 passed — Task 1's 4 plus Task 2's 9)

- [ ] **Step 7: Commit**

```bash
git add config/static_config.json pipeline/config.py tests/test_config.py
git commit -m "feat: add .env and static-config loader with placeholder detection"
```

---

## What this plan deliberately does not cover

`telegram_client.py`, `replicate_client.py`, `gelato_client.py`, `etsy_client.py`, and all 12 stage modules (`research.py` through `cleanup.py`) are out of scope here — each needs its own plan once this foundation lands, per CLAUDE.md's "commit after each stage passes its manual M1 test" convention. The M1 build-order in the proposal (research → generate → primary_mockup → ... ) still holds; this plan only covers the shared layer everything else imports.
