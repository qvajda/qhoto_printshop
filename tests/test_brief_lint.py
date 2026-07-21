import pipeline.brief_lint as brief_lint


def _valid_brief(**overrides):
    brief = {
        "niche": "mid-century modern botanical",
        "art_brief": (
            "A mid-century modern botanical bouquet with bold filled leaf shapes in "
            "sage and terracotta, dense full-frame composition on a warm cream ground."
        ),
    }
    brief.update(overrides)
    return brief


def test_lint_brief_passes_a_well_formed_brief():
    assert brief_lint.lint_brief(_valid_brief()) == []


def test_lint_brief_flags_missing_niche():
    errors = brief_lint.lint_brief(_valid_brief(niche=""))
    assert any("niche" in e for e in errors)


def test_lint_brief_flags_missing_boldness_term():
    errors = brief_lint.lint_brief(_valid_brief(art_brief="A quiet sage and terracotta scene on cream."))
    assert any("boldness" in e for e in errors)


def test_lint_brief_flags_missing_palette():
    errors = brief_lint.lint_brief(_valid_brief(
        art_brief="A bold filled botanical bouquet, dense full-frame composition on a warm cream ground."
    ))
    assert any("palette" in e for e in errors)


def test_lint_brief_flags_empty_text_without_crashing():
    errors = brief_lint.lint_brief(_valid_brief(art_brief=""))
    assert any("art_brief text" in e for e in errors)


def test_lint_batch_passes_a_diverse_batch():
    briefs = [
        _valid_brief(niche="a", art_brief="Bold filled sage botanical dense full-frame, no backdrop."),
        _valid_brief(niche="b", art_brief="Confident medium-weight terracotta line art, arch backdrop, dense composition."),
        _valid_brief(niche="c", art_brief="Bold filled burnt orange sunburst, wash backdrop, dense full-frame."),
    ]
    assert brief_lint.lint_batch(briefs) == []


def test_lint_batch_rejects_more_than_two_briefs_sharing_a_backdrop_device():
    briefs = [
        _valid_brief(niche=str(i), art_brief=f"Bold filled sage botanical #{i}, circle backdrop, dense full-frame.")
        for i in range(3)
    ]
    errors = brief_lint.lint_batch(briefs)
    assert any("backdrop device 'circle'" in e for e in errors)


def test_lint_batch_rejects_more_than_two_briefs_sharing_a_palette_family():
    briefs = [
        _valid_brief(niche=str(i), art_brief=f"Bold filled sage and olive botanical #{i}, dense full-frame, no backdrop.")
        for i in range(3)
    ]
    errors = brief_lint.lint_batch(briefs)
    assert any("palette family 'neutral'" in e for e in errors)


def test_lint_batch_does_not_count_absent_backdrop_or_unknown_palette_towards_diversity():
    briefs = [
        _valid_brief(niche=str(i), art_brief=f"Bold filled sage botanical #{i}, dense full-frame, no backdrop shape.")
        for i in range(3)
    ]
    # All three share palette family 'neutral' (sage) -> that IS a real conflict,
    # so use only the "none" backdrop device to isolate the "none is never
    # counted as a shared device" behavior.
    errors = brief_lint.lint_batch(briefs)
    assert not any("backdrop device 'none'" in e for e in errors)


def test_assert_batch_valid_raises_on_bad_batch():
    briefs = [{"niche": "x", "art_brief": ""}]
    try:
        brief_lint.assert_batch_valid(briefs)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "art_brief text" in str(exc)


def test_assert_batch_valid_is_a_noop_on_a_clean_batch():
    briefs = [_valid_brief()]
    brief_lint.assert_batch_valid(briefs)  # must not raise
