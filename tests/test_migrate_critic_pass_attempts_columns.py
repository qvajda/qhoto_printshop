import sqlite3

import migrate_critic_pass_attempts_columns as migration

NEW_COLUMNS = ("overall", "criteria_json", "cov")


def _old_schema_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE critic_pass_attempts (
          id INTEGER PRIMARY KEY,
          group_id INTEGER NOT NULL,
          attempt_number INTEGER NOT NULL,
          passed INTEGER NOT NULL,
          failure_reason TEXT,
          correction_notes TEXT,
          created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def test_migrate_adds_missing_columns(tmp_path):
    db_path = tmp_path / "old.sqlite3"
    conn = _old_schema_db(db_path)
    conn.close()

    added = migration.migrate(db_path)

    assert set(added) == set(NEW_COLUMNS)
    conn = sqlite3.connect(db_path)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(critic_pass_attempts)").fetchall()}
    assert set(NEW_COLUMNS) <= cols
    conn.close()


def test_migrate_is_idempotent(tmp_path):
    db_path = tmp_path / "old.sqlite3"
    conn = _old_schema_db(db_path)
    conn.close()

    migration.migrate(db_path)
    added_second_run = migration.migrate(db_path)

    assert added_second_run == []


def test_migrate_only_adds_columns_actually_missing(tmp_path):
    db_path = tmp_path / "partial.sqlite3"
    conn = _old_schema_db(db_path)
    conn.execute("ALTER TABLE critic_pass_attempts ADD COLUMN cov REAL")
    conn.commit()
    conn.close()

    added = migration.migrate(db_path)

    assert set(added) == {"overall", "criteria_json"}
