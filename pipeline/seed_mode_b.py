"""R3-d Cowork seam-population CLI (docs/2026-07-21-generation-quality-round3-plan.md
section 3). Thin wrapper around the EXISTING mode-B insert seam
(`pipeline.seed_candidates.seed_candidates_from_briefs`, shipped round 2) -
this file never forks the insert path, it only adds a preview + dry-run-by-
default layer in front of it.

Usage:
    python -m pipeline.seed_mode_b docs/round3_mode_b_briefs.json
    python -m pipeline.seed_mode_b docs/round3_mode_b_briefs.json --commit

Reads a deep-research briefs JSON file (see docs/round3_mode_b_briefs.json
for a concrete real example / test fixture, and
docs/deep-research-briefing-template.md for the authoring schema), lints it
with the shared pipeline.brief_lint gate, prints a human-readable preview
table + all lint findings (errors AND warnings), then STOPS. Per CLAUDE.md's
reversibility policy ("use dry-run flags where available while iterating"),
dry-run is the default; insertion only happens with an explicit --commit,
which calls seed_candidates_from_briefs (all-or-nothing insert, hard lint
via assert_batch_valid - a batch with lint ERRORS inserts nothing).
"""
import argparse
import json
from pathlib import Path

import pipeline.brief_lint as brief_lint
import pipeline.db as db
import pipeline.seed_candidates as seed_candidates

# Small curated list for the preview table's "occupant summary" column - not
# a mandatory-field check, just a human-readable eyeball aid. "none" if no
# known occupant noun appears in the brief text.
OCCUPANT_KEYWORDS = (
    "moth", "dragonfly", "ladybug", "butterfly", "beetle", "seabird",
    "swallow", "finch", "bee", "hummingbird", "dove", "bird",
)


def _occupant_summary(text: str) -> str:
    lowered = text.lower()
    for word in OCCUPANT_KEYWORDS:
        if word in lowered:
            return word
    return "none"


def _preview_rows(briefs: list) -> list:
    rows = []
    for brief in briefs:
        text = brief.get("art_brief") or ""
        rows.append(
            {
                "niche": brief.get("niche", "?"),
                "palette": brief_lint._detect_palette_family(text),
                "backdrop": brief_lint._detect_backdrop_device(text),
                "occupant": _occupant_summary(text),
                "words": len(text.split()),
            }
        )
    return rows


def _print_preview(briefs: list) -> None:
    rows = _preview_rows(briefs)
    header = f"{'niche':<40} {'palette':<16} {'backdrop':<10} {'occupant':<12} {'words':>5}"
    print(header)
    print("-" * len(header))
    for row in rows:
        print(f"{row['niche']:<40} {row['palette']:<16} {row['backdrop']:<10} {row['occupant']:<12} {row['words']:>5}")


def _print_findings(briefs: list) -> list:
    """Prints errors + warnings, returns the error list (empty if clean)."""
    errors = brief_lint.lint_batch(briefs)
    warnings = brief_lint.lint_batch_warnings(briefs)
    print(f"\nlint: {len(errors)} error(s), {len(warnings)} warning(s)")
    for err in errors:
        print(f"  ERROR: {err}")
    for warn in warnings:
        print(f"  WARNING: {warn}")
    return errors


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Preview and (optionally) seed a mode-B briefs batch into the candidates table."
    )
    parser.add_argument("json_path", help="Path to a JSON array of {niche, trend_source, art_brief, go_hold_kill_rationale} objects")
    parser.add_argument("--commit", action="store_true", help="Actually insert the batch (default: dry-run preview only)")
    parser.add_argument("--db-path", default=str(Path(__file__).resolve().parent.parent / "db" / "qhoto.sqlite3"))
    args = parser.parse_args(argv)

    briefs = json.loads(Path(args.json_path).read_text(encoding="utf-8"))

    print(f"Loaded {len(briefs)} brief(s) from {args.json_path}\n")
    _print_preview(briefs)
    _print_findings(briefs)

    if not args.commit:
        print("\nDry-run only - no rows inserted. Re-run with --commit to insert.")
        return 0

    conn = db.get_connection(args.db_path)
    db.init_db(conn)
    try:
        inserted_ids = seed_candidates.seed_candidates_from_briefs(conn, briefs)
    except ValueError as exc:
        print(f"\nERROR: commit aborted, batch failed lint:\n{exc}")
        return 1
    finally:
        conn.close()

    print(f"\nCommitted: inserted {len(inserted_ids)} candidate(s): {inserted_ids}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
