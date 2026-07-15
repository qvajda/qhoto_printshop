import random
from datetime import date, datetime, timedelta
from pathlib import Path

import pipeline.anthropic_client as anthropic_client
import pipeline.config as config
import pipeline.etsy_client as etsy_client

SAFE_EVERGREEN_BUCKET_PATH = config.REPO_ROOT / "docs" / "safe_evergreen_bucket.md"


def load_safe_evergreen_terms(path=None) -> list:
    path = Path(path) if path else SAFE_EVERGREEN_BUCKET_PATH
    lines = path.read_text(encoding="utf-8").splitlines()

    terms = []
    in_buckets_section = False
    for line in lines:
        stripped = line.strip()
        if stripped == "## Buckets":
            in_buckets_section = True
            continue
        if in_buckets_section and stripped.startswith("## "):
            break
        if not in_buckets_section or stripped.startswith("### ") or not stripped:
            continue
        terms.extend(term.strip() for term in stripped.split(","))
    return terms


def pick_safe_evergreen_fallback(*, rng=None) -> dict:
    rng = rng or random
    term = rng.choice(load_safe_evergreen_terms())
    return {
        "niche": term,
        "trend_source": f"safe_evergreen_fallback:{term}",
        "rationale": "Safe-evergreen bucket fallback - no Go candidate this cycle (docs/safe_evergreen_bucket.md).",
        "window_start": None,
        "window_end": None,
        "demand_ratio": None,
        "listing_count": None,
    }


# Rough heuristic per SPEC_v4.10.md section 3 step 1 ("Start these thresholds
# as rough manual heuristics; revisit at M3 once real data exists").
MIN_EVENT_LEAD_DAYS = 14

# Dates are this cycle's (2026-2027) concrete mapping of SPEC_v4.10.md section
# 3 step 1's event table. Diwali's date is lunar-calendar-driven and must be
# re-researched annually; the others' month/day boundaries are this plan's
# concrete interpretation of the spec's prose ranges ("late Nov", "Sept-Oct")
# and should be refreshed monthly per the spec's own instruction.
EVENT_WINDOWS_2026 = [
    {
        "name": "fall_cozy_aesthetic",
        "start": date(2026, 9, 1),
        "end": date(2026, 10, 31),
        "niche_note": "Strong for nature/botanical specifically",
    },
    {
        "name": "holiday_peak",
        "start": date(2026, 11, 10),
        "end": date(2026, 12, 20),
        "niche_note": "Biggest window overall",
    },
    {
        "name": "diwali",
        "start": date(2026, 11, 8),
        "end": date(2026, 11, 8),
        "niche_note": "Cultural gifting/home decor",
    },
    {
        "name": "black_friday_cyber_monday",
        "start": date(2026, 11, 27),
        "end": date(2026, 11, 30),
        "niche_note": "General gift-shopping surge",
    },
    {
        "name": "engagement_season",
        "start": date(2026, 11, 21),
        "end": date(2027, 2, 14),
        "niche_note": "Gift/registry shopping, first home decor",
    },
    {
        "name": "new_year_refresh",
        "start": date(2027, 1, 1),
        "end": date(2027, 1, 31),
        "niche_note": "Self-purchase redecorating",
    },
]


def collect_event_lookahead() -> list:
    return [
        {
            "niche": f"botanical/minimalist nature illustration - {window['name']}",
            "trend_source": f"event_lookahead:{window['name']}",
            "rationale": window["niche_note"],
            "window_start": window["start"],
            "window_end": window["end"],
            "demand_ratio": None,
            "listing_count": None,
        }
        for window in EVENT_WINDOWS_2026
    ]


def classify(raw: dict, *, now=None) -> dict:
    now = now or date.today()
    if raw.get("window_end") is not None:
        return _classify_by_timing(raw, now)
    if raw.get("demand_ratio") is not None:
        return _classify_by_demand(raw)
    return {"go_hold_kill": "go", "hold_recheck_date": None, "kill_reason": None}


def _classify_by_timing(raw: dict, now: date) -> dict:
    days_until_close = (raw["window_end"] - now).days
    if days_until_close >= MIN_EVENT_LEAD_DAYS:
        return {"go_hold_kill": "go", "hold_recheck_date": None, "kill_reason": None}

    next_year_start = date(raw["window_start"].year + 1, raw["window_start"].month, raw["window_start"].day)
    recheck_date = next_year_start - timedelta(days=60)
    return {"go_hold_kill": "hold", "hold_recheck_date": recheck_date.isoformat(), "kill_reason": None}


# Rough heuristic per SPEC_v4.10.md section 3 step 1 ("a keyword with very
# high competition and no differentiation angle" / "revisit at M3").
KILL_DEMAND_RATIO_THRESHOLD = 0.002

TRENDING_NOW_PROMPT = (
    "You are researching Etsy trends for a shop selling AI-generated botanical/minimalist "
    "wall art and posters. Using web search, identify 3-5 currently trending or rising search "
    "keywords/niches on Etsy that fit this niche (nature, botanical, minimalist landscape wall "
    "art). For each, give a short keyword phrase suitable for an Etsy search and a one-sentence "
    "rationale. Reply with ONLY a JSON list of objects with 'keyword' and 'rationale' fields, "
    "no other text."
)


def _classify_by_demand(raw: dict) -> dict:
    if raw["demand_ratio"] < KILL_DEMAND_RATIO_THRESHOLD:
        return {
            "go_hold_kill": "kill",
            "hold_recheck_date": None,
            "kill_reason": (
                f"demand_ratio {raw['demand_ratio']:.6f} below threshold "
                f"{KILL_DEMAND_RATIO_THRESHOLD} (listing_count={raw['listing_count']})"
            ),
        }
    return {"go_hold_kill": "go", "hold_recheck_date": None, "kill_reason": None}


def _build_demand_checked_candidate(keyword: str, rationale: str, source_label: str, *,
                                     etsy_api_key=None, etsy_api_secret=None) -> dict:
    demand = etsy_client.find_all_listings_active(
        keyword, limit=10, sort_on="favorites", sort_order="desc",
        api_key=etsy_api_key, api_secret=etsy_api_secret,
    )
    listing_count = demand["count"]
    results = demand["results"]
    avg_favorers = (sum(r["num_favorers"] for r in results) / len(results)) if results else 0.0
    demand_ratio = (avg_favorers / listing_count) if listing_count else 0.0
    return {
        "niche": keyword,
        "trend_source": f"{source_label}:{keyword}",
        "rationale": rationale,
        "window_start": None,
        "window_end": None,
        "demand_ratio": demand_ratio,
        "listing_count": listing_count,
    }


def collect_trending_now(*, anthropic_api_key=None, etsy_api_key=None, etsy_api_secret=None) -> list:
    search_result = anthropic_client.research_web_search(TRENDING_NOW_PROMPT, api_key=anthropic_api_key)
    keyword_ideas = anthropic_client.parse_json_response(search_result["text"])
    return [
        _build_demand_checked_candidate(
            idea["keyword"], idea["rationale"], "trending_now",
            etsy_api_key=etsy_api_key, etsy_api_secret=etsy_api_secret,
        )
        for idea in keyword_ideas
    ]


def collect_on_demand(topic: str, *, etsy_api_key=None, etsy_api_secret=None) -> dict:
    return _build_demand_checked_candidate(
        topic, "Requested via Telegram /research command", "telegram_on_demand",
        etsy_api_key=etsy_api_key, etsy_api_secret=etsy_api_secret,
    )


def _insert_candidate(conn, raw: dict, classification: dict, *, now=None) -> int:
    now = now or datetime.utcnow()
    timestamp = now.isoformat()
    status = "pending" if classification["go_hold_kill"] == "go" else "abandoned"

    cursor = conn.execute(
        """
        INSERT INTO candidates (
            created_at, niche, trend_source, go_hold_kill, hold_recheck_date,
            kill_reason, status, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            timestamp, raw["niche"], raw["trend_source"], classification["go_hold_kill"],
            classification["hold_recheck_date"], classification["kill_reason"], status, timestamp,
        ),
    )
    conn.commit()
    return cursor.lastrowid


def run_research_cycle(conn, static_config, *, on_demand_topics=None, now=None) -> list:
    now_dt = datetime.combine(now, datetime.min.time()) if now else datetime.utcnow()
    today = now_dt.date()
    on_demand_topics = on_demand_topics or []

    raw_candidates = collect_event_lookahead()
    raw_candidates += collect_trending_now()
    for topic in on_demand_topics:
        raw_candidates.append(collect_on_demand(topic))

    inserted_ids = []
    any_go = False
    for raw in raw_candidates:
        classification = classify(raw, now=today)
        if classification["go_hold_kill"] == "go":
            any_go = True
        inserted_ids.append(_insert_candidate(conn, raw, classification, now=now_dt))

    if not any_go:
        fallback_raw = pick_safe_evergreen_fallback()
        fallback_classification = classify(fallback_raw, now=today)
        inserted_ids.append(_insert_candidate(conn, fallback_raw, fallback_classification, now=now_dt))

    return inserted_ids


def trigger_fallback_if_needed(conn, *, now=None) -> int:
    other_alive = conn.execute(
        "SELECT 1 FROM candidates WHERE status NOT IN ('failed', 'abandoned', 'completed') LIMIT 1"
    ).fetchone()
    if other_alive is not None:
        return None

    fallback_raw = pick_safe_evergreen_fallback()
    classification = classify(fallback_raw, now=(now.date() if now else date.today()))
    return _insert_candidate(conn, fallback_raw, classification, now=now)
