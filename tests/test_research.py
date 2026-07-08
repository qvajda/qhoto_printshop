import pipeline.research as research


def test_load_safe_evergreen_terms_reads_all_buckets():
    terms = research.load_safe_evergreen_terms()

    assert "monstera line art" in terms
    assert "moon phase print" in terms
    assert "mid century modern wall art" in terms


def test_load_safe_evergreen_terms_excludes_non_bucket_sections():
    terms = research.load_safe_evergreen_terms()

    joined = " ".join(terms).lower()
    assert "zodiac" not in joined
    assert "printify" not in joined


def test_pick_safe_evergreen_fallback_returns_go_eligible_raw_candidate():
    class FakeRng:
        def choice(self, seq):
            return seq[0]

    raw = research.pick_safe_evergreen_fallback(rng=FakeRng())

    assert raw["niche"] == research.load_safe_evergreen_terms()[0]
    assert raw["trend_source"].startswith("safe_evergreen_fallback:")
    assert raw["window_end"] is None
    assert raw["demand_ratio"] is None
