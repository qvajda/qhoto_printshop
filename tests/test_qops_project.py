"""This project's half of the qops assertions — the ones that do NOT travel.

`tests/test_qops.py` tests the substrate and, from P8.1 on, may not name a
vendor, a model or a table of this shop's. Everything that must name one lives
here: the tripwire list, the declared-schema check, and anything else that is
true of `qhoto_printshop` rather than of qops.

Success criterion 6: the qops repo takes `test_qops.py` and leaves this file
behind.
"""

import sqlite3
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from qops import config as qconfig  # noqa: E402
from qops import guard, install  # noqa: E402

FEATURE = {"branch": "gl-63-thing", "worktrees": 1}


# --------------------------------------------------------------------------
# the tripwires — CLAUDE.md's hard constraints, enforced twice (hook + CI)
# --------------------------------------------------------------------------

@pytest.mark.parametrize("payload", [
    ("Bash", {"command": "python -c \"etsy_client.create_draft_listing()\""}),
    ("Write", {"file_path": "pipeline/x.py", "content": "resp = create_draft_listing(x)"}),
    ("Edit", {"file_path": "pipeline/generate.py", "new_string": 'MODEL = "FLUX.1 [dev]"'}),
    ("Write", {"file_path": "config/static_config.json",
               "content": '{"template_id": "PLACEHOLDER_PORTRAIT"}'}),
])
def test_guard_blocks_project_tripwires(payload):
    tool, inp = payload
    reason = guard.check(tool, inp, FEATURE, qconfig.load(REPO))
    assert reason, f"{tool} {inp} should have tripped a tripwire"


def test_guard_lets_a_commit_message_quote_a_tripwire():
    cmd = "git commit -m 'never substitute FLUX.1 [dev]'"
    assert guard.check("Bash", {"command": cmd}, FEATURE, qconfig.load(REPO)) is None
    # ...but a write of the same string is still blocked
    assert guard.check("Bash", {"command": "echo 'FLUX.1 [dev]' >> pipeline/x.py"},
                       FEATURE, qconfig.load(REPO))


def test_guard_lets_the_constraint_docs_name_the_tripwires():
    """CLAUDE.md states the FLUX.1 [dev] prohibition; writing it must not be
    blocked by the tripwire that enforces it."""
    inp = {"file_path": "CLAUDE.md", "content": "Never substitute FLUX.1 [dev]."}
    assert guard.check("Write", inp, FEATURE, qconfig.load(REPO)) is None


def test_guard_reasons_are_ascii():
    """Blocked-call reasons go to a Windows console via the hook."""
    for tw in qconfig.load(REPO)["tripwires"]:
        tw["why"].encode("ascii")


def test_guard_scan_is_clean_on_this_repo():
    """The tripwire scan guard.yml runs. Green today; it is a regression alarm."""
    hits = guard.scan(REPO, qconfig.load(REPO))
    assert hits == [], f"tripwires present: {hits}"


def test_guard_scan_catches_a_planted_string(tmp_path):
    (tmp_path / "pipeline").mkdir()
    (tmp_path / "pipeline" / "generate.py").write_text('m = "FLUX.1 [dev]"\n')
    hits = guard.scan(tmp_path, qconfig.load(REPO))
    assert any("FLUX" in h["pattern"] for h in hits)


# --------------------------------------------------------------------------
# schema drift (#160) — the paths are this project's, so the test is too
# --------------------------------------------------------------------------

def _schema_sql_path():
    return REPO / qconfig.load(REPO)["schema_check"]["sql"]


def test_schema_drift_reports_a_column_dropped_from_the_live_db(tmp_path):
    """GL-32 shape (#160): schema.sql declares a column, the live DB never
    ran the migration that added it - `CREATE TABLE IF NOT EXISTS` is a
    silent no-op against an already-created table."""
    schema_sql = _schema_sql_path().read_text(encoding="utf-8")
    stripped = schema_sql.replace("  gelato_create_intent_at TEXT,\n", "")
    assert stripped != schema_sql
    db_path = tmp_path / "live.sqlite3"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(stripped)
    conn.commit()
    conn.close()

    problems = install.schema_drift(REPO, qconfig.load(REPO), db_path)
    assert any("group_products.gelato_create_intent_at" in p for p in problems)


def test_schema_drift_is_clean_on_a_fully_migrated_db(tmp_path):
    db_path = tmp_path / "live.sqlite3"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(_schema_sql_path().read_text(encoding="utf-8"))
    conn.commit()
    conn.close()
    assert install.schema_drift(REPO, qconfig.load(REPO), db_path) == []


def test_schema_drift_is_quiet_when_there_is_no_live_db(tmp_path):
    assert install.schema_drift(tmp_path, qconfig.load(REPO)) == []


def test_schema_drift_is_quiet_when_the_config_declares_no_schema():
    """A substrate repo has no database. No `schema_check:` block, no check —
    and no reaching for one project's filenames from substrate code (leak 5)."""
    assert install.schema_drift(REPO, {}) == []
