import random
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
