from unittest.mock import patch

import pytest

import pipeline.config as config
import pipeline.db as db
import pipeline.group_product as group_product


def _fresh_conn(tmp_path):
    conn = db.get_connection(tmp_path / "test.sqlite3")
    db.init_db(conn)
    return conn


def _insert_candidate(conn, niche="monstera line art", *, status="primary_review",
                       base_image_url="https://replicate.delivery/out.png"):
    timestamp = "2026-07-16T09:00:00"
    cursor = conn.execute(
        "INSERT INTO candidates (created_at, niche, go_hold_kill, status, base_image_url, updated_at) "
        "VALUES (?, ?, 'go', ?, ?, ?)",
        (timestamp, niche, status, base_image_url, timestamp),
    )
    conn.commit()
    return cursor.lastrowid


def _insert_group(conn, candidate_id, group_type="primary", *, status="pending_review"):
    timestamp = "2026-07-16T09:05:00"
    cursor = conn.execute(
        "INSERT INTO groups (candidate_id, group_type, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (candidate_id, group_type, status, timestamp, timestamp),
    )
    conn.commit()
    return cursor.lastrowid


def _static_config():
    return config.load_static_config()


def test_create_or_reuse_group_product_creates_one_product_with_all_variants(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_group(conn, candidate_id)
    candidate = dict(conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone())
    static_config = _static_config()

    with patch("pipeline.gelato_client.create_product_from_template") as mock_create:
        mock_create.return_value = {"id": "gelato-prod-1", "_dry_run": True, "previewUrl": None, "productImages": []}
        result = group_product.create_or_reuse_group_product(
            conn, group_id, ["8x12", "A3", "A2", "A1"], candidate, static_config,
            "Monstera Line Art", now="2026-07-16T09:10:00",
        )

    assert mock_create.call_count == 1
    variants_arg = mock_create.call_args[0][1]
    assert [v["template_variant_id"] for v in variants_arg] == [
        static_config["gelato_templates"][f"{s}_portrait"]["template_variant_id"]
        for s in ("8x12", "A3", "A2", "A1")
    ]
    assert result["gelato_product_id"] == "gelato-prod-1"

    gp_row = conn.execute("SELECT * FROM group_products WHERE id = ?", (result["group_product_id"],)).fetchone()
    assert gp_row["status"] == "created"
    variant_rows = conn.execute(
        "SELECT size, price_eur FROM group_product_variants WHERE group_product_id = ? ORDER BY size",
        (result["group_product_id"],),
    ).fetchall()
    assert {r["size"]: r["price_eur"] for r in variant_rows} == {
        "8x12": static_config["prices_eur"]["8x12"], "A1": static_config["prices_eur"]["A1"],
        "A2": static_config["prices_eur"]["A2"], "A3": static_config["prices_eur"]["A3"],
    }


def test_create_or_reuse_group_product_reuses_existing_created_row(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_group(conn, candidate_id)
    candidate = dict(conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone())
    static_config = _static_config()

    with patch("pipeline.gelato_client.create_product_from_template") as mock_create:
        mock_create.return_value = {"id": "gelato-prod-1", "_dry_run": True, "previewUrl": None, "productImages": []}
        first = group_product.create_or_reuse_group_product(
            conn, group_id, ["8x12"], candidate, static_config, "Title", now="2026-07-16T09:10:00",
        )
        second = group_product.create_or_reuse_group_product(
            conn, group_id, ["8x12"], candidate, static_config, "Title", now="2026-07-16T09:11:00",
        )

    assert mock_create.call_count == 1
    assert first["group_product_id"] == second["group_product_id"]


def test_create_or_reuse_group_product_deletes_orphan_before_retry(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_group(conn, candidate_id)
    candidate = dict(conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone())
    static_config = _static_config()
    timestamp = "2026-07-16T09:10:00"

    conn.execute(
        "INSERT INTO group_products (group_id, gelato_template_id, gelato_product_id, status, created_at, updated_at) "
        "VALUES (?, 'tmpl', 'stale-gelato-id', 'publish_failed', ?, ?)",
        (group_id, timestamp, timestamp),
    )
    conn.commit()

    with patch("pipeline.gelato_client.delete_product") as mock_delete, \
         patch("pipeline.gelato_client.create_product_from_template") as mock_create:
        mock_create.return_value = {"id": "gelato-prod-new", "_dry_run": True, "previewUrl": None, "productImages": []}
        result = group_product.create_or_reuse_group_product(
            conn, group_id, ["8x12"], candidate, static_config, "Title", now=timestamp,
        )

    mock_delete.assert_called_once_with("stale-gelato-id", store_id=None, api_key=None)
    assert result["gelato_product_id"] == "gelato-prod-new"
    stale_row = conn.execute(
        "SELECT status FROM group_products WHERE gelato_product_id = 'stale-gelato-id'"
    ).fetchone()
    assert stale_row["status"] == "deleted"


def test_patch_etsy_listing_resolves_id_patches_and_sets_variant_prices(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_group(conn, candidate_id)
    static_config = _static_config()
    timestamp = "2026-07-16T09:10:00"
    conn.execute(
        "INSERT INTO group_products (group_id, gelato_template_id, gelato_product_id, status, created_at, updated_at) "
        "VALUES (?, 'tmpl', 'gelato-prod-1', 'created', ?, ?)",
        (group_id, timestamp, timestamp),
    )
    group_product_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
    conn.execute(
        "INSERT INTO group_product_variants (group_product_id, size, orientation, gelato_template_variant_id, price_eur, created_at) "
        "VALUES (?, '8x12', 'portrait', 'var1', 24.0, ?)", (group_product_id, timestamp),
    )
    conn.commit()

    listing_text = {
        "title": "Monstera Line Art", "description": "desc", "tags": '["a", "b"]',
        "who_made": "i_did", "taxonomy_id": "1027", "production_partner_ids": "[5717252]",
    }

    with patch("pipeline.gelato_client.get_etsy_listing_id") as mock_resolve, \
         patch("pipeline.etsy_client.update_listing") as mock_update, \
         patch("pipeline.etsy_client.update_listing_inventory") as mock_inventory:
        mock_resolve.return_value = "etsy-listing-42"
        listing_id = group_product.patch_etsy_listing(
            conn, group_product_id, "primary", listing_text, static_config,
            shop_id="shop1", dry_run=True, now=timestamp,
        )

    assert listing_id == "etsy-listing-42"
    mock_update.assert_called_once()
    patched_data = mock_update.call_args[0][2]
    assert patched_data["title"] == "Monstera Line Art"
    assert "8x12" not in patched_data["title"]
    mock_inventory.assert_called_once_with(
        "shop1", "etsy-listing-42", {"8x12": 24.0},
        api_key=None, api_secret=None, access_token=None, dry_run=True,
    )
    gp_row = conn.execute("SELECT etsy_listing_id, status FROM group_products WHERE id = ?", (group_product_id,)).fetchone()
    assert gp_row["etsy_listing_id"] == "etsy-listing-42"
    assert gp_row["status"] == "published"
