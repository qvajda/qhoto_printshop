import json as _json
from datetime import datetime
from unittest.mock import patch

import pytest

import pipeline.db as db
import pipeline.group_critic_pass as group_critic_pass


def _fresh_conn(tmp_path):
    conn = db.get_connection(tmp_path / "test.sqlite3")
    db.init_db(conn)
    return conn


def _insert_candidate(conn, niche="monstera line art", *, status="primary_review",
                       base_image_url="https://replicate.delivery/out.png"):
    timestamp = "2026-07-13T09:00:00"
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
                           gelato_product_id="gelato_prod_1", group_status="pending_review",
                           group_product_status="created"):
    timestamp = "2026-07-13T09:05:00"
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
        "VALUES (?, ?, 'portrait', 'tpl_1', ?, 19, ?, ?, ?)",
        (group_id, size, gelato_product_id, group_product_status, timestamp, timestamp),
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
    timestamp = "2026-07-13T09:10:00"
    conn.execute(
        """
        INSERT INTO listing_texts (
            candidate_id, title, tags, description, disclosure_text,
            who_made, production_partner_ids, taxonomy_id, shipping_profile_id, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            candidate_id, f"{niche} print", _json.dumps(["botanical", "wall art"]),
            f"A print of {niche}.", "disclosure text",
            "i_did", _json.dumps([5717252]), "1027", "", timestamp,
        ),
    )
    conn.commit()


def test_get_group_critic_state_returns_gallery_and_listing_text(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_group_gallery(conn, candidate_id, "5x7", "5x7")
    _insert_listing_text(conn, candidate_id)

    state = group_critic_pass.get_group_critic_state(conn, candidate_id, "5x7")

    assert state["image_urls"] == ["https://gelato/flat.jpg", "https://gelato/life.jpg"]
    assert state["listing_text"]["title"] == "monstera line art print"
    conn.close()


def test_get_group_critic_state_raises_when_no_group(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)

    with pytest.raises(ValueError, match="5x7 group"):
        group_critic_pass.get_group_critic_state(conn, candidate_id, "5x7")
    conn.close()


def test_get_group_critic_state_raises_when_no_live_group_product(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_group_gallery(conn, candidate_id, "10x24", "10x24", group_product_status="mockup_failed")

    with pytest.raises(ValueError, match="group_products"):
        group_critic_pass.get_group_critic_state(conn, candidate_id, "10x24")
    conn.close()


def test_get_group_critic_state_raises_when_no_listing_text(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_group_gallery(conn, candidate_id, "5x7", "5x7")

    with pytest.raises(ValueError, match="listing_texts"):
        group_critic_pass.get_group_critic_state(conn, candidate_id, "5x7")
    conn.close()


def test_abandon_group_marks_only_that_group_failed(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id, _ = _insert_group_gallery(conn, candidate_id, "5x7", "5x7")
    other_group_id, _ = _insert_group_gallery(conn, candidate_id, "10x24", "10x24",
                                               gelato_product_id="gelato_prod_2")

    group_critic_pass.abandon_group(
        conn, group_id, "exhausted 3 attempts: off-center crop",
        now=datetime(2026, 7, 13, 12, 0, 0),
    )

    group_row = conn.execute(
        "SELECT status, failed_reason FROM groups WHERE id = ?", (group_id,)
    ).fetchone()
    assert group_row["status"] == "failed_abandoned"
    assert group_row["failed_reason"] == "exhausted 3 attempts: off-center crop"

    other_group_row = conn.execute(
        "SELECT status FROM groups WHERE id = ?", (other_group_id,)
    ).fetchone()
    assert other_group_row["status"] == "pending_review"

    candidate_row = conn.execute(
        "SELECT status FROM candidates WHERE id = ?", (candidate_id,)
    ).fetchone()
    assert candidate_row["status"] == "primary_review"
    conn.close()
