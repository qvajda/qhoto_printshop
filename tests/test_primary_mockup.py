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


STATIC_CONFIG = {
    "gelato_templates": {
        "8x12_portrait": {
            "template_id": "tpl_real_8x12",
            "template_variant_id": "variant_real_8x12",
            "image_placeholder_name": "real_image_slot.jpg",
        }
    },
    "prices_eur": {"8x12": 24},
}


def test_create_primary_mockup_happy_path_writes_group_product_and_images(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn, niche="monstera line art")

    def fake_create_product_from_template(template_id, template_variant_id, image_placeholder_name,
                                           image_url, title, *, store_id=None, api_key=None, **kwargs):
        assert template_id == "tpl_real_8x12"
        assert template_variant_id == "variant_real_8x12"
        assert image_placeholder_name == "real_image_slot.jpg"
        assert image_url == "https://replicate.delivery/out.png"
        assert "monstera line art" in title
        return {"id": "gelato_prod_1", "isReadyToPublish": False, "productImages": []}

    def fake_get_product(product_id, *, store_id=None, api_key=None):
        assert product_id == "gelato_prod_1"
        return {
            "id": "gelato_prod_1",
            "isReadyToPublish": True,
            "productImages": [
                {"fileUrl": "https://gelato/lifestyle1.jpg", "isPrimary": False},
                {"fileUrl": "https://gelato/flat.jpg", "isPrimary": True},
                {"fileUrl": "https://gelato/lifestyle2.jpg", "isPrimary": False},
            ],
        }

    with patch("pipeline.primary_mockup.gelato_client.create_product_from_template",
               side_effect=fake_create_product_from_template), \
         patch("pipeline.primary_mockup.gelato_client.get_product", side_effect=fake_get_product):
        result = primary_mockup.create_primary_mockup(
            conn, candidate_id, static_config=STATIC_CONFIG, store_id="store1", api_key="key1",
            poll_interval=0, poll_timeout=10, now=datetime(2026, 7, 9, 12, 0, 0),
        )

    assert result["gelato_product_id"] == "gelato_prod_1"

    group_row = conn.execute("SELECT * FROM groups WHERE id = ?", (result["group_id"],)).fetchone()
    assert group_row["status"] == "pending_review"

    gp_row = conn.execute("SELECT * FROM group_products WHERE id = ?", (result["group_product_id"],)).fetchone()
    assert gp_row["status"] == "created"
    assert gp_row["gelato_product_id"] == "gelato_prod_1"
    assert gp_row["size"] == "8x12"
    assert gp_row["orientation"] == "portrait"
    assert gp_row["price_eur"] == 24

    images = conn.execute(
        "SELECT * FROM product_images WHERE group_product_id = ? ORDER BY gallery_order",
        (result["group_product_id"],),
    ).fetchall()
    assert len(images) == 3
    assert images[0]["image_type"] == "flat_mockup"
    assert images[0]["image_url"] == "https://gelato/flat.jpg"
    assert images[0]["alt_text"] == ""
    assert [img["image_type"] for img in images[1:]] == ["lifestyle", "lifestyle"]
    conn.close()


def test_create_primary_mockup_dry_run_skips_polling(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn, niche="moon phase print")

    def fake_create_product_from_template(*args, **kwargs):
        return {
            "id": "DRY_RUN_PRODUCT_ID", "previewUrl": None, "productImages": [],
            "_dry_run": True,
        }

    with patch("pipeline.primary_mockup.gelato_client.create_product_from_template",
               side_effect=fake_create_product_from_template), \
         patch("pipeline.primary_mockup.gelato_client.get_product") as mock_get_product:
        result = primary_mockup.create_primary_mockup(
            conn, candidate_id, static_config=STATIC_CONFIG, store_id="store1", api_key="key1",
            now=datetime(2026, 7, 9, 12, 0, 0),
        )

    mock_get_product.assert_not_called()

    images = conn.execute(
        "SELECT * FROM product_images WHERE group_product_id = ?",
        (result["group_product_id"],),
    ).fetchall()
    assert len(images) == 1
    assert images[0]["image_type"] == "flat_mockup"
    assert images[0]["gallery_order"] == 0

    gp_row = conn.execute("SELECT * FROM group_products WHERE id = ?", (result["group_product_id"],)).fetchone()
    assert gp_row["status"] == "created"
    conn.close()
