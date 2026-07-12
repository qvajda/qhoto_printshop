from datetime import datetime
from unittest.mock import patch

import pytest

import pipeline.db as db
import pipeline.group_mockup as group_mockup


def _fresh_conn(tmp_path):
    conn = db.get_connection(tmp_path / "test.sqlite3")
    db.init_db(conn)
    return conn


def _insert_candidate(conn, niche="monstera line art", *, status="completed",
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


def _insert_published_primary_group(conn, candidate_id):
    timestamp = "2026-07-12T09:00:00"
    cursor = conn.execute(
        """
        INSERT INTO groups (candidate_id, group_type, status, created_at, updated_at)
        VALUES (?, 'primary', 'approved_published', ?, ?)
        """,
        (candidate_id, timestamp, timestamp),
    )
    conn.commit()
    return cursor.lastrowid


def test_get_or_create_group_creates_new_row(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)

    group_id = group_mockup.get_or_create_group(
        conn, candidate_id, "5x7", now=datetime(2026, 7, 12, 18, 0, 0)
    )

    row = conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone()
    assert row["candidate_id"] == candidate_id
    assert row["group_type"] == "5x7"
    assert row["status"] == "pending_generation"
    assert row["created_at"] == "2026-07-12T18:00:00"
    conn.close()


def test_get_or_create_group_returns_existing_row(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    first_id = group_mockup.get_or_create_group(
        conn, candidate_id, "10x24", now=datetime(2026, 7, 12, 18, 0, 0)
    )

    second_id = group_mockup.get_or_create_group(
        conn, candidate_id, "10x24", now=datetime(2026, 7, 12, 19, 0, 0)
    )

    assert second_id == first_id
    rows = conn.execute(
        "SELECT * FROM groups WHERE candidate_id = ? AND group_type = '10x24'", (candidate_id,)
    ).fetchall()
    assert len(rows) == 1
    conn.close()


def test_get_or_create_group_keeps_5x7_and_10x24_separate(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)

    id_5x7 = group_mockup.get_or_create_group(conn, candidate_id, "5x7", now=datetime(2026, 7, 12, 18, 0, 0))
    id_10x24 = group_mockup.get_or_create_group(conn, candidate_id, "10x24", now=datetime(2026, 7, 12, 18, 0, 0))

    assert id_5x7 != id_10x24
    conn.close()
