import json

import pipeline.db as db
import pipeline.seed_mode_b as seed_mode_b


def _briefs():
    return [
        {
            "niche": "mid-century modern botanical",
            "trend_source": "cowork_deep_research:mcm_botanical",
            "art_brief": (
                "A mid-century modern botanical bouquet with bold filled leaf shapes in "
                "sage and terracotta, dense full-frame composition on a warm cream ground."
            ),
            "go_hold_kill_rationale": "Bestseller-badge cluster observed on Etsy, BE locale.",
        },
        {
            "niche": "art deco geometric dahlia",
            "trend_source": "cowork_deep_research:deco_dahlia",
            "art_brief": (
                "An art deco geometric dahlia pattern, bold filled petals in mustard and "
                "teal, dense full-frame composition, no backdrop shape."
            ),
            "go_hold_kill_rationale": "Round-1 confirmed-good niche family, deco lane.",
        },
    ]


def _write_briefs_json(tmp_path, briefs):
    path = tmp_path / "briefs.json"
    path.write_text(json.dumps(briefs), encoding="utf-8")
    return path


def test_preview_rows_reports_niche_palette_backdrop_occupant_and_word_count():
    briefs = _briefs()
    briefs[0]["art_brief"] += " A finch tucked in the lower-left corner."
    rows = seed_mode_b._preview_rows(briefs)

    assert rows[0]["niche"] == "mid-century modern botanical"
    assert rows[0]["palette"] == "neutral"
    assert rows[0]["occupant"] == "finch"
    assert rows[0]["words"] == len(briefs[0]["art_brief"].split())

    assert rows[1]["palette"] == "saturated_retro"
    assert rows[1]["backdrop"] == "none"
    assert rows[1]["occupant"] == "none"


def test_main_dry_run_does_not_insert_and_returns_zero(tmp_path, capsys):
    briefs = _briefs()
    json_path = _write_briefs_json(tmp_path, briefs)
    db_path = tmp_path / "test.sqlite3"

    exit_code = seed_mode_b.main([str(json_path), "--db-path", str(db_path)])

    assert exit_code == 0
    assert not db_path.exists()  # nothing was ever opened/inserted
    out = capsys.readouterr().out
    assert "Dry-run only" in out
    assert "mid-century modern botanical" in out
    assert "0 error(s)" in out


def test_main_commit_inserts_via_the_existing_seam_and_prints_ids(tmp_path, capsys):
    briefs = _briefs()
    json_path = _write_briefs_json(tmp_path, briefs)
    db_path = tmp_path / "test.sqlite3"

    exit_code = seed_mode_b.main([str(json_path), "--db-path", str(db_path), "--commit"])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Committed: inserted 2 candidate(s)" in out

    conn = db.get_connection(db_path)
    rows = conn.execute("SELECT niche, art_brief FROM candidates ORDER BY id").fetchall()
    assert [r["niche"] for r in rows] == [b["niche"] for b in briefs]
    assert rows[0]["art_brief"] == briefs[0]["art_brief"]
    conn.close()


def test_main_commit_aborts_and_inserts_nothing_on_a_lint_failure(tmp_path, capsys):
    briefs = [_briefs()[0]]
    briefs[0]["art_brief"] = ""  # fails lint: empty art_brief text
    json_path = _write_briefs_json(tmp_path, briefs)
    db_path = tmp_path / "test.sqlite3"

    exit_code = seed_mode_b.main([str(json_path), "--db-path", str(db_path), "--commit"])

    assert exit_code == 1
    out = capsys.readouterr().out
    assert "commit aborted" in out

    conn = db.get_connection(db_path)
    db.init_db(conn)
    assert conn.execute("SELECT COUNT(*) AS c FROM candidates").fetchone()["c"] == 0
    conn.close()


def test_main_previews_the_real_round3_mode_b_fixture_clean(capsys):
    """Exercises the CLI against the actual owner-produced example fixture
    (docs/round3_mode_b_briefs.json) - should preview + lint clean, dry-run."""
    exit_code = seed_mode_b.main(["docs/round3_mode_b_briefs.json"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Loaded 5 brief(s)" in out
    assert "0 error(s)" in out
