import pipeline.primary_mockup as primary_mockup


def test_build_mockup_title_includes_niche():
    candidate = {"niche": "monstera line art"}

    title = primary_mockup.build_mockup_title(candidate)

    assert "monstera line art" in title
    assert "primary mockup" in title.lower()
