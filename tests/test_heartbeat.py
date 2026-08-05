import sqlite3
from datetime import datetime

import migrate
import pipeline.db as db
import pipeline.heartbeat as heartbeat


def _conn(tmp_path):
    conn = db.get_connection(tmp_path / "test.sqlite3")
    db.init_db(conn)
    return conn


def test_last_returns_none_when_never_recorded(tmp_path):
    conn = _conn(tmp_path)

    assert heartbeat.last(conn, "hourly") is None


def test_record_then_last_round_trips(tmp_path):
    conn = _conn(tmp_path)
    now = datetime(2026, 8, 5, 3, 0, 0)

    heartbeat.record(conn, "hourly", ok=True, detail="3 updates processed", now=now)

    result = heartbeat.last(conn, "hourly")
    assert result["job_name"] == "hourly"
    assert result["ok"] is True
    assert result["detail"] == "3 updates processed"
    assert result["ran_at"] == now.isoformat()


def test_record_overwrites_previous_row_for_same_job(tmp_path):
    conn = _conn(tmp_path)
    heartbeat.record(conn, "hourly", ok=True, now=datetime(2026, 8, 5, 3, 0, 0))

    heartbeat.record(conn, "hourly", ok=False, detail="crashed", now=datetime(2026, 8, 5, 4, 0, 0))

    result = heartbeat.last(conn, "hourly")
    assert result["ok"] is False
    assert result["detail"] == "crashed"
    count = conn.execute("SELECT COUNT(*) FROM heartbeats WHERE job_name = 'hourly'").fetchone()[0]
    assert count == 1


def test_record_keeps_separate_jobs_independent(tmp_path):
    conn = _conn(tmp_path)
    heartbeat.record(conn, "hourly", ok=True, now=datetime(2026, 8, 5, 3, 0, 0))
    heartbeat.record(conn, "batch", ok=True, now=datetime(2026, 8, 5, 6, 0, 0))

    assert heartbeat.last(conn, "hourly")["ran_at"] == "2026-08-05T03:00:00"
    assert heartbeat.last(conn, "batch")["ran_at"] == "2026-08-05T06:00:00"


def test_record_works_against_db_bootstrapped_by_migrate_from_zero(tmp_path):
    """C1 regression: heartbeat.record() must work on the real bootstrap path
    (migrate.migrate() on a virgin DB file), not just on db.init_db() called
    directly like every other fixture in this file does."""
    db_path = tmp_path / "test.sqlite3"
    sqlite3.connect(db_path).close()  # virgin file, zero tables

    migrate.migrate(db_path)

    conn = db.get_connection(db_path)
    heartbeat.record(conn, "hourly", ok=True)

    assert heartbeat.last(conn, "hourly")["ok"] is True
