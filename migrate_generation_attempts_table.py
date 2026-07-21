"""One-off: create the generation_attempts table (R2-c,
docs/2026-07-21-generation-quality-round2-plan.md) on an existing DB whose
schema predates it, and backfill what's recoverable for the round-1
validation batch (candidates 5-14): their art_brief is already stored on
candidates.art_brief, and no correction notes fired during that batch (per
the plan's §1 scorecard), so prompt_text is reconstructable as
brief + the CURRENT scaffold text at backfill time. Safe to run against any
DB, any number of times - table creation and backfill are both idempotent.
"""
import sqlite3
import sys
from pathlib import Path

import pipeline.generate as generate
import pipeline.replicate_client as replicate_client

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "db" / "qhoto.sqlite3"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS generation_attempts (
  id INTEGER PRIMARY KEY,
  candidate_id INTEGER NOT NULL REFERENCES candidates(id),
  attempt_number INTEGER NOT NULL,
  prompt_text TEXT NOT NULL,
  art_brief_snapshot TEXT NOT NULL,
  correction_note TEXT,
  brief_template_version TEXT NOT NULL,
  scaffold_version TEXT NOT NULL,
  model TEXT NOT NULL,
  prediction_id TEXT,
  created_at TEXT NOT NULL,
  UNIQUE(candidate_id, attempt_number)
)
"""

# Round-1 validation batch (docs/2026-07-20-execution-steps-1-4-kickoff.md,
# round-2 plan §1): candidates 5-14, base artwork only, no correction notes
# fired. "pre-v1" (not "v1") because this batch ran before
# art_brief.BRIEF_TEMPLATE_VERSION / generate.SCAFFOLD_VERSION existed at
# all - it's not the same template/scaffold text "v1" now names, just the
# closest queryable label for "predates versioning".
BACKFILL_CANDIDATE_IDS = range(5, 15)
BACKFILL_VERSION_TAG = "pre-v1"
BACKFILL_TIMESTAMP = "2026-07-21T00:00:00"


def migrate(db_path) -> dict:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(CREATE_TABLE_SQL)
        conn.commit()
        backfilled = _backfill(conn)
        return {"backfilled_candidate_ids": backfilled}
    finally:
        conn.close()


def _backfill(conn) -> list:
    backfilled = []
    for candidate_id in BACKFILL_CANDIDATE_IDS:
        already_logged = conn.execute(
            "SELECT 1 FROM generation_attempts WHERE candidate_id = ? AND attempt_number = 1",
            (candidate_id,),
        ).fetchone()
        if already_logged:
            continue
        row = conn.execute(
            "SELECT art_brief, base_replicate_prediction_id FROM candidates WHERE id = ?",
            (candidate_id,),
        ).fetchone()
        if row is None or not row["art_brief"]:
            continue
        prompt_text = generate.build_prompt({"art_brief": row["art_brief"]})
        conn.execute(
            """
            INSERT INTO generation_attempts (
                candidate_id, attempt_number, prompt_text, art_brief_snapshot, correction_note,
                brief_template_version, scaffold_version, model, prediction_id, created_at
            ) VALUES (?, 1, ?, ?, NULL, ?, ?, ?, ?, ?)
            """,
            (
                candidate_id, prompt_text, row["art_brief"], BACKFILL_VERSION_TAG, BACKFILL_VERSION_TAG,
                replicate_client.FLUX_SCHNELL_MODEL, row["base_replicate_prediction_id"],
                BACKFILL_TIMESTAMP,
            ),
        )
        backfilled.append(candidate_id)
    conn.commit()
    return backfilled


def main():
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB_PATH
    result = migrate(db_path)
    if result["backfilled_candidate_ids"]:
        ids = ", ".join(str(i) for i in result["backfilled_candidate_ids"])
        print(f"backfilled {len(result['backfilled_candidate_ids'])} candidate(s): {ids}")
    else:
        print("no candidates backfilled (already present or no art_brief stored)")


if __name__ == "__main__":
    main()
