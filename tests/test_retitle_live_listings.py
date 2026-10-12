"""#257: scripts/retitle_live_listings.py - preview never writes, passing titles are
skipped, the PATCH carries title only, a read-back mismatch fails the run."""
import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pipeline.db as db

_SPEC = importlib.util.spec_from_file_location(
    "retitle_live_listings", Path(__file__).resolve().parents[1] / "scripts" / "retitle_live_listings.py"
)
retitle = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(retitle)

BAD = "Vintage Eucalyptus Art Print, Botanical Wall Art, Herbarium"
GOOD = "Vintage Eucalyptus Herbarium Poster, Botanical Wall Art, Herbarium"
NEW = "Eucalyptus Botanical Poster, Wall Art, Herbarium"


def _conn(tmp_path, listing_ids):
    conn = db.get_connection(tmp_path / "t.sqlite3")
    db.init_db(conn)
    ts = "2026-07-16T09:00:00"
    for lid in listing_ids:
        cid = conn.execute(
            "INSERT INTO candidates (created_at, niche, go_hold_kill, status, base_image_url, updated_at) "
            "VALUES (?, 'n', 'go', 'primary_review', 'u', ?)", (ts, ts)).lastrowid
        gid = conn.execute(
            "INSERT INTO groups (candidate_id, group_type, status, created_at, updated_at) "
            "VALUES (?, 'primary', 'pending_review', ?, ?)", (cid, ts, ts)).lastrowid
        conn.execute(
            "INSERT INTO group_products (group_id, candidate_id, gelato_template_id, etsy_listing_id, "
            "status, created_at, updated_at) VALUES (?, ?, 'tpl', ?, 'published', ?, ?)",
            (gid, cid, lid, ts, ts))
    conn.commit()
    return conn


def _run(conn, live, *, apply, readback=None):
    """live: {listing_id: title}; readback overrides the title seen after a PATCH."""
    patched = []

    def get_listing(lid, **kw):
        return {"title": readback if (readback and lid in patched_ids) else live[lid]}

    patched_ids = set()

    def update_listing(shop_id, lid, data, **kw):
        patched.append((lid, data))
        patched_ids.add(lid)
        return {}

    with patch.object(retitle.etsy_client, "get_listing", side_effect=get_listing), \
         patch.object(retitle.etsy_client, "update_listing", side_effect=update_listing):
        errors = retitle.run(conn, apply=apply, shop_id="s", draft_fn=lambda c, cid: NEW)
    return errors, patched


def test_preview_makes_no_update_calls(tmp_path):
    errors, patched = _run(_conn(tmp_path, ["1"]), {"1": BAD}, apply=False)
    assert errors == [] and patched == []


def test_passing_title_is_skipped(tmp_path):
    errors, patched = _run(_conn(tmp_path, ["1"]), {"1": GOOD}, apply=True)
    assert errors == [] and patched == []


def test_digital_word_fails_rule():
    assert "printable" in retitle.title_rule_failed("Herb Poster Printable, Wall Art").lower()


def test_patch_payload_is_title_only(tmp_path):
    errors, patched = _run(_conn(tmp_path, ["1"]), {"1": BAD}, apply=True, readback=NEW)
    assert errors == [] and patched == [("1", {"title": NEW})]


def test_readback_mismatch_fails_run(tmp_path):
    errors, _ = _run(_conn(tmp_path, ["1"]), {"1": BAD}, apply=True, readback=BAD)
    assert len(errors) == 1 and "read-back mismatch" in errors[0]
