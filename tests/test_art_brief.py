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
    assert "density/coverage clause" in prompt
    assert "Mark boldness" in prompt
    assert "backdrop shape" in prompt
    assert "accent colors" in prompt
    assert "60 words" in prompt


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
