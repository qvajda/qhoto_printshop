from datetime import date

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


def test_collect_event_lookahead_returns_one_candidate_per_window():
    raw_candidates = research.collect_event_lookahead()

    assert len(raw_candidates) == len(research.EVENT_WINDOWS_2026)
    names = {raw["trend_source"] for raw in raw_candidates}
    assert "event_lookahead:holiday_peak" in names
    assert "event_lookahead:fall_cozy_aesthetic" in names


def test_classify_event_candidate_goes_when_lead_time_available():
    raw = {
        "niche": "x", "trend_source": "event_lookahead:holiday_peak", "rationale": "r",
        "window_start": date(2026, 11, 10), "window_end": date(2026, 12, 20),
        "demand_ratio": None, "listing_count": None,
    }

    result = research.classify(raw, now=date(2026, 11, 1))

    assert result == {"go_hold_kill": "go", "hold_recheck_date": None, "kill_reason": None}


def test_classify_event_candidate_holds_when_window_closed():
    raw = {
        "niche": "x", "trend_source": "event_lookahead:holiday_peak", "rationale": "r",
        "window_start": date(2026, 11, 10), "window_end": date(2026, 12, 20),
        "demand_ratio": None, "listing_count": None,
    }

    result = research.classify(raw, now=date(2026, 12, 25))

    assert result["go_hold_kill"] == "hold"
    assert result["hold_recheck_date"] == "2027-09-11"
    assert result["kill_reason"] is None


def test_classify_event_candidate_holds_when_inside_window_but_too_close_to_close():
    raw = {
        "niche": "x", "trend_source": "event_lookahead:diwali", "rationale": "r",
        "window_start": date(2026, 11, 8), "window_end": date(2026, 11, 8),
        "demand_ratio": None, "listing_count": None,
    }

    result = research.classify(raw, now=date(2026, 11, 1))

    assert result["go_hold_kill"] == "hold"
