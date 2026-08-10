import copy
from datetime import datetime
from unittest.mock import patch

import pytest

import pipeline.config as config
import pipeline.db as db
import pipeline.group_mockup as group_mockup


def _fresh_conn(tmp_path):
    conn = db.get_connection(tmp_path / "test.sqlite3")
    db.init_db(conn)
    return conn


def _insert_candidate(conn, niche="monstera line art", *, status="completed",
                       base_image_url="https://replicate.delivery/out.png",
                       base_image_local_path=None):
    timestamp = "2026-07-09T09:00:00"
    cursor = conn.execute(
        """
        INSERT INTO candidates (created_at, niche, go_hold_kill, status, base_image_url,
        base_image_local_path, updated_at)
        VALUES (?, ?, 'go', ?, ?, ?, ?)
        """,
        (timestamp, niche, status, base_image_url, base_image_local_path, timestamp),
    )
    conn.commit()
    return cursor.lastrowid


def _static_config_with_scenes():
    # Real static_config.json has empty mockup_templates for 5x7/10x24 (no scene
    # bundles authored yet - GL-6-proper's job; see Important #1 of the GL-5 final
    # review). run_group_mockup_cycle now skips a group_type with no scenes before
    # ever calling create_group_mockup, so tests proving the *non-skip* fan-out path
    # need a static_config with a scene present. Callers of this fixture mock
    # group_product.render_group_mockups, so the dummy scene id is never actually
    # resolved to a bundle on disk.
    static_config = copy.deepcopy(config.load_static_config())
    static_config["mockup_templates"]["5x7"]["portrait"] = ["dummy_scene"]
    static_config["mockup_templates"]["10x24"]["portrait"] = ["dummy_scene"]
    return static_config


def _make_master(tmp_path, name="master.png", size=(900, 1350)):
    from PIL import Image
    p = tmp_path / name
    Image.new("RGB", size, (200, 180, 150)).save(p, format="PNG")
    return str(p)


def _insert_primary_group(conn, candidate_id, *, status="approved_published", decision="approved"):
    # v4.12: run_group_mockup_cycle's candidate-selection query keys on the primary
    # group's DECISION ('approved'), not its status ('approved_published') - approving
    # the primary no longer publishes anything by itself under v4.12 [D1], so status
    # alone no longer signals "ready for the secondary groups to render".
    timestamp = "2026-07-12T09:00:00"
    cursor = conn.execute(
        "INSERT INTO groups (candidate_id, group_type, status, decision, created_at, updated_at) "
        "VALUES (?, 'primary', ?, ?, ?, ?)",
        (candidate_id, status, decision, timestamp, timestamp),
    )
    conn.commit()
    return cursor.lastrowid


def test_get_or_create_group_creates_new_row(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)

    group_id = group_mockup.get_or_create_group(
        conn, candidate_id, "5x7", now=datetime(2026, 7, 12, 18, 0, 0)
    )

    row = conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone()
    assert row["candidate_id"] == candidate_id
    assert row["group_type"] == "5x7"
    assert row["status"] == "pending_generation"
    assert row["created_at"] == "2026-07-12T18:00:00"
    conn.close()


def test_get_or_create_group_returns_existing_row(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    first_id = group_mockup.get_or_create_group(
        conn, candidate_id, "10x24", now=datetime(2026, 7, 12, 18, 0, 0)
    )

    second_id = group_mockup.get_or_create_group(
        conn, candidate_id, "10x24", now=datetime(2026, 7, 12, 19, 0, 0)
    )

    assert second_id == first_id
    rows = conn.execute(
        "SELECT * FROM groups WHERE candidate_id = ? AND group_type = '10x24'", (candidate_id,)
    ).fetchall()
    assert len(rows) == 1
    conn.close()


def test_get_or_create_group_keeps_5x7_and_10x24_separate(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)

    id_5x7 = group_mockup.get_or_create_group(conn, candidate_id, "5x7", now=datetime(2026, 7, 12, 18, 0, 0))
    id_10x24 = group_mockup.get_or_create_group(conn, candidate_id, "10x24", now=datetime(2026, 7, 12, 18, 0, 0))

    assert id_5x7 != id_10x24
    conn.close()


def test_create_group_mockup_creates_group_product_with_group_variant(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn, base_image_local_path=_make_master(tmp_path))
    _insert_primary_group(conn, candidate_id, status="approved_published")
    static_config = config.load_static_config()

    result = group_mockup.create_group_mockup(
        conn, candidate_id, "5x7", static_config=static_config, now="2026-07-16T09:00:00",
    )

    variant_row = conn.execute(
        "SELECT size, price_eur FROM group_product_variants WHERE group_product_id = ?",
        (result["group_product_id"],),
    ).fetchone()
    assert variant_row["size"] == "5x7"
    assert variant_row["price_eur"] == static_config["prices_eur"]["5x7"]

    group_row = conn.execute("SELECT * FROM groups WHERE id = ?", (result["group_id"],)).fetchone()
    assert group_row["group_type"] == "5x7"
    assert group_row["status"] == "pending_review"
    conn.close()


def test_create_group_mockup_delegates_with_full_sizes_list_from_config(tmp_path):
    # _group_sizes must pull the *whole* aspect_ratio_groups[group_type] list (not assume a
    # single size) - today's config has exactly one size per 5x7/10x24 group, but a future
    # multi-size 5x7/10x24 group must work without another rewrite here.
    #
    # create_or_reuse_group_product is gone (split into render_group_mockups +
    # create_candidate_gelato_product); create_group_mockup only calls the render half
    # and forwards no title/Gelato-poll args - there is no Gelato call at mockup time
    # under v4.12.
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn, niche="monstera line art")
    _insert_primary_group(conn, candidate_id)
    static_config = {
        "aspect_ratio_groups": {"primary": ["8x12", "A3", "A2", "A1"], "5x7": ["5x7", "5x7-alt"]},
        "prices_eur": {"5x7": 19, "5x7-alt": 21},
    }

    with patch("pipeline.group_mockup.group_product.render_group_mockups") as mock_render:
        mock_render.return_value = {"group_product_id": 42, "image_count": 2}
        result = group_mockup.create_group_mockup(
            conn, candidate_id, "5x7", static_config=static_config, store_id="store1", api_key="key1",
            poll_interval=1, poll_timeout=5, now=datetime(2026, 7, 16, 12, 0, 0),
        )

    assert mock_render.call_count == 1
    args, kwargs = mock_render.call_args
    conn_arg, group_id_arg, sizes_arg, candidate_arg, static_config_arg = args
    assert sizes_arg == ["5x7", "5x7-alt"]
    assert candidate_arg["niche"] == "monstera line art"
    assert kwargs == {"now": datetime(2026, 7, 16, 12, 0, 0)}

    assert result["group_product_id"] == 42
    assert "gelato_product_id" not in result
    conn.close()


def test_create_group_mockup_builds_no_title_for_render(tmp_path):
    # v4.12: render_group_mockups takes no title at all - group_mockup.py no longer
    # builds a per-group Gelato-push title (that function, and this 140-char cap, was
    # deleted along with create_or_reuse_group_product; see git log 0417909). Etsy
    # title-length compliance is now enforced exactly once, in
    # compliance_draft.validate_listing_text, against the one title the shared listing
    # actually uses - covered by tests/test_compliance_draft.py, not re-tested here.
    # This just proves group_mockup doesn't resurrect a title concern of its own: a
    # 150-char niche must not change what's forwarded to render_group_mockups.
    conn = _fresh_conn(tmp_path)
    long_niche = "a" * 150
    candidate_id = _insert_candidate(conn, niche=long_niche)
    _insert_primary_group(conn, candidate_id)
    static_config = {
        "aspect_ratio_groups": {"primary": ["8x12", "A3", "A2", "A1"], "10x24": ["10x24"]},
        "prices_eur": {"10x24": 45},
    }

    with patch("pipeline.group_mockup.group_product.render_group_mockups") as mock_render:
        mock_render.return_value = {"group_product_id": 1, "image_count": 1}
        group_mockup.create_group_mockup(
            conn, candidate_id, "10x24", static_config=static_config, store_id="store1", api_key="key1",
            poll_interval=1, poll_timeout=5, now=datetime(2026, 7, 16, 12, 0, 0),
        )

    args, kwargs = mock_render.call_args
    assert len(args) == 5  # conn, group_id, sizes, candidate, static_config - no title
    assert "title" not in kwargs
    conn.close()


def test_create_group_mockup_skips_when_already_created(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn, base_image_local_path=_make_master(tmp_path))
    _insert_primary_group(conn, candidate_id, status="approved_published")
    static_config = config.load_static_config()

    first = group_mockup.create_group_mockup(
        conn, candidate_id, "5x7", static_config=static_config, now=datetime(2026, 7, 12, 18, 0, 0),
    )
    second = group_mockup.create_group_mockup(
        conn, candidate_id, "5x7", static_config=static_config, now=datetime(2026, 7, 12, 19, 0, 0),
    )

    assert first is not None
    assert second is None
    conn.close()


def test_create_group_mockup_returns_none_for_failed_abandoned_group(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_primary_group(conn, candidate_id)
    group_mockup.get_or_create_group(conn, candidate_id, "5x7", now=datetime(2026, 7, 12, 18, 0, 0))
    conn.execute(
        "UPDATE groups SET status = 'failed_abandoned' WHERE candidate_id = ? AND group_type = '5x7'",
        (candidate_id,),
    )
    conn.commit()
    static_config = config.load_static_config()

    with patch("pipeline.group_mockup.group_product.render_group_mockups") as mock_render:
        result = group_mockup.create_group_mockup(
            conn, candidate_id, "5x7", static_config=static_config, now=datetime(2026, 7, 12, 19, 0, 0),
        )

    assert result is None
    mock_render.assert_not_called()
    conn.close()


def test_create_group_mockup_returns_none_for_rejected_group(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_primary_group(conn, candidate_id)
    group_mockup.get_or_create_group(conn, candidate_id, "10x24", now=datetime(2026, 7, 12, 18, 0, 0))
    conn.execute(
        "UPDATE groups SET status = 'rejected' WHERE candidate_id = ? AND group_type = '10x24'",
        (candidate_id,),
    )
    conn.commit()
    static_config = config.load_static_config()

    with patch("pipeline.group_mockup.group_product.render_group_mockups") as mock_render:
        result = group_mockup.create_group_mockup(
            conn, candidate_id, "10x24", static_config=static_config, now=datetime(2026, 7, 12, 19, 0, 0),
        )

    assert result is None
    mock_render.assert_not_called()
    conn.close()


def test_create_group_mockup_retries_once_then_succeeds(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_primary_group(conn, candidate_id)
    static_config = config.load_static_config()

    with patch(
        "pipeline.group_mockup.group_product.render_group_mockups",
        side_effect=[RuntimeError("Gelato throttled"),
                     {"group_product_id": 1, "image_count": 1}],
    ) as mock_render:
        result = group_mockup.create_group_mockup(
            conn, candidate_id, "5x7", static_config=static_config, now=datetime(2026, 7, 12, 18, 0, 0),
        )

    assert result["group_product_id"] == 1
    assert mock_render.call_count == 2
    conn.close()


def test_create_group_mockup_propagates_after_second_failure(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_primary_group(conn, candidate_id)
    static_config = config.load_static_config()

    with patch(
        "pipeline.group_mockup.group_product.render_group_mockups",
        side_effect=RuntimeError("Gelato down"),
    ):
        try:
            group_mockup.create_group_mockup(
                conn, candidate_id, "10x24", static_config=static_config, now=datetime(2026, 7, 12, 18, 0, 0),
            )
            assert False, "expected RuntimeError"
        except RuntimeError as exc:
            assert "Gelato down" in str(exc)

    group_row = conn.execute(
        "SELECT status FROM groups WHERE candidate_id = ? AND group_type = '10x24'", (candidate_id,)
    ).fetchone()
    # group creation happens before delegation and is not rolled back on failure; the
    # 'mockup_failed' status on the group_products row itself is group_product.py's own
    # responsibility (tests/test_group_product.py), not re-verified here.
    assert group_row["status"] == "pending_generation"
    conn.close()


def test_run_group_mockup_cycle_processes_both_group_types_for_ready_candidate(tmp_path):
    # KNOWN PRODUCTION BUG (pipeline/group_mockup.py:132): run_group_mockup_cycle still
    # reads result["gelato_product_id"] when building `processed`, but
    # create_group_mockup/render_group_mockups return {"group_id","group_product_id"} -
    # there is no "gelato_product_id" key any more (v4.12: no Gelato call at mockup
    # time). That line is outside the per-group-type try/except, so it raises KeyError
    # and crashes the whole cycle on any successful render. Filed, not fixed here -
    # out of scope (pipeline/ is not an editable file for this task). This test asserts
    # the correct, intended behaviour and will fail against today's code until that
    # line is fixed to use result["group_product_id"] (or drops the key).
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn, niche="monstera line art", base_image_local_path=_make_master(tmp_path))
    _insert_primary_group(conn, candidate_id)
    static_config = _static_config_with_scenes()

    with patch("pipeline.group_mockup.group_product.render_group_mockups") as mock_render:
        mock_render.side_effect = lambda conn, group_id, sizes, candidate, static_config, **kwargs: {
            "group_product_id": group_id, "image_count": len(sizes),
        }
        processed = group_mockup.run_group_mockup_cycle(
            conn, static_config=static_config, poll_interval=0, poll_timeout=10,
            now=datetime(2026, 7, 12, 20, 0, 0),
        )

    assert {(p["candidate_id"], p["group_type"]) for p in processed} == {
        (candidate_id, "5x7"), (candidate_id, "10x24"),
    }
    conn.close()


def test_run_group_mockup_cycle_skips_candidates_without_published_primary(tmp_path):
    conn = _fresh_conn(tmp_path)
    _insert_candidate(conn, niche="unreviewed one", status="primary_review")
    static_config = config.load_static_config()

    processed = group_mockup.run_group_mockup_cycle(conn, static_config=static_config)

    assert processed == []
    conn.close()


def _fake_render_writes_gallery_row(conn, group_id, sizes, candidate, static_config, **kwargs):
    # create_group_mockup's own "already done" skip (checked in group_mockup.py, not
    # mocked here) now reads for a product_images row on a non-deleted group_products
    # row for THIS group_id - not group_products.status - so a fake that doesn't write
    # both a group_products row and a product_images row can never prove the skip
    # (v4.12: the row belongs to the candidate and is shared across groups).
    candidate_id = candidate["id"]
    row = conn.execute(
        "SELECT id FROM group_products WHERE candidate_id = ? AND status != 'deleted'", (candidate_id,)
    ).fetchone()
    if row is None:
        cursor = conn.execute(
            "INSERT INTO group_products (candidate_id, group_id, gelato_template_id, status, created_at, updated_at) "
            "VALUES (?, ?, 'tmpl', 'pending', '2026-07-12T20:00:00', '2026-07-12T20:00:00')",
            (candidate_id, group_id),
        )
        group_product_id = cursor.lastrowid
    else:
        group_product_id = row["id"]
    conn.execute(
        "INSERT INTO product_images (group_product_id, group_id, image_url, alt_text, gallery_order, image_type) "
        "VALUES (?, ?, 'https://example.com/x.png', '', 0, 'flat_mockup')",
        (group_product_id, group_id),
    )
    conn.commit()
    return {"group_product_id": group_product_id, "image_count": 1}


def test_run_group_mockup_cycle_skips_group_types_already_created(tmp_path):
    # See the KNOWN PRODUCTION BUG note on
    # test_run_group_mockup_cycle_processes_both_group_types_for_ready_candidate - the
    # first_run here hits the same result["gelato_product_id"] KeyError and will fail
    # against today's code.
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn, base_image_local_path=_make_master(tmp_path))
    _insert_primary_group(conn, candidate_id)
    static_config = _static_config_with_scenes()

    with patch(
        "pipeline.group_mockup.group_product.render_group_mockups",
        side_effect=_fake_render_writes_gallery_row,
    ):
        first_run = group_mockup.run_group_mockup_cycle(
            conn, static_config=static_config, poll_interval=0, poll_timeout=10,
            now=datetime(2026, 7, 12, 20, 0, 0),
        )
        second_run = group_mockup.run_group_mockup_cycle(
            conn, static_config=static_config, poll_interval=0, poll_timeout=10,
            now=datetime(2026, 7, 12, 21, 0, 0),
        )

    assert len(first_run) == 2
    assert second_run == []
    conn.close()


def test_run_group_mockup_cycle_isolates_per_group_type_failures(tmp_path):
    # See the KNOWN PRODUCTION BUG note above - the surviving 10x24 result still hits
    # result["gelato_product_id"] and will fail against today's code.
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_primary_group(conn, candidate_id)
    static_config = _static_config_with_scenes()

    def fake_render(conn, group_id, sizes, candidate, static_config, **kwargs):
        if "5x7" in sizes:
            raise RuntimeError("Gelato throttled")
        return {"group_product_id": 1, "image_count": len(sizes)}

    with patch(
        "pipeline.group_mockup.group_product.render_group_mockups",
        side_effect=fake_render,
    ):
        # GL-54: the loop still finishes (10x24 still gets its turn), but the
        # cycle now raises once at the end so run_batch's _run_stage sees it.
        with pytest.raises(group_mockup.GroupMockupCycleError, match="Gelato throttled"):
            group_mockup.run_group_mockup_cycle(
                conn, static_config=static_config, poll_interval=0, poll_timeout=10,
                now=datetime(2026, 7, 12, 20, 0, 0),
            )

    failing_group = conn.execute(
        "SELECT status, failed_reason FROM groups WHERE candidate_id = ? AND group_type = '5x7'",
        (candidate_id,),
    ).fetchone()
    assert failing_group["status"] == "pending_generation"
    assert "Gelato throttled" in failing_group["failed_reason"]
    conn.close()


def test_run_group_mockup_cycle_does_not_resurrect_abandoned_group(tmp_path):
    # See the KNOWN PRODUCTION BUG note above - the surviving 10x24 result still hits
    # result["gelato_product_id"] and will fail against today's code.
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn, base_image_local_path=_make_master(tmp_path))
    _insert_primary_group(conn, candidate_id)
    group_mockup.get_or_create_group(conn, candidate_id, "5x7", now=datetime(2026, 7, 12, 18, 0, 0))
    conn.execute(
        "UPDATE groups SET status = 'failed_abandoned' WHERE candidate_id = ? AND group_type = '5x7'",
        (candidate_id,),
    )
    conn.commit()
    static_config = _static_config_with_scenes()

    with patch("pipeline.group_mockup.group_product.render_group_mockups") as mock_render:
        mock_render.side_effect = lambda conn, group_id, sizes, candidate, static_config, **kwargs: {
            "group_product_id": group_id, "image_count": len(sizes),
        }
        processed = group_mockup.run_group_mockup_cycle(
            conn, static_config=static_config, poll_interval=0, poll_timeout=10,
            now=datetime(2026, 7, 12, 20, 0, 0),
        )

    assert [(p["candidate_id"], p["group_type"]) for p in processed] == [(candidate_id, "10x24")]
    group_row = conn.execute(
        "SELECT status FROM groups WHERE candidate_id = ? AND group_type = '5x7'", (candidate_id,)
    ).fetchone()
    assert group_row["status"] == "failed_abandoned"
    conn.close()


def test_run_group_mockup_cycle_returns_empty_list_when_nothing_ready(tmp_path):
    conn = _fresh_conn(tmp_path)
    static_config = config.load_static_config()

    processed = group_mockup.run_group_mockup_cycle(conn, static_config=static_config)

    assert processed == []
    conn.close()


# H4's original regression (poll_interval silently downgraded on the fan-out path) no
# longer applies: render_group_mockups makes no Gelato call at all, so there is no poll
# to calm and nothing Gelato-related for create_group_mockup/run_group_mockup_cycle to
# forward to it any more. These now lock the opposite: a caller-supplied
# store_id/api_key/poll_interval/poll_timeout must NOT leak into the render call.
def test_create_group_mockup_does_not_forward_gelato_poll_kwargs(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_primary_group(conn, candidate_id)
    static_config = config.load_static_config()

    with patch("pipeline.group_mockup.group_product.render_group_mockups") as mock_render:
        mock_render.return_value = {"group_product_id": 1, "image_count": 1}
        group_mockup.create_group_mockup(
            conn, candidate_id, "5x7", static_config=static_config, store_id="s1", api_key="k1",
            poll_interval=1, poll_timeout=5, now=datetime(2026, 7, 16, 12, 0, 0),
        )

    assert mock_render.call_args.kwargs == {"now": datetime(2026, 7, 16, 12, 0, 0)}
    conn.close()


def test_run_group_mockup_cycle_does_not_forward_gelato_poll_kwargs(tmp_path):
    # See the KNOWN PRODUCTION BUG note on
    # test_run_group_mockup_cycle_processes_both_group_types_for_ready_candidate - a
    # successful render still hits result["gelato_product_id"] and will fail against
    # today's code.
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_primary_group(conn, candidate_id)
    static_config = _static_config_with_scenes()

    with patch("pipeline.group_mockup.group_product.render_group_mockups") as mock_render:
        mock_render.return_value = {"group_product_id": 1, "image_count": 1}
        group_mockup.run_group_mockup_cycle(
            conn, static_config=static_config, store_id="s1", api_key="k1",
            poll_interval=1, poll_timeout=5, now=datetime(2026, 7, 16, 12, 0, 0),
        )

    assert mock_render.call_count >= 1
    for call in mock_render.call_args_list:
        assert call.kwargs == {"now": datetime(2026, 7, 16, 12, 0, 0)}
    conn.close()


# GL-5 final review, Important #1: a group_type with no scene bundles authored yet
# (today: 5x7 and 10x24, per config/static_config.json) must be skipped entirely -
# no groups row, no group_products row, no Gelato/critic/digest call - rather than
# created empty and left to loop forever in group_critic_pass/group_digest.
def test_run_group_mockup_cycle_skips_group_type_with_empty_mockup_templates(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_primary_group(conn, candidate_id)
    # Both secondary groups emptied here rather than read off the real config:
    # 5x7 and 10x24 had no scenes until 2026-07-31, and this test silently
    # became a test of the library's contents rather than of the skip.
    static_config = copy.deepcopy(config.load_static_config())
    for g in ("5x7", "10x24"):
        static_config["mockup_templates"][g] = {"portrait": [], "landscape": []}

    with patch("pipeline.group_mockup.group_product.render_group_mockups") as mock_render:
        processed = group_mockup.run_group_mockup_cycle(
            conn, static_config=static_config, poll_interval=0, poll_timeout=10,
            now=datetime(2026, 7, 12, 20, 0, 0),
        )

    assert processed == []
    mock_render.assert_not_called()
    assert conn.execute("SELECT COUNT(*) AS n FROM groups WHERE candidate_id = ?", (candidate_id,)).fetchone()["n"] == 1
    assert conn.execute("SELECT COUNT(*) AS n FROM group_products").fetchone()["n"] == 0
    conn.close()


def test_run_group_mockup_cycle_still_processes_group_type_with_scenes_configured(tmp_path):
    # See the KNOWN PRODUCTION BUG note on
    # test_run_group_mockup_cycle_processes_both_group_types_for_ready_candidate - the
    # 5x7 success still hits result["gelato_product_id"] and will fail against today's
    # code.
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_primary_group(conn, candidate_id)
    # Only 5x7 gets a scene here and 10x24 is emptied, so this also proves the
    # skip is per-group_type, not all-or-nothing.
    static_config = copy.deepcopy(config.load_static_config())
    static_config["mockup_templates"]["5x7"] = {"portrait": ["dummy_scene"], "landscape": []}
    static_config["mockup_templates"]["10x24"] = {"portrait": [], "landscape": []}

    with patch("pipeline.group_mockup.group_product.render_group_mockups") as mock_render:
        mock_render.return_value = {"group_product_id": 1, "image_count": 1}
        processed = group_mockup.run_group_mockup_cycle(
            conn, static_config=static_config, poll_interval=0, poll_timeout=10,
            now=datetime(2026, 7, 12, 20, 0, 0),
        )

    assert [(p["candidate_id"], p["group_type"]) for p in processed] == [(candidate_id, "5x7")]
    mock_render.assert_called_once()
    conn.close()
