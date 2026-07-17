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


def test_create_or_reuse_group_product_recreates_when_sizes_expand(tmp_path):
    # Regression: primary_mockup.py creates the group_products row with sizes=["8x12"] only.
    # On approval, publish_primary_group.py calls this again with the full 4-size list for the
    # same group_id. The old code only checked status (not variant sizes) and returned the
    # stale 8x12-only row unchanged - A3/A2/A1 would never be created on the real Gelato product.
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

    with patch("pipeline.gelato_client.delete_product") as mock_delete, \
         patch("pipeline.gelato_client.create_product_from_template") as mock_create:
        mock_create.return_value = {"id": "gelato-prod-2", "_dry_run": True, "previewUrl": None, "productImages": []}
        second = group_product.create_or_reuse_group_product(
            conn, group_id, ["8x12", "A3", "A2", "A1"], candidate, static_config, "Title",
            now="2026-07-16T09:11:00",
        )

    mock_delete.assert_called_once_with("gelato-prod-1", store_id=None, api_key=None)
    assert mock_create.call_count == 1
    variants_arg = mock_create.call_args[0][1]
    assert len(variants_arg) == 4
    assert second["group_product_id"] != first["group_product_id"]
    assert second["gelato_product_id"] == "gelato-prod-2"

    old_row = conn.execute(
        "SELECT status FROM group_products WHERE id = ?", (first["group_product_id"],)
    ).fetchone()
    assert old_row["status"] == "deleted"


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


def test_create_or_reuse_group_product_falls_back_to_base_image_when_gelato_returns_no_images(tmp_path):
    # Regression: single-variant group products (5x7, 10x24) never get a Gelato-rendered
    # productImages entry - confirmed live 2026-07-17, Gelato's mockup preview defaults to a
    # variant key (A1) not present in a 1-variant product. Without this fallback, critic_pass
    # and the digest gallery are stuck with 0 images forever and the group auto-abandons.
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn, base_image_url="https://replicate.delivery/flat-art.png")
    group_id = _insert_group(conn, candidate_id, group_type="5x7")
    candidate = dict(conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone())
    static_config = _static_config()

    with patch("pipeline.config.is_live_mode", return_value=True), \
         patch("pipeline.gelato_client.create_product_from_template") as mock_create, \
         patch("pipeline.group_product.poll_until_ready") as mock_poll, \
         patch("pipeline.image_crop.crop_for_group") as mock_crop:
        mock_create.return_value = {"id": "gelato-prod-1"}
        mock_poll.return_value = {"isReadyToPublish": True, "productImages": []}
        mock_crop.return_value = "/tmp/cropped-5x7.jpg"
        result = group_product.create_or_reuse_group_product(
            conn, group_id, ["5x7"], candidate, static_config, "Title", now="2026-07-16T09:10:00",
        )

    mock_crop.assert_called_once_with(
        "https://replicate.delivery/flat-art.png", "5x7", result["group_product_id"],
    )
    image_rows = conn.execute(
        "SELECT image_url, image_type FROM product_images WHERE group_product_id = ?",
        (result["group_product_id"],),
    ).fetchall()
    assert [dict(r) for r in image_rows] == [
        {"image_url": "/tmp/cropped-5x7.jpg", "image_type": "flat_mockup"},
    ]


def test_create_or_reuse_group_product_prefers_primary_group_image_over_dead_base_url(tmp_path):
    # Regression: candidate.base_image_url (raw Replicate delivery link) expires within a
    # couple hours - confirmed live 2026-07-17 - well within the time a design can sit
    # waiting for admin approval before its 5x7/10x24 groups get created. The primary
    # group's already-rehosted Gelato image is re-fetched live and never goes stale, so it
    # must be preferred over the raw base_image_url when Gelato returns no images.
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn, base_image_url="https://replicate.delivery/dead-link.png")
    primary_group_id = _insert_group(conn, candidate_id, group_type="primary")
    conn.execute(
        "INSERT INTO group_products (group_id, gelato_template_id, gelato_product_id, status, created_at, updated_at) "
        "VALUES (?, 'tmpl', 'primary-gelato-id', 'published', '2026-07-16T09:00:00', '2026-07-16T09:00:00')",
        (primary_group_id,),
    )
    conn.commit()
    group_id = _insert_group(conn, candidate_id, group_type="5x7")
    candidate = dict(conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone())
    static_config = _static_config()

    with patch("pipeline.config.is_live_mode", return_value=True), \
         patch("pipeline.gelato_client.create_product_from_template") as mock_create, \
         patch("pipeline.group_product.poll_until_ready") as mock_poll, \
         patch("pipeline.gelato_client.get_product") as mock_get_product, \
         patch("pipeline.image_crop.crop_for_group") as mock_crop:
        mock_create.return_value = {"id": "gelato-prod-1"}
        mock_poll.return_value = {"isReadyToPublish": True, "productImages": []}
        mock_get_product.return_value = {
            "productImages": [{"fileUrl": "https://gelato-rehosted/primary-flat.jpg", "isPrimary": True}]
        }
        mock_crop.return_value = "/tmp/cropped-5x7.jpg"
        result = group_product.create_or_reuse_group_product(
            conn, group_id, ["5x7"], candidate, static_config, "Title", now="2026-07-16T09:10:00",
        )

    mock_get_product.assert_called_once_with("primary-gelato-id", store_id=None, api_key=None)
    mock_crop.assert_called_once_with(
        "https://gelato-rehosted/primary-flat.jpg", "5x7", result["group_product_id"],
    )
    image_rows = conn.execute(
        "SELECT image_url FROM product_images WHERE group_product_id = ?",
        (result["group_product_id"],),
    ).fetchall()
    assert [dict(r)["image_url"] for r in image_rows] == ["/tmp/cropped-5x7.jpg"]


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

    # Gelato is "live" here (a real product exists to resolve externalId from) even though the
    # Etsy-side dry_run=True keeps the actual Etsy write calls dry. These are independent gates.
    with patch("pipeline.config.is_live_mode", return_value=True) as mock_live, \
         patch("pipeline.gelato_client.get_etsy_listing_id") as mock_resolve, \
         patch("pipeline.etsy_client.update_listing") as mock_update, \
         patch("pipeline.etsy_client.update_listing_inventory") as mock_inventory:
        mock_resolve.return_value = "etsy-listing-42"
        listing_id = group_product.patch_etsy_listing(
            conn, group_product_id, "primary", listing_text, static_config,
            shop_id="shop1", dry_run=True, now=timestamp,
        )

    mock_live.assert_called_with("GELATO")
    mock_resolve.assert_called_once_with("gelato-prod-1", store_id=None, api_key=None)
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


def test_patch_etsy_listing_uses_placeholder_id_when_gelato_not_live(tmp_path):
    # Regression test: patch_etsy_listing's dry_run parameter only gates the Etsy write calls.
    # Resolving etsy_listing_id is a Gelato-side read (gelato_client.get_product has no dry_run
    # of its own and always makes a real HTTP call) - it must be gated on Gelato's own liveness,
    # not on this function's dry_run. Otherwise, in the standard dev state (GELATO_LIVE_MODE
    # unset, create_or_reuse_group_product returns a fake "DRY_RUN_PRODUCT_ID"), calling this
    # would crash (missing creds) or hang (up to the 600s poll timeout).
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_group(conn, candidate_id)
    static_config = _static_config()
    timestamp = "2026-07-16T09:10:00"
    conn.execute(
        "INSERT INTO group_products (group_id, gelato_template_id, gelato_product_id, status, created_at, updated_at) "
        "VALUES (?, 'tmpl', 'DRY_RUN_PRODUCT_ID', 'created', ?, ?)",
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

    with patch("pipeline.config.is_live_mode", return_value=False), \
         patch("pipeline.gelato_client.get_etsy_listing_id") as mock_resolve, \
         patch("pipeline.etsy_client.update_listing") as mock_update, \
         patch("pipeline.etsy_client.update_listing_inventory") as mock_inventory:
        listing_id = group_product.patch_etsy_listing(
            conn, group_product_id, "primary", listing_text, static_config,
            shop_id="shop1", dry_run=True, now=timestamp,
        )

    mock_resolve.assert_not_called()
    assert listing_id == "DRY_RUN_ETSY_LISTING_ID"
    mock_update.assert_called_once()
    mock_inventory.assert_called_once()
    gp_row = conn.execute("SELECT etsy_listing_id FROM group_products WHERE id = ?", (group_product_id,)).fetchone()
    assert gp_row["etsy_listing_id"] == "DRY_RUN_ETSY_LISTING_ID"
