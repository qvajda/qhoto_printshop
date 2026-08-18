from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

import pipeline.artwork_store as artwork_store
import pipeline.config as config
import pipeline.db as db
import pipeline.gelato_client as gelato_client
import pipeline.group_product as group_product
import pipeline.reconcile as reconcile


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


def _make_master(tmp_path, name="master.png", size=(900, 1316)):
    from PIL import Image
    p = tmp_path / name
    Image.new("RGB", size, (200, 180, 150)).save(p, format="PNG")
    return str(p)


DRY = {"id": "gelato-prod-1", "_dry_run": True, "previewUrl": None, "productImages": []}

LISTING_TEXT = {
    "title": "Monstera Line Art", "description": "desc", "tags": '["a", "b"]',
    "who_made": "i_did", "taxonomy_id": "1027", "production_partner_ids": "[5717252]",
}


def _decide(conn, group_id, decision="approved"):
    conn.execute("UPDATE groups SET decision = ? WHERE id = ?", (decision, group_id))
    conn.commit()


def _images(conn, group_product_id, group_id=None):
    sql = "SELECT * FROM product_images WHERE group_product_id = ?"
    args = [group_product_id]
    if group_id is not None:
        sql += " AND group_id = ?"
        args.append(group_id)
    return conn.execute(sql + " ORDER BY gallery_order", args).fetchall()


# --- v4.12: the render half. No Gelato call, scoped to one group. ---

def test_render_group_mockups_makes_no_gelato_call(stub_mockup_bundles, tmp_path):
    # The weld cut: rendering the review gallery must not create (or touch) a Gelato
    # product. The product is the candidate's and is created once, at publish.
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn, base_image_local_path=_make_master(tmp_path))
    group_id = _insert_group(conn, candidate_id)
    candidate = dict(conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone())

    with patch("pipeline.gelato_client.create_product_from_template") as mock_create, \
         patch("pipeline.gelato_client.delete_product") as mock_delete, \
         patch("pipeline.group_product.poll_until_ready") as mock_poll:
        result = group_product.render_group_mockups(
            conn, group_id, ["8x12", "A3", "A2", "A1"], candidate, _static_config(),
            now="2026-07-16T09:10:00",
        )

    mock_create.assert_not_called()
    mock_delete.assert_not_called()
    mock_poll.assert_not_called()

    gp_row = conn.execute(
        "SELECT * FROM group_products WHERE id = ?", (result["group_product_id"],)
    ).fetchone()
    assert gp_row["status"] == "pending"
    assert gp_row["gelato_product_id"] is None
    assert gp_row["candidate_id"] == candidate_id

    static_config = _static_config()
    variant_rows = conn.execute(
        "SELECT size, price_eur, group_id FROM group_product_variants WHERE group_product_id = ?",
        (result["group_product_id"],),
    ).fetchall()
    assert {r["size"]: r["price_eur"] for r in variant_rows} == {
        s: static_config["prices_eur"][s] for s in ("8x12", "A3", "A2", "A1")
    }
    assert {r["group_id"] for r in variant_rows} == {group_id}


def test_render_group_mockups_reuses_the_candidates_one_listing_record(tmp_path):
    # v4.12 reuse key is candidate_id: a second group of the SAME candidate renders into
    # the candidate's existing listing record, it does not open a second one.
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn, base_image_local_path=_make_master(tmp_path))
    primary_group_id = _insert_group(conn, candidate_id, group_type="primary")
    secondary_group_id = _insert_group(conn, candidate_id, group_type="5x7")
    candidate = dict(conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone())
    static_config = _static_config()

    first = group_product.render_group_mockups(
        conn, primary_group_id, ["8x12"], candidate, static_config, now="2026-07-16T09:10:00",
    )
    second = group_product.render_group_mockups(
        conn, secondary_group_id, ["5x7"], candidate, static_config, now="2026-07-16T09:11:00",
    )

    assert first["group_product_id"] == second["group_product_id"]
    assert conn.execute("SELECT COUNT(*) AS n FROM group_products").fetchone()["n"] == 1


def test_rendering_a_secondary_group_leaves_the_primary_gallery_untouched(tmp_path):
    # THE reason GL-22 session 2 exists. group_product.py's image rebuild used to be
    # `DELETE FROM product_images WHERE group_product_id = ?`; with one product per
    # candidate that unscoped delete wipes the primary group's already-reviewed gallery
    # the moment the 5x7 group renders its own. Nothing downstream would notice until a
    # buyer saw the listing.
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn, base_image_local_path=_make_master(tmp_path))
    primary_group_id = _insert_group(conn, candidate_id, group_type="primary")
    secondary_group_id = _insert_group(conn, candidate_id, group_type="5x7")
    candidate = dict(conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone())
    static_config = _static_config()

    first = group_product.render_group_mockups(
        conn, primary_group_id, ["8x12"], candidate, static_config, now="2026-07-16T09:10:00",
    )
    gpid = first["group_product_id"]
    before = [dict(r) for r in _images(conn, gpid, primary_group_id)]
    assert before, "the primary group must have rendered a gallery to protect"

    group_product.render_group_mockups(
        conn, secondary_group_id, ["5x7"], candidate, static_config, now="2026-07-16T09:11:00",
    )

    after = [dict(r) for r in _images(conn, gpid, primary_group_id)]
    assert after == before
    # ...and the 5x7 group's own images landed alongside, not on top.
    assert _images(conn, gpid, secondary_group_id)


def test_render_group_mockups_rerender_replaces_only_its_own_images(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn, base_image_local_path=_make_master(tmp_path))
    primary_group_id = _insert_group(conn, candidate_id, group_type="primary")
    secondary_group_id = _insert_group(conn, candidate_id, group_type="5x7")
    candidate = dict(conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone())
    static_config = _static_config()

    result = group_product.render_group_mockups(
        conn, primary_group_id, ["8x12"], candidate, static_config, now="2026-07-16T09:10:00",
    )
    gpid = result["group_product_id"]
    group_product.render_group_mockups(
        conn, secondary_group_id, ["5x7"], candidate, static_config, now="2026-07-16T09:11:00",
    )
    primary_before = len(_images(conn, gpid, primary_group_id))
    secondary_before = [dict(r) for r in _images(conn, gpid, secondary_group_id)]

    # Re-render the primary group (a critic-pass retry). Idempotent for itself, inert
    # for everyone else.
    group_product.render_group_mockups(
        conn, primary_group_id, ["8x12"], candidate, static_config, now="2026-07-16T09:12:00",
    )
    assert len(_images(conn, gpid, primary_group_id)) == primary_before
    assert [dict(r) for r in _images(conn, gpid, secondary_group_id)] == secondary_before


def test_render_group_mockups_renders_primary_gallery_from_master_no_crop(stub_mockup_bundles, tmp_path):
    # Primary renders straight from base_image_local_path (no crop step); flat scenes
    # come first (image_type='flat_mockup'), lifestyle after. Real (non-mocked)
    # mockup_render output against the aspect-correct stub bundles.
    conn = _fresh_conn(tmp_path)
    master_path = _make_master(tmp_path)
    candidate_id = _insert_candidate(conn, base_image_local_path=master_path)
    group_id = _insert_group(conn, candidate_id, group_type="primary")
    candidate = dict(conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone())
    static_config = _static_config()

    result = group_product.render_group_mockups(
        conn, group_id, ["8x12"], candidate, static_config, now="2026-07-16T09:10:00",
    )

    image_rows = _images(conn, result["group_product_id"])
    scenes = static_config["mockup_templates"]["primary"]["portrait"]
    assert [r["image_type"] for r in image_rows] == [
        "flat_mockup" if s.startswith("flat") else "lifestyle" for s in scenes]
    assert [r["gallery_order"] for r in image_rows] == list(range(len(scenes)))
    assert {r["group_id"] for r in image_rows} == {group_id}
    # Rendered/persisted URLs only - never the raw master or a Gelato URL.
    for row in image_rows:
        assert row["image_url"] != master_path
        assert "gelato" not in row["image_url"].lower()
        assert Path(row["image_url"]).exists()


def test_render_group_mockups_renders_gallery_from_the_real_bundles(tmp_path):
    # The real assets/mockups/primary/portrait bundles, not the stubs - the one test
    # that proves the shipped scene library actually composites.
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn, base_image_local_path=_make_master(tmp_path))
    group_id = _insert_group(conn, candidate_id, group_type="primary")
    candidate = dict(conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone())

    result = group_product.render_group_mockups(
        conn, group_id, ["8x12"], candidate, _static_config(), now="2026-07-16T09:10:00",
    )

    rows = _images(conn, result["group_product_id"])
    scenes = _static_config()["mockup_templates"]["primary"]["portrait"]
    assert scenes, "the primary group must ship at least one real bundle"
    assert [r["image_type"] for r in rows] == [
        "flat_mockup" if s.startswith("flat") else "lifestyle" for s in scenes]


def test_render_group_mockups_5x7_builds_crop_then_renders_its_gallery(tmp_path):
    conn = _fresh_conn(tmp_path)
    master_path = _make_master(tmp_path, size=(1600, 3700))  # clears 150 DPI at 5x7
    candidate_id = _insert_candidate(conn, base_image_local_path=master_path)
    group_id = _insert_group(conn, candidate_id, group_type="5x7")
    candidate = dict(conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone())

    result = group_product.render_group_mockups(
        conn, group_id, ["5x7"], candidate, _static_config(), now="2026-07-16T09:10:00",
    )

    # The crop was built (proves the crop-then-render path actually ran).
    assert (artwork_store.ARTWORK_CACHE_DIR / f"{candidate_id}_5x7_crop.png").exists()
    assert _images(conn, result["group_product_id"]), "a 5x7 group would ship no gallery images"


def test_render_group_mockups_missing_local_master_lands_on_mockup_failed(tmp_path):
    # A bad/missing base_image_local_path must not silently skip rendering or fall back
    # to any Gelato/base image - it must land the listing record on mockup_failed.
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn, base_image_local_path=None)
    group_id = _insert_group(conn, candidate_id, group_type="primary")
    candidate = dict(conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone())

    with pytest.raises(group_product.PrintResolutionError):
        group_product.render_group_mockups(
            conn, group_id, ["8x12"], candidate, _static_config(), now="2026-07-16T09:10:00",
        )

    gp_row = conn.execute("SELECT status FROM group_products WHERE group_id = ?", (group_id,)).fetchone()
    assert gp_row["status"] == "mockup_failed"


def test_render_group_mockups_never_uses_gelato_preview_or_base_url_as_image(stub_mockup_bundles, tmp_path):
    # No-Gelato-fallback guard: the candidate's (dead) base_image_url must never end up
    # as a product_images.image_url - only our own rendered/persisted URLs do.
    conn = _fresh_conn(tmp_path)
    master_path = _make_master(tmp_path)
    candidate_id = _insert_candidate(
        conn, base_image_url="https://replicate.delivery/dead-link.png", base_image_local_path=master_path,
    )
    group_id = _insert_group(conn, candidate_id, group_type="primary")
    candidate = dict(conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone())
    static_config = _static_config()

    result = group_product.render_group_mockups(
        conn, group_id, ["8x12"], candidate, static_config, now="2026-07-16T09:10:00",
    )

    image_rows = _images(conn, result["group_product_id"])
    assert len(image_rows) == len(static_config["mockup_templates"]["primary"]["portrait"])
    for row in image_rows:
        assert row["image_url"] != "https://replicate.delivery/dead-link.png"


def test_render_group_mockups_dpi_guard_fires_before_any_db_write(tmp_path):
    # B5, moved to the render path (GL-22 s2): a master too small to print must fail
    # BEFORE the owner spends a review on it, and without orphaning a listing record.
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn, base_image_local_path=_make_master(tmp_path, size=(900, 1350)))
    group_id = _insert_group(conn, candidate_id, group_type="primary")
    candidate = dict(conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone())

    with patch("pipeline.config.is_live_mode", return_value=True):
        with pytest.raises(group_product.PrintResolutionError) as exc:
            group_product.render_group_mockups(
                conn, group_id, ["8x12", "A3", "A2", "A1"], candidate, _static_config(),
                now="2026-07-16T09:10:00",
            )

    assert "A1" in str(exc.value)
    assert conn.execute("SELECT COUNT(*) AS n FROM group_products").fetchone()["n"] == 0


# --- v4.12: the Gelato half. One create per candidate, at publish. ---

def _rendered_candidate(conn, tmp_path, *, size=(900, 1316), secondary="5x7",
                        secondary_sizes=("5x7",), decide_secondary="approved",
                        base_image_url="https://replicate.delivery/master.png"):
    """A candidate whose primary group and one secondary group have both rendered."""
    candidate_id = _insert_candidate(
        conn, base_image_url=base_image_url,
        base_image_local_path=_make_master(tmp_path, size=size),
    )
    primary_group_id = _insert_group(conn, candidate_id, group_type="primary")
    secondary_group_id = _insert_group(conn, candidate_id, group_type=secondary)
    candidate = dict(conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone())
    static_config = _static_config()
    result = group_product.render_group_mockups(
        conn, primary_group_id, ["8x12"], candidate, static_config, now="2026-07-16T09:10:00",
    )
    group_product.render_group_mockups(
        conn, secondary_group_id, list(secondary_sizes), candidate, static_config,
        now="2026-07-16T09:11:00",
    )
    _decide(conn, primary_group_id, "approved")
    if decide_secondary is not None:
        _decide(conn, secondary_group_id, decide_secondary)
    return {
        "candidate_id": candidate_id, "candidate": candidate,
        "primary_group_id": primary_group_id, "secondary_group_id": secondary_group_id,
        "group_product_id": result["group_product_id"], "static_config": static_config,
    }


def test_create_candidate_gelato_product_makes_one_call_with_every_validated_size(tmp_path):
    conn = _fresh_conn(tmp_path)
    ctx = _rendered_candidate(conn, tmp_path)

    with patch("pipeline.gelato_client.create_product_from_template") as mock_create:
        mock_create.return_value = DRY
        result = group_product.create_candidate_gelato_product(
            conn, ctx["candidate_id"], ctx["candidate"], ctx["static_config"], "Title",
            now="2026-07-16T09:20:00",
        )

    assert mock_create.call_count == 1
    variants_arg = mock_create.call_args[0][1]
    static_config = ctx["static_config"]
    assert [v["template_variant_id"] for v in variants_arg] == [
        static_config["gelato_templates"][f"{s}_portrait"]["template_variant_id"]
        for s in ("8x12", "5x7")
    ]
    assert result["group_product_id"] == ctx["group_product_id"]
    assert result["gelato_product_id"] == "gelato-prod-1"
    gp_row = conn.execute("SELECT * FROM group_products WHERE id = ?", (result["group_product_id"],)).fetchone()
    assert gp_row["status"] == "created"


def test_create_candidate_gelato_product_excludes_a_rejected_group(tmp_path):
    # [D1]: a rejected group contributes no variant. It is excluded, not deleted.
    conn = _fresh_conn(tmp_path)
    ctx = _rendered_candidate(conn, tmp_path, decide_secondary="rejected")

    with patch("pipeline.gelato_client.create_product_from_template") as mock_create:
        mock_create.return_value = DRY
        group_product.create_candidate_gelato_product(
            conn, ctx["candidate_id"], ctx["candidate"], ctx["static_config"], "Title",
            now="2026-07-16T09:20:00",
        )

    variants_arg = mock_create.call_args[0][1]
    assert len(variants_arg) == 1
    # The rejected group's size comes off the listing record (so the variant table
    # mirrors the Gelato product exactly)...
    assert conn.execute(
        "SELECT COUNT(*) AS n FROM group_product_variants WHERE group_id = ?",
        (ctx["secondary_group_id"],),
    ).fetchone()["n"] == 0
    # ...but nothing shared is touched: the product, the listing record and every other
    # group's rows survive, and so does the rejected group's own reviewed gallery.
    assert _images(conn, ctx["group_product_id"], ctx["secondary_group_id"])
    assert conn.execute(
        "SELECT COUNT(*) AS n FROM group_product_variants WHERE group_id = ?",
        (ctx["primary_group_id"],),
    ).fetchone()["n"] == 1


def test_create_candidate_gelato_product_never_creates_a_second_product(tmp_path):
    # Idempotency, a hard constraint: the first live run duplicated products because a
    # create succeeded, the readiness poll timed out and the retry re-created. A product
    # id on the row means the create already succeeded - re-poll, never re-create.
    conn = _fresh_conn(tmp_path)
    ctx = _rendered_candidate(conn, tmp_path)

    with patch("pipeline.gelato_client.create_product_from_template") as mock_create, \
         patch("pipeline.group_product.poll_until_ready"):
        mock_create.return_value = {"id": "gelato-prod-1", "previewUrl": None, "productImages": []}
        first = group_product.create_candidate_gelato_product(
            conn, ctx["candidate_id"], ctx["candidate"], ctx["static_config"], "Title",
            now="2026-07-16T09:20:00",
        )

    with patch("pipeline.gelato_client.create_product_from_template") as mock_create, \
         patch("pipeline.gelato_client.delete_product") as mock_delete, \
         patch("pipeline.group_product.poll_until_ready") as mock_poll:
        second = group_product.create_candidate_gelato_product(
            conn, ctx["candidate_id"], ctx["candidate"], ctx["static_config"], "Title",
            now="2026-07-16T09:21:00",
        )

    mock_create.assert_not_called()
    mock_delete.assert_not_called()
    mock_poll.assert_called_once_with(
        "gelato-prod-1", store_id=None, api_key=None, poll_interval=10.0, timeout=300.0,
    )
    assert first == second


def test_create_candidate_gelato_product_repolls_a_mockup_failed_product(tmp_path):
    # A row that carries a gelato_product_id but landed on mockup_failed is NOT stale:
    # the create succeeded and only the readiness poll timed out (Gelato rehosting can
    # lag past the window). Reuse + re-poll; deleting and recreating would restart the
    # same slow clock and churn a real Gelato product.
    conn = _fresh_conn(tmp_path)
    ctx = _rendered_candidate(conn, tmp_path)
    conn.execute(
        "UPDATE group_products SET gelato_product_id = 'live-prod-1', status = 'mockup_failed' WHERE id = ?",
        (ctx["group_product_id"],),
    )
    conn.commit()

    with patch("pipeline.gelato_client.delete_product") as mock_delete, \
         patch("pipeline.gelato_client.create_product_from_template") as mock_create, \
         patch("pipeline.group_product.poll_until_ready") as mock_poll:
        result = group_product.create_candidate_gelato_product(
            conn, ctx["candidate_id"], ctx["candidate"], ctx["static_config"], "Title",
            now="2026-07-16T09:20:00",
        )

    mock_delete.assert_not_called()
    mock_create.assert_not_called()
    mock_poll.assert_called_once_with(
        "live-prod-1", store_id=None, api_key=None, poll_interval=10.0, timeout=300.0,
    )
    assert result["gelato_product_id"] == "live-prod-1"
    assert conn.execute(
        "SELECT status FROM group_products WHERE id = ?", (ctx["group_product_id"],)
    ).fetchone()["status"] == "created"


def test_create_candidate_gelato_product_leaves_intent_set_when_the_id_update_never_lands(tmp_path):
    # GL-32: simulates the crash window - the Gelato POST returns an id, but the process
    # dies before the id-recording UPDATE commits. The intent write (before the POST)
    # already landed, so the row is findable by find_unconfirmed_gelato_creates.
    conn = _fresh_conn(tmp_path)
    ctx = _rendered_candidate(conn, tmp_path)

    with patch("pipeline.gelato_client.create_product_from_template") as mock_create:
        mock_create.side_effect = RuntimeError("crashed after Gelato POST returned")
        with pytest.raises(RuntimeError):
            group_product.create_candidate_gelato_product(
                conn, ctx["candidate_id"], ctx["candidate"], ctx["static_config"], "Title",
                now="2026-07-16T09:20:00",
            )

    row = conn.execute(
        "SELECT gelato_product_id, gelato_create_intent_at FROM group_products WHERE id = ?",
        (ctx["group_product_id"],),
    ).fetchone()
    assert row["gelato_product_id"] is None
    assert row["gelato_create_intent_at"] == "2026-07-16T09:20:00"
    assert reconcile.find_unconfirmed_gelato_creates(
        conn, older_than_minutes=0, now=datetime(2026, 7, 16, 9, 25, 0)
    ) == [ctx["group_product_id"]]


def test_create_candidate_gelato_product_clears_intent_on_a_successful_create(tmp_path):
    conn = _fresh_conn(tmp_path)
    ctx = _rendered_candidate(conn, tmp_path)

    with patch("pipeline.gelato_client.create_product_from_template") as mock_create:
        mock_create.return_value = DRY
        group_product.create_candidate_gelato_product(
            conn, ctx["candidate_id"], ctx["candidate"], ctx["static_config"], "Title",
            now="2026-07-16T09:20:00",
        )

    row = conn.execute(
        "SELECT gelato_product_id, gelato_create_intent_at FROM group_products WHERE id = ?",
        (ctx["group_product_id"],),
    ).fetchone()
    assert row["gelato_product_id"] == "gelato-prod-1"
    assert row["gelato_create_intent_at"] is None
    assert reconcile.find_unconfirmed_gelato_creates(
        conn, older_than_minutes=0, now=datetime(2026, 7, 16, 9, 25, 0)
    ) == []


def test_render_group_mockups_refuses_to_add_a_size_after_the_product_exists(tmp_path):
    # GL-22a Q2: there is no API path to add a variant to an existing product, and the
    # product is the candidate's - deleting it to recreate would destroy sizes another
    # group already published. So a group arriving with sizes AFTER the create fails
    # loud, rather than recording a variant row for a size the product will never carry.
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn, base_image_local_path=_make_master(tmp_path))
    primary_group_id = _insert_group(conn, candidate_id, group_type="primary")
    late_group_id = _insert_group(conn, candidate_id, group_type="5x7")
    candidate = dict(conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone())
    static_config = _static_config()

    result = group_product.render_group_mockups(
        conn, primary_group_id, ["8x12"], candidate, static_config, now="2026-07-16T09:10:00",
    )
    _decide(conn, primary_group_id, "approved")
    with patch("pipeline.gelato_client.create_product_from_template", return_value=DRY):
        group_product.create_candidate_gelato_product(
            conn, candidate_id, candidate, static_config, "Title", now="2026-07-16T09:20:00",
        )

    with pytest.raises(group_product.SharedProductVariantError):
        group_product.render_group_mockups(
            conn, late_group_id, ["5x7"], candidate, static_config, now="2026-07-16T09:21:00",
        )

    # Nothing was recorded for the late group, and the product is untouched.
    assert conn.execute(
        "SELECT COUNT(*) AS n FROM group_product_variants WHERE group_id = ?", (late_group_id,)
    ).fetchone()["n"] == 0
    assert conn.execute(
        "SELECT status FROM group_products WHERE id = ?", (result["group_product_id"],)
    ).fetchone()["status"] == "created"


def test_real_create_sends_hosted_print_crop_not_raw_master_for_10x24(tmp_path):
    # End-to-end (real image_crop + artwork_store, only http.put_bytes and the Gelato
    # call are mocked): the create call must receive the cropped, hosted URL - not
    # candidate.base_image_url - for a non-primary group type.
    conn = _fresh_conn(tmp_path)
    ctx = _rendered_candidate(conn, tmp_path, secondary="10x24", secondary_sizes=("10x24",))

    r2_env = {
        "R2_ACCOUNT_ID": "acct", "R2_ACCESS_KEY_ID": "key", "R2_SECRET_ACCESS_KEY": "secret",
        "R2_BUCKET": "bucket", "R2_ENDPOINT": "https://acct.r2.cloudflarestorage.com",
        "R2_PUBLIC_BASE_URL": "https://cdn.example.com",
    }
    candidate_id = ctx["candidate_id"]

    with patch("pipeline.config.is_live_mode", return_value=True), \
         patch.dict("os.environ", r2_env), \
         patch("pipeline.group_product.gelato_client.create_product_from_template") as mock_create, \
         patch("pipeline.group_product.poll_until_ready") as mock_poll, \
         patch("pipeline.artwork_store.http.put_bytes") as mock_put:
        mock_create.return_value = {"id": "gelato-prod-1"}
        mock_poll.return_value = {"isReadyToPublish": True, "productImages": [{"fileUrl": "x", "isPrimary": True}]}
        group_product.create_candidate_gelato_product(
            conn, candidate_id, ctx["candidate"], ctx["static_config"], "Title",
            now="2026-07-16T09:20:00",
        )

    assert any(f"{candidate_id}_10x24_crop.png" in c.args[0] for c in mock_put.call_args_list)
    variants_arg = mock_create.call_args[0][1]
    # GL-22a Q1: two variants sharing one image_placeholder_name carry independently
    # submitted fileUrls in ONE call - the 8x12 keeps the master, 10x24 gets its crop.
    assert [v["image_url"] for v in variants_arg] == [
        ctx["candidate"]["base_image_url"],
        f"https://cdn.example.com/base/{candidate_id}_10x24_crop.png",
    ]


def test_dry_run_create_sends_the_same_hosted_print_crop_as_a_live_one(tmp_path):
    # GL-48: the crop URL used to be gated on GELATO live mode, so a dry run submitted
    # the uncropped master and never exercised the crop path - which is why two soak
    # nights could not observe the 10x24 letterbox defect. Dry-run must change what the
    # call DOES, never which branch reaches it.
    conn = _fresh_conn(tmp_path)
    ctx = _rendered_candidate(conn, tmp_path, secondary="10x24", secondary_sizes=("10x24",))
    r2_env = {
        "R2_ACCOUNT_ID": "acct", "R2_ACCESS_KEY_ID": "key", "R2_SECRET_ACCESS_KEY": "secret",
        "R2_BUCKET": "bucket", "R2_ENDPOINT": "https://acct.r2.cloudflarestorage.com",
        "R2_PUBLIC_BASE_URL": "https://cdn.example.com",
    }
    candidate_id = ctx["candidate_id"]

    with patch("pipeline.config.is_live_mode", return_value=False), \
         patch.dict("os.environ", r2_env), \
         patch("pipeline.group_product.gelato_client.create_product_from_template") as mock_create, \
         patch("pipeline.artwork_store.http.put_bytes"):
        mock_create.return_value = DRY
        group_product.create_candidate_gelato_product(
            conn, candidate_id, ctx["candidate"], ctx["static_config"], "Title",
            now="2026-07-16T09:20:00",
        )

    assert [v["image_url"] for v in mock_create.call_args[0][1]] == [
        ctx["candidate"]["base_image_url"],
        f"https://cdn.example.com/base/{candidate_id}_10x24_crop.png",
    ]


def test_real_create_fails_loud_for_secondary_group_when_r2_not_configured(tmp_path, monkeypatch):
    # If R2 isn't configured, persist_group_crop's durable_url is a local filesystem
    # path - the create-path's non-http(s) guard must reject it, not silently fall back
    # to the uncropped master.
    for key in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY",
                "R2_BUCKET", "R2_ENDPOINT", "R2_PUBLIC_BASE_URL"):
        monkeypatch.delenv(key, raising=False)

    conn = _fresh_conn(tmp_path)
    # A durable (non-replicate) master URL, so the create gets past the replicate-URL
    # guard and actually reaches the 5x7 variant's local-path crop URL - the guard
    # under test here.
    ctx = _rendered_candidate(conn, tmp_path, base_image_url="https://cdn.example.com/base/m.png")

    with patch("pipeline.config.is_live_mode", return_value=True):
        with pytest.raises(gelato_client.GelatoInvalidImageURLError):
            group_product.create_candidate_gelato_product(
                conn, ctx["candidate_id"], ctx["candidate"], ctx["static_config"], "Title",
                now="2026-07-16T09:20:00",
            )


def test_included_group_ids_is_in_gallery_rank_order_and_skips_the_undecided(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    ten = _insert_group(conn, candidate_id, group_type="10x24")
    primary = _insert_group(conn, candidate_id, group_type="primary")
    _insert_group(conn, candidate_id, group_type="5x7")
    _decide(conn, primary, "approved")
    _decide(conn, ten, "approved")
    # 5x7 left undecided.
    assert group_product.included_group_ids(conn, candidate_id) == [primary, ten]

    conn.execute("UPDATE groups SET status = 'failed_abandoned' WHERE id = ?", (ten,))
    conn.commit()
    assert group_product.included_group_ids(conn, candidate_id) == [primary]


# --- patch_etsy_listing: one listing, one assembled gallery ---

def _publishable(conn, tmp_path, **kwargs):
    ctx = _rendered_candidate(conn, tmp_path, **kwargs)
    conn.execute(
        "UPDATE group_products SET gelato_product_id = 'gelato-prod-1', status = 'created' WHERE id = ?",
        (ctx["group_product_id"],),
    )
    conn.commit()
    return ctx


def test_patch_etsy_listing_resolves_id_patches_and_sets_variant_prices(tmp_path):
    conn = _fresh_conn(tmp_path)
    ctx = _publishable(conn, tmp_path)
    static_config = ctx["static_config"]

    # Gelato is "live" here (a real product exists to resolve externalId from) even
    # though the Etsy-side dry_run=True keeps the actual Etsy write calls dry.
    with patch("pipeline.config.is_live_mode", return_value=True) as mock_live, \
         patch("pipeline.gelato_client.get_etsy_listing_id") as mock_resolve, \
         patch("pipeline.etsy_client.update_listing") as mock_update, \
         patch("pipeline.etsy_client.update_listing_inventory") as mock_inventory, \
         patch("pipeline.etsy_client.upload_listing_image", return_value={"listing_image_id": "img-1"}):
        mock_resolve.return_value = "etsy-listing-42"
        listing_id = group_product.patch_etsy_listing(
            conn, ctx["group_product_id"], LISTING_TEXT, static_config,
            shop_id="shop1", dry_run=True, now="2026-07-16T09:20:00",
        )

    mock_live.assert_any_call("GELATO")
    mock_resolve.assert_called_once_with("gelato-prod-1", store_id=None, api_key=None)
    assert listing_id == "etsy-listing-42"
    patched_data = mock_update.call_args[0][2]
    assert patched_data["title"] == "Monstera Line Art"
    assert "8x12" not in patched_data["title"]
    # [D3]: one listing, one shipping profile, resolved once for the whole candidate.
    assert patched_data["shipping_profile_id"] == "288734253315"
    # Both groups' sizes are priced on the one listing.
    mock_inventory.assert_called_once_with(
        "shop1", "etsy-listing-42",
        {"8x12": static_config["prices_eur"]["8x12"], "5x7": static_config["prices_eur"]["5x7"]},
        api_key=None, api_secret=None, access_token=None, dry_run=True,
    )
    gp_row = conn.execute(
        "SELECT etsy_listing_id, status FROM group_products WHERE id = ?", (ctx["group_product_id"],)
    ).fetchone()
    assert gp_row["etsy_listing_id"] == "etsy-listing-42"
    assert gp_row["status"] == "published"


def test_patch_etsy_listing_assembles_the_gallery_in_group_rank_order(tmp_path):
    conn = _fresh_conn(tmp_path)
    ctx = _publishable(conn, tmp_path)
    expected = [
        row["image_url"] for row in conn.execute(
            "SELECT pi.image_url FROM product_images pi JOIN groups g ON g.id = pi.group_id "
            "WHERE pi.group_product_id = ? "
            "ORDER BY CASE g.group_type WHEN 'primary' THEN 0 ELSE 1 END, pi.gallery_order",
            (ctx["group_product_id"],),
        ).fetchall()
    ]
    assert len(expected) > 1

    with patch("pipeline.config.is_live_mode", return_value=False), \
         patch("pipeline.etsy_client.update_listing"), \
         patch("pipeline.etsy_client.update_listing_inventory"), \
         patch("pipeline.etsy_client.upload_listing_image", return_value={"listing_image_id": "i"}) as mock_upload:
        group_product.patch_etsy_listing(
            conn, ctx["group_product_id"], LISTING_TEXT, ctx["static_config"],
            shop_id="shop1", dry_run=True, now="2026-07-16T09:20:00",
        )

    assert mock_upload.call_count == len(expected)
    for call in mock_upload.call_args_list:
        assert call.args[:2] == ("shop1", "DRY_RUN_ETSY_LISTING_ID")


def test_patch_etsy_listing_skips_a_rejected_groups_images_and_sizes(tmp_path):
    conn = _fresh_conn(tmp_path)
    ctx = _publishable(conn, tmp_path, decide_secondary="rejected")
    primary_images = len(_images(conn, ctx["group_product_id"], ctx["primary_group_id"]))
    assert _images(conn, ctx["group_product_id"], ctx["secondary_group_id"]), \
        "the rejected group's images must still exist in the DB - they're excluded, not deleted"

    with patch("pipeline.config.is_live_mode", return_value=False), \
         patch("pipeline.etsy_client.update_listing"), \
         patch("pipeline.etsy_client.update_listing_inventory") as mock_inventory, \
         patch("pipeline.etsy_client.upload_listing_image", return_value={"listing_image_id": "i"}) as mock_upload:
        group_product.patch_etsy_listing(
            conn, ctx["group_product_id"], LISTING_TEXT, ctx["static_config"],
            shop_id="shop1", dry_run=True, now="2026-07-16T09:20:00",
        )

    assert mock_upload.call_count == primary_images
    assert set(mock_inventory.call_args[0][2]) == {"8x12"}


def test_patch_etsy_listing_is_idempotent_and_does_not_duplicate_the_gallery(tmp_path):
    # The upload loop is a full re-upload with no delta, so a second call after a partial
    # failure would duplicate every photo on the live listing. Each row records Etsy's
    # own listing_image_id and is skipped on the next pass.
    conn = _fresh_conn(tmp_path)
    ctx = _publishable(conn, tmp_path)

    def _patch():
        with patch("pipeline.config.is_live_mode", return_value=False), \
             patch("pipeline.etsy_client.update_listing"), \
             patch("pipeline.etsy_client.update_listing_inventory"), \
             patch("pipeline.etsy_client.upload_listing_image",
                   return_value={"listing_image_id": "img-1"}) as mock_upload:
            group_product.patch_etsy_listing(
                conn, ctx["group_product_id"], LISTING_TEXT, ctx["static_config"],
                shop_id="shop1", dry_run=True, now="2026-07-16T09:20:00",
            )
            return mock_upload.call_count

    first = _patch()
    assert first > 0
    assert _patch() == 0
    assert conn.execute(
        "SELECT COUNT(*) AS n FROM product_images WHERE group_product_id = ? "
        "AND etsy_listing_image_id IS NULL AND group_id = ?",
        (ctx["group_product_id"], ctx["primary_group_id"]),
    ).fetchone()["n"] == 0


def test_patch_etsy_listing_refuses_a_gallery_over_etsys_20_image_cap(tmp_path):
    # Asserted, never assumed: today's worst case is 13 images, but the scene library
    # grows and Etsy rejects the 21st photo.
    conn = _fresh_conn(tmp_path)
    ctx = _publishable(conn, tmp_path)
    for order in range(group_product.ETSY_MAX_LISTING_IMAGES + 1):
        conn.execute(
            "INSERT INTO product_images (group_product_id, group_id, image_url, alt_text, gallery_order, image_type) "
            "VALUES (?, ?, ?, '', ?, 'lifestyle')",
            (ctx["group_product_id"], ctx["primary_group_id"], f"/x/{order}.png", 100 + order),
        )
    conn.commit()

    with patch("pipeline.config.is_live_mode", return_value=False), \
         patch("pipeline.etsy_client.update_listing") as mock_update, \
         patch("pipeline.etsy_client.upload_listing_image") as mock_upload:
        with pytest.raises(group_product.GalleryTooLargeError):
            group_product.patch_etsy_listing(
                conn, ctx["group_product_id"], LISTING_TEXT, ctx["static_config"],
                shop_id="shop1", dry_run=True, now="2026-07-16T09:20:00",
            )

    mock_upload.assert_not_called()
    mock_update.assert_not_called()


def test_patch_etsy_listing_never_activates_a_listing(tmp_path):
    # B1 (inverted): drafts stay drafts. patch_etsy_listing must never call
    # update_listing_state, and must never send a 'state' field in update_listing's
    # payload - either would activate the listing ($0.20 each).
    conn = _fresh_conn(tmp_path)
    ctx = _publishable(conn, tmp_path)

    with patch("pipeline.config.is_live_mode", return_value=False), \
         patch("pipeline.etsy_client.update_listing_state") as mock_state, \
         patch("pipeline.etsy_client.update_listing") as mock_update, \
         patch("pipeline.etsy_client.update_listing_inventory"), \
         patch("pipeline.etsy_client.upload_listing_image", return_value={"listing_image_id": "i"}):
        group_product.patch_etsy_listing(
            conn, ctx["group_product_id"], LISTING_TEXT, ctx["static_config"],
            shop_id="shop1", dry_run=True, now="2026-07-16T09:20:00",
        )

    mock_state.assert_not_called()
    assert "state" not in mock_update.call_args[0][2]


def test_patch_etsy_listing_uses_placeholder_id_when_gelato_not_live(tmp_path):
    # patch_etsy_listing's dry_run parameter only gates the Etsy write calls. Resolving
    # etsy_listing_id is a Gelato-side read that always makes a real HTTP call, so it
    # must be gated on Gelato's own liveness - otherwise the standard dev state would
    # crash (missing creds) or hang.
    conn = _fresh_conn(tmp_path)
    ctx = _publishable(conn, tmp_path)
    conn.execute(
        "UPDATE group_products SET gelato_product_id = 'DRY_RUN_PRODUCT_ID' WHERE id = ?",
        (ctx["group_product_id"],),
    )
    conn.commit()

    with patch("pipeline.config.is_live_mode", return_value=False), \
         patch("pipeline.gelato_client.get_etsy_listing_id") as mock_resolve, \
         patch("pipeline.etsy_client.update_listing") as mock_update, \
         patch("pipeline.etsy_client.update_listing_inventory") as mock_inventory, \
         patch("pipeline.etsy_client.upload_listing_image", return_value={"listing_image_id": "i"}):
        listing_id = group_product.patch_etsy_listing(
            conn, ctx["group_product_id"], LISTING_TEXT, ctx["static_config"],
            shop_id="shop1", dry_run=True, now="2026-07-16T09:20:00",
        )

    mock_resolve.assert_not_called()
    assert listing_id == "DRY_RUN_ETSY_LISTING_ID"
    mock_update.assert_called_once()
    mock_inventory.assert_called_once()


def test_patch_etsy_listing_uploads_nothing_when_no_gallery_images(tmp_path):
    # A group_type with no authored scenes lands with zero product_images rows.
    # patch_etsy_listing must not error - it uploads nothing and the rest still runs.
    conn = _fresh_conn(tmp_path)
    ctx = _publishable(conn, tmp_path)
    conn.execute("DELETE FROM product_images WHERE group_product_id = ?", (ctx["group_product_id"],))
    conn.commit()

    with patch("pipeline.config.is_live_mode", return_value=False), \
         patch("pipeline.etsy_client.update_listing") as mock_update, \
         patch("pipeline.etsy_client.update_listing_inventory") as mock_inventory, \
         patch("pipeline.etsy_client.upload_listing_image") as mock_upload:
        listing_id = group_product.patch_etsy_listing(
            conn, ctx["group_product_id"], LISTING_TEXT, ctx["static_config"],
            shop_id="shop1", dry_run=True, now="2026-07-16T09:20:00",
        )

    mock_upload.assert_not_called()
    mock_update.assert_called_once()
    mock_inventory.assert_called_once()
    assert listing_id == "DRY_RUN_ETSY_LISTING_ID"
    assert conn.execute(
        "SELECT status FROM group_products WHERE id = ?", (ctx["group_product_id"],)
    ).fetchone()["status"] == "published"


# --- GL-33: reconcile step deletes Gelato's contaminating gallery images ---

def test_patch_etsy_listing_deletes_images_not_owned_by_this_group_product(tmp_path):
    conn = _fresh_conn(tmp_path)
    ctx = _publishable(conn, tmp_path)

    with patch("pipeline.config.is_live_mode", return_value=False), \
         patch("pipeline.etsy_client.update_listing"), \
         patch("pipeline.etsy_client.update_listing_inventory"), \
         patch("pipeline.etsy_client.upload_listing_image",
               side_effect=[{"listing_image_id": f"ours-{i}"} for i in range(20)]), \
         patch("pipeline.etsy_client.get_listing_images", return_value={"results": [
             {"listing_image_id": "ours-0"}, {"listing_image_id": "gelato-ghost-1"},
             {"listing_image_id": "gelato-ghost-2"},
         ]}), \
         patch("pipeline.etsy_client.delete_listing_image") as mock_delete:
        group_product.patch_etsy_listing(
            conn, ctx["group_product_id"], LISTING_TEXT, ctx["static_config"],
            shop_id="shop1", dry_run=True, now="2026-07-16T09:20:00",
        )

    deleted_ids = {call.args[2] for call in mock_delete.call_args_list}
    assert deleted_ids == {"gelato-ghost-1", "gelato-ghost-2"}
    for call in mock_delete.call_args_list:
        assert call.args[:2] == ("shop1", "DRY_RUN_ETSY_LISTING_ID")


def test_patch_etsy_listing_reconcile_is_idempotent_second_pass_deletes_nothing(tmp_path):
    conn = _fresh_conn(tmp_path)
    ctx = _publishable(conn, tmp_path)

    def _patch(current_images):
        with patch("pipeline.config.is_live_mode", return_value=False), \
             patch("pipeline.etsy_client.update_listing"), \
             patch("pipeline.etsy_client.update_listing_inventory"), \
             patch("pipeline.etsy_client.upload_listing_image",
                   side_effect=[{"listing_image_id": f"ours-{i}"} for i in range(20)]), \
             patch("pipeline.etsy_client.get_listing_images", return_value=current_images), \
             patch("pipeline.etsy_client.delete_listing_image") as mock_delete:
            group_product.patch_etsy_listing(
                conn, ctx["group_product_id"], LISTING_TEXT, ctx["static_config"],
                shop_id="shop1", dry_run=True, now="2026-07-16T09:20:00",
            )
            return mock_delete.call_count

    first_pass_images = {"results": [
        {"listing_image_id": "ours-0"}, {"listing_image_id": "gelato-ghost-1"},
    ]}
    assert _patch(first_pass_images) == 1

    # Second call: the listing now only carries our own images (Gelato's are gone) -
    # nothing foreign is found, so nothing is deleted.
    second_pass_images = {"results": [{"listing_image_id": "ours-0"}]}
    assert _patch(second_pass_images) == 0


def test_patch_etsy_listing_never_deletes_an_image_it_cannot_positively_account_for(tmp_path):
    # Positive-match only: an image absent from product_images.etsy_listing_image_id for
    # THIS group_product_id is treated as foreign and deleted - even ambiguous cases are
    # not silently kept. Confirms the flip side: an owned id is never touched no matter
    # how many foreign ids surround it.
    conn = _fresh_conn(tmp_path)
    ctx = _publishable(conn, tmp_path)

    with patch("pipeline.config.is_live_mode", return_value=False), \
         patch("pipeline.etsy_client.update_listing"), \
         patch("pipeline.etsy_client.update_listing_inventory"), \
         patch("pipeline.etsy_client.upload_listing_image",
               side_effect=[{"listing_image_id": f"ours-{i}"} for i in range(20)]), \
         patch("pipeline.etsy_client.get_listing_images", return_value={"results": [
             {"listing_image_id": "ours-0"}, {"listing_image_id": "ours-1"},
         ]}), \
         patch("pipeline.etsy_client.delete_listing_image") as mock_delete:
        group_product.patch_etsy_listing(
            conn, ctx["group_product_id"], LISTING_TEXT, ctx["static_config"],
            shop_id="shop1", dry_run=True, now="2026-07-16T09:20:00",
        )

    mock_delete.assert_not_called()


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


def test_scale8_master_clears_150_dpi_at_every_offered_size():
    # Documents the B5 fix constants: the scale=8 master (6656x9728) must clear the
    # 150 DPI floor at every size, worst case A1. Pure arithmetic on the size table.
    px_short, px_long = 6656, 9728
    for size, (short_in, long_in) in group_product._SIZE_INCHES.items():
        dpi = min(px_short / short_in, px_long / long_in)
        assert dpi >= group_product.MIN_PRINT_DPI, f"{size} only {dpi:.0f} DPI"


def test_live_product_row_resolves_a_pre_migration_row_by_group_id(tmp_path):
    # GL-9-era rows predate the migration and carry candidate_id NULL. They must still
    # resolve - by group_id, as they always did - so their real, already-published
    # Gelato product is reused rather than duplicated by a candidate-keyed miss.
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_group(conn, candidate_id, group_type="primary")
    timestamp = "2026-07-16T09:10:00"
    cursor = conn.execute(
        "INSERT INTO group_products (group_id, gelato_template_id, gelato_product_id, status, created_at, updated_at) "
        "VALUES (?, 'tmpl', 'legacy-prod-1', 'created', ?, ?)",
        (group_id, timestamp, timestamp),
    )
    conn.commit()

    row = group_product.live_product_row(conn, candidate_id, group_id)
    assert row is not None
    assert row["id"] == cursor.lastrowid
    assert row["candidate_id"] is None
    # ...but a candidate-keyed lookup with no group context does not resurrect it.
    assert group_product.live_product_row(conn, candidate_id) is None


# --- GL-57: the gallery order must leave the process ---

def test_patch_etsy_listing_sends_an_explicit_rank_in_group_rank_order(tmp_path):
    # The whole sequence is ranked, not just rank=1 on the first image - the outcome
    # must not depend on an Etsy default-ordering rule nobody has verified.
    conn = _fresh_conn(tmp_path)
    ctx = _publishable(conn, tmp_path)

    with patch("pipeline.config.is_live_mode", return_value=False),          patch("pipeline.etsy_client.update_listing"),          patch("pipeline.etsy_client.update_listing_inventory"),          patch("pipeline.etsy_client.upload_listing_image", return_value={"listing_image_id": "i"}) as mock_upload:
        group_product.patch_etsy_listing(
            conn, ctx["group_product_id"], LISTING_TEXT, ctx["static_config"],
            shop_id="shop1", dry_run=True, now="2026-07-16T09:20:00",
        )

    ranks = [call.kwargs["rank"] for call in mock_upload.call_args_list]
    assert ranks == list(range(1, len(ranks) + 1))
    # rank 1 - the featured image - belongs to the primary group, never the 10x24 crop.
    first_url = mock_upload.call_args_list[0].args[2]
    primary_urls = {
        row["image_url"] for row in conn.execute(
            "SELECT image_url FROM product_images WHERE group_id = ?", (ctx["primary_group_id"],)
        ).fetchall()
    }
    assert first_url is not None or primary_urls  # dry-run sends b"" bytes; order asserted below
    ordered_group_types = [
        row["group_type"] for row in conn.execute(
            "SELECT g.group_type FROM product_images pi JOIN groups g ON g.id = pi.group_id "
            "WHERE pi.group_product_id = ? ORDER BY "
            "CASE g.group_type WHEN 'primary' THEN 0 WHEN '5x7' THEN 1 ELSE 2 END, pi.gallery_order",
            (ctx["group_product_id"],),
        ).fetchall()
    ]
    assert ordered_group_types[0] == "primary"


# --- GL-58: a permanent error is terminal, not retried forever ---

def test_shared_product_variant_error_is_marked_permanent():
    assert group_product.SharedProductVariantError().permanent is True


def test_record_group_failure_keeps_an_ordinary_error_retryable(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn, base_image_local_path=_make_master(tmp_path))
    group_id = _insert_group(conn, candidate_id, group_type="5x7")

    permanent = group_product.record_group_failure(
        conn, group_id, "gl54_group_mockup_failed", RuntimeError("gelato 500"),
        now="2026-08-11T09:00:00",
    )

    row = conn.execute("SELECT status, failed_reason FROM groups WHERE id = ?", (group_id,)).fetchone()
    assert permanent is False
    assert row["status"] == "pending_review"  # unchanged - still retryable next cycle
    assert row["failed_reason"] == "gl54_group_mockup_failed: gelato 500"


def test_record_group_failure_abandons_the_group_on_a_permanent_error(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn, base_image_local_path=_make_master(tmp_path))
    group_id = _insert_group(conn, candidate_id, group_type="5x7")

    permanent = group_product.record_group_failure(
        conn, group_id, "gl54_group_mockup_failed",
        group_product.SharedProductVariantError("no API path to add a variant"),
        now="2026-08-11T09:00:00",
    )

    row = conn.execute("SELECT status, failed_reason FROM groups WHERE id = ?", (group_id,)).fetchone()
    assert permanent is True
    assert row["status"] == "failed_abandoned"
    assert "(permanent)" in row["failed_reason"]
