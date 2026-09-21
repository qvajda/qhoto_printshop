import sqlite3

import pytest

import pipeline.etsy_client as etsy_client
import pipeline.listing_metrics as lm
import migrate_gl230_listing_metrics_snapshots as migration

TODAY = "2026-09-21"


@pytest.fixture
def conn(tmp_path):
    c = sqlite3.connect(tmp_path / "t.sqlite3")
    c.row_factory = sqlite3.Row
    c.executescript(
        "CREATE TABLE group_products (id INTEGER PRIMARY KEY, status TEXT, etsy_listing_id TEXT);"
        "INSERT INTO group_products VALUES (1,'published','100'),(2,'published','200'),"
        "(3,'pending',NULL),(4,'published',NULL);"
    )
    c.close()
    migration.migrate(tmp_path / "t.sqlite3")
    c = sqlite3.connect(tmp_path / "t.sqlite3")
    c.row_factory = sqlite3.Row
    return c


def _stub(monkeypatch, fail=()):
    def fake(listing_id, **kw):
        if listing_id in fail:
            raise RuntimeError("404")
        return {"listing_id": listing_id, "views": int(listing_id), "num_favorers": 2}
    monkeypatch.setattr(etsy_client, "get_listing", fake)


def _rows(conn):
    return conn.execute("SELECT * FROM listing_metrics_snapshots ORDER BY group_product_id").fetchall()


def test_writes_one_row_per_published_listing_with_null_orders(conn, monkeypatch):
    _stub(monkeypatch)
    lm.run_listing_metrics(conn, today=TODAY, dry_run_override=False)
    rows = _rows(conn)
    assert [(r["group_product_id"], r["views"], r["num_favorers"], r["orders_count"]) for r in rows] == [
        (1, 100, 2, None), (2, 200, 2, None)]


def test_second_run_same_date_writes_nothing(conn, monkeypatch):
    _stub(monkeypatch)
    lm.run_listing_metrics(conn, today=TODAY, dry_run_override=False)
    result = lm.run_listing_metrics(conn, today=TODAY, dry_run_override=False)
    assert result["selected"] == 0 and len(_rows(conn)) == 2


def test_dry_run_selects_but_writes_nothing(conn, monkeypatch):
    calls = []
    monkeypatch.setattr(etsy_client, "get_listing", lambda lid, **kw: calls.append(lid) or {"listing_id": lid, "_dry_run": True})
    result = lm.run_listing_metrics(conn, today=TODAY, dry_run_override=True)
    assert calls == ["100", "200"] and result["would_write"] == 2 and _rows(conn) == []


def test_one_failure_does_not_abort_rest_and_fails_stage_once(conn, monkeypatch):
    _stub(monkeypatch, fail=("100",))
    with pytest.raises(RuntimeError, match="100"):
        lm.run_listing_metrics(conn, today=TODAY, dry_run_override=False)
    assert [r["group_product_id"] for r in _rows(conn)] == [2]


def test_migration_nullable_unique_and_idempotent(tmp_path):
    db = tmp_path / "old.sqlite3"
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE listing_metrics_snapshots (id INTEGER PRIMARY KEY, group_product_id INTEGER NOT NULL,"
              " snapshot_date TEXT NOT NULL, views INTEGER NOT NULL, num_favorers INTEGER NOT NULL,"
              " orders_count INTEGER NOT NULL)")
    c.commit(); c.close()
    assert migration.migrate(db) is True
    assert migration.migrate(db) is False
    c = sqlite3.connect(db)
    assert {r[1]: r[3] for r in c.execute("PRAGMA table_info(listing_metrics_snapshots)")}["orders_count"] == 0
    c.execute("INSERT INTO listing_metrics_snapshots (group_product_id, snapshot_date, views, num_favorers) VALUES (1,'d',1,1)")
    with pytest.raises(sqlite3.IntegrityError):
        c.execute("INSERT INTO listing_metrics_snapshots (group_product_id, snapshot_date, views, num_favorers) VALUES (1,'d',2,2)")
