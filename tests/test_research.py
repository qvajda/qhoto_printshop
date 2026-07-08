import json
from datetime import date
from unittest.mock import patch

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


def test_classify_demand_candidate_goes_when_ratio_above_threshold():
    raw = {
        "niche": "x", "trend_source": "trending_now:x", "rationale": "r",
        "window_start": None, "window_end": None,
        "demand_ratio": research.KILL_DEMAND_RATIO_THRESHOLD * 10, "listing_count": 1000,
    }

    result = research.classify(raw)

    assert result == {"go_hold_kill": "go", "hold_recheck_date": None, "kill_reason": None}


def test_classify_demand_candidate_kills_when_ratio_below_threshold():
    raw = {
        "niche": "x", "trend_source": "trending_now:x", "rationale": "r",
        "window_start": None, "window_end": None,
        "demand_ratio": research.KILL_DEMAND_RATIO_THRESHOLD / 10, "listing_count": 1000,
    }

    result = research.classify(raw)

    assert result["go_hold_kill"] == "kill"
    assert result["hold_recheck_date"] is None
    assert "1000" in result["kill_reason"]


def test_collect_trending_now_combines_web_search_and_demand_proxy():
    search_response = json.dumps([
        {"keyword": "monstera line art", "rationale": "rising interest"},
        {"keyword": "moon phase print", "rationale": "steady evergreen demand"},
    ])

    def fake_web_search(prompt, api_key=None, max_tokens=2048):
        return {"text": search_response, "raw": {}}

    def fake_find_listings(keywords, **kwargs):
        return {
            "count": 1000,
            "results": [{"num_favorers": 5}, {"num_favorers": 15}],
        }

    with patch("pipeline.research.anthropic_client.research_web_search", side_effect=fake_web_search), \
         patch("pipeline.research.etsy_client.find_all_listings_active", side_effect=fake_find_listings):
        raw_candidates = research.collect_trending_now()

    assert len(raw_candidates) == 2
    assert raw_candidates[0]["niche"] == "monstera line art"
    assert raw_candidates[0]["trend_source"] == "trending_now:monstera line art"
    assert raw_candidates[0]["listing_count"] == 1000
    assert raw_candidates[0]["demand_ratio"] == 10 / 1000
