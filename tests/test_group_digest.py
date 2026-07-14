import json as _json
from datetime import datetime
from unittest.mock import patch

import pytest

import pipeline.db as db
import pipeline.group_digest as group_digest


def _fresh_conn(tmp_path):
    conn = db.get_connection(tmp_path / "test.sqlite3")
    db.init_db(conn)
    return conn


def _insert_candidate(conn, niche="monstera line art", *, status="primary_review",
                       base_image_url="https://replicate.delivery/out.png"):
    timestamp = "2026-07-14T09:00:00"
    cursor = conn.execute(
        """
        INSERT INTO candidates (created_at, niche, go_hold_kill, status, base_image_url, updated_at)
        VALUES (?, ?, 'go', ?, ?, ?)
        """,
        (timestamp, niche, status, base_image_url, timestamp),
    )
    conn.commit()
    return cursor.lastrowid


def _insert_group_gallery(conn, candidate_id, group_type, size, *,
                           image_urls=("https://gelato/flat.jpg", "https://gelato/life.jpg"),
                           price_eur=19, group_status="pending_review",
                           group_product_status="created"):
    timestamp = "2026-07-14T09:05:00"
    group_cursor = conn.execute(
        "INSERT INTO groups (candidate_id, group_type, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (candidate_id, group_type, group_status, timestamp, timestamp),
    )
    group_id = group_cursor.lastrowid
    gp_cursor = conn.execute(
        "INSERT INTO group_products "
        "(group_id, size, orientation, gelato_template_id, gelato_product_id, price_eur, "
        "status, created_at, updated_at) "
        "VALUES (?, ?, 'portrait', 'tpl_1', 'gelato_prod_1', ?, ?, ?, ?)",
        (group_id, size, price_eur, group_product_status, timestamp, timestamp),
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
    timestamp = "2026-07-14T09:10:00"
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


def _insert_critic_pass(conn, group_id, *, attempt_number=1, passed=1):
    timestamp = "2026-07-14T09:15:00"
    conn.execute(
        "INSERT INTO critic_pass_attempts (group_id, attempt_number, passed, created_at) "
        "VALUES (?, ?, ?, ?)",
        (group_id, attempt_number, passed, timestamp),
    )
    conn.commit()


def test_get_review_group_returns_candidate_type_and_price(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id, _ = _insert_group_gallery(conn, candidate_id, "5x7", "5x7", price_eur=19)

    result = group_digest.get_review_group(conn, group_id)

    assert result == {"candidate_id": candidate_id, "group_type": "5x7", "price_eur": 19}
    conn.close()


def test_get_review_group_raises_when_no_live_group_product(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id, _ = _insert_group_gallery(
        conn, candidate_id, "5x7", "5x7", group_product_status="mockup_failed",
    )

    with pytest.raises(ValueError, match="group_product"):
        group_digest.get_review_group(conn, group_id)
    conn.close()


def test_get_group_gallery_urls_returns_ordered_urls(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id, _ = _insert_group_gallery(
        conn, candidate_id, "10x24", "10x24",
        image_urls=("https://gelato/flat.jpg", "https://gelato/life1.jpg", "https://gelato/life2.jpg"),
    )

    urls = group_digest.get_group_gallery_urls(conn, group_id)

    assert urls == [
        "https://gelato/flat.jpg", "https://gelato/life1.jpg", "https://gelato/life2.jpg",
    ]
    conn.close()


def test_build_group_digest_message_text_includes_group_type_and_price():
    listing_text = {
        "title": "Monstera Line Art Botanical Print",
        "tags": _json.dumps(["botanical", "wall art"]),
        "description": "A minimalist botanical print.",
        "disclosure_text": "AI disclosure text.",
    }

    text = group_digest.build_group_digest_message_text(7, 42, "5x7", listing_text, 19)

    assert "Candidate #7" in text
    assert "5x7 group" in text
    assert "#42" in text
    assert "Monstera Line Art Botanical Print" in text
    assert "A minimalist botanical print." in text
    assert "botanical, wall art" in text
    assert "AI disclosure text." in text
    assert "19" in text
