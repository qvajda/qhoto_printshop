import sqlite3

import migrate_generation_attempts_table as migration


def _old_schema_db_with_candidates(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE candidates (
          id INTEGER PRIMARY KEY,
          created_at TEXT NOT NULL,
          niche TEXT NOT NULL,
          go_hold_kill TEXT NOT NULL,
          status TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          art_brief TEXT,
          base_replicate_prediction_id TEXT
        )
        """
    )
    timestamp = "2026-07-20T09:00:00"
    for candidate_id in range(1, 15):
        has_brief = candidate_id >= 5
        conn.execute(
            """
            INSERT INTO candidates (
                id, created_at, niche, go_hold_kill, status, updated_at, art_brief,
                base_replicate_prediction_id
            ) VALUES (?, ?, ?, 'go', 'completed', ?, ?, ?)
            """,
            (
                candidate_id, timestamp, f"niche {candidate_id}", timestamp,
                f"A dense brief for niche {candidate_id}." if has_brief else None,
                f"pred-{candidate_id}" if has_brief else None,
            ),
        )
    conn.commit()
    return conn


def test_migrate_creates_table_on_old_schema(tmp_path):
    db_path = tmp_path / "old.sqlite3"
    conn = _old_schema_db_with_candidates(db_path)
    conn.close()

    migration.migrate(db_path)

    conn = sqlite3.connect(db_path)
    tables = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()}
    assert "generation_attempts" in tables
    conn.close()


def test_migrate_backfills_candidates_5_through_14_only(tmp_path):
    db_path = tmp_path / "old.sqlite3"
    conn = _old_schema_db_with_candidates(db_path)
    conn.close()

    result = migration.migrate(db_path)

    assert result["backfilled_candidate_ids"] == list(range(5, 15))

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM generation_attempts ORDER BY candidate_id").fetchall()
    assert len(rows) == 10
    for row in rows:
        assert row["candidate_id"] in range(5, 15)
        assert row["attempt_number"] == 1
        assert row["correction_note"] is None
        assert row["brief_template_version"] == migration.BACKFILL_VERSION_TAG
        assert row["scaffold_version"] == migration.BACKFILL_VERSION_TAG
        assert row["model"] == "black-forest-labs/flux-schnell"
        assert row["art_brief_snapshot"] in row["prompt_text"]
        assert row["prediction_id"] == f"pred-{row['candidate_id']}"
    # Candidates 1-4 have no art_brief -> nothing recoverable, correctly skipped.
    no_brief_rows = conn.execute(
        "SELECT * FROM generation_attempts WHERE candidate_id < 5"
    ).fetchall()
    assert no_brief_rows == []
    conn.close()


def test_migrate_is_idempotent(tmp_path):
    db_path = tmp_path / "old.sqlite3"
    conn = _old_schema_db_with_candidates(db_path)
    conn.close()

    migration.migrate(db_path)
    second_result = migration.migrate(db_path)

    assert second_result["backfilled_candidate_ids"] == []
    conn = sqlite3.connect(db_path)
    count = conn.execute("SELECT COUNT(*) FROM generation_attempts").fetchone()[0]
    assert count == 10
    conn.close()
