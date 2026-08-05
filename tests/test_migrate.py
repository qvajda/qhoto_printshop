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
