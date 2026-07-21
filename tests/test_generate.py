from datetime import datetime
from unittest.mock import patch

import pytest

import pipeline.art_brief as art_brief
import pipeline.db as db
import pipeline.generate as generate


def _fresh_conn(tmp_path):
    conn = db.get_connection(tmp_path / "test.sqlite3")
    db.init_db(conn)
    return conn


def _insert_pending_candidate(conn, niche="monstera line art", *, status="pending", art_brief=None):
    timestamp = "2026-07-09T09:00:00"
    cursor = conn.execute(
        """
        INSERT INTO candidates (created_at, niche, go_hold_kill, status, updated_at, art_brief)
        VALUES (?, ?, 'go', ?, ?, ?)
        """,
        (timestamp, niche, status, timestamp, art_brief),
    )
    conn.commit()
    return cursor.lastrowid


def test_build_prompt_uses_art_brief_not_raw_niche():
    candidate = {"art_brief": "A dense mid-century modern botanical bouquet in bold filled shapes."}

    prompt = generate.build_prompt(candidate)

    assert "A dense mid-century modern botanical bouquet in bold filled shapes." in prompt


def test_build_prompt_appends_scaffold_after_brief():
    candidate = {"art_brief": "A dense mid-century modern botanical bouquet."}

    prompt = generate.build_prompt(candidate)

    assert prompt.startswith("A dense mid-century modern botanical bouquet.")
    assert prompt.endswith(generate.POSITIVE_SCAFFOLD)


def test_build_prompt_puts_correction_note_before_scaffold_tail_not_last():
    candidate = {"art_brief": "A dense mid-century modern botanical bouquet."}

    prompt = generate.build_prompt(candidate, correction_note="composition was off-center")

    assert "Previous attempt was rejected for: composition was off-center" in prompt
    # S4-c(2): correction note must sit BEFORE the scaffold tail, not appended
    # last - if truncation ever hits schnell's 256-token cap, the short
    # scaffold (redundant with the brief) should be what's at risk, not the
    # critic's actionable retry feedback.
    assert prompt.endswith(generate.POSITIVE_SCAFFOLD)
    assert prompt.index("Previous attempt was rejected") < prompt.index(generate.POSITIVE_SCAFFOLD)


def test_build_prompt_omits_correction_note_when_not_retrying():
    candidate = {"art_brief": "A dense mid-century modern botanical bouquet."}

    prompt = generate.build_prompt(candidate)

    assert "Previous attempt was rejected" not in prompt


def test_build_prompt_scaffold_is_positive_only_flat_2d_full_bleed():
    candidate = {"art_brief": "A dense mid-century modern botanical bouquet."}

    prompt = generate.build_prompt(candidate).lower()

    for guardrail in (
        "flat 2d full-bleed", "coherent centered subject", "dense composition filling the frame",
        "bold filled color zones", "crisp clean edges", "warm muted palette", "soft cream ground",
    ):
        assert guardrail in prompt


def test_positive_scaffold_has_no_negation_no_go_language():
    # S4-c(1): the no-go list moved entirely into art_brief.py's brief-writing
    # instructions - FLUX has no negative-prompt channel, so the image prompt
    # scaffold must carry no "no X" / "Do not" clauses at all (its two
    # remaining negatives - "no smudging", "no text or watermarks" - are
    # allowed exceptions per the plan's own scaffold vocabulary, everything
    # else must be positive).
    assert "named artist" not in generate.POSITIVE_SCAFFOLD.lower()
    assert "do not" not in generate.POSITIVE_SCAFFOLD.lower()
    assert "no frame" not in generate.POSITIVE_SCAFFOLD.lower()
    assert "no wall" not in generate.POSITIVE_SCAFFOLD.lower()
    assert "no room" not in generate.POSITIVE_SCAFFOLD.lower()
    assert "no mockup" not in generate.POSITIVE_SCAFFOLD.lower()


def test_positive_scaffold_is_roughly_40_words():
    word_count = len(generate.POSITIVE_SCAFFOLD.split())
    assert 25 <= word_count <= 45


# S4-c(2): build-time token budget check. Real google/t5-v1_1-xxl tokenizer
# counts (measured offline, not a test dependency - see generate.py's
# T5_TOKEN_WORD_RATIO comment) on this exact worst-case fixture: 60-word
# brief -> 99 tokens, 48-word correction note -> 66 tokens, 39-word scaffold
# -> 63 tokens, full combined prompt -> 226 real T5 tokens - under schnell's
# 256-token cap, confirming the old design's ~336-token overflow (RC-C) is
# fixed by this rework, not just moved around.
_WORST_CASE_BRIEF = (
    "A mid-century modern botanical illustration of a dense monstera and fiddle-leaf fig "
    "arrangement, rendered as bold filled color shapes with confident medium-weight outlines, "
    "in a dense full-frame composition filling the frame edge to edge, set against a warm "
    "cream textured ground with a muted terracotta circular backdrop, using sage, olive, "
    "terracotta, and dusty pink as accent colors throughout the piece."
)
_WORST_CASE_CORRECTION_NOTE = (
    "subject was off-center and crammed into the bottom-left corner, with roughly ninety "
    "percent of the frame left as empty dead space and no clear focal point, plus a second "
    "smaller malformed shape overlapping the main subject"
)


def test_build_prompt_stays_within_t5_token_budget_worst_case():
    candidate = {"art_brief": _WORST_CASE_BRIEF}

    prompt = generate.build_prompt(candidate, correction_note=_WORST_CASE_CORRECTION_NOTE)

    assert generate.approx_t5_tokens(prompt) <= 240


def _fake_persist_base_artwork(candidate_id, raw_bytes):
    return {
        "durable_url": f"https://durable.example/{candidate_id}.png",
        "local_path": f"/fake/db/base_artwork/{candidate_id}.png",
        "sha256": "fakesha256hash",
    }


def test_generate_for_candidate_computes_and_persists_art_brief_once(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_pending_candidate(conn, niche="monstera line art")
    captured = {}

    def fake_generate_art_brief(candidate, *, api_key=None):
        captured["art_brief_candidate"] = candidate
        return "A dense mid-century modern botanical bouquet."

    def fake_generate_image(prompt, *, api_token=None):
        captured["prompt"] = prompt
        return {"image_url": "https://replicate.delivery/raw.png", "prediction_id": "pred123"}

    def fake_upscale_image(image_url, *, api_token=None):
        return {"image_url": "https://replicate.delivery/upscaled.png", "prediction_id": "pred-up1"}

    with patch("pipeline.generate.art_brief.generate_art_brief", side_effect=fake_generate_art_brief), \
         patch("pipeline.generate.replicate_client.generate_image", side_effect=fake_generate_image), \
         patch("pipeline.generate.replicate_client.upscale_image", side_effect=fake_upscale_image), \
         patch("pipeline.generate.http.fetch_bytes", return_value=b"fake-image-bytes"), \
         patch("pipeline.generate.artwork_store.persist_base_artwork", side_effect=_fake_persist_base_artwork):
        generate.generate_for_candidate(
            conn, candidate_id, api_token="test-token", now=datetime(2026, 7, 9, 10, 0, 0)
        )

    assert captured["art_brief_candidate"]["niche"] == "monstera line art"
    assert "A dense mid-century modern botanical bouquet." in captured["prompt"]

    row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    assert row["art_brief"] == "A dense mid-century modern botanical bouquet."
    conn.close()


def test_generate_for_candidate_reuses_stored_art_brief_without_recalling_anthropic(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_pending_candidate(
        conn, niche="monstera line art", status="generating",
        art_brief="An already-computed stored brief.",
    )
    captured = {}

    def fake_generate_image(prompt, *, api_token=None):
        captured["prompt"] = prompt
        return {"image_url": "https://replicate.delivery/retry.png", "prediction_id": "pred456"}

    def fake_upscale_image(image_url, *, api_token=None):
        return {"image_url": "https://replicate.delivery/retry-upscaled.png", "prediction_id": "pred-up2"}

    with patch("pipeline.generate.art_brief.generate_art_brief") as mock_brief, \
         patch("pipeline.generate.replicate_client.generate_image", side_effect=fake_generate_image), \
         patch("pipeline.generate.replicate_client.upscale_image", side_effect=fake_upscale_image), \
         patch("pipeline.generate.http.fetch_bytes", return_value=b"fake-image-bytes"), \
         patch("pipeline.generate.artwork_store.persist_base_artwork", side_effect=_fake_persist_base_artwork):
        generate.generate_for_candidate(
            conn, candidate_id, correction_note="composition was off-center",
            now=datetime(2026, 7, 9, 11, 0, 0),
        )

    mock_brief.assert_not_called()
    assert "An already-computed stored brief." in captured["prompt"]
    assert "Previous attempt was rejected for: composition was off-center" in captured["prompt"]

    row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    assert row["art_brief"] == "An already-computed stored brief."
    conn.close()


def test_generate_for_candidate_no_upscale_skips_esrgan_and_persists_raw_flux_output(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_pending_candidate(conn, niche="monstera line art")

    def fake_generate_art_brief(candidate, *, api_key=None):
        return "A dense mid-century modern botanical bouquet."

    def fake_generate_image(prompt, *, api_token=None):
        return {"image_url": "https://replicate.delivery/raw.png", "prediction_id": "pred123"}

    with patch("pipeline.generate.art_brief.generate_art_brief", side_effect=fake_generate_art_brief), \
         patch("pipeline.generate.replicate_client.generate_image", side_effect=fake_generate_image), \
         patch("pipeline.generate.replicate_client.upscale_image") as mock_upscale, \
         patch("pipeline.generate.http.fetch_bytes", return_value=b"fake-image-bytes") as mock_fetch, \
         patch("pipeline.generate.artwork_store.persist_base_artwork", side_effect=_fake_persist_base_artwork):
        result = generate.generate_for_candidate(
            conn, candidate_id, api_token="test-token",
            now=datetime(2026, 7, 9, 10, 0, 0), no_upscale=True,
        )

    mock_upscale.assert_not_called()
    mock_fetch.assert_called_once_with("https://replicate.delivery/raw.png")
    assert result["upscale_prediction_id"] is None

    row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    assert row["base_upscale_prediction_id"] is None
    assert row["base_replicate_delivery_url"] == "https://replicate.delivery/raw.png"
    assert row["base_replicate_prediction_id"] == "pred123"
    conn.close()


def test_generate_for_candidate_leaves_row_untouched_when_upscale_fails(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_pending_candidate(conn, niche="monstera line art", status="pending")

    def fake_generate_art_brief(candidate, *, api_key=None):
        return "A dense mid-century modern botanical bouquet."

    def fake_generate_image(prompt, *, api_token=None):
        return {"image_url": "https://replicate.delivery/raw.png", "prediction_id": "pred-raw"}

    def fake_upscale_image(image_url, *, api_token=None):
        raise RuntimeError("Replicate upscale throttled")

    with patch("pipeline.generate.art_brief.generate_art_brief", side_effect=fake_generate_art_brief), \
         patch("pipeline.generate.replicate_client.generate_image", side_effect=fake_generate_image), \
         patch("pipeline.generate.replicate_client.upscale_image", side_effect=fake_upscale_image):
        with pytest.raises(RuntimeError, match="Replicate upscale throttled"):
            generate.generate_for_candidate(conn, candidate_id, api_token="test-token")

    row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    # art_brief is computed+persisted independently of the base-image write -
    # it's the same visual concept either way, so it's fine (and desirable)
    # for a retry to reuse it rather than re-calling Anthropic.
    assert row["art_brief"] == "A dense mid-century modern botanical bouquet."
    assert row["status"] == "pending"
    assert row["base_image_url"] is None
    assert row["base_image_local_path"] is None
    assert row["base_image_sha256"] is None
    assert row["base_replicate_delivery_url"] is None
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
    captured_siblings = []

    def fake_generate_art_brief(candidate, *, api_key=None, sibling_briefs=None):
        captured_siblings.append(list(sibling_briefs) if sibling_briefs else [])
        return f"A dense brief for {candidate['niche']}."

    def fake_generate_image(prompt, *, api_token=None):
        call_count["n"] += 1
        return {"image_url": f"https://replicate.delivery/out{call_count['n']}.png", "prediction_id": f"pred{call_count['n']}"}

    def fake_upscale_image(image_url, *, api_token=None):
        return {"image_url": image_url.replace("out", "upscaled"), "prediction_id": "pred-up"}

    with patch("pipeline.generate.art_brief.generate_art_brief", side_effect=fake_generate_art_brief), \
         patch("pipeline.generate.replicate_client.generate_image", side_effect=fake_generate_image), \
         patch("pipeline.generate.replicate_client.upscale_image", side_effect=fake_upscale_image), \
         patch("pipeline.generate.http.fetch_bytes", return_value=b"fake-image-bytes"), \
         patch("pipeline.generate.artwork_store.persist_base_artwork", side_effect=_fake_persist_base_artwork):
        processed_ids = generate.run_generate_cycle(
            conn, now=datetime(2026, 7, 9, 12, 0, 0), sleep_fn=lambda seconds: None
        )

    assert sorted(processed_ids) == sorted([pending_id_1, pending_id_2])
    assert call_count["n"] == 2
    # FM-5 sibling-diversity plumbing: first candidate sees no siblings, second sees
    # the first candidate's brief.
    assert captured_siblings[0] == []
    assert len(captured_siblings[1]) == 1

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

    def fake_generate_art_brief(candidate, *, api_key=None, sibling_briefs=None):
        return f"A dense brief for {candidate['niche']}."

    def fake_generate_image(prompt, *, api_token=None):
        if "monstera line art" in prompt:
            raise RuntimeError("Replicate throttled")
        return {"image_url": "https://replicate.delivery/out2.png", "prediction_id": "pred2"}

    def fake_upscale_image(image_url, *, api_token=None):
        return {"image_url": "https://replicate.delivery/upscaled2.png", "prediction_id": "pred-up2"}

    with patch("pipeline.generate.art_brief.generate_art_brief", side_effect=fake_generate_art_brief), \
         patch("pipeline.generate.replicate_client.generate_image", side_effect=fake_generate_image), \
         patch("pipeline.generate.replicate_client.upscale_image", side_effect=fake_upscale_image), \
         patch("pipeline.generate.http.fetch_bytes", return_value=b"fake-image-bytes"), \
         patch("pipeline.generate.artwork_store.persist_base_artwork", side_effect=_fake_persist_base_artwork):
        processed_ids = generate.run_generate_cycle(
            conn, now=datetime(2026, 7, 9, 12, 0, 0), sleep_fn=lambda seconds: None
        )

    assert processed_ids == [succeeding_id]

    failing_row = conn.execute("SELECT * FROM candidates WHERE id = ?", (failing_id,)).fetchone()
    succeeding_row = conn.execute("SELECT * FROM candidates WHERE id = ?", (succeeding_id,)).fetchone()

    assert failing_row["status"] == "pending"
    assert failing_row["base_image_url"] is None

    assert succeeding_row["status"] == "generating"
    assert succeeding_row["base_image_url"] == f"https://durable.example/{succeeding_id}.png"
    conn.close()


def test_run_generate_cycle_returns_empty_list_when_no_pending_candidates(tmp_path):
    conn = _fresh_conn(tmp_path)
    _insert_pending_candidate(conn, niche="saturated term", status="abandoned")

    processed_ids = generate.run_generate_cycle(conn, sleep_fn=lambda seconds: None)

    assert processed_ids == []
    conn.close()


# R2-c (docs/2026-07-21-generation-quality-round2-plan.md): provenance write path.
def test_generate_for_candidate_records_generation_attempt_on_success(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_pending_candidate(
        conn, niche="monstera line art", art_brief="An already-computed stored brief."
    )

    def fake_generate_image(prompt, *, api_token=None):
        return {"image_url": "https://replicate.delivery/raw.png", "prediction_id": "pred-attempt-1"}

    def fake_upscale_image(image_url, *, api_token=None):
        return {"image_url": "https://replicate.delivery/upscaled.png", "prediction_id": "pred-up1"}

    with patch("pipeline.generate.replicate_client.generate_image", side_effect=fake_generate_image), \
         patch("pipeline.generate.replicate_client.upscale_image", side_effect=fake_upscale_image), \
         patch("pipeline.generate.http.fetch_bytes", return_value=b"fake-image-bytes"), \
         patch("pipeline.generate.artwork_store.persist_base_artwork", side_effect=_fake_persist_base_artwork):
        generate.generate_for_candidate(
            conn, candidate_id, api_token="test-token", now=datetime(2026, 7, 21, 10, 0, 0),
        )

    row = conn.execute(
        "SELECT * FROM generation_attempts WHERE candidate_id = ?", (candidate_id,)
    ).fetchone()
    assert row["attempt_number"] == 1
    assert "An already-computed stored brief." in row["prompt_text"]
    assert row["art_brief_snapshot"] == "An already-computed stored brief."
    assert row["correction_note"] is None
    assert row["brief_template_version"] == art_brief.BRIEF_TEMPLATE_VERSION
    assert row["scaffold_version"] == generate.SCAFFOLD_VERSION
    assert row["model"] == "black-forest-labs/flux-schnell"
    assert row["prediction_id"] == "pred-attempt-1"
    conn.close()


def test_generate_for_candidate_records_generation_attempt_with_correction_note_on_retry(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_pending_candidate(
        conn, niche="monstera line art", status="generating", art_brief="Stored brief."
    )
    # Simulate a prior attempt already logged (first critic-pass regeneration).
    conn.execute(
        """
        INSERT INTO generation_attempts (
            candidate_id, attempt_number, prompt_text, art_brief_snapshot, correction_note,
            brief_template_version, scaffold_version, model, prediction_id, created_at
        ) VALUES (?, 1, 'prior prompt', 'Stored brief.', NULL, 'v1', 'v1', 'black-forest-labs/flux-schnell',
                  'pred-prior', '2026-07-21T09:00:00')
        """,
        (candidate_id,),
    )
    conn.commit()

    def fake_generate_image(prompt, *, api_token=None):
        return {"image_url": "https://replicate.delivery/retry.png", "prediction_id": "pred-attempt-2"}

    def fake_upscale_image(image_url, *, api_token=None):
        return {"image_url": "https://replicate.delivery/upscaled2.png", "prediction_id": "pred-up2"}

    with patch("pipeline.generate.replicate_client.generate_image", side_effect=fake_generate_image), \
         patch("pipeline.generate.replicate_client.upscale_image", side_effect=fake_upscale_image), \
         patch("pipeline.generate.http.fetch_bytes", return_value=b"fake-image-bytes"), \
         patch("pipeline.generate.artwork_store.persist_base_artwork", side_effect=_fake_persist_base_artwork):
        generate.generate_for_candidate(
            conn, candidate_id, correction_note="composition was off-center",
            now=datetime(2026, 7, 21, 11, 0, 0),
        )

    rows = conn.execute(
        "SELECT * FROM generation_attempts WHERE candidate_id = ? ORDER BY attempt_number", (candidate_id,)
    ).fetchall()
    assert len(rows) == 2
    assert rows[1]["attempt_number"] == 2
    assert rows[1]["correction_note"] == "composition was off-center"
    assert rows[1]["prediction_id"] == "pred-attempt-2"
    conn.close()


def test_generate_for_candidate_records_failed_attempt_with_null_prediction_id(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_pending_candidate(
        conn, niche="monstera line art", art_brief="Stored brief."
    )

    def fake_generate_image(prompt, *, api_token=None):
        raise RuntimeError("Replicate throttled")

    with patch("pipeline.generate.replicate_client.generate_image", side_effect=fake_generate_image):
        with pytest.raises(RuntimeError, match="Replicate throttled"):
            generate.generate_for_candidate(conn, candidate_id, now=datetime(2026, 7, 21, 12, 0, 0))

    row = conn.execute(
        "SELECT * FROM generation_attempts WHERE candidate_id = ?", (candidate_id,)
    ).fetchone()
    assert row is not None
    assert row["prediction_id"] is None
    conn.close()


# R2-d: inter-call pacing between candidates in a batch.
def test_run_generate_cycle_paces_between_candidates_not_before_the_first(tmp_path):
    conn = _fresh_conn(tmp_path)
    id_1 = _insert_pending_candidate(conn, niche="monstera line art", status="pending")
    id_2 = _insert_pending_candidate(conn, niche="moon phase print", status="pending")
    id_3 = _insert_pending_candidate(conn, niche="desert mesa", status="pending")
    sleep_calls = []

    def fake_generate_image(prompt, *, api_token=None):
        return {"image_url": "https://replicate.delivery/out.png", "prediction_id": "pred-x"}

    def fake_upscale_image(image_url, *, api_token=None):
        return {"image_url": "https://replicate.delivery/upscaled.png", "prediction_id": "pred-up-x"}

    def fake_generate_art_brief(candidate, *, api_key=None):
        return f"A dense brief for {candidate['niche']}."

    with patch("pipeline.generate.art_brief.generate_art_brief", side_effect=fake_generate_art_brief), \
         patch("pipeline.generate.replicate_client.generate_image", side_effect=fake_generate_image), \
         patch("pipeline.generate.replicate_client.upscale_image", side_effect=fake_upscale_image), \
         patch("pipeline.generate.http.fetch_bytes", return_value=b"fake-image-bytes"), \
         patch("pipeline.generate.artwork_store.persist_base_artwork", side_effect=_fake_persist_base_artwork):
        processed_ids = generate.run_generate_cycle(
            conn, now=datetime(2026, 7, 21, 12, 0, 0), sleep_fn=sleep_calls.append
        )

    assert sorted(processed_ids) == sorted([id_1, id_2, id_3])
    # 3 candidates -> 2 inter-call gaps, none before the first call.
    assert sleep_calls == [generate.DEFAULT_GENERATE_CYCLE_PACING_SECONDS] * 2
    conn.close()


def test_generate_cycle_pacing_seconds_reads_env_override(monkeypatch):
    monkeypatch.setenv("GENERATE_CYCLE_PACING_SECONDS", "5")
    assert generate._generate_cycle_pacing_seconds() == 5.0
    monkeypatch.delenv("GENERATE_CYCLE_PACING_SECONDS")
    assert generate._generate_cycle_pacing_seconds() == generate.DEFAULT_GENERATE_CYCLE_PACING_SECONDS
