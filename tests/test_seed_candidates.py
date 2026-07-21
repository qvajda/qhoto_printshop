from datetime import datetime

import pytest

import pipeline.db as db
import pipeline.seed_candidates as seed_candidates


def _fresh_conn(tmp_path):
    conn = db.get_connection(tmp_path / "test.sqlite3")
    db.init_db(conn)
    return conn


def _brief(**overrides):
    brief = {
        "niche": "mid-century modern botanical",
        "trend_source": "cowork_deep_research:mcm_botanical",
        "art_brief": (
            "A mid-century modern botanical bouquet with bold filled leaf shapes in "
            "sage and terracotta, dense full-frame composition on a warm cream ground."
        ),
        "go_hold_kill_rationale": "Bestseller-badge cluster observed on Etsy, BE locale.",
    }
    brief.update(overrides)
    return brief


def test_seed_candidates_from_briefs_inserts_one_row_per_brief_with_art_brief_prefilled(tmp_path):
    conn = _fresh_conn(tmp_path)
    briefs = [
        _brief(niche="a", art_brief="Bold filled sage botanical, dense full-frame, no backdrop."),
        _brief(niche="b", art_brief="Confident medium-weight terracotta line art, arch backdrop, dense composition."),
    ]

    ids = seed_candidates.seed_candidates_from_briefs(conn, briefs, now=datetime(2026, 7, 21, 9, 0, 0))

    assert len(ids) == 2
    rows = conn.execute("SELECT * FROM candidates ORDER BY id").fetchall()
    assert [r["niche"] for r in rows] == ["a", "b"]
    assert rows[0]["art_brief"] == briefs[0]["art_brief"]
    assert rows[1]["art_brief"] == briefs[1]["art_brief"]
    conn.close()


def test_seed_candidates_from_briefs_marks_rows_go_and_pending(tmp_path):
    conn = _fresh_conn(tmp_path)
    ids = seed_candidates.seed_candidates_from_briefs(conn, [_brief()], now=datetime(2026, 7, 21, 9, 0, 0))

    row = conn.execute("SELECT * FROM candidates WHERE id = ?", (ids[0],)).fetchone()
    assert row["go_hold_kill"] == "go"
    assert row["status"] == "pending"
    conn.close()


def test_seed_candidates_from_briefs_folds_rationale_into_trend_source(tmp_path):
    conn = _fresh_conn(tmp_path)
    ids = seed_candidates.seed_candidates_from_briefs(conn, [_brief()], now=datetime(2026, 7, 21, 9, 0, 0))

    row = conn.execute("SELECT * FROM candidates WHERE id = ?", (ids[0],)).fetchone()
    assert "cowork_deep_research:mcm_botanical" in row["trend_source"]
    assert "Bestseller-badge cluster observed" in row["trend_source"]
    conn.close()


def test_seed_candidates_from_briefs_lets_generate_for_candidate_skip_the_haiku_call(tmp_path):
    """The whole point of the seam: generate_for_candidate's existing hook is
    `if not candidate.get("art_brief")` - confirm a mode-B row already has a
    truthy art_brief and so trips that branch's else-path (no brief write)."""
    conn = _fresh_conn(tmp_path)
    ids = seed_candidates.seed_candidates_from_briefs(conn, [_brief()], now=datetime(2026, 7, 21, 9, 0, 0))

    row = conn.execute("SELECT * FROM candidates WHERE id = ?", (ids[0],)).fetchone()
    candidate = dict(row)
    assert not (not candidate.get("art_brief"))  # i.e. generate_for_candidate's guard is False -> skips Haiku
    conn.close()


def test_seed_candidates_from_briefs_rejects_a_batch_that_fails_lint_and_inserts_nothing(tmp_path):
    conn = _fresh_conn(tmp_path)
    briefs = [_brief(art_brief="")]

    with pytest.raises(ValueError):
        seed_candidates.seed_candidates_from_briefs(conn, briefs, now=datetime(2026, 7, 21, 9, 0, 0))

    assert conn.execute("SELECT COUNT(*) AS c FROM candidates").fetchone()["c"] == 0
    conn.close()


def test_seed_candidates_from_briefs_rejects_a_batch_with_too_little_diversity(tmp_path):
    conn = _fresh_conn(tmp_path)
    briefs = [
        _brief(niche=str(i), art_brief=f"Bold filled sage botanical #{i}, circle backdrop, dense full-frame.")
        for i in range(3)
    ]

    with pytest.raises(ValueError):
        seed_candidates.seed_candidates_from_briefs(conn, briefs, now=datetime(2026, 7, 21, 9, 0, 0))

    assert conn.execute("SELECT COUNT(*) AS c FROM candidates").fetchone()["c"] == 0
    conn.close()
