import pipeline.generate as generate


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
