import sqlite3

import migrate_base_artwork_columns as migration

NEW_COLUMNS = ("base_image_local_path", "base_image_sha256", "base_replicate_delivery_url")


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
          updated_at TEXT NOT NULL
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


def test_migrate_only_adds_columns_actually_missing(tmp_path):
    db_path = tmp_path / "partial.sqlite3"
    conn = _old_schema_db(db_path)
    conn.execute("ALTER TABLE candidates ADD COLUMN base_image_sha256 TEXT")
    conn.commit()
    conn.close()

    added = migration.migrate(db_path)

    assert set(added) == {"base_image_local_path", "base_replicate_delivery_url"}
