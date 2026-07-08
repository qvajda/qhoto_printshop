import random
from datetime import date, timedelta
from pathlib import Path

import pipeline.config as config

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
            "niche": f"botanical/minimalist wall art - {window['name']}",
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
