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


# R3-c: boldness false-positive fix - families of phrases, not one literal substring.


def test_lint_brief_accepts_reordered_bold_filled_phrasing():
    errors = brief_lint.lint_brief(_valid_brief(
        art_brief="A sage and terracotta botanical, filled and bold leaf shapes, dense full-frame composition on cream."
    ))
    assert not any("boldness" in e for e in errors)


def test_lint_brief_accepts_medium_weight_lines_without_the_word_confident():
    errors = brief_lint.lint_brief(_valid_brief(
        art_brief="A sage and terracotta botanical rendered in clean medium-weight lines, dense full-frame composition on cream."
    ))
    assert not any("boldness" in e for e in errors)


def test_lint_brief_still_flags_a_brief_with_no_boldness_language_at_all():
    errors = brief_lint.lint_brief(_valid_brief(art_brief="A quiet sage and terracotta scene on cream, dense full-frame."))
    assert any("boldness" in e for e in errors)


# R3-c: diversity caps scale with batch size - a 5/5 palette split on N=10 must lint clean.


def test_lint_batch_admits_an_ideal_5_5_palette_split_on_ten_briefs():
    neutral = [
        _valid_brief(niche=f"n{i}", art_brief=f"Bold filled sage and olive botanical #{i}, dense full-frame, no backdrop.")
        for i in range(5)
    ]
    saturated = [
        _valid_brief(niche=f"s{i}", art_brief=f"Bold filled mustard and teal botanical #{i}, dense full-frame, no backdrop.")
        for i in range(5)
    ]
    errors = brief_lint.lint_batch(neutral + saturated)
    assert not any("palette family" in e for e in errors)


def test_lint_batch_still_rejects_a_lopsided_palette_split_on_ten_briefs():
    briefs = [
        _valid_brief(niche=f"n{i}", art_brief=f"Bold filled sage and olive botanical #{i}, dense full-frame, no backdrop.")
        for i in range(7)
    ] + [
        _valid_brief(niche=f"s{i}", art_brief=f"Bold filled mustard and teal botanical #{i}, dense full-frame, no backdrop.")
        for i in range(3)
    ]
    errors = brief_lint.lint_batch(briefs)
    assert any("palette family 'neutral'" in e for e in errors)


# R3-c FM-8: geometric shape-words describing a gap/opening -> error; "circle" excluded.


def test_lint_brief_flags_triangle_gap_geometry():
    errors = brief_lint.lint_brief(_valid_brief(
        art_brief="Bold filled fern and blooms in sage and terracotta, a ladybug in the triangle gap between fronds."
    ))
    assert any("FM-8" in e for e in errors)


def test_lint_brief_flags_rectangular_opening_geometry():
    errors = brief_lint.lint_brief(_valid_brief(
        art_brief="Bold filled stem study in sage and terracotta, a beetle inside a rectangular opening in the leaves."
    ))
    assert any("FM-8" in e for e in errors)


def test_lint_brief_does_not_flag_circle_as_a_shape_word_for_gap():
    errors = brief_lint.lint_brief(_valid_brief(
        art_brief="Bold filled desert mesa in terracotta and sage, a sun disc circle behind the peak, dense full-frame."
    ))
    assert not any("FM-8" in e for e in errors)


def test_lint_brief_does_not_flag_triangle_used_as_a_described_object_not_a_gap():
    errors = brief_lint.lint_brief(_valid_brief(
        art_brief="Bold filled art deco pattern in sage and terracotta, a triangle motif repeated along the border, dense full-frame."
    ))
    assert not any("FM-8" in e for e in errors)


# R3-c FM-10: batch-level backdrop-device floor/ceiling warning, N >= 6 only.


def test_lint_batch_warnings_flags_zero_backdrop_devices_on_a_batch_of_ten():
    briefs = [
        _valid_brief(niche=str(i), art_brief=f"Bold filled sage botanical #{i}, dense full-frame, no backdrop shape.")
        for i in range(10)
    ]
    warnings = brief_lint.lint_batch_warnings(briefs)
    assert any("FM-10" in w and "0/10" in w for w in warnings)


def test_lint_batch_warnings_flags_backdrop_device_overuse_on_a_batch_of_ten():
    briefs = [
        _valid_brief(niche=str(i), art_brief=f"Bold filled sage botanical #{i}, circle backdrop, dense full-frame.")
        if i < 8
        else _valid_brief(niche=str(i), art_brief=f"Bold filled terracotta botanical #{i}, dense full-frame, no backdrop.")
        for i in range(10)
    ]
    warnings = brief_lint.lint_batch_warnings(briefs)
    assert any("FM-10" in w and "8/10" in w for w in warnings)


def test_lint_batch_warnings_skips_the_fm10_check_below_six_briefs():
    briefs = [
        _valid_brief(niche=str(i), art_brief=f"Bold filled sage botanical #{i}, dense full-frame, no backdrop shape.")
        for i in range(5)
    ]
    warnings = brief_lint.lint_batch_warnings(briefs)
    assert not any("FM-10" in w for w in warnings)


# R3-c FM-9: stem/bouquet/herbarium-native briefs missing a bottom-edge/grounding clause -> warning.


def test_lint_brief_warnings_flags_a_bouquet_brief_with_no_grounding_clause():
    warnings = brief_lint.lint_brief_warnings(_valid_brief(
        niche="wildflower bouquet",
        art_brief="Bold filled wildflower bouquet in sage and terracotta, dense full-frame composition on cream.",
    ))
    assert any("FM-9" in w for w in warnings)


def test_lint_brief_warnings_does_not_flag_a_bouquet_brief_that_states_bottom_edge_grounding():
    warnings = brief_lint.lint_brief_warnings(_valid_brief(
        niche="wildflower bouquet",
        art_brief="Bold filled wildflower bouquet, stems rooted at and running off the bottom edge, sage and terracotta on cream.",
    ))
    assert not any("FM-9" in w for w in warnings)


def test_lint_brief_warnings_does_not_flag_a_non_stem_native_niche():
    warnings = brief_lint.lint_brief_warnings(_valid_brief(
        niche="art deco geometric",
        art_brief="Bold filled art deco sunburst in terracotta and sage, dense full-frame composition on cream.",
    ))
    assert not any("FM-9" in w for w in warnings)
