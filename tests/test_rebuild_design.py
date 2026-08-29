import json as _json
from unittest.mock import patch

import pytest

import pipeline.config as config
import pipeline.db as db
import pipeline.gelato_client as gelato_client
import pipeline.group_product as group_product
import scripts.rebuild_design as rebuild_design


def _fresh_conn(tmp_path):
    conn = db.get_connection(tmp_path / "test.sqlite3")
    db.init_db(conn)
    return conn


def _insert_candidate(conn, niche="monstera line art", *, base_image_local_path=None,
                       base_image_url="https://replicate.delivery/master.png"):
    timestamp = "2026-08-29T09:00:00"
    cursor = conn.execute(
        "INSERT INTO candidates (created_at, niche, go_hold_kill, status, base_image_url, "
        "base_image_local_path, base_image_sha256, updated_at) "
        "VALUES (?, ?, 'go', 'completed', ?, ?, 'deadbeef', ?)",
        (timestamp, niche, base_image_url, base_image_local_path, timestamp),
    )
    conn.commit()
    return cursor.lastrowid


def _insert_approved_primary_group(conn, candidate_id):
    timestamp = "2026-08-29T09:05:00"
    cursor = conn.execute(
        "INSERT INTO groups (candidate_id, group_type, status, decision, created_at, updated_at) "
        "VALUES (?, 'primary', 'approved_published', 'approved', ?, ?)",
        (candidate_id, timestamp, timestamp),
    )
    conn.commit()
    return cursor.lastrowid


def _insert_listing_text(conn, candidate_id, niche="monstera line art"):
    timestamp = "2026-08-29T09:10:00"
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


def _insert_old_listing(conn, candidate_id, group_id, *, etsy_listing_id="old-etsy-1",
                         gelato_product_id="old-gelato-1", status="published"):
    timestamp = "2026-08-29T09:11:00"
    cursor = conn.execute(
        "INSERT INTO group_products (candidate_id, group_id, gelato_template_id, "
        "gelato_product_id, etsy_listing_id, status, created_at, updated_at) "
        "VALUES (?, ?, 'tpl_old', ?, ?, ?, ?, ?)",
        (candidate_id, group_id, gelato_product_id, etsy_listing_id, status, timestamp, timestamp),
    )
    gp_id = cursor.lastrowid
    conn.execute(
        "INSERT INTO group_product_variants (group_product_id, group_id, size, orientation, "
        "gelato_template_variant_id, price_eur, created_at) VALUES (?, ?, '8x12', 'portrait', "
        "'variant_old', 24, ?)",
        (gp_id, group_id, timestamp),
    )
    conn.execute(
        "INSERT INTO product_images (group_product_id, group_id, image_url, alt_text, "
        "gallery_order, image_type) VALUES (?, ?, 'https://old/img.jpg', 'old alt', 0, 'flat_mockup')",
        (gp_id, group_id),
    )
    conn.commit()
    return gp_id


def _fake_redraft(conn, candidate_id):
    """Stands in for compliance_draft.build_compliance_draft + critic_pass.run_critic_pass
    (both API-backed) the way test_publish_primary_group's redraft test does - copy-only,
    no artwork touched."""
    def fake_build_compliance_draft(conn, candidate_id, *, static_config=None, anthropic_api_key=None, now=None):
        conn.execute("DELETE FROM listing_texts WHERE candidate_id = ?", (candidate_id,))
        _insert_listing_text(conn, candidate_id, niche="evergreen botanical")

    def fake_run_critic_pass(conn, candidate_id, **kwargs):
        assert kwargs["copy_only"] is True
        return {"candidate_id": candidate_id, "passed": True, "attempts": 1}

    return patch(
        "pipeline.publish_primary_group.compliance_draft.build_compliance_draft",
        side_effect=fake_build_compliance_draft,
    ), patch(
        "pipeline.publish_primary_group.critic_pass.run_critic_pass",
        side_effect=fake_run_critic_pass,
    )


def _make_master(tmp_path, name="master.png", size=(900, 1316)):
    from PIL import Image
    p = tmp_path / name
    Image.new("RGB", size, (200, 180, 150)).save(p, format="PNG")
    return str(p)


def _rebuild_scenario(conn, tmp_path):
    candidate_id = _insert_candidate(conn, base_image_local_path=_make_master(tmp_path))
    primary_group_id = _insert_approved_primary_group(conn, candidate_id)
    _insert_listing_text(conn, candidate_id)
    old_group_product_id = _insert_old_listing(conn, candidate_id, primary_group_id)
    return {
        "candidate_id": candidate_id,
        "primary_group_id": primary_group_id,
        "old_group_product_id": old_group_product_id,
    }


DRY_GELATO_CREATE = {"id": "new-gelato-1", "_dry_run": True, "previewUrl": None, "productImages": []}


def _run_rebuild(conn, candidate_id, **kwargs):
    fake_build, fake_critic = _fake_redraft(conn, candidate_id)
    with fake_build, fake_critic, \
         patch("pipeline.gelato_client.create_product_from_template", return_value=DRY_GELATO_CREATE):
        return rebuild_design.rebuild(
            conn, candidate_id, static_config=config.load_static_config(), dry_run=True,
            shop_id="shop1", **kwargs
        )


def test_rebuild_makes_no_generation_call_and_leaves_artwork_byte_identical(tmp_path):
    conn = _fresh_conn(tmp_path)
    ctx = _rebuild_scenario(conn, tmp_path)
    before = dict(conn.execute(
        "SELECT base_image_sha256, base_image_local_path FROM candidates WHERE id = ?",
        (ctx["candidate_id"],),
    ).fetchone())
    with patch("pipeline.publish_primary_group.generate.generate_for_candidate") as mock_generate, \
         patch("pipeline.replicate_client.generate_image") as mock_replicate:
        mock_generate.side_effect = AssertionError("generate must never be called")
        mock_replicate.side_effect = AssertionError("replicate must never be called")
        with patch("scripts.rebuild_design.classify_listing_case", return_value="draft"):
            _run_rebuild(conn, ctx["candidate_id"])

    mock_generate.assert_not_called()
    mock_replicate.assert_not_called()
    after = dict(conn.execute(
        "SELECT base_image_sha256, base_image_local_path FROM candidates WHERE id = ?",
        (ctx["candidate_id"],),
    ).fetchone())
    assert after == before
    assert conn.execute(
        "SELECT COUNT(*) AS n FROM generation_attempts WHERE candidate_id = ?", (ctx["candidate_id"],)
    ).fetchone()["n"] == 0


def test_rebuild_draft_listing_creates_a_new_listing_record_and_marks_the_old_one_deleted(tmp_path):
    conn = _fresh_conn(tmp_path)
    ctx = _rebuild_scenario(conn, tmp_path)

    with patch("scripts.rebuild_design.classify_listing_case", return_value="draft"):
        result = _run_rebuild(conn, ctx["candidate_id"])

    new_row = group_product.live_product_row(conn, ctx["candidate_id"])
    assert new_row is not None
    assert new_row["id"] != ctx["old_group_product_id"]
    old_row = conn.execute(
        "SELECT status FROM group_products WHERE id = ?", (ctx["old_group_product_id"],)
    ).fetchone()
    assert old_row["status"] == "deleted"
    assert result["old_group_product_id"] == ctx["old_group_product_id"]


def test_rebuild_refuses_a_published_listing_without_the_flag(tmp_path):
    conn = _fresh_conn(tmp_path)
    ctx = _rebuild_scenario(conn, tmp_path)

    with patch("scripts.rebuild_design.classify_listing_case", return_value="published"), \
         pytest.raises(rebuild_design.RebuildRefusedError):
        _run_rebuild(conn, ctx["candidate_id"])

    old_row = conn.execute(
        "SELECT status FROM group_products WHERE id = ?", (ctx["old_group_product_id"],)
    ).fetchone()
    assert old_row["status"] == "published"
    assert conn.execute("SELECT COUNT(*) AS n FROM group_products").fetchone()["n"] == 1


def test_rebuild_published_listing_proceeds_with_the_explicit_flag(tmp_path):
    conn = _fresh_conn(tmp_path)
    ctx = _rebuild_scenario(conn, tmp_path)

    with patch("scripts.rebuild_design.classify_listing_case", return_value="published"):
        _run_rebuild(conn, ctx["candidate_id"], published_loses_url_age_stats=True)

    assert conn.execute("SELECT COUNT(*) AS n FROM group_products WHERE status != 'deleted'").fetchone()["n"] == 1


def test_rebuild_refuses_when_listing_state_cannot_be_determined(tmp_path):
    conn = _fresh_conn(tmp_path)
    ctx = _rebuild_scenario(conn, tmp_path)

    with patch("pipeline.etsy_client.get_listing", side_effect=Exception("404")), \
         pytest.raises(rebuild_design.RebuildRefusedError):
        _run_rebuild(conn, ctx["candidate_id"])

    old_row = conn.execute(
        "SELECT status FROM group_products WHERE id = ?", (ctx["old_group_product_id"],)
    ).fetchone()
    assert old_row["status"] == "published"


def test_rebuild_ends_with_exactly_one_live_listing_per_artwork(tmp_path):
    conn = _fresh_conn(tmp_path)
    ctx = _rebuild_scenario(conn, tmp_path)

    with patch("scripts.rebuild_design.classify_listing_case", return_value="draft"):
        _run_rebuild(conn, ctx["candidate_id"])

    live_rows = conn.execute(
        "SELECT id FROM group_products WHERE candidate_id = ? AND status != 'deleted'",
        (ctx["candidate_id"],),
    ).fetchall()
    assert len(live_rows) == 1
    new_group_product_id = live_rows[0]["id"]
    assert new_group_product_id != ctx["old_group_product_id"]

    included = group_product.included_group_ids(conn, ctx["candidate_id"])
    variant_count = conn.execute(
        "SELECT COUNT(*) AS n FROM group_product_variants WHERE group_product_id = ?",
        (new_group_product_id,),
    ).fetchone()["n"]
    expected_sizes = sum(
        len(config.load_static_config()["aspect_ratio_groups"][
            conn.execute("SELECT group_type FROM groups WHERE id = ?", (gid,)).fetchone()["group_type"]
        ])
        for gid in included
    )
    assert variant_count == expected_sizes


def test_rebuild_deletes_nothing_when_the_gelato_create_fails(tmp_path):
    conn = _fresh_conn(tmp_path)
    ctx = _rebuild_scenario(conn, tmp_path)

    fake_build, fake_critic = _fake_redraft(conn, ctx["candidate_id"])
    with fake_build, fake_critic, \
         patch("scripts.rebuild_design.classify_listing_case", return_value="draft"), \
         patch("pipeline.gelato_client.create_product_from_template", side_effect=RuntimeError("gelato down")), \
         patch("pipeline.etsy_client.delete_listing") as mock_delete_listing, \
         patch("pipeline.gelato_client.delete_product") as mock_delete_product, \
         pytest.raises(RuntimeError):
        rebuild_design.rebuild(
            conn, ctx["candidate_id"], static_config=config.load_static_config(), dry_run=True,
            shop_id="shop1",
        )

    mock_delete_listing.assert_not_called()
    mock_delete_product.assert_not_called()
    # The old row is still there - "deleted" is a soft supersede flag, not a physical
    # drop, so a failed rebuild can be diagnosed and retried.
    recovered = conn.execute(
        "SELECT * FROM group_products WHERE id = ?", (ctx["old_group_product_id"],)
    ).fetchone()
    assert recovered is not None
    assert conn.execute(
        "SELECT COUNT(*) AS n FROM group_product_variants WHERE group_product_id = ?",
        (ctx["old_group_product_id"],),
    ).fetchone()["n"] == 1


def test_retire_deletes_only_the_enumerated_old_listing_once_the_new_one_is_confirmed_live(tmp_path):
    conn = _fresh_conn(tmp_path)
    ctx = _rebuild_scenario(conn, tmp_path)
    # A real retire always runs after rebuild has already superseded the old row.
    conn.execute(
        "UPDATE group_products SET status = 'deleted' WHERE id = ?", (ctx["old_group_product_id"],)
    )
    # Simulate a new, confirmed-live listing record already in place.
    timestamp = "2026-08-29T10:00:00"
    conn.execute(
        "INSERT INTO group_products (candidate_id, group_id, gelato_template_id, gelato_product_id, "
        "etsy_listing_id, status, created_at, updated_at) VALUES (?, ?, 'tpl_new', 'new-gelato-1', "
        "'new-etsy-1', 'published', ?, ?)",
        (ctx["candidate_id"], ctx["primary_group_id"], timestamp, timestamp),
    )
    conn.commit()

    with patch("pipeline.etsy_client.delete_listing") as mock_delete_listing, \
         patch("pipeline.gelato_client.delete_product") as mock_delete_product:
        retired = rebuild_design.retire(
            conn, ctx["candidate_id"], [ctx["old_group_product_id"]], dry_run=True,
        )

    assert retired == [ctx["old_group_product_id"]]
    mock_delete_listing.assert_called_once_with(
        "old-etsy-1", api_key=None, api_secret=None, access_token=None, dry_run=True,
    )
    mock_delete_product.assert_called_once_with(
        "old-gelato-1", store_id=None, api_key=None, dry_run=True,
    )


def test_retire_refuses_when_the_new_listing_is_not_confirmed_live(tmp_path):
    conn = _fresh_conn(tmp_path)
    ctx = _rebuild_scenario(conn, tmp_path)
    # No new group_products row exists at all yet - only the old one, which is not the
    # "current" listing record retire is meant to protect.
    conn.execute(
        "UPDATE group_products SET status = 'deleted' WHERE id = ?", (ctx["old_group_product_id"],)
    )
    conn.commit()

    with patch("pipeline.etsy_client.delete_listing") as mock_delete_listing, \
         patch("pipeline.gelato_client.delete_product") as mock_delete_product, \
         pytest.raises(rebuild_design.RebuildRefusedError):
        rebuild_design.retire(conn, ctx["candidate_id"], [ctx["old_group_product_id"]])

    mock_delete_listing.assert_not_called()
    mock_delete_product.assert_not_called()


def test_gallery_repair_reuploads_every_image_with_ranks_and_creates_no_gelato_product(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn, base_image_local_path=_make_master(tmp_path))
    primary_group_id = _insert_approved_primary_group(conn, candidate_id)
    _insert_listing_text(conn, candidate_id)
    timestamp = "2026-08-29T11:00:00"
    cursor = conn.execute(
        "INSERT INTO group_products (candidate_id, group_id, gelato_template_id, gelato_product_id, "
        "etsy_listing_id, status, created_at, updated_at) VALUES (?, ?, 'tpl_x', 'gelato-1', "
        "'etsy-listing-1', 'published', ?, ?)",
        (candidate_id, primary_group_id, timestamp, timestamp),
    )
    group_product_id = cursor.lastrowid
    for order, url in enumerate(["https://gelato/a.jpg", "https://gelato/b.jpg", "https://gelato/c.jpg"]):
        conn.execute(
            "INSERT INTO product_images (group_product_id, group_id, image_url, alt_text, "
            "gallery_order, image_type) VALUES (?, ?, ?, 'alt', ?, 'flat_mockup')",
            (group_product_id, primary_group_id, url, order),
        )
    conn.commit()

    with patch("pipeline.gelato_client.create_product_from_template") as mock_create, \
         patch("pipeline.etsy_client.upload_listing_image",
               return_value={"listing_image_id": "new-img"}) as mock_upload, \
         patch("pipeline.etsy_client.get_listing_images", return_value={"results": []}):
        rebuild_design.gallery_repair(
            conn, candidate_id, config.load_static_config(), shop_id="shop1", dry_run=True,
        )

    mock_create.assert_not_called()
    assert mock_upload.call_count == 3
    ranks = [call.kwargs["rank"] for call in mock_upload.call_args_list]
    assert ranks == [1, 2, 3]


def test_classify_listing_case_reads_draft_published_and_unknown(tmp_path):
    with patch("pipeline.etsy_client.get_listing", return_value={"state": "draft"}):
        assert rebuild_design.classify_listing_case("1") == "draft"
    with patch("pipeline.etsy_client.get_listing", return_value={"state": "active"}):
        assert rebuild_design.classify_listing_case("1") == "published"
    with patch("pipeline.etsy_client.get_listing", side_effect=Exception("404")):
        assert rebuild_design.classify_listing_case("1") == "unknown"
    assert rebuild_design.classify_listing_case(None) == "unknown"
