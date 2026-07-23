"""GL-16 definition-of-done test: a stage killed mid-run leaves a resumable
state that the next scheduled cycle reclaims with zero manual DB edits.
Two scenarios per docs/2026-07-22-resilience-design.md section 4/5:
1. generate_for_candidate interrupted before its terminal status write.
2. create_or_reuse_group_product interrupted between the 'pending' row
   commit and the Gelato call - cleanup.py's reclaim makes the next
   create_or_reuse_group_product call start clean instead of leaking a
   phantom row per crashed attempt."""
from datetime import datetime
from unittest.mock import patch

import pipeline.cleanup as cleanup
import pipeline.config as config
import pipeline.db as db
import pipeline.generate as generate
import pipeline.group_product as group_product


def _fresh_conn(tmp_path):
    conn = db.get_connection(tmp_path / "test.sqlite3")
    db.init_db(conn)
    return conn


def _insert_candidate(conn, niche="monstera line art", *, status="pending",
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


def test_generate_cycle_resumes_after_mid_stage_kill_without_manual_intervention(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)

    # Cycle 1: process gets killed mid-generate (simulated as an unhandled
    # exception from the Replicate call, the same failure shape a SIGKILL or a
    # genuine vendor outage produces from the caller's perspective).
    with patch("pipeline.art_brief.generate_art_brief", return_value="A line-art monstera leaf, cream backdrop."), \
         patch("pipeline.generate.replicate_client.generate_image",
               side_effect=RuntimeError("simulated kill mid-generate")):
        processed_1 = generate.run_generate_cycle(conn, api_token="tok1")

    assert processed_1 == []
    row_after_kill = conn.execute(
        "SELECT status, art_brief FROM candidates WHERE id = ?", (candidate_id,)
    ).fetchone()
    # Left exactly where it was - no partial write, no manual DB edit performed here.
    assert row_after_kill["status"] == "pending"
    assert row_after_kill["art_brief"]  # brief was written and persists - not redone on resume

    # Cycle 2: next scheduled run, same code path, no human touched the DB in between.
    with patch("pipeline.generate.replicate_client.generate_image",
               return_value={"image_url": "https://replicate.delivery/raw.png", "prediction_id": "pred_1"}), \
         patch("pipeline.generate.replicate_client.upscale_image",
               return_value={"image_url": "https://replicate.delivery/upscaled.png", "prediction_id": "pred_1_up"}), \
         patch("pipeline.generate.http.fetch_bytes", return_value=b"fake-image-bytes"), \
         patch("pipeline.generate.artwork_store.persist_base_artwork",
               side_effect=lambda cid, raw: {
                   "durable_url": f"https://pub-fake.r2.dev/base/{cid}.png",
                   "local_path": f"/fake/db/base_artwork/{cid}.png",
                   "sha256": "fakesha256hash",
               }):
        processed_2 = generate.run_generate_cycle(conn, api_token="tok1")

    assert processed_2 == [candidate_id]
    row_after_resume = conn.execute(
        "SELECT status, base_image_url FROM candidates WHERE id = ?", (candidate_id,)
    ).fetchone()
    assert row_after_resume["status"] == "generating"
    assert row_after_resume["base_image_url"] == f"https://pub-fake.r2.dev/base/{candidate_id}.png"
    conn.close()


def test_stranded_pending_group_product_reclaimed_then_create_or_reuse_succeeds_cleanly(tmp_path):
    from PIL import Image
    conn = _fresh_conn(tmp_path)
    master_path = tmp_path / "master.png"
    Image.new("RGB", (900, 1350), (200, 180, 150)).save(master_path, format="PNG")
    candidate_id = _insert_candidate(
        conn, status="primary_review", base_image_local_path=str(master_path),
    )
    group_id = _insert_group(conn, candidate_id)

    # Simulate the exact crash window: create_or_reuse_group_product's INSERT +
    # commit landed, then the process died before the Gelato call. No human
    # fixes this row - the next cron cycle's cleanup pass must reclaim it.
    stranded_id = conn.execute(
        "INSERT INTO group_products (group_id, gelato_template_id, status, created_at, updated_at) "
        "VALUES (?, 'tpl_x', 'pending', '2026-07-16T09:00:00', '2026-07-16T09:00:00')",
        (group_id,),
    ).lastrowid
    conn.commit()

    reclaimed = cleanup.reclaim_stranded_pending_group_products(
        conn, max_age_minutes=10, now=datetime(2026, 7, 16, 9, 20, 0),
    )
    assert reclaimed == [stranded_id]
    assert conn.execute(
        "SELECT id FROM group_products WHERE id = ?", (stranded_id,)
    ).fetchone() is None

    # Next scheduled run re-invokes the same stage - starts clean, exactly one
    # live row, no leaked duplicate from the crashed attempt.
    candidate = dict(conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone())
    with patch("pipeline.group_product.gelato_client.create_product_from_template") as mock_create:
        mock_create.return_value = {"id": "gelato-prod-resumed", "_dry_run": True, "previewUrl": None, "productImages": []}
        result = group_product.create_or_reuse_group_product(
            conn, group_id, ["8x12", "A3", "A2", "A1"], candidate, config.load_static_config(),
            "Monstera Line Art", now="2026-07-16T09:20:00",
        )

    assert mock_create.call_count == 1
    live_rows = conn.execute(
        "SELECT id FROM group_products WHERE group_id = ? AND status IN ('pending', 'created', 'published')",
        (group_id,),
    ).fetchall()
    assert [row["id"] for row in live_rows] == [result["group_product_id"]]
    conn.close()
