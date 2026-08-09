import pipeline.db as db
import pipeline.heartbeat as heartbeat
import heartbeat_status


def test_format_status_never_ran():
    assert "never ran" in heartbeat_status.format_status("hourly", None)


def test_format_status_ok_includes_time_and_detail():
    row = {"job_name": "hourly", "ran_at": "2026-08-05T03:00:00", "ok": True, "detail": "3 updates"}
    out = heartbeat_status.format_status("hourly", row)
    assert "ok" in out
    assert "2026-08-05T03:00:00" in out
    assert "3 updates" in out


def test_format_status_failed():
    row = {"job_name": "batch", "ran_at": "2026-08-05T06:00:00", "ok": False, "detail": "boom"}
    assert "FAILED" in heartbeat_status.format_status("batch", row)


def test_main_prints_populated_and_empty_jobs(tmp_path, capsys):
    db_path = tmp_path / "test.sqlite3"
    conn = db.get_connection(db_path)
    db.init_db(conn)
    heartbeat.record(conn, "hourly", ok=True)
    conn.close()

    heartbeat_status.main(db_path)

    out = capsys.readouterr().out
    assert "hourly: ok" in out
    assert "batch: never ran" in out
