import json
from datetime import date, datetime
from unittest.mock import patch

import pipeline.db as db
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


def test_collect_on_demand_returns_single_demand_checked_candidate():
    def fake_find_listings(keywords, **kwargs):
        assert keywords == "coastal minimalist print"
        return {"count": 500, "results": [{"num_favorers": 2}]}

    with patch("pipeline.research.etsy_client.find_all_listings_active", side_effect=fake_find_listings):
        raw = research.collect_on_demand("coastal minimalist print")

    assert raw["niche"] == "coastal minimalist print"
    assert raw["trend_source"] == "telegram_on_demand:coastal minimalist print"
    assert raw["listing_count"] == 500
    assert raw["demand_ratio"] == 2 / 500


def _fresh_conn(tmp_path):
    conn = db.get_connection(tmp_path / "test.sqlite3")
    db.init_db(conn)
    return conn


def test_insert_candidate_writes_go_row_as_pending(tmp_path):
    conn = _fresh_conn(tmp_path)
    raw = {"niche": "monstera line art", "trend_source": "trending_now:monstera line art"}
    classification = {"go_hold_kill": "go", "hold_recheck_date": None, "kill_reason": None}

    candidate_id = research._insert_candidate(conn, raw, classification, now=datetime(2026, 7, 8, 10, 0, 0))

    row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    assert row["niche"] == "monstera line art"
    assert row["go_hold_kill"] == "go"
    assert row["status"] == "pending"
    assert row["created_at"] == "2026-07-08T10:00:00"
    conn.close()


def test_insert_candidate_writes_hold_row_as_abandoned(tmp_path):
    conn = _fresh_conn(tmp_path)
    raw = {"niche": "holiday design", "trend_source": "event_lookahead:holiday_peak"}
    classification = {"go_hold_kill": "hold", "hold_recheck_date": "2027-09-11", "kill_reason": None}

    candidate_id = research._insert_candidate(conn, raw, classification, now=datetime(2026, 7, 8, 10, 0, 0))

    row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    assert row["go_hold_kill"] == "hold"
    assert row["hold_recheck_date"] == "2027-09-11"
    assert row["status"] == "abandoned"
    conn.close()


def test_insert_candidate_writes_kill_row_as_abandoned_with_reason(tmp_path):
    conn = _fresh_conn(tmp_path)
    raw = {"niche": "saturated term", "trend_source": "trending_now:saturated term"}
    classification = {"go_hold_kill": "kill", "hold_recheck_date": None, "kill_reason": "demand_ratio too low"}

    candidate_id = research._insert_candidate(conn, raw, classification, now=datetime(2026, 7, 8, 10, 0, 0))

    row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    assert row["go_hold_kill"] == "kill"
    assert row["kill_reason"] == "demand_ratio too low"
    assert row["status"] == "abandoned"
    conn.close()


def test_run_research_cycle_writes_all_collected_candidates(tmp_path):
    conn = _fresh_conn(tmp_path)

    def fake_web_search(prompt, api_key=None, max_tokens=2048):
        return {"text": json.dumps([{"keyword": "monstera line art", "rationale": "rising"}]), "raw": {}}

    def fake_find_listings(keywords, **kwargs):
        return {"count": 1000, "results": [{"num_favorers": 50}]}  # ratio 0.05, well above threshold -> go

    with patch("pipeline.research.anthropic_client.research_web_search", side_effect=fake_web_search), \
         patch("pipeline.research.etsy_client.find_all_listings_active", side_effect=fake_find_listings):
        inserted_ids = research.run_research_cycle(conn, {}, now=date(2026, 9, 1))

    rows = conn.execute("SELECT * FROM candidates").fetchall()
    assert len(rows) == len(inserted_ids)
    assert len(rows) == len(research.EVENT_WINDOWS_2026) + 1  # 6 event candidates + 1 trending-now
    conn.close()


def test_run_research_cycle_includes_on_demand_topics(tmp_path):
    conn = _fresh_conn(tmp_path)

    def fake_web_search(prompt, api_key=None, max_tokens=2048):
        return {"text": "[]", "raw": {}}

    def fake_find_listings(keywords, **kwargs):
        return {"count": 1000, "results": [{"num_favorers": 50}]}

    with patch("pipeline.research.anthropic_client.research_web_search", side_effect=fake_web_search), \
         patch("pipeline.research.etsy_client.find_all_listings_active", side_effect=fake_find_listings):
        research.run_research_cycle(conn, {}, on_demand_topics=["desert minimalist art"], now=date(2026, 9, 1))

    row = conn.execute(
        "SELECT * FROM candidates WHERE trend_source = ?", ("telegram_on_demand:desert minimalist art",)
    ).fetchone()
    assert row is not None
    assert row["go_hold_kill"] == "go"
    conn.close()


def test_run_research_cycle_falls_back_to_safe_evergreen_when_nothing_goes(tmp_path):
    conn = _fresh_conn(tmp_path)

    def fake_web_search(prompt, api_key=None, max_tokens=2048):
        return {"text": "[]", "raw": {}}

    with patch("pipeline.research.anthropic_client.research_web_search", side_effect=fake_web_search):
        # now chosen so every event window (including engagement_season, which runs
        # to 2027-02-14 - the latest end date of any window) is within MIN_EVENT_LEAD_DAYS
        # of closing or already closed
        inserted_ids = research.run_research_cycle(conn, {}, now=date(2027, 2, 10))

    rows = conn.execute("SELECT * FROM candidates WHERE go_hold_kill = 'go'").fetchall()
    assert len(rows) == 1
    assert rows[0]["trend_source"].startswith("safe_evergreen_fallback:")
    assert len(inserted_ids) == len(research.EVENT_WINDOWS_2026) + 1  # events (all hold) + 1 fallback
    conn.close()
