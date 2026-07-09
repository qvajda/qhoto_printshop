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

    assert "moon phase print" in prompt
    assert "Previous attempt was rejected for: composition was off-center" in prompt


def test_build_prompt_omits_correction_note_when_not_retrying():
    candidate = {"niche": "moon phase print"}

    prompt = generate.build_prompt(candidate)

    assert "Previous attempt was rejected" not in prompt


def test_generate_for_candidate_calls_replicate_and_writes_image_back(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_pending_candidate(conn, niche="monstera line art")
    captured = {}

    def fake_generate_image(prompt, *, api_token=None):
        captured["prompt"] = prompt
        captured["api_token"] = api_token
        return {"image_url": "https://replicate.delivery/out.png", "prediction_id": "pred123"}

    with patch("pipeline.generate.replicate_client.generate_image", side_effect=fake_generate_image):
        result = generate.generate_for_candidate(
            conn, candidate_id, api_token="test-token", now=datetime(2026, 7, 9, 10, 0, 0)
        )

    assert result == {"image_url": "https://replicate.delivery/out.png", "prediction_id": "pred123"}
    assert "monstera line art" in captured["prompt"]
    assert captured["api_token"] == "test-token"

    row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    assert row["base_image_url"] == "https://replicate.delivery/out.png"
    assert row["base_replicate_prediction_id"] == "pred123"
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

    with patch("pipeline.generate.replicate_client.generate_image", side_effect=fake_generate_image):
        generate.generate_for_candidate(
            conn, candidate_id, correction_note="composition was off-center",
            now=datetime(2026, 7, 9, 11, 0, 0),
        )

    assert "Previous attempt was rejected for: composition was off-center" in captured["prompt"]

    row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    assert row["base_image_url"] == "https://replicate.delivery/retry.png"
    conn.close()


def test_generate_for_candidate_raises_on_unknown_candidate_id(tmp_path):
    conn = _fresh_conn(tmp_path)

    with pytest.raises(ValueError, match="999"):
        generate.generate_for_candidate(conn, 999)

    conn.close()
