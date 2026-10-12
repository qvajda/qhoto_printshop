"""#262: scripts/retaxonomy_live_listings.py - preview never writes, apply PATCHes only the
differing ids, a read-back mismatch fails the run, --to 1027 targets the old id."""
import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pipeline.db as db

_SPEC = importlib.util.spec_from_file_location(
    "retaxonomy_live_listings", Path(__file__).resolve().parents[1] / "scripts" / "retaxonomy_live_listings.py"
)
retax = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(retax)

PROPS = [{"name": "Framing", "property_id": 145330288558, "value_id": 2342, "value": "Unframed"}]


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


def _run(conn, live, *, to, apply, stuck=False):
    """live: {listing_id: taxonomy_id}; stuck=True means a PATCH is silently dropped."""
    patched, puts = [], []

    def get_listing(lid, **kw):
        return {"taxonomy_id": live[lid]}

    def update_listing(shop_id, lid, data, **kw):
        patched.append((lid, data))
        if not stuck:
            live[lid] = data["taxonomy_id"]
        return {}

    def update_property(shop_id, lid, pid, vids, vals, **kw):
        puts.append((lid, pid))

    def live_props(shop_id, lid, **kw):
        return [{"property_id": 145330288558, "value_ids": [2342]}]

    with patch.object(retax.etsy_client, "get_listing", side_effect=get_listing), \
         patch.object(retax.etsy_client, "update_listing", side_effect=update_listing), \
         patch.object(retax.etsy_client, "update_listing_property", side_effect=update_property), \
         patch.object(retax.etsy_client, "get_listing_properties", side_effect=live_props):
        errors = retax.run(conn, to=to, properties=PROPS, apply=apply, shop_id="s")
    return errors, patched, puts


def test_preview_makes_no_write(tmp_path):
    conn = _conn(tmp_path, ["1", "2"])
    errors, patched, puts = _run(conn, {"1": 1027, "2": 1027}, to=1029, apply=False)
    assert errors == [] and patched == [] and puts == []


def test_apply_patches_only_differing_ids(tmp_path):
    conn = _conn(tmp_path, ["1", "2"])
    errors, patched, puts = _run(conn, {"1": 1027, "2": 1029}, to=1029, apply=True)
    assert errors == []
    assert patched == [("1", {"taxonomy_id": 1029})]
    assert puts == [("1", 145330288558)]


def test_readback_mismatch_fails_run(tmp_path):
    conn = _conn(tmp_path, ["1"])
    errors, _, _ = _run(conn, {"1": 1027}, to=1029, apply=True, stuck=True)
    assert len(errors) == 1 and "read-back mismatch" in errors[0]


def test_to_old_id_is_the_revert(tmp_path):
    conn = _conn(tmp_path, ["1"])
    errors, patched, _ = _run(conn, {"1": 1029}, to=1027, apply=True)
    assert errors == [] and patched == [("1", {"taxonomy_id": 1027})]
