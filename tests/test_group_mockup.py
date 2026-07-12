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


STATIC_CONFIG = {
    "gelato_templates": {
        "5x7_portrait": {
            "template_id": "tpl_5x7",
            "template_variant_id": "variant_5x7",
            "image_placeholder_name": "slot_5x7.jpg",
        },
        "10x24_portrait": {
            "template_id": "tpl_10x24",
            "template_variant_id": "variant_10x24",
            "image_placeholder_name": "slot_10x24.jpg",
        },
    },
    "prices_eur": {"5x7": 19, "10x24": 45},
    "aspect_ratio_groups": {"primary": ["8x12", "A3", "A2", "A1"], "5x7": ["5x7"], "10x24": ["10x24"]},
}


def test_create_group_mockup_happy_path_writes_group_product_and_images(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn, niche="monstera line art")
    _insert_published_primary_group(conn, candidate_id)

    def fake_create_product_from_template(template_id, template_variant_id, image_placeholder_name,
                                           image_url, title, *, store_id=None, api_key=None, **kwargs):
        assert template_id == "tpl_5x7"
        assert template_variant_id == "variant_5x7"
        assert image_placeholder_name == "slot_5x7.jpg"
        assert image_url == "https://replicate.delivery/out.png"
        return {"id": "gelato_prod_5x7", "isReadyToPublish": True,
                "productImages": [
                    {"fileUrl": "https://gelato/flat.jpg", "isPrimary": True},
                    {"fileUrl": "https://gelato/lifestyle.jpg", "isPrimary": False},
                ]}

    with patch("pipeline.group_mockup.gelato_client.create_product_from_template",
               side_effect=fake_create_product_from_template):
        result = group_mockup.create_group_mockup(
            conn, candidate_id, "5x7", static_config=STATIC_CONFIG, store_id="store1",
            api_key="key1", poll_interval=0, poll_timeout=10, now=datetime(2026, 7, 12, 18, 0, 0),
        )

    assert result["gelato_product_id"] == "gelato_prod_5x7"

    group_row = conn.execute("SELECT * FROM groups WHERE id = ?", (result["group_id"],)).fetchone()
    assert group_row["group_type"] == "5x7"
    assert group_row["status"] == "pending_review"

    gp_row = conn.execute(
        "SELECT * FROM group_products WHERE id = ?", (result["group_product_id"],)
    ).fetchone()
    assert gp_row["status"] == "created"
    assert gp_row["size"] == "5x7"
    assert gp_row["orientation"] == "portrait"
    assert gp_row["price_eur"] == 19

    images = conn.execute(
        "SELECT * FROM product_images WHERE group_product_id = ? ORDER BY gallery_order",
        (result["group_product_id"],),
    ).fetchall()
    assert len(images) == 2
    assert images[0]["image_type"] == "flat_mockup"
    assert images[1]["image_type"] == "lifestyle"
    conn.close()


def test_create_group_mockup_dry_run_skips_polling(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn, niche="moon phase print")
    _insert_published_primary_group(conn, candidate_id)

    def fake_create_product_from_template(*args, **kwargs):
        return {"id": "DRY_RUN_PRODUCT_ID", "previewUrl": None, "productImages": [], "_dry_run": True}

    with patch("pipeline.group_mockup.gelato_client.create_product_from_template",
               side_effect=fake_create_product_from_template), \
         patch("pipeline.group_mockup.primary_mockup.poll_until_ready") as mock_poll:
        result = group_mockup.create_group_mockup(
            conn, candidate_id, "10x24", static_config=STATIC_CONFIG, store_id="store1",
            api_key="key1", now=datetime(2026, 7, 12, 18, 0, 0),
        )

    mock_poll.assert_not_called()
    gp_row = conn.execute(
        "SELECT * FROM group_products WHERE id = ?", (result["group_product_id"],)
    ).fetchone()
    assert gp_row["status"] == "created"
    assert gp_row["size"] == "10x24"
    conn.close()


def test_create_group_mockup_skips_when_already_created(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_published_primary_group(conn, candidate_id)

    def fake_create_product_from_template(*args, **kwargs):
        return {"id": "gelato_prod_once", "isReadyToPublish": True,
                "productImages": [{"fileUrl": "https://gelato/flat.jpg", "isPrimary": True}]}

    with patch("pipeline.group_mockup.gelato_client.create_product_from_template",
               side_effect=fake_create_product_from_template) as mock_create:
        first = group_mockup.create_group_mockup(
            conn, candidate_id, "5x7", static_config=STATIC_CONFIG,
            poll_interval=0, poll_timeout=10, now=datetime(2026, 7, 12, 18, 0, 0),
        )
        second = group_mockup.create_group_mockup(
            conn, candidate_id, "5x7", static_config=STATIC_CONFIG,
            poll_interval=0, poll_timeout=10, now=datetime(2026, 7, 12, 19, 0, 0),
        )

    assert first is not None
    assert second is None
    mock_create.assert_called_once()
    conn.close()


def test_create_group_mockup_retries_once_then_succeeds(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_published_primary_group(conn, candidate_id)

    attempts = {"n": 0}

    def flaky_create(*args, **kwargs):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise RuntimeError("Gelato throttled")
        return {"id": "gelato_prod_retry", "isReadyToPublish": True,
                "productImages": [{"fileUrl": "https://gelato/flat.jpg", "isPrimary": True}]}

    with patch("pipeline.group_mockup.gelato_client.create_product_from_template",
               side_effect=flaky_create):
        result = group_mockup.create_group_mockup(
            conn, candidate_id, "5x7", static_config=STATIC_CONFIG,
            poll_interval=0, poll_timeout=10, now=datetime(2026, 7, 12, 18, 0, 0),
        )

    assert result["gelato_product_id"] == "gelato_prod_retry"
    assert attempts["n"] == 2
    conn.close()


def test_create_group_mockup_marks_mockup_failed_after_second_failure(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_published_primary_group(conn, candidate_id)

    with patch("pipeline.group_mockup.gelato_client.create_product_from_template",
               side_effect=RuntimeError("Gelato down")):
        with pytest.raises(RuntimeError, match="Gelato down"):
            group_mockup.create_group_mockup(
                conn, candidate_id, "10x24", static_config=STATIC_CONFIG,
                poll_interval=0, poll_timeout=10, now=datetime(2026, 7, 12, 18, 0, 0),
            )

    gp_row = conn.execute(
        "SELECT gp.* FROM group_products gp JOIN groups g ON g.id = gp.group_id "
        "WHERE g.candidate_id = ? AND g.group_type = '10x24'", (candidate_id,)
    ).fetchone()
    assert gp_row["status"] == "mockup_failed"

    group_row = conn.execute(
        "SELECT status FROM groups WHERE candidate_id = ? AND group_type = '10x24'", (candidate_id,)
    ).fetchone()
    assert group_row["status"] == "pending_generation"
    conn.close()
