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
