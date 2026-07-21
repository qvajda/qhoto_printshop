from unittest.mock import patch

import pipeline.anthropic_client as anthropic_client
import pipeline.art_brief as art_brief


def test_sanitize_niche_removes_known_scene_tokens():
    assert art_brief.sanitize_niche("mid-century botanical wall poster") == "mid-century botanical"
    assert art_brief.sanitize_niche("nature wall décor print") == "nature"
    assert art_brief.sanitize_niche("monstera line art") == "monstera line art"


def test_build_brief_prompt_includes_niche_and_mandatory_fields():
    candidate = {"niche": "monstera line art", "trend_source": "event_lookahead:fall_cozy_aesthetic"}

    prompt = art_brief.build_brief_prompt(candidate)

    assert "monstera line art" in prompt
    assert "event_lookahead:fall_cozy_aesthetic" in prompt
    assert "NAMED art idiom" in prompt
    assert "A density clause" in prompt
    assert "Mark boldness" in prompt
    assert "backdrop device" in prompt
    assert "accent colors" in prompt
    assert "60 words" in prompt


def test_build_brief_prompt_includes_round2_focal_hierarchy_and_backdrop_demotion():
    prompt = art_brief.build_brief_prompt({"niche": "monstera line art", "trend_source": None})

    # FM-2 fix (round 2, still present): mandatory focal-hierarchy field.
    assert "Focal hierarchy" in prompt
    # FM-1 fix (round 2, still present): wide backdrop-device menu.
    assert "arch, wash, band, sun disc" in prompt
    # FM-3 fix: boldness qualifies the medium, doesn't replace it.
    assert "never a replacement for it" in prompt
    # FM-4 stopgap: landscape-native scenes get a foreground-anchor nudge.
    assert "foreground anchor subject" in prompt


def test_build_brief_prompt_subject_named_first():
    prompt = art_brief.build_brief_prompt({"niche": "monstera line art", "trend_source": None})

    # R3-a (FM-7 root cause 3 / research finding 1): subject-first ordering.
    assert "named FIRST" in prompt
    assert "naming the primary subject in the opening words" in prompt


def test_build_brief_prompt_includes_conditional_sparse_density_clause():
    prompt = art_brief.build_brief_prompt({"niche": "monstera line art", "trend_source": None})

    # FM-13: sparse idiom legitimized - either dense or one large dominant
    # subject with generous empty space; only a SMALL subject in empty space
    # is invalid.
    assert "one large dominant subject" in prompt
    assert "generous, intentional empty space" in prompt
    assert "Never describe a small subject adrift in a mostly empty frame" in prompt


def test_build_brief_prompt_includes_occupant_conditionality_and_integration_vocab():
    prompt = art_brief.build_brief_prompt({"niche": "monstera line art", "trend_source": None})

    # FM-11: occupant conditionality - only when it genuinely helps, and
    # "no occupant" / "closes over it" are equally valid choices.
    assert "use it ONLY when it genuinely improves the composition" in prompt
    assert "closes over the opening entirely" in prompt
    assert "the subject has no secondary occupant at all" in prompt
    assert "dynamic pose (in flight, mid-glide, mid-crawl)" in prompt
    # FM-7: integration vocabulary - scale, physical contact, anatomy.
    assert "large enough to read across a room" in prompt
    assert "spanning a third of the frame width" in prompt
    assert "physical-contact language" in prompt
    assert "six legs gripping the stem" in prompt
    assert "symmetrically and anatomically complete" in prompt


def test_build_brief_prompt_forbids_shape_words_for_negative_space():
    prompt = art_brief.build_brief_prompt({"niche": "monstera line art", "trend_source": None})

    # FM-8: negative-space wording hygiene - describe position relative to
    # subject matter, never the geometry of the gap.
    assert "relative to the surrounding stems, fronds, or blooms only" in prompt
    assert "never call it a triangle, rectangle, square, or circle of space" in prompt


def test_build_brief_prompt_includes_bottom_edge_grounding_clause():
    prompt = art_brief.build_brief_prompt({"niche": "monstera line art", "trend_source": None})

    # FM-9: bottom-edge grounding for stem/bouquet/herbarium subjects.
    assert "Edge contact" in prompt
    assert "stems running off the bottom edge of the frame" in prompt


def test_build_brief_prompt_backdrop_device_no_longer_small_subject_only():
    prompt = art_brief.build_brief_prompt({"niche": "monstera line art", "trend_source": None})

    # FM-10: backdrop rebalanced to a positive menu device for SOME designs,
    # including behind a large dominant subject - not just small motifs.
    assert "SMALL, single-motif subject only" not in prompt
    assert "appropriate behind a large dominant subject" in prompt
    assert "not the default and not forbidden" in prompt


def test_build_brief_prompt_includes_sibling_diversity_note_only_when_given():
    no_sibling_prompt = art_brief.build_brief_prompt({"niche": "monstera", "trend_source": None})
    assert "Briefs already written earlier in this batch" not in no_sibling_prompt

    sibling_prompt = art_brief.build_brief_prompt(
        {"niche": "monstera", "trend_source": None},
        sibling_briefs=["A sage and terracotta mid-century botanical."],
    )
    assert "Briefs already written earlier in this batch" in sibling_prompt
    assert "A sage and terracotta mid-century botanical." in sibling_prompt


def test_sibling_note_floors_backdrop_device_when_none_used_yet():
    # R3-a (FM-10): no earlier brief used a backdrop device -> strongly
    # consider one here.
    prompt = art_brief.build_brief_prompt(
        {"niche": "monstera", "trend_source": None},
        sibling_briefs=["A dense sage and terracotta mid-century botanical bouquet, filling the frame."],
    )
    assert "strongly consider one here" in prompt


def test_sibling_note_caps_backdrop_device_when_two_already_used():
    # R3-a (FM-10): two+ earlier briefs already used a backdrop device ->
    # use none here (the pre-existing cap, still enforced).
    prompt = art_brief.build_brief_prompt(
        {"niche": "monstera", "trend_source": None},
        sibling_briefs=[
            "A sage botanical bouquet against a sun disc backdrop.",
            "A terracotta sunburst behind an arch device.",
        ],
    )
    assert "use none here" in prompt


def test_sibling_note_neutral_when_exactly_one_backdrop_device_used():
    prompt = art_brief.build_brief_prompt(
        {"niche": "monstera", "trend_source": None},
        sibling_briefs=["A sage botanical bouquet against a sun disc backdrop."],
    )
    assert "strongly consider one here" not in prompt
    assert "use none here" not in prompt


def test_build_brief_prompt_moves_no_go_list_into_instructions():
    prompt = art_brief.build_brief_prompt({"niche": "monstera line art", "trend_source": None})

    assert "named artist" in prompt
    assert "recognizable character" in prompt
    assert "celebrity likeness" in prompt
    assert "hand-painted" in prompt


def test_build_brief_prompt_strips_scene_tokens_from_niche_before_injection():
    candidate = {"niche": "botanical minimalist wall art - holiday_peak", "trend_source": None}

    prompt = art_brief.build_brief_prompt(candidate)

    assert "wall art" not in prompt.lower().split("niche/keyword:")[1].split("\n")[0]
    assert "holiday_peak" in prompt


def test_build_brief_prompt_handles_missing_trend_source():
    prompt = art_brief.build_brief_prompt({"niche": "monstera line art", "trend_source": None})

    assert "no trend data available" in prompt


def test_generate_art_brief_calls_anthropic_complete_and_strips_result():
    captured = {}

    def fake_complete(prompt, *, api_key=None, max_tokens=1024, model=None):
        captured["prompt"] = prompt
        captured["api_key"] = api_key
        captured["max_tokens"] = max_tokens
        captured["model"] = model
        return {"text": "  A dense mid-century modern botanical bouquet.  \n"}

    with patch("pipeline.art_brief.anthropic_client.complete", side_effect=fake_complete):
        result = art_brief.generate_art_brief(
            {"niche": "monstera line art", "trend_source": "trending_now:monstera"},
            api_key="test-key",
        )

    assert result == "A dense mid-century modern botanical bouquet."
    assert "monstera line art" in captured["prompt"]
    assert captured["api_key"] == "test-key"
    assert captured["model"] == anthropic_client.HAIKU_MODEL


def test_generate_art_brief_threads_sibling_briefs_into_prompt():
    captured = {}

    def fake_complete(prompt, *, api_key=None, max_tokens=1024, model=None):
        captured["prompt"] = prompt
        return {"text": "A distinct art deco sunburst study."}

    with patch("pipeline.art_brief.anthropic_client.complete", side_effect=fake_complete):
        art_brief.generate_art_brief(
            {"niche": "sunburst deco", "trend_source": None},
            sibling_briefs=["A sage mid-century botanical bouquet."],
        )

    assert "A sage mid-century botanical bouquet." in captured["prompt"]
