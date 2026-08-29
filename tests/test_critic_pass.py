import json as _json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

import pipeline.critic_pass as critic_pass
import pipeline.db as db
import pipeline.http as http
import pipeline.replicate_client as replicate_client

# GL-10c: generate_draft_text now requires exactly 3 paragraphs, 80-110 words, no
# size wording - see compliance_draft.check_prose_shape.
_VALID_DESCRIPTION_PROSE = (
    "Bring a calm botanical moment into your space with this sage green monstera line "
    "art print, drawn in a minimalist herbarium style that keeps every leaf vein crisp "
    "and quietly detailed.\n\n"
    "It suits a modern, plant-filled interior built around warm neutral tones, natural "
    "textures, and simple, uncluttered furniture that lets the print do the talking.\n\n"
    "This print looks equally at home above a bed in a calm bedroom, along a hallway "
    "wall, or tucked into a quiet reading nook, adding a soft natural accent wherever "
    "it hangs."
)


# Compliant against compliance_draft.validate_draft_formula (#208): 4 comma clauses,
# 12 words, no repeated word >2x, no banned title term; 13 unique tags <=20 chars.
_DRAFT_TITLE = (
    "Monstera Line Art Print, Botanical Wall Decor, "
    "Bedroom Poster, Modern Green Foliage"
)
_DRAFT_TAGS = [
    "monstera print", "botanical wall art", "line art poster", "green plant print",
    "bedroom wall decor", "living room art", "modern home decor", "leaf wall art",
    "tropical plant art", "minimalist poster", "nature wall print", "foliage artwork",
    "plant lover gift",
]


class _VisionDispatch:
    """GL-68: the drafter now sends the artwork too, so compliance_draft and critic_pass
    both call anthropic_client.complete_with_images - and since they import the SAME
    module object, patching it 'in compliance_draft' patches it in critic_pass as well.
    One fake, routed on the prompt, with the critic calls counted separately."""

    def __init__(self, draft_response, critic_responses):
        self.draft_response = draft_response
        self._critic = critic_responses
        self.critic_call_count = 0
        self.draft_call_count = 0

    # Only these two prompts are critic verdicts (tier 2 master sanity, tier 3 rubric).
    # Everything else on this seam is a drafting-side call - the listing draft, and
    # generate.py's art-brief call, which shares the module attribute.
    _CRITIC_PROMPTS = ("You are the compliance and quality critic",
                       "You are a cheap, narrow pre-filter")

    def __call__(self, prompt, image_urls=None, *args, **kwargs):
        if not prompt.startswith(self._CRITIC_PROMPTS):
            self.draft_call_count += 1
            return self.draft_response
        self.critic_call_count += 1
        return next(self._critic) if hasattr(self._critic, "__next__") else self._critic


def test_build_critic_prompt_includes_rubric_and_listing_text():
    listing_text = {
        "title": "Monstera Line Art Botanical Print",
        "description": "A minimalist botanical print.",
    }

    prompt = critic_pass.build_critic_prompt(listing_text, 3)

    assert "Monstera Line Art Botanical Print" in prompt
    assert "A minimalist botanical print." in prompt
    assert "named artist's style" in prompt
    assert "3 gallery images" in prompt
    # S4-d per-criterion verdict shape.
    assert "criterion_1" in prompt
    assert "criterion_7" in prompt
    assert "good" in prompt and "refine" in prompt and "reject" in prompt
    # H5 rubric extension: subject/coherence/composition/detail/density criteria.
    assert "near-empty" in prompt
    assert "coherence" in prompt.lower()
    assert "off-center or cut-off" in prompt
    assert "smudging" in prompt
    assert "sparse" in prompt
    # R2-b: criterion 4 names the two new round-2 defect classes.
    assert "floats unintegrated in leftover negative space" in prompt
    assert "no focal occupant" in prompt
    # R2-b: criterion 7 gains a brief-vs-image adherence check.
    assert "brief adherence" in prompt
    # R3-b (FM-7/9): criterion 3 names anatomical incompleteness + smudge-merging.
    assert "anatomically incomplete" in prompt
    assert "smudges/merges into a neighboring element" in prompt
    # R3-b (FM-7/8/9): criterion 4 names the three round-3 defect classes.
    assert "no physical contact or integration" in prompt
    assert "literal drawn containment geometry" in prompt
    assert "unintended one-sided blank band" in prompt
    # R3-b (FM-13): criterion 6's text itself carries the owner's sparse-gate ruling.
    assert "legitimate, deliberate style" in prompt
    assert "the subject itself is small" in prompt


def _verdict_response(overall="good", failing=None):
    """Builds a fake Anthropic critic response in the S4-d per-criterion shape.
    failing is an optional {criterion_number: note} dict; all other criteria pass.
    Also carries the flat legacy {passed, reason} keys (ignored by the per-criterion
    parser, consumed by the tier-2 master-image sanity parser) so ONE fixture works as
    the mocked complete_with_images return value regardless of which tier calls it -
    tests that care which tier ran assert on call_count/prompts, not response shape."""
    failing = failing or {}
    payload = {}
    for i in range(1, 8):
        key = f"criterion_{i}"
        if i in failing:
            payload[key] = {"passed": False, "note": failing[i]}
        else:
            payload[key] = {"passed": True, "note": "ok"}
    payload["overall"] = overall
    notes = [v["note"] for v in payload.values() if isinstance(v, dict) and not v["passed"]]
    payload["passed"] = overall != "reject"
    payload["reason"] = "; ".join(notes) if notes else "meets rubric"
    return {"text": _json.dumps(payload)}


def _fresh_conn(tmp_path):
    conn = db.get_connection(tmp_path / "test.sqlite3")
    db.init_db(conn)
    return conn


def _insert_candidate(conn, niche="monstera line art", *, status="generating",
                       base_image_url="https://replicate.delivery/out.png"):
    timestamp = "2026-07-10T11:00:00"
    cursor = conn.execute(
        """
        INSERT INTO candidates (created_at, niche, go_hold_kill, status, base_image_url, updated_at)
        VALUES (?, ?, 'go', ?, ?, ?)
        """,
        (timestamp, niche, status, base_image_url, timestamp),
    )
    conn.commit()
    return cursor.lastrowid


def _insert_primary_gallery(conn, candidate_id,
                             image_urls=("https://gelato/flat.jpg", "https://gelato/life.jpg"),
                             *, gelato_product_id="gelato_prod_1", group_product_status="created"):
    timestamp = "2026-07-10T11:05:00"
    group_cursor = conn.execute(
        "INSERT INTO groups (candidate_id, group_type, status, created_at, updated_at) "
        "VALUES (?, 'primary', 'pending_review', ?, ?)",
        (candidate_id, timestamp, timestamp),
    )
    group_id = group_cursor.lastrowid
    gp_cursor = conn.execute(
        "INSERT INTO group_products "
        "(candidate_id, group_id, gelato_template_id, gelato_product_id, "
        "status, created_at, updated_at) "
        "VALUES (?, ?, 'tpl_1', ?, ?, ?, ?)",
        (candidate_id, group_id, gelato_product_id, group_product_status, timestamp, timestamp),
    )
    group_product_id = gp_cursor.lastrowid
    conn.execute(
        "INSERT INTO group_product_variants "
        "(group_product_id, group_id, size, orientation, gelato_template_variant_id, price_eur, created_at) "
        "VALUES (?, ?, '8x12', 'portrait', 'variant_8x12', 24, ?)",
        (group_product_id, group_id, timestamp),
    )
    for order, image_url in enumerate(image_urls):
        image_type = "flat_mockup" if order == 0 else "lifestyle"
        conn.execute(
            "INSERT INTO product_images (group_product_id, group_id, image_url, alt_text, gallery_order, image_type) "
            "VALUES (?, ?, ?, 'placeholder alt', ?, ?)",
            (group_product_id, group_id, image_url, order, image_type),
        )
    conn.commit()
    return group_id, group_product_id


def _insert_listing_text(conn, candidate_id, niche="monstera line art"):
    timestamp = "2026-07-10T11:10:00"
    conn.execute(
        """
        INSERT INTO listing_texts (
            candidate_id, title, tags, description, disclosure_text,
            who_made, production_partner_ids, taxonomy_id, shipping_profile_id, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            candidate_id, f"{niche} print", _json.dumps(["botanical", "wall art"]),
            f"A print of {niche}.", "disclosure text",
            "i_did", _json.dumps([5717252]), "1027", "", timestamp,
        ),
    )
    conn.commit()


def _insert_ready_candidate(conn, niche="monstera line art"):
    candidate_id = _insert_candidate(conn, niche=niche)
    _insert_primary_gallery(conn, candidate_id)
    _insert_listing_text(conn, candidate_id, niche=niche)
    return candidate_id


def test_get_primary_group_state_returns_gallery_and_listing_text(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_ready_candidate(conn, niche="monstera line art")

    state = critic_pass.get_primary_group_state(conn, candidate_id)

    assert state["image_urls"] == ["https://gelato/flat.jpg", "https://gelato/life.jpg"]
    assert state["listing_text"]["title"] == "monstera line art print"
    assert state["listing_text"]["description"] == "A print of monstera line art."
    conn.close()


def test_get_primary_group_state_raises_when_no_primary_group(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)

    with pytest.raises(ValueError, match="primary group"):
        critic_pass.get_primary_group_state(conn, candidate_id)
    conn.close()


def test_get_primary_group_state_raises_when_no_listing_text(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    _insert_primary_gallery(conn, candidate_id)

    with pytest.raises(ValueError, match="listing_texts"):
        critic_pass.get_primary_group_state(conn, candidate_id)
    conn.close()


def test_evaluate_critic_pass_returns_parsed_result():
    listing_text = {"title": "Monstera Line Art Botanical Print", "description": "A minimalist botanical print."}
    fake_response = _verdict_response("good")

    with patch("pipeline.critic_pass.anthropic_client.complete_with_images",
               return_value=fake_response) as mock_call:
        result = critic_pass.evaluate_critic_pass(
            ["https://gelato/a.jpg", "https://gelato/b.jpg"], listing_text, api_key="key1"
        )

    mock_call.assert_called_once()
    called_prompt, called_images = mock_call.call_args.args
    assert "Monstera Line Art Botanical Print" in called_prompt
    assert called_images == ["https://gelato/a.jpg", "https://gelato/b.jpg"]
    assert mock_call.call_args.kwargs["api_key"] == "key1"
    assert result["passed"] is True
    assert result["reason"] == "meets rubric"
    assert result["overall"] == "good"
    assert set(result["criteria"]) == set(critic_pass.CRITERION_KEYS)


def test_evaluate_critic_pass_raises_on_missing_key():
    listing_text = {"title": "A title", "description": "A description."}
    fake_response = {"text": _json.dumps({"criterion_1": {"passed": True, "note": "ok"}})}

    with patch("pipeline.critic_pass.anthropic_client.complete_with_images", return_value=fake_response):
        with pytest.raises(ValueError, match="missing required key"):
            critic_pass.evaluate_critic_pass(["https://gelato/a.jpg"], listing_text, api_key="key1")


def test_evaluate_critic_pass_raises_on_invalid_overall():
    listing_text = {"title": "A title", "description": "A description."}
    payload = {f"criterion_{i}": {"passed": True, "note": "ok"} for i in range(1, 8)}
    payload["overall"] = "maybe"
    fake_response = {"text": _json.dumps(payload)}

    with patch("pipeline.critic_pass.anthropic_client.complete_with_images", return_value=fake_response):
        with pytest.raises(ValueError, match="overall"):
            critic_pass.evaluate_critic_pass(["https://gelato/a.jpg"], listing_text, api_key="key1")


# --- H5 local near-empty gate ---

def _save_png(tmp_path, name, image):
    p = tmp_path / name
    image.save(p, format="PNG")
    return str(p)


def test_check_local_image_sanity_fails_near_empty_image(tmp_path):
    from PIL import Image
    # Near-uniform cream fill (like run-#1 masters 2 & 6): low variance, no edges.
    path = _save_png(tmp_path, "empty.png", Image.new("RGB", (600, 900), (238, 232, 210)))

    result = critic_pass.check_local_image_sanity(path)

    assert result is not None
    assert result["passed"] is False
    assert "near-empty image" in result["reason"]


def test_check_local_image_sanity_passes_structured_image(tmp_path):
    from PIL import Image, ImageDraw
    # A structured image with real edges and variance (a normal botanical print stand-in).
    img = Image.new("RGB", (600, 900), (240, 235, 215))
    draw = ImageDraw.Draw(img)
    for i in range(0, 600, 40):
        draw.line([(i, 0), (i, 900)], fill=(30, 60, 40), width=6)
        draw.ellipse([i, i, i + 120, i + 200], outline=(20, 40, 30), width=8)

    result = critic_pass.check_local_image_sanity(_save_png(tmp_path, "art.png", img))

    assert result is None  # inconclusive locally -> defer to vision critic (i.e. not blocked)


def test_check_local_image_sanity_returns_none_for_missing_or_null_path(tmp_path):
    assert critic_pass.check_local_image_sanity(None) is None
    assert critic_pass.check_local_image_sanity(str(tmp_path / "does-not-exist.png")) is None


# --- S4-d calibration set: must-FAIL {4} / must-PASS {1,2,5} / borderline {3} ---
# (docs/2026-07-20-s4a-failure-taxonomy.md) - run against the real current masters,
# not synthetic stand-ins, so a threshold regression here is a real regression.
# 6.png/7.png were the original must-FAIL masters for this set but got overwritten
# locally with no backup - retired from the parametrize since there's nothing left
# to calibrate against.

_BASE_ARTWORK_DIR = Path(__file__).resolve().parent.parent / "db" / "base_artwork"


@pytest.mark.parametrize("n", [1, 2, 5])
def test_calibration_set_must_pass_clears_local_gate_clean(n):
    path = _BASE_ARTWORK_DIR / f"{n}.png"
    if not path.exists():
        pytest.skip(f"{path} not present in this checkout")
    stats = critic_pass.compute_image_sanity_stats(path)
    assert critic_pass.check_local_image_sanity(path) is None
    assert critic_pass.local_sanity_flag_note(stats) is None


@pytest.mark.parametrize("n", [4])
def test_calibration_set_must_fail_hard_fails_local_gate(n):
    path = _BASE_ARTWORK_DIR / f"{n}.png"
    if not path.exists():
        pytest.skip(f"{path} not present in this checkout")
    result = critic_pass.check_local_image_sanity(path)
    assert result is not None
    assert result["passed"] is False


def test_calibration_set_borderline_is_flagged_not_hard_failed():
    path = _BASE_ARTWORK_DIR / "3.png"
    if not path.exists():
        pytest.skip(f"{path} not present in this checkout")
    stats = critic_pass.compute_image_sanity_stats(path)
    assert critic_pass.check_local_image_sanity(path) is None  # not hard-failed
    assert critic_pass.local_sanity_flag_note(stats) is not None  # but flagged


# --- R3-b FM-13 fix: subject-extent stat + sparse-gate rework ---
# Owner ruling: one large dominant subject with generous empty space is a legitimate
# style and must PASS; the defect is a mostly-empty frame where the subject itself is
# ALSO small. Candidates 12 (round-2 fan-in's headline finding) and 22 (round-3) are the
# key sparse anchors: both measure low cov but a large subject_extent, and must clear the
# gate unflagged (not merely non-hard-failed - unflagged, so the vision critic never sees
# an alarming note steering it toward rejecting a legitimate sparse design).

@pytest.mark.parametrize("n", [12, 22])
def test_sparse_anchor_candidates_skip_the_flag_entirely(n):
    path = _BASE_ARTWORK_DIR / f"{n}.png"
    if not path.exists():
        pytest.skip(f"{path} not present in this checkout")
    stats = critic_pass.compute_image_sanity_stats(path)
    assert stats["cov"] < critic_pass.SANITY_COV_FLAG_CEILING  # low cov, as FM-13 requires
    assert stats["subject_extent"] >= critic_pass.SANITY_SUBJECT_EXTENT_SMALL  # but a big subject
    assert critic_pass.check_local_image_sanity(path) is None  # not hard-failed
    assert critic_pass.local_sanity_flag_note(stats) is None  # and not flagged at all


def test_compute_image_sanity_stats_includes_subject_extent(tmp_path):
    from PIL import Image
    path = _save_png(tmp_path, "flat.png", Image.new("RGB", (600, 900), (238, 232, 210)))

    stats = critic_pass.compute_image_sanity_stats(path)

    assert "subject_extent" in stats


def test_subject_extent_high_for_one_big_subject_low_cov(tmp_path):
    from PIL import Image, ImageDraw
    # A single large filled subject on a plain background: low ink coverage overall
    # (the shape is thin relative to the frame) but the shape's bounding box spans most
    # of the frame - the FM-13 "legitimate sparse" case.
    img = Image.new("RGB", (600, 900), (245, 242, 235))
    draw = ImageDraw.Draw(img)
    draw.ellipse([80, 100, 520, 800], outline=(15, 15, 15), width=6)

    stats = critic_pass.compute_image_sanity_stats(_save_png(tmp_path, "big.png", img))

    assert stats["subject_extent"] > 0.5
    assert critic_pass.local_sanity_flag_note(stats) is None


def test_subject_extent_low_for_tiny_subject_in_empty_frame(tmp_path):
    from PIL import Image, ImageDraw
    # A tiny motif adrift in a large empty field - the actual FM-13 defect.
    img = Image.new("RGB", (600, 900), (245, 242, 235))
    draw = ImageDraw.Draw(img)
    draw.ellipse([280, 420, 320, 460], outline=(15, 15, 15), width=4)

    stats = critic_pass.compute_image_sanity_stats(_save_png(tmp_path, "tiny.png", img))

    assert stats["subject_extent"] < critic_pass.SANITY_SUBJECT_EXTENT_SMALL
    note = critic_pass.local_sanity_flag_note(stats)
    assert note is not None
    assert "small" in note and "mostly-empty" in note


def test_local_sanity_flag_note_wording_carries_the_owner_distinction():
    stats = {"cov": 0.02, "subject_extent": 0.1}

    note = critic_pass.local_sanity_flag_note(stats)

    assert "legitimate style" in note
    assert "mostly-empty frame" in note
    assert "subject itself is ALSO small" in note


# --- S4-d tier 2: cheap single-image vision pre-filter ---

def test_check_master_image_ai_sanity_returns_none_when_passed():
    fake_response = {"text": _json.dumps({"passed": True, "reason": "looks fine"})}
    with patch("pipeline.critic_pass.anthropic_client.complete_with_images",
               return_value=fake_response) as mock_call:
        result = critic_pass.check_master_image_ai_sanity("https://gelato/flat.jpg", api_key="key1")

    assert result is None
    called_prompt, called_images = mock_call.call_args.args
    assert called_images == ["https://gelato/flat.jpg"]  # single image, not the gallery
    assert mock_call.call_args.kwargs["api_key"] == "key1"


def test_check_master_image_ai_sanity_returns_fail_dict_when_rejected():
    fake_response = {"text": _json.dumps({"passed": False, "reason": "blank canvas"})}
    with patch("pipeline.critic_pass.anthropic_client.complete_with_images", return_value=fake_response):
        result = critic_pass.check_master_image_ai_sanity("https://gelato/flat.jpg")

    assert result == {"passed": False, "reason": "blank canvas"}


def test_check_master_image_ai_sanity_returns_none_for_missing_source():
    assert critic_pass.check_master_image_ai_sanity(None) is None


def test_check_master_image_ai_sanity_threads_flag_note_into_prompt():
    fake_response = {"text": _json.dumps({"passed": True, "reason": "ok"})}
    with patch("pipeline.critic_pass.anthropic_client.complete_with_images",
               return_value=fake_response) as mock_call:
        critic_pass.check_master_image_ai_sanity(
            "https://gelato/flat.jpg", flag_note="Note: borderline-sparse (coverage 0.020)."
        )

    called_prompt = mock_call.call_args.args[0]
    assert "borderline-sparse" in called_prompt


def test_run_local_and_master_gate_hard_fails_locally_without_any_vision_call(tmp_path):
    from PIL import Image
    empty_path = _save_png(tmp_path, "empty.png", Image.new("RGB", (600, 900), (238, 232, 210)))

    with patch("pipeline.critic_pass.anthropic_client.complete_with_images") as mock_call:
        result, flag_note = critic_pass.run_local_and_master_gate(empty_path, ["https://gelato/flat.jpg"])

    mock_call.assert_not_called()
    assert result["passed"] is False
    assert flag_note is None


def test_run_local_and_master_gate_falls_through_to_none_with_flag_note(tmp_path):
    from PIL import Image, ImageDraw
    # Sparse but structured image (stand-in for master 3's "borderline" profile) - real
    # thresholds against actual masters are covered by the calibration-set tests above;
    # this just exercises the flag_note plumbing through run_local_and_master_gate.
    img = Image.new("RGB", (600, 900), (240, 235, 215))
    draw = ImageDraw.Draw(img)
    draw.ellipse([200, 350, 400, 550], outline=(10, 10, 10), width=30)
    path = _save_png(tmp_path, "sparse.png", img)

    fake_response = {"text": _json.dumps({"passed": True, "reason": "looks fine"})}
    with patch("pipeline.critic_pass.anthropic_client.complete_with_images", return_value=fake_response):
        result, flag_note = critic_pass.run_local_and_master_gate(path, ["https://gelato/flat.jpg"])

    assert result is None


def test_run_critic_pass_local_gate_fails_attempt_without_vision_call(tmp_path):
    from PIL import Image
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_ready_candidate(conn, niche="monstera line art")
    # Point the candidate's local master at a near-empty file - attempt 1 must fail
    # locally, no Anthropic call, then regenerate (mocked) to a nonexistent local path
    # so attempt 2 defers to the vision critic, which passes.
    empty_path = _save_png(tmp_path, "master.png", Image.new("RGB", (600, 900), (238, 232, 210)))
    conn.execute("UPDATE candidates SET base_image_local_path = ? WHERE id = ?", (empty_path, candidate_id))
    conn.commit()

    def fake_create(*a, **k):
        return {"id": "gelato_prod_retry", "isReadyToPublish": True,
                "productImages": [{"fileUrl": "https://gelato-api-live.s3/v2.jpg", "isPrimary": True}]}

    # attempt 2's local gate is inconclusive (nonexistent file) -> falls through to tier 2
    # (cheap master-image check) then tier 3 (full rubric) - two vision calls total.
    dispatch = _VisionDispatch(
        {"text": _json.dumps({"title": _DRAFT_TITLE, "tags": _DRAFT_TAGS,
                              "description": _VALID_DESCRIPTION_PROSE, "alt_texts": []})},
        _verdict_response("good"),
    )
    with patch("pipeline.critic_pass.anthropic_client.complete_with_images",
               side_effect=dispatch), \
         patch("pipeline.compliance_draft.anthropic_client.complete",
               side_effect=lambda *a, **k: dispatch(*a, **k)), \
         patch("pipeline.generate.replicate_client.generate_image",
               return_value={"image_url": "https://replicate.delivery/r.png", "prediction_id": "p"}), \
         patch("pipeline.generate.replicate_client.upscale_image",
               return_value={"image_url": "https://replicate.delivery/ru.png", "prediction_id": "pu"}), \
         patch("pipeline.generate.http.fetch_bytes", return_value=b"bytes"), \
         patch("pipeline.generate.artwork_store.persist_base_artwork",
               side_effect=lambda candidate_id, raw_bytes: {
                   "durable_url": f"https://pub-fake.r2.dev/base/{candidate_id}.png",
                   "local_path": f"/fake/nonexistent/{candidate_id}.png", "sha256": "x"}), \
         patch("pipeline.group_product.gelato_client.create_product_from_template", side_effect=fake_create), \
         patch("pipeline.group_product.gelato_client.get_product",
               side_effect=lambda pid, *, store_id=None, api_key=None: fake_create()):
        result = critic_pass.run_critic_pass(
            conn, candidate_id, static_config=STATIC_CONFIG, anthropic_api_key="key1",
            store_id="store1", gelato_api_key="key2", replicate_api_token="tok1",
            now=datetime(2026, 7, 10, 12, 0, 0),
        )

    assert result == {"candidate_id": candidate_id, "passed": True, "attempts": 2}
    # Vision called exactly twice (attempt 2's tier-2 master check + tier-3 full rubric)
    # - attempt 1 was the zero-cost local fail, no vision call at all.
    assert dispatch.critic_call_count == 2
    attempts = conn.execute(
        "SELECT passed, failure_reason FROM critic_pass_attempts WHERE group_id = "
        "(SELECT id FROM groups WHERE candidate_id = ? AND group_type = 'primary') ORDER BY attempt_number",
        (candidate_id,),
    ).fetchall()
    assert attempts[0]["passed"] == 0
    assert "near-empty image" in attempts[0]["failure_reason"]
    assert attempts[1]["passed"] == 1
    conn.close()


def test_record_critic_attempt_stores_pass(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id, _ = _insert_primary_gallery(conn, candidate_id)

    attempt_id = critic_pass.record_critic_attempt(
        conn, group_id, 1, {"passed": True, "reason": "meets rubric"},
        now=datetime(2026, 7, 10, 12, 0, 0),
    )

    row = conn.execute("SELECT * FROM critic_pass_attempts WHERE id = ?", (attempt_id,)).fetchone()
    assert row["group_id"] == group_id
    assert row["attempt_number"] == 1
    assert row["passed"] == 1
    assert row["failure_reason"] is None
    assert row["created_at"] == "2026-07-10T12:00:00"
    conn.close()


def test_record_critic_attempt_stores_failure_with_reason_and_correction_notes(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id, _ = _insert_primary_gallery(conn, candidate_id)

    attempt_id = critic_pass.record_critic_attempt(
        conn, group_id, 1, {"passed": False, "reason": "composition is off-center"},
        correction_notes="composition is off-center", now=datetime(2026, 7, 10, 12, 0, 0),
    )

    row = conn.execute("SELECT * FROM critic_pass_attempts WHERE id = ?", (attempt_id,)).fetchone()
    assert row["passed"] == 0
    assert row["failure_reason"] == "composition is off-center"
    assert row["correction_notes"] == "composition is off-center"
    conn.close()


def test_discard_superseded_attempt_leaves_shared_product_and_listing_untouched(tmp_path):
    # v4.12: the Gelato product / group_products row belongs to the CANDIDATE, shared by
    # every group - discarding one group's attempt must delete nothing shared (inverted
    # from the pre-v4.12 behaviour this test used to assert).
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id, group_product_id = _insert_primary_gallery(conn, candidate_id)

    critic_pass.discard_superseded_attempt(
        conn, group_product_id, group_id, store_id="store1", api_key="key2"
    )

    # v4.12: discard makes no Gelato call at all (nothing shared to delete).
    assert conn.execute(
        "SELECT * FROM group_products WHERE id = ?", (group_product_id,)
    ).fetchone() is not None
    assert conn.execute(
        "SELECT * FROM product_images WHERE group_product_id = ? AND group_id = ?",
        (group_product_id, group_id),
    ).fetchall() == []
    conn.close()


def test_discard_superseded_attempt_keeps_variant_rows(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    timestamp = "2026-07-16T09:00:00"
    group_id = conn.execute(
        "INSERT INTO groups (candidate_id, group_type, status, created_at, updated_at) "
        "VALUES (?, 'primary', 'pending_review', ?, ?)",
        (candidate_id, timestamp, timestamp),
    ).lastrowid
    group_product_id = conn.execute(
        "INSERT INTO group_products (candidate_id, group_id, gelato_template_id, gelato_product_id, status, created_at, updated_at) "
        "VALUES (?, ?, 'tmpl', 'gelato-1', 'created', ?, ?)",
        (candidate_id, group_id, timestamp, timestamp),
    ).lastrowid
    conn.execute(
        "INSERT INTO group_product_variants "
        "(group_product_id, group_id, size, orientation, gelato_template_variant_id, price_eur, created_at) "
        "VALUES (?, ?, '8x12', 'portrait', 'var1', 24.0, ?)",
        (group_product_id, group_id, timestamp),
    )
    conn.commit()

    critic_pass.discard_superseded_attempt(conn, group_product_id, group_id)

    # v4.12: the group's SIZES don't change between attempts, only its artwork does -
    # so the variant rows stay and the next render writes into the same slots. (Was
    # "also_deletes_variant_rows": under v4.11 the whole product was torn down and
    # rebuilt per attempt, so deleting them was the only way to avoid duplicates.)
    remaining = conn.execute(
        "SELECT COUNT(*) AS n FROM group_product_variants WHERE group_product_id = ?", (group_product_id,)
    ).fetchone()
    assert remaining["n"] == 1
    # The shared listing record (group_products row) survives too.
    assert conn.execute(
        "SELECT id FROM group_products WHERE id = ?", (group_product_id,)
    ).fetchone() is not None
    conn.close()


def test_discard_superseded_attempt_skips_gelato_call_when_no_product_id(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id, group_product_id = _insert_primary_gallery(
        conn, candidate_id, gelato_product_id=None, group_product_status="pending"
    )

    critic_pass.discard_superseded_attempt(conn, group_product_id, group_id, store_id="store1", api_key="key2")

    # v4.12: no gelato_product_id means nothing to delete either way, but the shared
    # group_products row (the candidate's listing record) is never deleted here.
    assert conn.execute(
        "SELECT * FROM group_products WHERE id = ?", (group_product_id,)
    ).fetchone() is not None
    conn.close()


STATIC_CONFIG = {
    "gelato_templates": {
        "8x12_portrait": {
            "template_id": "tpl_real_8x12",
            "template_variant_id": "variant_real_8x12",
            "image_placeholder_name": "real_image_slot.jpg",
        }
    },
    "prices_eur": {"8x12": 24},
    "etsy_who_made": "i_did",
    "etsy_production_partner_ids": [5717252],
    "etsy_taxonomy_id": "1027",
    "etsy_shipping_profile_id": "",
    "aspect_ratio_groups": {"primary": ["8x12"]},
    # No mockup bundles wired into this hand-built STATIC_CONFIG - empty scene list is
    # the normal "nothing to render" case (Task 2's contract), so these tests never
    # need a real local master image on disk.
    "mockup_templates": {"primary": {"portrait": [], "landscape": []}},
}


def test_run_critic_pass_happy_path_sets_primary_review_on_first_pass(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_ready_candidate(conn, niche="monstera line art")

    fake_response = _verdict_response("good")
    with patch("pipeline.critic_pass.anthropic_client.complete_with_images", return_value=fake_response):
        result = critic_pass.run_critic_pass(
            conn, candidate_id, static_config=STATIC_CONFIG, anthropic_api_key="key1",
            store_id="store1", gelato_api_key="key2", now=datetime(2026, 7, 10, 12, 0, 0),
        )

    assert result == {"candidate_id": candidate_id, "passed": True, "attempts": 1}

    candidate_row = conn.execute("SELECT status FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    assert candidate_row["status"] == "primary_review"

    attempts = conn.execute(
        "SELECT * FROM critic_pass_attempts WHERE group_id = "
        "(SELECT id FROM groups WHERE candidate_id = ? AND group_type = 'primary')",
        (candidate_id,),
    ).fetchall()
    assert len(attempts) == 1
    assert attempts[0]["passed"] == 1
    conn.close()


def test_run_critic_pass_resumes_attempt_count_after_crash_before_regenerate(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_ready_candidate(conn, niche="monstera line art")

    group_row = conn.execute(
        "SELECT id FROM groups WHERE candidate_id = ? AND group_type = 'primary'",
        (candidate_id,),
    ).fetchone()
    group_id = group_row["id"]

    # Reproduce the exact post-crash DB state: attempt 1 failed and was recorded,
    # its group_product_variants/product_images were discarded (v4.12: the shared
    # group_products row - the candidate's listing record - survives a discard, it is
    # never deleted), its listing_texts row was deleted, then
    # generate.generate_for_candidate raised before attempt 2 could be set up.
    # candidate is still 'generating', with one attempt row recorded.
    critic_pass.record_critic_attempt(
        conn, group_id, 1, {"passed": False, "reason": "reason one"},
        now=datetime(2026, 7, 10, 12, 0, 0),
    )
    group_product_id = conn.execute(
        "SELECT id FROM group_products WHERE group_id = ?", (group_id,)
    ).fetchone()["id"]
    critic_pass.discard_superseded_attempt(
        conn, group_product_id, group_id, store_id="store1", api_key="key2"
    )
    conn.execute("DELETE FROM listing_texts WHERE candidate_id = ?", (candidate_id,))
    conn.commit()

    # A later batch cycle re-processed the candidate: run_primary_mockup_cycle's
    # get_or_create_primary_group finds the *same* group_id (idempotent design), and
    # render_group_mockups (v4.12) reuses the SAME group_products row - it is keyed off
    # the candidate and was never deleted by the discard above - rather than inserting a
    # new one; the variant rows were never dropped (the sizes didn't change), so it
    # only re-renders this group's image rows.
    # run_compliance_draft_cycle adds a fresh listing_texts row.
    timestamp = "2026-07-10T12:30:00"
    for order, image_url in enumerate(
        ("https://gelato/flat_resumed.jpg", "https://gelato/life_resumed.jpg")
    ):
        image_type = "flat_mockup" if order == 0 else "lifestyle"
        conn.execute(
            "INSERT INTO product_images (group_product_id, group_id, image_url, alt_text, gallery_order, image_type) "
            "VALUES (?, ?, ?, 'placeholder alt', ?, ?)",
            (group_product_id, group_id, image_url, order, image_type),
        )
    conn.commit()
    _insert_listing_text(conn, candidate_id, niche="monstera line art")

    fake_response = _verdict_response("good")
    with patch("pipeline.critic_pass.anthropic_client.complete_with_images", return_value=fake_response):
        result = critic_pass.run_critic_pass(
            conn, candidate_id, static_config=STATIC_CONFIG, anthropic_api_key="key1",
            store_id="store1", gelato_api_key="key2", now=datetime(2026, 7, 10, 13, 0, 0),
        )

    assert result == {"candidate_id": candidate_id, "passed": True, "attempts": 2}

    candidate_row = conn.execute("SELECT status FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    assert candidate_row["status"] == "primary_review"

    attempts = conn.execute(
        "SELECT * FROM critic_pass_attempts WHERE group_id = ? ORDER BY attempt_number",
        (group_id,),
    ).fetchall()
    assert len(attempts) == 2
    assert attempts[0]["attempt_number"] == 1
    assert attempts[1]["attempt_number"] == 2
    conn.close()


def test_abandon_candidate_marks_candidate_and_group_failed(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id, _ = _insert_primary_gallery(conn, candidate_id)

    critic_pass.abandon_candidate(
        conn, candidate_id, group_id, "exhausted 3 attempts: off-center composition",
        now=datetime(2026, 7, 10, 12, 30, 0),
    )

    candidate_row = conn.execute(
        "SELECT status, failed_reason, updated_at FROM candidates WHERE id = ?", (candidate_id,)
    ).fetchone()
    assert candidate_row["status"] == "failed"
    assert candidate_row["failed_reason"] == "exhausted 3 attempts: off-center composition"
    assert candidate_row["updated_at"] == "2026-07-10T12:30:00"

    group_row = conn.execute(
        "SELECT status, failed_reason FROM groups WHERE id = ?", (group_id,)
    ).fetchone()
    assert group_row["status"] == "failed_abandoned"
    assert group_row["failed_reason"] == "exhausted 3 attempts: off-center composition"
    conn.close()


def test_run_critic_pass_retries_once_then_passes(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_ready_candidate(conn, niche="monstera line art")

    # attempt 1's reject short-circuits at tier 2 (1 call); attempt 2's pass runs both
    # tier 2 and tier 3 (2 calls) - 3 responses total.
    critic_responses = iter([
        _verdict_response("reject", {4: "composition is off-center"}),
        _verdict_response("good"),
        _verdict_response("good"),
    ])

    def fake_create_product_from_template(*args, **kwargs):
        return {"id": "gelato_prod_retry", "isReadyToPublish": True,
                "productImages": [{"fileUrl": "https://gelato-api-live.s3/flat_v2.jpg", "isPrimary": True}]}

    def fake_get_product(product_id, *, store_id=None, api_key=None):
        return {"id": product_id, "isReadyToPublish": True,
                "productImages": [{"fileUrl": "https://gelato-api-live.s3/flat_v2.jpg", "isPrimary": True}]}

    def fake_generate_image(prompt, *, api_token=None):
        assert "composition is off-center" in prompt
        return {"image_url": "https://replicate.delivery/retry.png", "prediction_id": "pred_retry"}

    def fake_upscale_image(image_url, *, api_token=None):
        return {"image_url": "https://replicate.delivery/retry-upscaled.png", "prediction_id": "pred_retry_up"}

    fake_draft_response = {
        "text": _json.dumps({
            "title": _DRAFT_TITLE,
            "tags": _DRAFT_TAGS, "description": _VALID_DESCRIPTION_PROSE,
            # STATIC_CONFIG has no mockup_templates scenes wired in, so the regenerated
            # gallery is empty (Task 2/3's valid "nothing to render" case) - alt_texts
            # must match that count, not a hardcoded gallery size.
            "alt_texts": [],
        })
    }

    dispatch = _VisionDispatch(fake_draft_response, critic_responses)
    with patch("pipeline.critic_pass.anthropic_client.complete_with_images",
               side_effect=dispatch), \
         patch("pipeline.compliance_draft.anthropic_client.complete",
               side_effect=lambda *a, **k: dispatch(*a, **k)), \
         patch("pipeline.generate.replicate_client.generate_image", side_effect=fake_generate_image), \
         patch("pipeline.generate.replicate_client.upscale_image", side_effect=fake_upscale_image), \
         patch("pipeline.generate.http.fetch_bytes", return_value=b"fake-image-bytes"), \
         patch("pipeline.generate.artwork_store.persist_base_artwork",
               side_effect=lambda candidate_id, raw_bytes: {
                   "durable_url": f"https://pub-fake.r2.dev/base/{candidate_id}.png",
                   "local_path": f"/fake/db/base_artwork/{candidate_id}.png",
                   "sha256": "fakesha256hash",
               }), \
         patch("pipeline.group_product.gelato_client.create_product_from_template",
               side_effect=fake_create_product_from_template), \
         patch("pipeline.group_product.gelato_client.get_product", side_effect=fake_get_product):
        result = critic_pass.run_critic_pass(
            conn, candidate_id, static_config=STATIC_CONFIG, anthropic_api_key="key1",
            store_id="store1", gelato_api_key="key2", replicate_api_token="tok1",
            now=datetime(2026, 7, 10, 12, 0, 0),
        )

    assert result == {"candidate_id": candidate_id, "passed": True, "attempts": 2}
    # v4.12: discard_superseded_attempt makes no Gelato call at all, and the retry's
    # render never creates a Gelato product either (that only happens once, at
    # publish) - the same shared group_products row is reused, never duplicated or
    # deleted.
    group_product_rows = conn.execute(
        "SELECT id, gelato_product_id FROM group_products WHERE candidate_id = ?", (candidate_id,)
    ).fetchall()
    assert len(group_product_rows) == 1
    assert group_product_rows[0]["gelato_product_id"] == "gelato_prod_1"

    candidate_row = conn.execute("SELECT status FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    assert candidate_row["status"] == "primary_review"

    listing_rows = conn.execute(
        "SELECT * FROM listing_texts WHERE candidate_id = ?", (candidate_id,)
    ).fetchall()
    assert len(listing_rows) == 1
    assert listing_rows[0]["title"] == _DRAFT_TITLE

    attempts = conn.execute(
        "SELECT * FROM critic_pass_attempts WHERE group_id = "
        "(SELECT id FROM groups WHERE candidate_id = ? AND group_type = 'primary') "
        "ORDER BY attempt_number",
        (candidate_id,),
    ).fetchall()
    assert len(attempts) == 2
    assert attempts[0]["passed"] == 0
    assert attempts[0]["failure_reason"] == "composition is off-center"
    assert attempts[1]["passed"] == 1
    conn.close()


def test_run_critic_pass_abandons_after_three_failures_and_triggers_fallback(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_ready_candidate(conn, niche="monstera line art")

    # each reject short-circuits at tier 2 - 1 call per attempt, 3 total.
    critic_responses = iter([
        _verdict_response("reject", {1: "reason one"}),
        _verdict_response("reject", {1: "reason two"}),
        _verdict_response("reject", {1: "reason three"}),
    ])

    def fake_create_product_from_template(*args, **kwargs):
        return {"id": "gelato_prod_new", "isReadyToPublish": True,
                "productImages": [{"fileUrl": "https://gelato-api-live.s3/flat_new.jpg", "isPrimary": True}]}

    def fake_get_product(product_id, *, store_id=None, api_key=None):
        return {"id": product_id, "isReadyToPublish": True,
                "productImages": [{"fileUrl": "https://gelato-api-live.s3/flat_new.jpg", "isPrimary": True}]}

    def fake_generate_image(prompt, *, api_token=None):
        return {"image_url": "https://replicate.delivery/retry.png", "prediction_id": "pred_retry"}

    def fake_upscale_image(image_url, *, api_token=None):
        return {"image_url": "https://replicate.delivery/retry-upscaled.png", "prediction_id": "pred_retry_up"}

    fake_draft_response = {
        "text": _json.dumps({
            "title": _DRAFT_TITLE, "tags": _DRAFT_TAGS, "description": _VALID_DESCRIPTION_PROSE,
            # See test_run_critic_pass_retries_once_then_passes - empty gallery, empty alt_texts.
            "alt_texts": [],
        })
    }

    dispatch = _VisionDispatch(fake_draft_response, critic_responses)
    with patch("pipeline.critic_pass.anthropic_client.complete_with_images",
               side_effect=dispatch), \
         patch("pipeline.compliance_draft.anthropic_client.complete",
               side_effect=lambda *a, **k: dispatch(*a, **k)), \
         patch("pipeline.generate.replicate_client.generate_image", side_effect=fake_generate_image), \
         patch("pipeline.generate.replicate_client.upscale_image", side_effect=fake_upscale_image), \
         patch("pipeline.generate.http.fetch_bytes", return_value=b"fake-image-bytes"), \
         patch("pipeline.generate.artwork_store.persist_base_artwork",
               side_effect=lambda candidate_id, raw_bytes: {
                   "durable_url": f"https://pub-fake.r2.dev/base/{candidate_id}.png",
                   "local_path": f"/fake/db/base_artwork/{candidate_id}.png",
                   "sha256": "fakesha256hash",
               }), \
         patch("pipeline.group_product.gelato_client.create_product_from_template",
               side_effect=fake_create_product_from_template), \
         patch("pipeline.group_product.gelato_client.get_product", side_effect=fake_get_product):
        result = critic_pass.run_critic_pass(
            conn, candidate_id, static_config=STATIC_CONFIG, anthropic_api_key="key1",
            store_id="store1", gelato_api_key="key2", replicate_api_token="tok1",
            now=datetime(2026, 7, 10, 12, 0, 0),
        )

    assert result == {"candidate_id": candidate_id, "passed": False, "attempts": 3}
    # v4.12: abandon never deletes a Gelato product either - the primary group's render
    # path never created one (that only happens once, at publish), so there is nothing
    # for cleanup.py's whole-candidate sweep to find until/unless one gets created later.
    group_product_rows = conn.execute(
        "SELECT gelato_product_id FROM group_products WHERE candidate_id = ?", (candidate_id,)
    ).fetchall()
    assert len(group_product_rows) == 1
    assert group_product_rows[0]["gelato_product_id"] == "gelato_prod_1"

    candidate_row = conn.execute(
        "SELECT status, failed_reason FROM candidates WHERE id = ?", (candidate_id,)
    ).fetchone()
    assert candidate_row["status"] == "failed"
    assert candidate_row["failed_reason"] == "reason three"

    group_row = conn.execute(
        "SELECT status, failed_reason FROM groups WHERE candidate_id = ? AND group_type = 'primary'",
        (candidate_id,),
    ).fetchone()
    assert group_row["status"] == "failed_abandoned"
    assert group_row["failed_reason"] == "reason three"

    fallback_row = conn.execute(
        "SELECT * FROM candidates WHERE trend_source LIKE 'safe_evergreen_fallback:%'"
    ).fetchone()
    assert fallback_row is not None
    assert fallback_row["status"] == "pending"
    conn.close()


def test_run_critic_pass_abandons_candidate_when_retry_regeneration_crashes(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_ready_candidate(conn, niche="monstera line art")
    group_row = conn.execute(
        "SELECT id FROM groups WHERE candidate_id = ? AND group_type = 'primary'", (candidate_id,),
    ).fetchone()
    group_id = group_row["id"]

    fake_critic_response = _verdict_response("reject", {4: "off-center composition"})

    with patch("pipeline.critic_pass.anthropic_client.complete_with_images", return_value=fake_critic_response), \
         patch("pipeline.generate.generate_for_candidate", side_effect=RuntimeError("Unterminated string")):
        with pytest.raises(RuntimeError, match="Unterminated string"):
            critic_pass.run_critic_pass(
                conn, candidate_id, static_config=STATIC_CONFIG, anthropic_api_key="key1",
                store_id="store1", gelato_api_key="key2", replicate_api_token="tok1",
                now=datetime(2026, 7, 10, 12, 0, 0),
            )

    # A crash mid-retry must not leave the candidate/group in a state cleanup.py never
    # sweeps (candidates.status outside failed/abandoned/completed, groups.status still
    # pending_review) - it must land in the same terminal state as a normal 3-attempt abandon.
    candidate_row = conn.execute(
        "SELECT status, failed_reason FROM candidates WHERE id = ?", (candidate_id,)
    ).fetchone()
    assert candidate_row["status"] == "failed"
    assert "Unterminated string" in candidate_row["failed_reason"]

    group_status_row = conn.execute("SELECT status FROM groups WHERE id = ?", (group_id,)).fetchone()
    assert group_status_row["status"] == "failed_abandoned"
    conn.close()


def test_run_critic_pass_does_not_abandon_on_transient_fault_during_regen(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_ready_candidate(conn, niche="monstera line art")
    group_row = conn.execute(
        "SELECT id FROM groups WHERE candidate_id = ? AND group_type = 'primary'", (candidate_id,),
    ).fetchone()
    group_id = group_row["id"]

    fake_critic_response = _verdict_response("reject", {4: "off-center composition"})

    with patch("pipeline.critic_pass.anthropic_client.complete_with_images", return_value=fake_critic_response), \
         patch("pipeline.generate.generate_for_candidate",
               side_effect=http.HTTPError(503, "upstream unavailable")):
        result = critic_pass.run_critic_pass(
            conn, candidate_id, static_config=STATIC_CONFIG, anthropic_api_key="key1",
            store_id="store1", gelato_api_key="key2", replicate_api_token="tok1",
            now=datetime(2026, 7, 10, 12, 0, 0),
        )

    # A vendor 503 mid-regen is not a verdict on the art - candidate stays exactly
    # where it was (still generating, same attempt), NOT abandoned. GL-16.
    assert result == {"candidate_id": candidate_id, "passed": False, "attempts": 1, "transient": True}

    candidate_row = conn.execute(
        "SELECT status, failed_reason FROM candidates WHERE id = ?", (candidate_id,)
    ).fetchone()
    assert candidate_row["status"] == "generating"
    assert candidate_row["failed_reason"] is None

    group_status_row = conn.execute("SELECT status FROM groups WHERE id = ?", (group_id,)).fetchone()
    assert group_status_row["status"] == "pending_review"

    # attempt 1's reject was still recorded (it's a real verdict); no attempt 2 row
    # exists since the regen never got far enough to produce a new verdict.
    attempts = conn.execute(
        "SELECT attempt_number FROM critic_pass_attempts WHERE group_id = ? ORDER BY attempt_number",
        (group_id,),
    ).fetchall()
    assert [row["attempt_number"] for row in attempts] == [1]
    conn.close()


def test_run_critic_pass_does_not_abandon_on_replicate_throttled_during_regen(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_ready_candidate(conn, niche="monstera line art")

    fake_critic_response = _verdict_response("reject", {4: "off-center composition"})

    with patch("pipeline.critic_pass.anthropic_client.complete_with_images", return_value=fake_critic_response), \
         patch("pipeline.generate.generate_for_candidate",
               side_effect=replicate_client.ReplicateThrottledError(retry_after=10.0)):
        result = critic_pass.run_critic_pass(
            conn, candidate_id, static_config=STATIC_CONFIG, anthropic_api_key="key1",
            store_id="store1", gelato_api_key="key2", replicate_api_token="tok1",
            now=datetime(2026, 7, 10, 12, 0, 0),
        )

    assert result["transient"] is True
    candidate_row = conn.execute("SELECT status FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    assert candidate_row["status"] == "generating"
    conn.close()


def test_run_critic_pass_still_abandons_on_non_transient_regen_crash(tmp_path):
    # RuntimeError (malformed data / code defect) must still abandon exactly as
    # before - only vendor/network faults get the transient treatment.
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_ready_candidate(conn, niche="monstera line art")
    group_row = conn.execute(
        "SELECT id FROM groups WHERE candidate_id = ? AND group_type = 'primary'", (candidate_id,),
    ).fetchone()
    group_id = group_row["id"]

    fake_critic_response = _verdict_response("reject", {4: "off-center composition"})

    with patch("pipeline.critic_pass.anthropic_client.complete_with_images", return_value=fake_critic_response), \
         patch("pipeline.generate.generate_for_candidate", side_effect=RuntimeError("Unterminated string")):
        with pytest.raises(RuntimeError, match="Unterminated string"):
            critic_pass.run_critic_pass(
                conn, candidate_id, static_config=STATIC_CONFIG, anthropic_api_key="key1",
                store_id="store1", gelato_api_key="key2", replicate_api_token="tok1",
                now=datetime(2026, 7, 10, 12, 0, 0),
            )

    candidate_row = conn.execute("SELECT status FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    assert candidate_row["status"] == "failed"
    group_status_row = conn.execute("SELECT status FROM groups WHERE id = ?", (group_id,)).fetchone()
    assert group_status_row["status"] == "failed_abandoned"
    conn.close()


def test_run_critic_pass_cycle_processes_ready_candidates_and_skips_undrafted(tmp_path):
    conn = _fresh_conn(tmp_path)
    ready_id = _insert_ready_candidate(conn, niche="monstera line art")
    undrafted_id = _insert_candidate(conn, niche="pending one", status="generating")
    _insert_primary_gallery(conn, undrafted_id)  # gallery exists but no listing_texts row yet

    fake_response = _verdict_response("good")
    with patch("pipeline.critic_pass.anthropic_client.complete_with_images", return_value=fake_response):
        processed_ids = critic_pass.run_critic_pass_cycle(
            conn, static_config=STATIC_CONFIG, anthropic_api_key="key1",
            store_id="store1", gelato_api_key="key2", now=datetime(2026, 7, 10, 12, 0, 0),
        )

    assert processed_ids == [ready_id]
    assert undrafted_id not in processed_ids
    conn.close()


def test_run_critic_pass_cycle_skips_candidates_already_passed(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_ready_candidate(conn, niche="monstera line art")

    fake_response = _verdict_response("good")
    with patch("pipeline.critic_pass.anthropic_client.complete_with_images", return_value=fake_response):
        first_run = critic_pass.run_critic_pass_cycle(
            conn, static_config=STATIC_CONFIG, anthropic_api_key="key1",
            store_id="store1", gelato_api_key="key2", now=datetime(2026, 7, 10, 12, 0, 0),
        )
        second_run = critic_pass.run_critic_pass_cycle(
            conn, static_config=STATIC_CONFIG, anthropic_api_key="key1",
            store_id="store1", gelato_api_key="key2", now=datetime(2026, 7, 10, 13, 0, 0),
        )

    assert first_run == [candidate_id]
    assert second_run == []
    conn.close()


def test_run_critic_pass_cycle_isolates_per_candidate_operational_failures(tmp_path):
    conn = _fresh_conn(tmp_path)
    failing_id = _insert_ready_candidate(conn, niche="saturated term")
    succeeding_id = _insert_ready_candidate(conn, niche="moon phase print")

    def fake_complete_with_images(prompt, image_urls, *, api_key=None, max_tokens=1024, model=None):
        if "saturated term" in prompt:
            raise RuntimeError("Anthropic throttled")
        return _verdict_response("good")

    with patch("pipeline.critic_pass.anthropic_client.complete_with_images",
               side_effect=fake_complete_with_images):
        # GL-54: the loop still finishes (the succeeding candidate still gets
        # processed), but the cycle now raises once at the end so run_batch's
        # _run_stage sees it instead of the failure being printed and swallowed.
        with pytest.raises(critic_pass.CriticPassCycleError, match="Anthropic throttled"):
            critic_pass.run_critic_pass_cycle(
                conn, static_config=STATIC_CONFIG, anthropic_api_key="key1",
                store_id="store1", gelato_api_key="key2", now=datetime(2026, 7, 10, 12, 0, 0),
            )

    succeeding_row = conn.execute("SELECT status FROM candidates WHERE id = ?", (succeeding_id,)).fetchone()
    assert succeeding_row["status"] == "primary_review"

    failing_row = conn.execute("SELECT status FROM candidates WHERE id = ?", (failing_id,)).fetchone()
    assert failing_row["status"] == "generating"  # exception happened before any status write
    conn.close()


def test_run_critic_pass_cycle_returns_empty_list_when_nothing_ready(tmp_path):
    conn = _fresh_conn(tmp_path)
    _insert_candidate(conn, niche="pending one", status="pending")

    processed_ids = critic_pass.run_critic_pass_cycle(conn, static_config=STATIC_CONFIG)

    assert processed_ids == []
    conn.close()
