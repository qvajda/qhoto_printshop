from datetime import datetime
from unittest.mock import patch

import pytest

import pipeline.db as db
import pipeline.generate as generate


def _fresh_conn(tmp_path):
    conn = db.get_connection(tmp_path / "test.sqlite3")
    db.init_db(conn)
    return conn


def _insert_pending_candidate(conn, niche="monstera line art", *, status="pending"):
    timestamp = "2026-07-09T09:00:00"
    cursor = conn.execute(
        """
        INSERT INTO candidates (created_at, niche, go_hold_kill, status, updated_at)
        VALUES (?, ?, 'go', ?, ?)
        """,
        (timestamp, niche, status, timestamp),
    )
    conn.commit()
    return cursor.lastrowid


def test_build_prompt_includes_niche_and_no_go_list():
    candidate = {"niche": "monstera line art"}

    prompt = generate.build_prompt(candidate)

    assert "monstera line art" in prompt
    assert "named artist" in prompt
    assert "recognizable characters, franchises, or logos" in prompt
    assert "celebrity likeness" in prompt
    assert "hand-painted" in prompt


def test_build_prompt_appends_correction_note_when_retrying():
    candidate = {"niche": "moon phase print"}

    prompt = generate.build_prompt(candidate, correction_note="composition was off-center")

    assert "moon phase" in prompt
    assert "Previous attempt was rejected for: composition was off-center" in prompt


def test_build_prompt_omits_correction_note_when_not_retrying():
    candidate = {"niche": "moon phase print"}

    prompt = generate.build_prompt(candidate)

    assert "Previous attempt was rejected" not in prompt


def test_build_prompt_forces_flat_full_bleed_2d_art_with_no_scene_words():
    candidate = {"niche": "monstera line art"}

    prompt = generate.build_prompt(candidate)

    for guardrail in ("flat 2d", "full-bleed", "fills the entire frame"):
        assert guardrail in prompt.lower()
    for banned in ("no frame", "no wall", "no room", "no mockup"):
        assert banned in prompt.lower()


def test_build_prompt_strips_scene_tokens_from_niche_before_injection():
    candidate = {"niche": "botanical minimalist wall art - holiday_peak"}

    prompt = generate.build_prompt(candidate)

    assert "wall art" not in prompt.lower()
    assert "holiday_peak" in prompt


def test_sanitize_niche_removes_known_scene_tokens():
    assert generate.sanitize_niche("mid-century botanical wall poster") == "mid-century botanical"
    assert generate.sanitize_niche("nature wall décor print") == "nature"
    assert generate.sanitize_niche("monstera line art") == "monstera line art"


def test_generate_for_candidate_calls_replicate_and_writes_image_back(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_pending_candidate(conn, niche="monstera line art")
    captured = {}

    def fake_generate_image(prompt, *, api_token=None):
        captured["prompt"] = prompt
        captured["api_token"] = api_token
        return {"image_url": "https://replicate.delivery/raw.png", "prediction_id": "pred123"}

    def fake_upscale_image(image_url, *, api_token=None):
        captured["upscale_input_url"] = image_url
        return {"image_url": "https://replicate.delivery/upscaled.png", "prediction_id": "pred-up1"}

    with patch("pipeline.generate.replicate_client.generate_image", side_effect=fake_generate_image), \
         patch("pipeline.generate.replicate_client.upscale_image", side_effect=fake_upscale_image):
        result = generate.generate_for_candidate(
            conn, candidate_id, api_token="test-token", now=datetime(2026, 7, 9, 10, 0, 0)
        )

    assert result == {
        "image_url": "https://replicate.delivery/upscaled.png",
        "prediction_id": "pred123",
        "upscale_prediction_id": "pred-up1",
    }
    assert "monstera line art" in captured["prompt"]
    assert captured["api_token"] == "test-token"
    assert captured["upscale_input_url"] == "https://replicate.delivery/raw.png"

    row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    assert row["base_image_url"] == "https://replicate.delivery/upscaled.png"
    assert row["base_replicate_prediction_id"] == "pred123"
    assert row["base_upscale_prediction_id"] == "pred-up1"
    assert row["status"] == "generating"
    assert row["updated_at"] == "2026-07-09T10:00:00"
    conn.close()


def test_generate_for_candidate_passes_correction_note_into_prompt(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_pending_candidate(conn, niche="moon phase print", status="generating")
    captured = {}

    def fake_generate_image(prompt, *, api_token=None):
        captured["prompt"] = prompt
        return {"image_url": "https://replicate.delivery/retry.png", "prediction_id": "pred456"}

    def fake_upscale_image(image_url, *, api_token=None):
        return {"image_url": "https://replicate.delivery/retry-upscaled.png", "prediction_id": "pred-up2"}

    with patch("pipeline.generate.replicate_client.generate_image", side_effect=fake_generate_image), \
         patch("pipeline.generate.replicate_client.upscale_image", side_effect=fake_upscale_image):
        generate.generate_for_candidate(
            conn, candidate_id, correction_note="composition was off-center",
            now=datetime(2026, 7, 9, 11, 0, 0),
        )

    assert "Previous attempt was rejected for: composition was off-center" in captured["prompt"]

    row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    assert row["base_image_url"] == "https://replicate.delivery/retry-upscaled.png"
    conn.close()


def test_generate_for_candidate_leaves_row_untouched_when_upscale_fails(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_pending_candidate(conn, niche="monstera line art", status="pending")

    def fake_generate_image(prompt, *, api_token=None):
        return {"image_url": "https://replicate.delivery/raw.png", "prediction_id": "pred-raw"}

    def fake_upscale_image(image_url, *, api_token=None):
        raise RuntimeError("Replicate upscale throttled")

    with patch("pipeline.generate.replicate_client.generate_image", side_effect=fake_generate_image), \
         patch("pipeline.generate.replicate_client.upscale_image", side_effect=fake_upscale_image):
        with pytest.raises(RuntimeError, match="Replicate upscale throttled"):
            generate.generate_for_candidate(conn, candidate_id, api_token="test-token")

    row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    assert row["status"] == "pending"
    assert row["base_image_url"] is None
    assert row["base_replicate_prediction_id"] is None
    assert row["base_upscale_prediction_id"] is None
    conn.close()


def test_generate_for_candidate_raises_on_unknown_candidate_id(tmp_path):
    conn = _fresh_conn(tmp_path)

    with pytest.raises(ValueError, match="999"):
        generate.generate_for_candidate(conn, 999)

    conn.close()


def test_run_generate_cycle_processes_all_pending_candidates_and_skips_others(tmp_path):
    conn = _fresh_conn(tmp_path)
    pending_id_1 = _insert_pending_candidate(conn, niche="monstera line art", status="pending")
    pending_id_2 = _insert_pending_candidate(conn, niche="moon phase print", status="pending")
    abandoned_id = _insert_pending_candidate(conn, niche="saturated term", status="abandoned")

    call_count = {"n": 0}

    def fake_generate_image(prompt, *, api_token=None):
        call_count["n"] += 1
        return {"image_url": f"https://replicate.delivery/out{call_count['n']}.png", "prediction_id": f"pred{call_count['n']}"}

    def fake_upscale_image(image_url, *, api_token=None):
        return {"image_url": image_url.replace("out", "upscaled"), "prediction_id": "pred-up"}

    with patch("pipeline.generate.replicate_client.generate_image", side_effect=fake_generate_image), \
         patch("pipeline.generate.replicate_client.upscale_image", side_effect=fake_upscale_image):
        processed_ids = generate.run_generate_cycle(conn, now=datetime(2026, 7, 9, 12, 0, 0))

    assert sorted(processed_ids) == sorted([pending_id_1, pending_id_2])
    assert call_count["n"] == 2

    row_1 = conn.execute("SELECT * FROM candidates WHERE id = ?", (pending_id_1,)).fetchone()
    row_2 = conn.execute("SELECT * FROM candidates WHERE id = ?", (pending_id_2,)).fetchone()
    abandoned_row = conn.execute("SELECT * FROM candidates WHERE id = ?", (abandoned_id,)).fetchone()

    assert row_1["status"] == "generating"
    assert row_1["base_image_url"] is not None
    assert row_2["status"] == "generating"
    assert row_2["base_image_url"] is not None
    assert abandoned_row["status"] == "abandoned"
    assert abandoned_row["base_image_url"] is None
    conn.close()


def test_run_generate_cycle_isolates_per_candidate_failures(tmp_path):
    conn = _fresh_conn(tmp_path)
    failing_id = _insert_pending_candidate(conn, niche="monstera line art", status="pending")
    succeeding_id = _insert_pending_candidate(conn, niche="moon phase print", status="pending")

    def fake_generate_image(prompt, *, api_token=None):
        if "monstera line art" in prompt:
            raise RuntimeError("Replicate throttled")
        return {"image_url": "https://replicate.delivery/out2.png", "prediction_id": "pred2"}

    def fake_upscale_image(image_url, *, api_token=None):
        return {"image_url": "https://replicate.delivery/upscaled2.png", "prediction_id": "pred-up2"}

    with patch("pipeline.generate.replicate_client.generate_image", side_effect=fake_generate_image), \
         patch("pipeline.generate.replicate_client.upscale_image", side_effect=fake_upscale_image):
        processed_ids = generate.run_generate_cycle(conn, now=datetime(2026, 7, 9, 12, 0, 0))

    assert processed_ids == [succeeding_id]

    failing_row = conn.execute("SELECT * FROM candidates WHERE id = ?", (failing_id,)).fetchone()
    succeeding_row = conn.execute("SELECT * FROM candidates WHERE id = ?", (succeeding_id,)).fetchone()

    assert failing_row["status"] == "pending"
    assert failing_row["base_image_url"] is None

    assert succeeding_row["status"] == "generating"
    assert succeeding_row["base_image_url"] == "https://replicate.delivery/upscaled2.png"
    conn.close()


def test_run_generate_cycle_returns_empty_list_when_no_pending_candidates(tmp_path):
    conn = _fresh_conn(tmp_path)
    _insert_pending_candidate(conn, niche="saturated term", status="abandoned")

    processed_ids = generate.run_generate_cycle(conn)

    assert processed_ids == []
    conn.close()
