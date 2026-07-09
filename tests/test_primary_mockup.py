from datetime import datetime

import pipeline.db as db
import pipeline.primary_mockup as primary_mockup


def _fresh_conn(tmp_path):
    conn = db.get_connection(tmp_path / "test.sqlite3")
    db.init_db(conn)
    return conn


def _insert_candidate(conn, niche="monstera line art", *, status="generating",
                       base_image_url="https://replicate.delivery/out.png"):
    timestamp = "2026-07-09T09:00:00"
    cursor = conn.execute(
        """
        INSERT INTO candidates (created_at, niche, go_hold_kill, status, base_image_url, updated_at)
        VALUES (?, ?, 'go', ?, ?, ?)
        """,
        (timestamp, niche, status, base_image_url, timestamp),
    )
    conn.commit()
    return cursor.lastrowid


def test_build_mockup_title_includes_niche():
    candidate = {"niche": "monstera line art"}

    title = primary_mockup.build_mockup_title(candidate)

    assert "monstera line art" in title
    assert "primary mockup" in title.lower()


def test_get_or_create_primary_group_creates_new_row(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)

    group_id = primary_mockup.get_or_create_primary_group(
        conn, candidate_id, now=datetime(2026, 7, 9, 10, 0, 0)
    )

    row = conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone()
    assert row["candidate_id"] == candidate_id
    assert row["group_type"] == "primary"
    assert row["status"] == "pending_generation"
    assert row["created_at"] == "2026-07-09T10:00:00"
    conn.close()


def test_get_or_create_primary_group_returns_existing_row(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    first_id = primary_mockup.get_or_create_primary_group(
        conn, candidate_id, now=datetime(2026, 7, 9, 10, 0, 0)
    )

    second_id = primary_mockup.get_or_create_primary_group(
        conn, candidate_id, now=datetime(2026, 7, 9, 11, 0, 0)
    )

    assert second_id == first_id
    rows = conn.execute(
        "SELECT * FROM groups WHERE candidate_id = ? AND group_type = 'primary'", (candidate_id,)
    ).fetchall()
    assert len(rows) == 1
    conn.close()
