from unittest.mock import patch

import pipeline.db as db
import pipeline.heartbeat as heartbeat
import pipeline.lock as lock
import migrate
import run_hourly


def _migrated_db(tmp_path):
    db_path = tmp_path / "test.sqlite3"
    conn = db.get_connection(db_path)
    db.init_db(conn)
    conn.close()
    migrate.migrate(db_path)
    return db_path


def test_main_returns_0_and_records_heartbeat_on_success(tmp_path, monkeypatch):
    db_path = _migrated_db(tmp_path)
    monkeypatch.setenv("TELEGRAM_ADMIN_CHAT_ID", "admin1")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")

    with patch("run_hourly.publish_primary_group.run_publish_primary_group_cycle", return_value=[]):
        exit_code = run_hourly.main(
            db_path=db_path, lock_path=tmp_path / "hourly.lock", load_dotenv=False,
        )

    assert exit_code == 0
    conn = db.get_connection(db_path)
    result = heartbeat.last(conn, "hourly")
    assert result["ok"] is True


def test_main_returns_1_and_notifies_telegram_on_stage_exception(tmp_path, monkeypatch):
    db_path = _migrated_db(tmp_path)
    monkeypatch.setenv("TELEGRAM_ADMIN_CHAT_ID", "admin1")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")

    with patch(
        "run_hourly.publish_primary_group.run_publish_primary_group_cycle",
        side_effect=RuntimeError("boom"),
    ), patch("run_hourly.telegram_client.send_message") as mock_send:
        exit_code = run_hourly.main(
            db_path=db_path, lock_path=tmp_path / "hourly.lock", load_dotenv=False,
        )

    assert exit_code == 1
    mock_send.assert_called_once()
    args, kwargs = mock_send.call_args
    assert args[0] == "admin1"
    assert "hourly" in args[1]
    assert "boom" in args[1]
    conn = db.get_connection(db_path)
    result = heartbeat.last(conn, "hourly")
    assert result["ok"] is False


def test_main_returns_2_when_lock_held(tmp_path, monkeypatch):
    db_path = _migrated_db(tmp_path)
    monkeypatch.setenv("TELEGRAM_ADMIN_CHAT_ID", "admin1")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    lock_path = tmp_path / "hourly.lock"

    with lock.acquire(lock_path):
        exit_code = run_hourly.main(db_path=db_path, lock_path=lock_path, load_dotenv=False)

    assert exit_code == 2


def test_main_returns_3_on_stale_schema(tmp_path, monkeypatch):
    db_path = tmp_path / "test.sqlite3"
    conn = db.get_connection(db_path)
    db.init_db(conn)
    conn.close()
    monkeypatch.setenv("TELEGRAM_ADMIN_CHAT_ID", "admin1")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")

    exit_code = run_hourly.main(db_path=db_path, lock_path=tmp_path / "hourly.lock", load_dotenv=False)

    assert exit_code == 3
