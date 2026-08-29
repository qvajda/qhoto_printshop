import sqlite3
from pathlib import Path

import migrate
import pipeline.db as db


def _fresh_uninitialized_db(tmp_path):
    """A DB with only base tables applied (schema.sql), no migrate_*.py content
    layered on - simulates a DB that predates every migrate_*.py script, which is
    the state migrate.py must be able to bring current from zero."""
    path = tmp_path / "test.sqlite3"
    conn = db.get_connection(path)
    db.init_db(conn)
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
    # Verify no row was created in schema_version
    conn = sqlite3.connect(db_path)
    count = conn.execute("SELECT COUNT(*) FROM schema_version WHERE id = 1").fetchone()[0]
    assert count == 0, "check() should not create schema_version row"
    conn.close()


def _virgin_db(tmp_path, name="virgin.sqlite3"):
    """A DB file that has never been touched by db.init_db() at all - no
    schema_version, no heartbeats, no candidates/groups, nothing. This is the
    real production qhoto.sqlite3's actual starting state (C1): it only ever
    went through the individual migrate_*.py scripts directly, never
    pipeline.db.init_db()."""
    path = tmp_path / name
    sqlite3.connect(path).close()
    return path


def test_migrate_bootstraps_absolute_zero_db(tmp_path):
    """C1 regression: migrate() must bootstrap schema_version/heartbeats (and
    every other schema.sql table) itself, not assume init_db() already ran."""
    db_path = _virgin_db(tmp_path)

    result = migrate.migrate(db_path)

    assert result["current_version"] == len(migrate.MIGRATIONS)
    conn = sqlite3.connect(db_path)
    tables = {
        row[0] for row in
        conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    }
    assert "schema_version" in tables
    assert "heartbeats" in tables
    conn.close()


def test_check_raises_stale_schema_not_operational_error_on_virgin_db(tmp_path):
    """C1 regression: check() must never let sqlite3.OperationalError ("no such
    table: schema_version") leak past it on a DB that predates schema.sql's
    additions - it must still be StaleSchemaError, and it must still not write
    anything (check() stays read-only)."""
    db_path = _virgin_db(tmp_path, name="virgin2.sqlite3")

    try:
        migrate.check(db_path)
        assert False, "expected StaleSchemaError"
    except migrate.StaleSchemaError as exc:
        assert "0" in str(exc)
    except sqlite3.OperationalError:
        assert False, "check() leaked OperationalError instead of StaleSchemaError"

    conn = sqlite3.connect(db_path)
    tables = {
        row[0] for row in
        conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    }
    assert tables == set(), "check() must not create any tables"
    conn.close()


def test_every_migration_script_is_registered():
    # GL-10c/1 and GL-31 both shipped a migrate_*.py that was never added to
    # MIGRATIONS: schema_version still equalled len(MIGRATIONS), so check()
    # passed and the live DB silently missed the columns until a stage crashed
    # on "no such column". The registry, not schema.sql, is what a real DB gets.
    scripts = {p.stem for p in Path(migrate.__file__).resolve().parent.glob("migrate_*.py")}
    registered = {f"migrate_{name}" for _, name, _ in migrate.MIGRATIONS}
    assert scripts == registered, f"unregistered: {sorted(scripts - registered)}"
