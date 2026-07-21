"""R2-e mode-B ingest seam (docs/2026-07-21-generation-quality-round2-plan.md
section 3): a human-curated batch of BRIEFS (not prompts) as a second input
method alongside mode A's autonomous research -> art_brief.py pipeline.

Design: `seed_candidates_from_briefs` inserts one `candidates` row per brief
with `art_brief` pre-filled, so `generate_for_candidate`'s existing hook
(`if not candidate.get("art_brief")`, pipeline/generate.py) skips the Haiku
brief-writing call entirely - everything downstream (scaffold, token budget,
critic, provenance) is byte-identical to mode A. Reuses
`research._insert_candidate` for the actual row-insert so the column set
always matches whatever mode A populates at candidate-creation time (no
schema duplication).

Mode B briefs are human-curated and already vetted before this function is
called (the whole point of the batch-ideation seam is a human glance before
any Replicate spend) - so every seeded row is unconditionally 'go'/'pending',
never 'hold'/'kill'. If mode B ever needs its own go/hold/kill classification,
that's a new decision, not an assumption to bake in here.
"""
from datetime import datetime

import pipeline.brief_lint as brief_lint
import pipeline.research as research


def seed_candidates_from_briefs(conn, briefs: list[dict], *, now=None) -> list[int]:
    """`briefs` is a JSON-array-shaped list of
    `{niche, trend_source, art_brief, go_hold_kill_rationale}` objects (see
    docs/deep-research-briefing-template.md for the authoring schema).
    Validates the whole batch against brief_lint.assert_batch_valid before
    inserting anything (all-or-nothing - a bad batch inserts zero rows).
    Returns the list of inserted candidate ids, in input order."""
    brief_lint.assert_batch_valid(briefs)

    now_dt = now or datetime.utcnow()
    classification = {"go_hold_kill": "go", "hold_recheck_date": None, "kill_reason": None}

    inserted_ids = []
    for brief in briefs:
        # ponytail: go_hold_kill_rationale has no dedicated candidates column
        # (mode A's own rationale field is dropped the same way in
        # research._insert_candidate - not a mode-B-specific gap). Folded
        # into trend_source rather than silently discarded; a real fix is a
        # schema column, owned by the sibling agent on generation_attempts/
        # schema.sql in this round, not this file.
        trend_source = brief["trend_source"]
        rationale = brief.get("go_hold_kill_rationale")
        if rationale:
            trend_source = f"{trend_source} | go_hold_kill_rationale: {rationale}"

        raw = {"niche": brief["niche"], "trend_source": trend_source}
        candidate_id = research._insert_candidate(conn, raw, classification, now=now_dt)
        conn.execute(
            "UPDATE candidates SET art_brief = ? WHERE id = ?",
            (brief["art_brief"], candidate_id),
        )
        conn.commit()
        inserted_ids.append(candidate_id)

    return inserted_ids


def _main():
    import argparse
    import json
    from pathlib import Path

    import pipeline.db as db

    parser = argparse.ArgumentParser(description="Seed candidates from a mode-B batch-ideation JSON file.")
    parser.add_argument("json_path", help="Path to a JSON array of {niche, trend_source, art_brief, go_hold_kill_rationale} objects")
    parser.add_argument("--db-path", default=str(Path(__file__).resolve().parent.parent / "db" / "qhoto.sqlite3"))
    args = parser.parse_args()

    briefs = json.loads(Path(args.json_path).read_text(encoding="utf-8"))
    conn = db.get_connection(args.db_path)
    db.init_db(conn)
    inserted_ids = seed_candidates_from_briefs(conn, briefs)
    print(f"Seeded {len(inserted_ids)} candidates: {inserted_ids}")


if __name__ == "__main__":
    _main()
