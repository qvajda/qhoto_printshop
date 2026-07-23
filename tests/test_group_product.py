from pathlib import Path
from unittest.mock import patch

import pytest

import pipeline.artwork_store as artwork_store
import pipeline.config as config
import pipeline.db as db
import pipeline.gelato_client as gelato_client
import pipeline.group_product as group_product


def test_poll_until_ready_jitters_the_sleep_interval():
    # Sleeps between polls carry +-20% jitter so a run isn't a metronome of identical
    # fresh connections (a Cloudflare bot-rate signal). Inject sleep_fn - never real-sleep.
    slept = []
    ready = {
        "isReadyToPublish": True,
        "productImages": [{"fileUrl": f"https://{gelato_client.GELATO_IMAGE_HOST}/a.jpg", "isPrimary": True}],
    }
    not_ready = {"isReadyToPublish": False, "productImages": []}

    with patch("pipeline.gelato_client.get_product", side_effect=[not_ready, not_ready, ready]), \
         patch("pipeline.group_product._image_is_fetchable", return_value=True):
        result = group_product.poll_until_ready(
            "prod-1", poll_interval=10.0, timeout=1000.0,
            sleep_fn=slept.append, now_fn=lambda: 0.0,
        )

    assert result is ready
    assert len(slept) == 2
    assert all(8.0 <= s <= 12.0 for s in slept)


def test_jittered_stays_within_plus_minus_20_percent():
    # H4 regression: direct bounds check on the jitter helper the fan-out relies on.
    for _ in range(1000):
        assert 8.0 <= group_product._jittered(10.0) <= 12.0
    assert group_product._jittered(0.0) == 0.0


def _fresh_conn(tmp_path):
    conn = db.get_connection(tmp_path / "test.sqlite3")
    db.init_db(conn)
    return conn


def _insert_candidate(conn, niche="monstera line art", *, status="primary_review",
                       base_image_url="https://replicate.delivery/out.png", base_image_local_path=None):
    timestamp = "2026-07-16T09:00:00"
    cursor = conn.execute(
        "INSERT INTO candidates (created_at, niche, go_hold_kill, status, base_image_url, "
        "base_image_local_path, updated_at) VALUES (?, ?, 'go', ?, ?, ?, ?)",
        (timestamp, niche, status, base_image_url, base_image_local_path, timestamp),
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


def _make_master(tmp_path, name="master.png", size=(900, 1350)):
    from PIL import Image
    p = tmp_path / name
    Image.new("RGB", size, (200, 180, 150)).save(p, format="PNG")
    return str(p)


def test_create_or_reuse_group_product_creates_one_product_with_all_variants(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn, base_image_local_path=_make_master(tmp_path))
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
    candidate_id = _insert_candidate(conn, base_image_local_path=_make_master(tmp_path))
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
    candidate_id = _insert_candidate(conn, base_image_local_path=_make_master(tmp_path))
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
    candidate_id = _insert_candidate(conn, base_image_local_path=_make_master(tmp_path))
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


def test_create_or_reuse_group_product_reuses_mockup_failed_product_instead_of_recreating(tmp_path):
    # Regression: a mockup_failed row means Gelato created the product (gelato_product_id set)
    # but the readiness poll timed out on rehost lag. Retrying must REUSE + re-poll that same
    # product, never delete + recreate it (idempotency; avoids churning real Gelato products).
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn, base_image_local_path=_make_master(tmp_path))
    group_id = _insert_group(conn, candidate_id)
    candidate = dict(conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone())
    static_config = _static_config()
    timestamp = "2026-07-16T09:10:00"

    conn.execute(
        "INSERT INTO group_products (group_id, gelato_template_id, gelato_product_id, status, created_at, updated_at) "
        "VALUES (?, 'tmpl', 'live-prod-1', 'mockup_failed', ?, ?)",
        (group_id, timestamp, timestamp),
    )
    conn.commit()
    failed_id = conn.execute("SELECT id FROM group_products WHERE gelato_product_id = 'live-prod-1'").fetchone()["id"]

    with patch("pipeline.gelato_client.delete_product") as mock_delete, \
         patch("pipeline.gelato_client.create_product_from_template") as mock_create, \
         patch("pipeline.group_product.poll_until_ready") as mock_poll:
        mock_poll.return_value = {
            "isReadyToPublish": True,
            "productImages": [{"fileUrl": f"https://{gelato_client.GELATO_IMAGE_HOST}/a.jpg", "isPrimary": True}],
        }
        result = group_product.create_or_reuse_group_product(
            conn, group_id, ["8x12"], candidate, static_config, "Title", now="2026-07-16T09:12:00",
        )

    mock_delete.assert_not_called()
    mock_create.assert_not_called()
    mock_poll.assert_called_once_with(
        "live-prod-1", store_id=None, api_key=None, poll_interval=10.0, timeout=300.0,
    )
    assert result["group_product_id"] == failed_id
    assert result["gelato_product_id"] == "live-prod-1"
    row = conn.execute("SELECT status FROM group_products WHERE id = ?", (failed_id,)).fetchone()
    assert row["status"] == "created"


# --- GL-5 task 3: self-hosted mockup gallery replaces the Gelato-gallery fallback ---
# The two tests previously here (falls_back_to_base_image_when_gelato_returns_no_images,
# prefers_primary_group_image_over_dead_base_url) tested the old Gelato-gallery-driven
# fallback mechanism (_primary_flat_image_url + image_crop.crop_for_group), which this
# task deletes outright per the hard "no Gelato fallback, ever" constraint - their
# scenario no longer exists, so they're removed rather than patched.

def test_create_or_reuse_group_product_renders_primary_gallery_from_master_no_crop(tmp_path):
    # Real (non-mocked) mockup_render output, using the real Task 1 bundles under
    # assets/mockups/primary/portrait - proves the actual end-to-end integration, not
    # a fixture. Primary renders straight from base_image_local_path (no crop step);
    # flat scenes come first (image_type='flat_mockup'), lifestyle scenes after.
    conn = _fresh_conn(tmp_path)
    master_path = _make_master(tmp_path)
    candidate_id = _insert_candidate(conn, base_image_local_path=master_path)
    group_id = _insert_group(conn, candidate_id, group_type="primary")
    candidate = dict(conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone())
    static_config = _static_config()

    with patch("pipeline.gelato_client.create_product_from_template") as mock_create:
        mock_create.return_value = {"id": "gelato-prod-1", "_dry_run": True, "previewUrl": None, "productImages": []}
        result = group_product.create_or_reuse_group_product(
            conn, group_id, ["8x12"], candidate, static_config, "Title", now="2026-07-16T09:10:00",
        )

    image_rows = conn.execute(
        "SELECT image_url, image_type, gallery_order FROM product_images WHERE group_product_id = ? "
        "ORDER BY gallery_order",
        (result["group_product_id"],),
    ).fetchall()
    assert [r["image_type"] for r in image_rows] == [
        "flat_mockup", "flat_mockup", "lifestyle", "lifestyle",
    ]
    assert [r["gallery_order"] for r in image_rows] == [0, 1, 2, 3]
    # Rendered/persisted URLs only - never the raw master or a Gelato URL.
    for row in image_rows:
        assert row["image_url"] != master_path
        assert "gelato" not in row["image_url"].lower()
        assert Path(row["image_url"]).exists()

    gp_row = conn.execute("SELECT status FROM group_products WHERE id = ?", (result["group_product_id"],)).fetchone()
    assert gp_row["status"] == "created"


def test_create_or_reuse_group_product_5x7_builds_crop_then_zero_images_known_gap(tmp_path):
    # No 5x7 mockup bundles exist yet (GL-6-proper's job, not this task's - see the
    # brief's "known, plan-accepted gap"). This currently and correctly produces ZERO
    # product_images rows: config.get_mockup_templates("5x7", ...) resolves to [],
    # empty scene list -> empty render loop -> nothing to insert. Not a bug. What this
    # test actually guards: the group-specific cover-crop still gets built (proving the
    # non-primary crop-then-render path runs), and the group still lands on status
    # 'created' (not 'mockup_failed') - an empty gallery is a valid outcome, not a
    # failure.
    conn = _fresh_conn(tmp_path)
    master_path = _make_master(tmp_path, size=(1600, 3700))  # clears 150 DPI at 5x7
    candidate_id = _insert_candidate(conn, base_image_local_path=master_path)
    group_id = _insert_group(conn, candidate_id, group_type="5x7")
    candidate = dict(conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone())
    static_config = _static_config()

    with patch("pipeline.gelato_client.create_product_from_template") as mock_create:
        mock_create.return_value = {"id": "gelato-prod-1", "_dry_run": True, "previewUrl": None, "productImages": []}
        result = group_product.create_or_reuse_group_product(
            conn, group_id, ["5x7"], candidate, static_config, "Title", now="2026-07-16T09:10:00",
        )

    # The crop was built (proves the crop-then-render path actually ran).
    assert (artwork_store.ARTWORK_CACHE_DIR / f"{candidate_id}_5x7_crop.png").exists()

    image_rows = conn.execute(
        "SELECT image_url FROM product_images WHERE group_product_id = ?",
        (result["group_product_id"],),
    ).fetchall()
    assert image_rows == []  # known gap: no 5x7 bundles authored yet

    gp_row = conn.execute("SELECT status FROM group_products WHERE id = ?", (result["group_product_id"],)).fetchone()
    assert gp_row["status"] == "created"


def test_create_or_reuse_group_product_missing_local_master_lands_on_mockup_failed(tmp_path):
    # A bad/missing base_image_local_path must not silently skip rendering or fall back
    # to any Gelato/base image - it must propagate up through the existing except
    # Exception and land the group on mockup_failed, same as any other render failure.
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn, base_image_local_path=None)
    group_id = _insert_group(conn, candidate_id, group_type="primary")
    candidate = dict(conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone())
    static_config = _static_config()

    with patch("pipeline.gelato_client.create_product_from_template") as mock_create:
        mock_create.return_value = {"id": "gelato-prod-1", "_dry_run": True, "previewUrl": None, "productImages": []}
        with pytest.raises(group_product.PrintResolutionError):
            group_product.create_or_reuse_group_product(
                conn, group_id, ["8x12"], candidate, static_config, "Title", now="2026-07-16T09:10:00",
            )

    gp_row = conn.execute("SELECT status FROM group_products WHERE group_id = ?", (group_id,)).fetchone()
    assert gp_row["status"] == "mockup_failed"


def test_create_or_reuse_group_product_never_uses_gelato_preview_or_base_url_as_image(tmp_path):
    # Determinism / no-Gelato-fallback guard: even when the Gelato dry-run response
    # carries a previewUrl, and the candidate has a (dead) base_image_url, neither ends
    # up as a product_images.image_url - only our own rendered/persisted URLs do. This
    # directly guards the hard "no Gelato fallback, ever" constraint.
    conn = _fresh_conn(tmp_path)
    master_path = _make_master(tmp_path)
    candidate_id = _insert_candidate(
        conn, base_image_url="https://replicate.delivery/dead-link.png", base_image_local_path=master_path,
    )
    group_id = _insert_group(conn, candidate_id, group_type="primary")
    candidate = dict(conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone())
    static_config = _static_config()

    with patch("pipeline.gelato_client.create_product_from_template") as mock_create:
        mock_create.return_value = {
            "id": "gelato-prod-1", "_dry_run": True,
            "previewUrl": "https://gelato-preview.example.com/sneaky.jpg", "productImages": [],
        }
        result = group_product.create_or_reuse_group_product(
            conn, group_id, ["8x12"], candidate, static_config, "Title", now="2026-07-16T09:10:00",
        )

    image_rows = conn.execute(
        "SELECT image_url FROM product_images WHERE group_product_id = ?",
        (result["group_product_id"],),
    ).fetchall()
    assert len(image_rows) == 4
    for row in image_rows:
        assert row["image_url"] != "https://gelato-preview.example.com/sneaky.jpg"
        assert row["image_url"] != "https://replicate.delivery/dead-link.png"


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


def test_patch_etsy_listing_never_activates_a_listing(tmp_path):
    # B1 (inverted): drafts stay drafts. patch_etsy_listing must never call
    # update_listing_state, and must never send a 'state' field in update_listing's
    # payload - either would activate the listing ($0.20 each). group_products.status
    # 'published' means "patched draft", not "live on Etsy". Guards against a future
    # "helpful" wiring of the deliberately-unused update_listing_state.
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

    with patch("pipeline.config.is_live_mode", return_value=True), \
         patch("pipeline.gelato_client.get_etsy_listing_id", return_value="etsy-listing-42"), \
         patch("pipeline.etsy_client.update_listing_state") as mock_state, \
         patch("pipeline.etsy_client.update_listing") as mock_update, \
         patch("pipeline.etsy_client.update_listing_inventory"):
        group_product.patch_etsy_listing(
            conn, group_product_id, "primary", listing_text, static_config,
            shop_id="shop1", dry_run=True, now=timestamp,
        )

    mock_state.assert_not_called()
    patched_data = mock_update.call_args[0][2]
    assert "state" not in patched_data
    conn.close()


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


def test_patch_etsy_listing_uploads_gallery_images_in_gallery_order(tmp_path):
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
    # Deliberately inserted out of gallery_order to prove the SELECT's ORDER BY drives
    # upload order, not insertion order.
    conn.execute(
        "INSERT INTO product_images (group_product_id, image_url, alt_text, gallery_order, image_type) "
        "VALUES (?, 'https://cdn.example.com/second.jpg', 'alt', 1, 'lifestyle')", (group_product_id,),
    )
    conn.execute(
        "INSERT INTO product_images (group_product_id, image_url, alt_text, gallery_order, image_type) "
        "VALUES (?, '/local/first.jpg', 'alt', 0, 'flat_mockup')", (group_product_id,),
    )
    conn.commit()

    listing_text = {
        "title": "Monstera Line Art", "description": "desc", "tags": '["a", "b"]',
        "who_made": "i_did", "taxonomy_id": "1027", "production_partner_ids": "[5717252]",
    }

    with patch("pipeline.config.is_live_mode", return_value=True), \
         patch("pipeline.gelato_client.get_etsy_listing_id", return_value="etsy-listing-42"), \
         patch("pipeline.etsy_client.update_listing"), \
         patch("pipeline.etsy_client.update_listing_inventory"), \
         patch("pipeline.etsy_client.upload_listing_image") as mock_upload:
        group_product.patch_etsy_listing(
            conn, group_product_id, "primary", listing_text, static_config,
            shop_id="shop1", dry_run=True, now=timestamp,
        )

    assert mock_upload.call_count == 2
    first_call, second_call = mock_upload.call_args_list
    assert first_call.args[:2] == ("shop1", "etsy-listing-42")
    assert second_call.args[:2] == ("shop1", "etsy-listing-42")
    assert first_call.kwargs["dry_run"] is True
    assert second_call.kwargs["dry_run"] is True


def test_patch_etsy_listing_uploads_nothing_when_no_gallery_images(tmp_path):
    # Known Task 3 gap: 5x7/10x24 groups can land with zero product_images rows.
    # patch_etsy_listing must not error on that - it just uploads nothing and the
    # rest of the listing/inventory patch still completes.
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
        "VALUES (?, '5x7', 'portrait', 'var1', 19.0, ?)", (group_product_id, timestamp),
    )
    conn.commit()

    listing_text = {
        "title": "Monstera Line Art", "description": "desc", "tags": '["a", "b"]',
        "who_made": "i_did", "taxonomy_id": "1027", "production_partner_ids": "[5717252]",
    }

    with patch("pipeline.config.is_live_mode", return_value=True), \
         patch("pipeline.gelato_client.get_etsy_listing_id", return_value="etsy-listing-42"), \
         patch("pipeline.etsy_client.update_listing") as mock_update, \
         patch("pipeline.etsy_client.update_listing_inventory") as mock_inventory, \
         patch("pipeline.etsy_client.upload_listing_image") as mock_upload:
        listing_id = group_product.patch_etsy_listing(
            conn, group_product_id, "5x7", listing_text, static_config,
            shop_id="shop1", dry_run=True, now=timestamp,
        )

    mock_upload.assert_not_called()
    mock_update.assert_called_once()
    mock_inventory.assert_called_once()
    assert listing_id == "etsy-listing-42"
    gp_row = conn.execute("SELECT status FROM group_products WHERE id = ?", (group_product_id,)).fetchone()
    assert gp_row["status"] == "published"


# --- B5 pre-create print-DPI guard ---

def _make_image(tmp_path, name, size):
    from PIL import Image
    p = tmp_path / name
    Image.new("RGB", size, (200, 180, 150)).save(p, format="PNG")
    return str(p)


def test_assert_print_dpi_passes_for_adequate_master(tmp_path):
    # 900x1350 clears 150 DPI at 5x7 (900/5=180, 1350/7=192 -> 180 DPI).
    path = _make_image(tmp_path, "ok.png", (900, 1350))
    group_product._assert_print_dpi(["5x7"], path)  # must not raise


def test_assert_print_dpi_raises_for_undersized_master(tmp_path):
    # Same 900x1350 is far too small for A1 (900/23.39 ~= 38 DPI).
    path = _make_image(tmp_path, "small.png", (900, 1350))
    with pytest.raises(group_product.PrintResolutionError) as exc:
        group_product._assert_print_dpi(["A1"], path)
    assert "A1" in str(exc.value)
    assert "38 DPI" in str(exc.value)


def test_assert_print_dpi_takes_worst_size_in_a_multi_size_group(tmp_path):
    # A group offering 5x7 (passes) + A1 (fails) must fail on the worst size.
    path = _make_image(tmp_path, "mixed.png", (900, 1350))
    with pytest.raises(group_product.PrintResolutionError):
        group_product._assert_print_dpi(["5x7", "A1"], path)


def test_assert_print_dpi_raises_when_local_path_missing():
    with pytest.raises(group_product.PrintResolutionError) as exc:
        group_product._assert_print_dpi(["8x12"], None)
    assert "missing or unreadable" in str(exc.value)


# --- GL-14: real print crop reaches Gelato for 5x7/10x24 ---

def test_real_create_sends_hosted_print_crop_not_raw_master_for_10x24(tmp_path):
    # End-to-end (real image_crop + artwork_store, only http.put_bytes and the
    # Gelato call are mocked): the create call must receive the cropped, hosted
    # URL - not candidate.base_image_url - for a non-primary group type.
    from PIL import Image
    master_path = tmp_path / "master.png"
    # Clears 150 DPI at 10x24 (1600/10=160, 3700/24~=154).
    Image.new("RGB", (1600, 3700), (200, 180, 150)).save(master_path, format="PNG")

    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(
        conn, base_image_url="https://replicate.delivery/master.png",
        base_image_local_path=str(master_path),
    )
    group_id = _insert_group(conn, candidate_id, group_type="10x24")
    candidate = dict(conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone())
    static_config = _static_config()

    r2_env = {
        "R2_ACCOUNT_ID": "acct", "R2_ACCESS_KEY_ID": "key", "R2_SECRET_ACCESS_KEY": "secret",
        "R2_BUCKET": "bucket", "R2_ENDPOINT": "https://acct.r2.cloudflarestorage.com",
        "R2_PUBLIC_BASE_URL": "https://cdn.example.com",
    }

    with patch("pipeline.config.is_live_mode", return_value=True), \
         patch.dict("os.environ", r2_env), \
         patch("pipeline.group_product.gelato_client.create_product_from_template") as mock_create, \
         patch("pipeline.group_product.poll_until_ready") as mock_poll, \
         patch("pipeline.artwork_store.http.put_bytes") as mock_put:
        mock_create.return_value = {"id": "gelato-prod-1"}
        mock_poll.return_value = {"isReadyToPublish": True, "productImages": [{"fileUrl": "x", "isPrimary": True}]}
        group_product.create_or_reuse_group_product(
            conn, group_id, ["10x24"], candidate, static_config, "Title", now="2026-07-16T09:10:00",
        )

    mock_put.assert_called_once()  # the crop was actually built and uploaded
    variants_arg = mock_create.call_args[0][1]
    assert variants_arg[0]["image_url"] == f"https://cdn.example.com/base/{candidate_id}_10x24_crop.png"
    assert variants_arg[0]["image_url"] != candidate["base_image_url"]


def test_real_create_fails_loud_for_secondary_group_when_r2_not_configured(tmp_path, monkeypatch):
    # If R2 isn't configured, persist_group_crop's durable_url is a local filesystem
    # path - the create-path's existing non-http(s) guard must reject it, not
    # silently fall back to the uncropped master (that's the bug this fixes).
    from PIL import Image
    for key in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY",
                "R2_BUCKET", "R2_ENDPOINT", "R2_PUBLIC_BASE_URL"):
        monkeypatch.delenv(key, raising=False)

    master_path = tmp_path / "master.png"
    Image.new("RGB", (900, 1350), (200, 180, 150)).save(master_path, format="PNG")

    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(
        conn, base_image_url="https://replicate.delivery/master.png",
        base_image_local_path=str(master_path),
    )
    group_id = _insert_group(conn, candidate_id, group_type="5x7")
    candidate = dict(conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone())
    static_config = _static_config()

    with patch("pipeline.config.is_live_mode", return_value=True):
        with pytest.raises(gelato_client.GelatoInvalidImageURLError):
            group_product.create_or_reuse_group_product(
                conn, group_id, ["5x7"], candidate, static_config, "Title", now="2026-07-16T09:10:00",
            )

    gp_row = conn.execute("SELECT status FROM group_products WHERE group_id = ?", (group_id,)).fetchone()
    assert gp_row["status"] == "mockup_failed"


def test_scale8_master_clears_150_dpi_at_every_offered_size():
    # Documents the B5 fix constants: the scale=8 master (6656x9728) must clear the
    # 150 DPI floor at every size, worst case A1. Pure arithmetic on the size table.
    px_short, px_long = 6656, 9728
    for size, (short_in, long_in) in group_product._SIZE_INCHES.items():
        dpi = min(px_short / short_in, px_long / long_in)
        assert dpi >= group_product.MIN_PRINT_DPI, f"{size} only {dpi:.0f} DPI"
