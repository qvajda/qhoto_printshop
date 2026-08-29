import sqlite3

import migrate_candidates_dominant_colour as migration

NEW_COLUMNS = ("dominant_colour", "named_idiom")


def _old_schema_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE candidates (
          id INTEGER PRIMARY KEY,
          created_at TEXT NOT NULL,
          niche TEXT NOT NULL,
          go_hold_kill TEXT NOT NULL,
          status TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          art_brief TEXT
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
    cols = {row[1] for row in conn.execute("PRAGMA table_info(candidates)").fetchall()}
    assert set(NEW_COLUMNS) <= cols
    conn.close()


def test_migrate_is_idempotent(tmp_path):
    db_path = tmp_path / "old.sqlite3"
    conn = _old_schema_db(db_path)
    conn.close()

    migration.migrate(db_path)
    added_second_run = migration.migrate(db_path)

    assert added_second_run == []
