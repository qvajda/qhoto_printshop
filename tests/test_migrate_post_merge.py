import sqlite3

import migrate
import pipeline.db as db


def _stale_db(tmp_path):
    path = tmp_path / "test.sqlite3"
    conn = db.get_connection(path)
    db.init_db(conn)
    conn.close()
    return path


def test_post_merge_advances_a_stale_db(tmp_path):
    db_path = _stale_db(tmp_path)

    result = migrate.post_merge(db_path)

    assert result["skipped"] is None
    assert result["current_version"] == len(migrate.MIGRATIONS)
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()
    assert row[0] == len(migrate.MIGRATIONS)
    conn.close()


def test_post_merge_does_not_create_a_missing_file(tmp_path):
    db_path = tmp_path / "does_not_exist.sqlite3"

    result = migrate.post_merge(db_path)

    assert result["skipped"] == "missing"
    assert not db_path.exists()


def test_post_merge_skips_a_non_canonical_db(tmp_path):
    # A DB that carries someone else's canonical_path - the shape of a
    # restored .bak-* copy or a second worktree's file - stuck stale.
    db_path = _stale_db(tmp_path)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT OR REPLACE INTO db_identity (id, canonical_path) VALUES (1, ?)",
        (str(tmp_path / "elsewhere.sqlite3"),),
    )
    conn.commit()
    conn.close()

    result = migrate.post_merge(db_path)

    assert result["skipped"] == "non-canonical"
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()
    conn.close()
    assert row is None, "a non-canonical DB must not be migrated"


def test_post_merge_is_idempotent_on_a_current_db(tmp_path):
    db_path = _stale_db(tmp_path)
    migrate.migrate(db_path)

    result = migrate.post_merge(db_path)

    assert result["skipped"] is None
    assert result["applied"] == []
    assert result["current_version"] == len(migrate.MIGRATIONS)
