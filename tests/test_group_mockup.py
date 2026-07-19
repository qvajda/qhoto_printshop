from datetime import datetime
from unittest.mock import patch

import pipeline.config as config
import pipeline.db as db
import pipeline.group_mockup as group_mockup


def _fresh_conn(tmp_path):
    conn = db.get_connection(tmp_path / "test.sqlite3")
    db.init_db(conn)
    return conn


def _insert_candidate(conn, niche="monstera line art", *, status="completed",
                       base_image_url="https://replicate.delivery/out.png"):
    timestamp = "2026-07-09T09:00:00"
    cursor = conn.execute(
        """
        INSERT INTO candidates (created_at, niche, go_hold_kill, status, base_image_url, updated_at)
        VALUES (?, ?, 'go', ?, ?, ?)
        """,
        (timestamp, niche, status, base_image_url, timestamp),
    )
    conn.commit()
    return cursor.lastrowid


def _insert_primary_group(conn, candidate_id, *, status="approved_published"):
    timestamp = "2026-07-12T09:00:00"
    cursor = conn.execute(
        "INSERT INTO groups (candidate_id, group_type, status, created_at, updated_at) "
        "VALUES (?, 'primary', ?, ?, ?)",
        (candidate_id, status, timestamp, timestamp),
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
    candidate_id = _insert_candidate(conn)
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
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn, niche="monstera line art")
    _insert_primary_group(conn, candidate_id, status="approved_published")
    static_config = {
        "aspect_ratio_groups": {"primary": ["8x12", "A3", "A2", "A1"], "5x7": ["5x7", "5x7-alt"]},
        "prices_eur": {"5x7": 19, "5x7-alt": 21},
    }

    with patch("pipeline.group_mockup.group_product.create_or_reuse_group_product") as mock_create:
        mock_create.return_value = {"group_product_id": 42, "gelato_product_id": "gelato-prod-1"}
        result = group_mockup.create_group_mockup(
            conn, candidate_id, "5x7", static_config=static_config, store_id="store1", api_key="key1",
            poll_interval=1, poll_timeout=5, now=datetime(2026, 7, 16, 12, 0, 0),
        )

    assert mock_create.call_count == 1
    args, kwargs = mock_create.call_args
    conn_arg, group_id_arg, sizes_arg, candidate_arg, static_config_arg, title_arg = args
    assert sizes_arg == ["5x7", "5x7-alt"]
    assert candidate_arg["niche"] == "monstera line art"
    assert title_arg == "monstera line art - 5x7 mockup"
    assert kwargs["store_id"] == "store1"
    assert kwargs["api_key"] == "key1"
    assert kwargs["poll_interval"] == 1
    assert kwargs["poll_timeout"] == 5

    assert result["group_product_id"] == 42
    assert result["gelato_product_id"] == "gelato-prod-1"
    conn.close()


def test_create_group_mockup_caps_title_at_140_chars(tmp_path):
    conn = _fresh_conn(tmp_path)
    long_niche = "a" * 150
    candidate_id = _insert_candidate(conn, niche=long_niche)
    _insert_primary_group(conn, candidate_id, status="approved_published")
    static_config = {
        "aspect_ratio_groups": {"primary": ["8x12", "A3", "A2", "A1"], "10x24": ["10x24"]},
        "prices_eur": {"10x24": 45},
    }

    with patch("pipeline.group_mockup.group_product.create_or_reuse_group_product") as mock_create:
        mock_create.return_value = {"group_product_id": 1, "gelato_product_id": "gelato-prod-1"}
        group_mockup.create_group_mockup(
            conn, candidate_id, "10x24", static_config=static_config, store_id="store1", api_key="key1",
            poll_interval=1, poll_timeout=5, now=datetime(2026, 7, 16, 12, 0, 0),
        )

    args, _ = mock_create.call_args
    title_arg = args[5]
    assert len(title_arg) <= 140
    conn.close()


def test_create_group_mockup_skips_when_already_created(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
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
    _insert_primary_group(conn, candidate_id, status="approved_published")
    group_mockup.get_or_create_group(conn, candidate_id, "5x7", now=datetime(2026, 7, 12, 18, 0, 0))
    conn.execute(
        "UPDATE groups SET status = 'failed_abandoned' WHERE candidate_id = ? AND group_type = '5x7'",
        (candidate_id,),
    )
    conn.commit()
    static_config = config.load_static_config()

    with patch("pipeline.group_mockup.group_product.create_or_reuse_group_product") as mock_create:
        result = group_mockup.create_group_mockup(
            conn, candidate_id, "5x7", static_config=static_config, now=datetime(2026, 7, 12, 19, 0, 0),
        )

    assert result is None
    mock_create.assert_not_called()
    conn.close()


def test_create_group_mockup_returns_none_for_rejected_group(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_primary_group(conn, candidate_id, status="approved_published")
    group_mockup.get_or_create_group(conn, candidate_id, "10x24", now=datetime(2026, 7, 12, 18, 0, 0))
    conn.execute(
        "UPDATE groups SET status = 'rejected' WHERE candidate_id = ? AND group_type = '10x24'",
        (candidate_id,),
    )
    conn.commit()
    static_config = config.load_static_config()

    with patch("pipeline.group_mockup.group_product.create_or_reuse_group_product") as mock_create:
        result = group_mockup.create_group_mockup(
            conn, candidate_id, "10x24", static_config=static_config, now=datetime(2026, 7, 12, 19, 0, 0),
        )

    assert result is None
    mock_create.assert_not_called()
    conn.close()


def test_create_group_mockup_retries_once_then_succeeds(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_primary_group(conn, candidate_id, status="approved_published")
    static_config = config.load_static_config()

    with patch(
        "pipeline.group_mockup.group_product.create_or_reuse_group_product",
        side_effect=[RuntimeError("Gelato throttled"),
                     {"group_product_id": 1, "gelato_product_id": "gelato_prod_retry"}],
    ) as mock_create:
        result = group_mockup.create_group_mockup(
            conn, candidate_id, "5x7", static_config=static_config, now=datetime(2026, 7, 12, 18, 0, 0),
        )

    assert result["gelato_product_id"] == "gelato_prod_retry"
    assert mock_create.call_count == 2
    conn.close()


def test_create_group_mockup_propagates_after_second_failure(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_primary_group(conn, candidate_id, status="approved_published")
    static_config = config.load_static_config()

    with patch(
        "pipeline.group_mockup.group_product.create_or_reuse_group_product",
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
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn, niche="monstera line art")
    _insert_primary_group(conn, candidate_id, status="approved_published")
    static_config = config.load_static_config()

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


def test_run_group_mockup_cycle_skips_group_types_already_created(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_primary_group(conn, candidate_id, status="approved_published")
    static_config = config.load_static_config()

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
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_primary_group(conn, candidate_id, status="approved_published")
    static_config = config.load_static_config()

    def fake_create_or_reuse(conn, group_id, sizes, candidate, static_config, title, **kwargs):
        if "5x7" in sizes:
            raise RuntimeError("Gelato throttled")
        return {"group_product_id": 1, "gelato_product_id": f"gelato_prod_{sizes[0]}"}

    with patch(
        "pipeline.group_mockup.group_product.create_or_reuse_group_product",
        side_effect=fake_create_or_reuse,
    ):
        processed = group_mockup.run_group_mockup_cycle(
            conn, static_config=static_config, poll_interval=0, poll_timeout=10,
            now=datetime(2026, 7, 12, 20, 0, 0),
        )

    assert [(p["candidate_id"], p["group_type"]) for p in processed] == [(candidate_id, "10x24")]
    conn.close()


def test_run_group_mockup_cycle_does_not_resurrect_abandoned_group(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_primary_group(conn, candidate_id, status="approved_published")
    group_mockup.get_or_create_group(conn, candidate_id, "5x7", now=datetime(2026, 7, 12, 18, 0, 0))
    conn.execute(
        "UPDATE groups SET status = 'failed_abandoned' WHERE candidate_id = ? AND group_type = '5x7'",
        (candidate_id,),
    )
    conn.commit()
    static_config = config.load_static_config()

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


# H4 regression: the 1010 poll-calming fix (10s + jitter) has to reach the fan-out
# path. group_mockup.py defaulted poll_interval=3.0, silently overriding the 10.0
# default down in create_or_reuse_group_product - a 316-test-green run missed it
# because nothing asserted the fan-out default. These lock it at >=10s.
def test_create_group_mockup_defaults_poll_interval_to_at_least_10s(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_primary_group(conn, candidate_id, status="approved_published")
    static_config = config.load_static_config()

    with patch("pipeline.group_mockup.group_product.create_or_reuse_group_product") as mock_create:
        mock_create.return_value = {"group_product_id": 1, "gelato_product_id": "g1"}
        group_mockup.create_group_mockup(
            conn, candidate_id, "5x7", static_config=static_config, now=datetime(2026, 7, 16, 12, 0, 0),
        )

    assert mock_create.call_args.kwargs["poll_interval"] >= 10.0
    conn.close()


def test_run_group_mockup_cycle_defaults_poll_interval_to_at_least_10s(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_primary_group(conn, candidate_id, status="approved_published")
    static_config = config.load_static_config()

    with patch("pipeline.group_mockup.group_product.create_or_reuse_group_product") as mock_create:
        mock_create.return_value = {"group_product_id": 1, "gelato_product_id": "g1"}
        group_mockup.run_group_mockup_cycle(
            conn, static_config=static_config, now=datetime(2026, 7, 16, 12, 0, 0),
        )

    assert mock_create.call_count >= 1
    for call in mock_create.call_args_list:
        assert call.kwargs["poll_interval"] >= 10.0
    conn.close()
