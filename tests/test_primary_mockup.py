from datetime import datetime
from unittest.mock import patch

import pytest

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


def test_poll_until_ready_returns_product_once_ready():
    call_count = {"n": 0}

    def fake_get_product(product_id, *, store_id=None, api_key=None):
        call_count["n"] += 1
        if call_count["n"] < 3:
            return {"id": product_id, "isReadyToPublish": False, "productImages": []}
        return {
            "id": product_id, "isReadyToPublish": True,
            "productImages": [{"fileUrl": "https://img/1.jpg", "isPrimary": True}],
        }

    sleeps = []

    with patch("pipeline.primary_mockup.gelato_client.get_product", side_effect=fake_get_product):
        result = primary_mockup.poll_until_ready(
            "prod_1", store_id="store1", api_key="key1",
            poll_interval=3.0, timeout=90.0,
            sleep_fn=sleeps.append, now_fn=lambda: 0.0,
        )

    assert result["isReadyToPublish"] is True
    assert call_count["n"] == 3
    assert sleeps == [3.0, 3.0]


def test_poll_until_ready_raises_after_timeout():
    def fake_get_product(product_id, *, store_id=None, api_key=None):
        return {"id": product_id, "isReadyToPublish": False, "productImages": []}

    now_values = iter([0.0, 10.0, 95.0])

    with patch("pipeline.primary_mockup.gelato_client.get_product", side_effect=fake_get_product):
        with pytest.raises(primary_mockup.GelatoMockupTimeoutError, match="prod_1"):
            primary_mockup.poll_until_ready(
                "prod_1", store_id="store1", api_key="key1",
                poll_interval=3.0, timeout=90.0,
                sleep_fn=lambda seconds: None, now_fn=lambda: next(now_values),
            )
