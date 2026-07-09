import pytest

import pipeline.compliance_draft as compliance_draft
import pipeline.db as db


STATIC_CONFIG = {
    "etsy_who_made": "i_did",
    "etsy_production_partner_ids": [5717252],
    "etsy_taxonomy_id": "1027",
    "etsy_shipping_profile_id": "",
}


def _fresh_conn(tmp_path):
    conn = db.get_connection(tmp_path / "test.sqlite3")
    db.init_db(conn)
    return conn


def _insert_candidate(conn, niche="monstera line art", *, status="generating"):
    timestamp = "2026-07-10T09:00:00"
    cursor = conn.execute(
        """
        INSERT INTO candidates (created_at, niche, go_hold_kill, status, updated_at)
        VALUES (?, ?, 'go', ?, ?)
        """,
        (timestamp, niche, status, timestamp),
    )
    conn.commit()
    return cursor.lastrowid


def _insert_primary_gallery(conn, candidate_id, image_types=("flat_mockup", "lifestyle"),
                             *, group_product_status="created"):
    timestamp = "2026-07-10T09:05:00"
    group_cursor = conn.execute(
        "INSERT INTO groups (candidate_id, group_type, status, created_at, updated_at) "
        "VALUES (?, 'primary', 'pending_review', ?, ?)",
        (candidate_id, timestamp, timestamp),
    )
    group_id = group_cursor.lastrowid
    gp_cursor = conn.execute(
        "INSERT INTO group_products "
        "(group_id, size, orientation, gelato_template_id, price_eur, status, created_at, updated_at) "
        "VALUES (?, '8x12', 'portrait', 'tpl_1', 24, ?, ?, ?)",
        (group_id, group_product_status, timestamp, timestamp),
    )
    group_product_id = gp_cursor.lastrowid
    for order, image_type in enumerate(image_types):
        conn.execute(
            "INSERT INTO product_images (group_product_id, image_url, alt_text, gallery_order, image_type) "
            "VALUES (?, ?, '', ?, ?)",
            (group_product_id, f"https://gelato/img{order}.jpg", order, image_type),
        )
    conn.commit()
    return group_product_id


def _insert_ready_candidate(conn, niche="monstera line art", image_types=("flat_mockup", "lifestyle")):
    candidate_id = _insert_candidate(conn, niche=niche, status="generating")
    _insert_primary_gallery(conn, candidate_id, image_types=image_types)
    return candidate_id


def test_resolve_compliance_metadata_reads_static_config_fields():
    metadata = compliance_draft.resolve_compliance_metadata(STATIC_CONFIG)

    assert metadata == {
        "who_made": "i_did",
        "production_partner_ids": [5717252],
        "taxonomy_id": "1027",
        "shipping_profile_id": "",
    }


def test_validate_listing_text_accepts_valid_input():
    compliance_draft.validate_listing_text("Botanical Wall Art Print", ["botanical", "wall art", "minimalist"])


def test_validate_listing_text_rejects_title_over_140_chars():
    long_title = "x" * 141

    with pytest.raises(ValueError, match="140"):
        compliance_draft.validate_listing_text(long_title, ["botanical"])


def test_validate_listing_text_rejects_more_than_13_tags():
    too_many_tags = [f"tag{i}" for i in range(14)]

    with pytest.raises(ValueError, match="13"):
        compliance_draft.validate_listing_text("A short title", too_many_tags)


def test_validate_listing_text_rejects_tag_over_20_chars():
    long_tag = "x" * 21

    with pytest.raises(ValueError, match="20"):
        compliance_draft.validate_listing_text("A short title", [long_tag])


def test_get_primary_gallery_returns_images_in_order(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_ready_candidate(
        conn, image_types=("flat_mockup", "lifestyle", "lifestyle")
    )

    gallery = compliance_draft.get_primary_gallery(conn, candidate_id)

    assert [image["image_type"] for image in gallery] == ["flat_mockup", "lifestyle", "lifestyle"]
    assert [image["gallery_order"] for image in gallery] == [0, 1, 2]
    conn.close()


def test_get_primary_gallery_returns_empty_list_when_no_gallery(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)

    gallery = compliance_draft.get_primary_gallery(conn, candidate_id)

    assert gallery == []
    conn.close()
