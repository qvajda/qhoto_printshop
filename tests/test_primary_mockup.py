from datetime import datetime
from unittest.mock import patch

import pipeline.config as config
import pipeline.db as db
import pipeline.primary_mockup as primary_mockup


def _fresh_conn(tmp_path):
    conn = db.get_connection(tmp_path / "test.sqlite3")
    db.init_db(conn)
    return conn


def _insert_candidate(conn, niche="monstera line art", *, status="generating",
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


def _make_master(tmp_path, name="master.png", size=(900, 1350)):
    from PIL import Image
    p = tmp_path / name
    Image.new("RGB", size, (200, 180, 150)).save(p, format="PNG")
    return str(p)


def test_build_mockup_title_includes_niche():
    candidate = {"niche": "monstera line art"}

    title = primary_mockup.build_mockup_title(candidate)

    assert "monstera line art" in title
    assert "primary mockup" in title.lower()


def test_get_or_create_primary_group_creates_new_row(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)

    group_id = primary_mockup.get_or_create_primary_group(
        conn, candidate_id, now=datetime(2026, 7, 9, 10, 0, 0)
    )

    row = conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone()
    assert row["candidate_id"] == candidate_id
    assert row["group_type"] == "primary"
    assert row["status"] == "pending_generation"
    assert row["created_at"] == "2026-07-09T10:00:00"
    conn.close()


def test_get_or_create_primary_group_returns_existing_row(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    first_id = primary_mockup.get_or_create_primary_group(
        conn, candidate_id, now=datetime(2026, 7, 9, 10, 0, 0)
    )

    second_id = primary_mockup.get_or_create_primary_group(
        conn, candidate_id, now=datetime(2026, 7, 9, 11, 0, 0)
    )

    assert second_id == first_id
    rows = conn.execute(
        "SELECT * FROM groups WHERE candidate_id = ? AND group_type = 'primary'", (candidate_id,)
    ).fetchall()
    assert len(rows) == 1
    conn.close()


# poll_until_ready / GelatoMockupTimeoutError now live in pipeline.group_product - covered by
# tests/test_group_product.py, not re-tested here.


def test_create_primary_mockup_creates_group_product_with_8x12_variant(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn, base_image_local_path=_make_master(tmp_path))
    static_config = config.load_static_config()

    result = primary_mockup.create_primary_mockup(
        conn, candidate_id, static_config=static_config, now="2026-07-16T09:00:00",
    )

    gp_row = conn.execute(
        "SELECT * FROM group_products WHERE id = ?", (result["group_product_id"],)
    ).fetchone()
    assert gp_row["status"] == "created"
    variant_row = conn.execute(
        "SELECT size, price_eur FROM group_product_variants WHERE group_product_id = ?",
        (result["group_product_id"],),
    ).fetchone()
    assert variant_row["size"] == "8x12"
    assert variant_row["price_eur"] == static_config["prices_eur"]["8x12"]
    conn.close()


def test_create_primary_mockup_delegates_to_create_or_reuse_group_product(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn, niche="monstera line art")
    static_config = config.load_static_config()

    with patch(
        "pipeline.primary_mockup.group_product.create_or_reuse_group_product"
    ) as mock_create:
        mock_create.return_value = {"group_product_id": 42, "gelato_product_id": "gelato-prod-1"}
        result = primary_mockup.create_primary_mockup(
            conn, candidate_id, static_config=static_config, store_id="store1", api_key="key1",
            poll_interval=1, poll_timeout=5, now=datetime(2026, 7, 16, 12, 0, 0),
        )

    assert mock_create.call_count == 1
    args, kwargs = mock_create.call_args
    conn_arg, group_id_arg, sizes_arg, candidate_arg, static_config_arg, title_arg = args
    assert sizes_arg == ["8x12"]
    assert candidate_arg["niche"] == "monstera line art"
    assert title_arg == primary_mockup.build_mockup_title(candidate_arg)
    assert kwargs["store_id"] == "store1"
    assert kwargs["api_key"] == "key1"
    assert kwargs["poll_interval"] == 1
    assert kwargs["poll_timeout"] == 5

    assert result["group_product_id"] == 42
    assert result["gelato_product_id"] == "gelato-prod-1"

    group_row = conn.execute("SELECT * FROM groups WHERE id = ?", (result["group_id"],)).fetchone()
    assert group_row["status"] == "pending_review"
    conn.close()


def test_create_primary_mockup_propagates_delegate_failure(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn, niche="saturated term")
    static_config = config.load_static_config()

    with patch(
        "pipeline.primary_mockup.group_product.create_or_reuse_group_product",
        side_effect=RuntimeError("Gelato 500"),
    ):
        try:
            primary_mockup.create_primary_mockup(
                conn, candidate_id, static_config=static_config, now=datetime(2026, 7, 16, 12, 0, 0),
            )
            assert False, "expected RuntimeError"
        except RuntimeError as exc:
            assert "Gelato 500" in str(exc)

    group_row = conn.execute(
        "SELECT * FROM groups WHERE candidate_id = ? AND group_type = 'primary'", (candidate_id,)
    ).fetchone()
    # group creation happens before delegation and is not rolled back on failure
    assert group_row["status"] == "pending_generation"
    conn.close()


def test_run_primary_mockup_cycle_processes_ready_candidates_and_skips_others(tmp_path):
    conn = _fresh_conn(tmp_path)
    ready_id = _insert_candidate(conn, niche="monstera line art", status="generating",
                                  base_image_url="https://replicate.delivery/a.png")
    _insert_candidate(conn, niche="pending one", status="pending", base_image_url=None)
    static_config = config.load_static_config()

    with patch(
        "pipeline.primary_mockup.group_product.create_or_reuse_group_product"
    ) as mock_create:
        mock_create.return_value = {"group_product_id": 1, "gelato_product_id": "gelato-prod-x"}
        processed_ids = primary_mockup.run_primary_mockup_cycle(
            conn, static_config=static_config, store_id="store1", api_key="key1",
            now=datetime(2026, 7, 16, 12, 0, 0),
        )

    assert processed_ids == [ready_id]
    conn.close()


def test_run_primary_mockup_cycle_skips_candidates_already_mocked_up(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(
        conn, niche="monstera line art", status="generating", base_image_local_path=_make_master(tmp_path),
    )
    static_config = config.load_static_config()

    # Exercise the real create_or_reuse_group_product (dry-run, since GELATO_LIVE_MODE is unset)
    # so the group_products row it inserts is what makes the cycle's exclusion query work -
    # fully mocking that function away (as elsewhere in this file) would skip the DB write the
    # idempotency check here actually depends on.
    first_run = primary_mockup.run_primary_mockup_cycle(
        conn, static_config=static_config, store_id="store1", api_key="key1",
        now=datetime(2026, 7, 16, 12, 0, 0),
    )
    second_run = primary_mockup.run_primary_mockup_cycle(
        conn, static_config=static_config, store_id="store1", api_key="key1",
        now=datetime(2026, 7, 16, 13, 0, 0),
    )

    assert first_run == [candidate_id]
    assert second_run == []
    conn.close()


def test_run_primary_mockup_cycle_isolates_per_candidate_failures(tmp_path):
    conn = _fresh_conn(tmp_path)
    failing_id = _insert_candidate(conn, niche="monstera line art", status="generating",
                                    base_image_url="https://replicate.delivery/fail.png")
    succeeding_id = _insert_candidate(conn, niche="moon phase print", status="generating",
                                       base_image_url="https://replicate.delivery/ok.png")
    static_config = config.load_static_config()

    def fake_create_or_reuse(conn, group_id, sizes, candidate, static_config, title, **kwargs):
        if candidate["base_image_url"] == "https://replicate.delivery/fail.png":
            raise RuntimeError("Gelato throttled")
        return {"group_product_id": 1, "gelato_product_id": "gelato-prod-ok"}

    with patch(
        "pipeline.primary_mockup.group_product.create_or_reuse_group_product",
        side_effect=fake_create_or_reuse,
    ):
        processed_ids = primary_mockup.run_primary_mockup_cycle(
            conn, static_config=static_config, store_id="store1", api_key="key1",
            now=datetime(2026, 7, 16, 12, 0, 0), sleep_fn=lambda s: None,
        )

    assert processed_ids == [succeeding_id]
    conn.close()


def test_run_primary_mockup_cycle_retries_candidate_with_mockup_failed_product(tmp_path):
    # A prior cycle's group_product row can be left in 'mockup_failed' (e.g. a Gelato
    # timeout or transient 403) without ever reaching 'created'. The candidate-selection
    # query used to exclude a candidate if *any* group_products row existed for its
    # primary group, regardless of status - permanently orphaning it. It must still be
    # picked up so create_or_reuse_group_product's own mockup_failed cleanup can run.
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn, niche="monstera line art", status="generating")
    group_id = primary_mockup.get_or_create_primary_group(conn, candidate_id, now="2026-07-16T09:00:00")
    conn.execute(
        "INSERT INTO group_products (group_id, gelato_template_id, status, created_at, updated_at) "
        "VALUES (?, 'template-1', 'mockup_failed', '2026-07-16T09:00:00', '2026-07-16T09:00:00')",
        (group_id,),
    )
    conn.commit()
    static_config = config.load_static_config()

    with patch(
        "pipeline.primary_mockup.group_product.create_or_reuse_group_product"
    ) as mock_create:
        mock_create.return_value = {"group_product_id": 99, "gelato_product_id": "gelato-prod-retry"}
        processed_ids = primary_mockup.run_primary_mockup_cycle(
            conn, static_config=static_config, now=datetime(2026, 7, 16, 12, 0, 0),
        )

    assert processed_ids == [candidate_id]
    conn.close()


def test_run_primary_mockup_cycle_returns_empty_list_when_nothing_ready(tmp_path):
    conn = _fresh_conn(tmp_path)
    _insert_candidate(conn, niche="pending one", status="pending", base_image_url=None)
    static_config = config.load_static_config()

    processed_ids = primary_mockup.run_primary_mockup_cycle(conn, static_config=static_config)

    assert processed_ids == []
    conn.close()
