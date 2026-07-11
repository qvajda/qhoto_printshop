import json as _json
from datetime import datetime
from unittest.mock import patch

import pytest

import pipeline.digest as digest
import pipeline.db as db


def _fresh_conn(tmp_path):
    conn = db.get_connection(tmp_path / "test.sqlite3")
    db.init_db(conn)
    return conn


def _insert_candidate(conn, niche="monstera line art", *, status="primary_review",
                       base_image_url="https://replicate.delivery/out.png"):
    timestamp = "2026-07-11T09:00:00"
    cursor = conn.execute(
        """
        INSERT INTO candidates (created_at, niche, go_hold_kill, status, base_image_url, updated_at)
        VALUES (?, ?, 'go', ?, ?, ?)
        """,
        (timestamp, niche, status, base_image_url, timestamp),
    )
    conn.commit()
    return cursor.lastrowid


def _insert_primary_gallery(conn, candidate_id,
                             image_urls=("https://gelato/flat.jpg", "https://gelato/life.jpg"),
                             *, price_eur=24, group_product_status="created"):
    timestamp = "2026-07-11T09:05:00"
    group_cursor = conn.execute(
        "INSERT INTO groups (candidate_id, group_type, status, created_at, updated_at) "
        "VALUES (?, 'primary', 'pending_review', ?, ?)",
        (candidate_id, timestamp, timestamp),
    )
    group_id = group_cursor.lastrowid
    gp_cursor = conn.execute(
        "INSERT INTO group_products "
        "(group_id, size, orientation, gelato_template_id, gelato_product_id, price_eur, "
        "status, created_at, updated_at) "
        "VALUES (?, '8x12', 'portrait', 'tpl_1', 'gelato_prod_1', ?, ?, ?, ?)",
        (group_id, price_eur, group_product_status, timestamp, timestamp),
    )
    group_product_id = gp_cursor.lastrowid
    for order, image_url in enumerate(image_urls):
        image_type = "flat_mockup" if order == 0 else "lifestyle"
        conn.execute(
            "INSERT INTO product_images (group_product_id, image_url, alt_text, gallery_order, image_type) "
            "VALUES (?, ?, 'placeholder alt', ?, ?)",
            (group_product_id, image_url, order, image_type),
        )
    conn.commit()
    return group_id, group_product_id


def _insert_listing_text(conn, candidate_id, niche="monstera line art"):
    timestamp = "2026-07-11T09:10:00"
    conn.execute(
        """
        INSERT INTO listing_texts (
            candidate_id, title, tags, description, disclosure_text,
            who_made, production_partner_ids, taxonomy_id, shipping_profile_id, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            candidate_id, f"{niche} print", _json.dumps(["botanical", "wall art"]),
            f"A print of {niche}.", "AI disclosure text.",
            "i_did", _json.dumps([5717252]), "1027", "", timestamp,
        ),
    )
    conn.commit()


def _insert_ready_candidate(conn, niche="monstera line art"):
    candidate_id = _insert_candidate(conn, niche=niche)
    _insert_primary_gallery(conn, candidate_id)
    _insert_listing_text(conn, candidate_id, niche=niche)
    return candidate_id


def test_get_primary_group_returns_group_id_and_price(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    expected_group_id, _ = _insert_primary_gallery(conn, candidate_id, price_eur=24)

    result = digest.get_primary_group(conn, candidate_id)

    assert result == {"group_id": expected_group_id, "price_eur": 24}
    conn.close()


def test_get_primary_group_raises_when_no_live_group_product(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)

    with pytest.raises(ValueError, match="primary group_product"):
        digest.get_primary_group(conn, candidate_id)
    conn.close()


def test_get_primary_gallery_urls_returns_ordered_urls(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_primary_gallery(
        conn, candidate_id,
        image_urls=("https://gelato/flat.jpg", "https://gelato/life1.jpg", "https://gelato/life2.jpg"),
    )

    urls = digest.get_primary_gallery_urls(conn, candidate_id)

    assert urls == [
        "https://gelato/flat.jpg", "https://gelato/life1.jpg", "https://gelato/life2.jpg",
    ]
    conn.close()


def test_get_listing_text_returns_row(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_listing_text(conn, candidate_id, niche="monstera line art")

    result = digest.get_listing_text(conn, candidate_id)

    assert result["title"] == "monstera line art print"
    assert result["tags"] == _json.dumps(["botanical", "wall art"])
    assert result["description"] == "A print of monstera line art."
    assert result["disclosure_text"] == "AI disclosure text."
    conn.close()


def test_get_listing_text_raises_when_missing(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)

    with pytest.raises(ValueError, match="listing_texts"):
        digest.get_listing_text(conn, candidate_id)
    conn.close()
