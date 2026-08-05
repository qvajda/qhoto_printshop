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


REQUIRED_ENV = {
    "TELEGRAM_ADMIN_CHAT_ID": "admin1",
    "TELEGRAM_BOT_TOKEN": "tok",
    "REPLICATE_API_TOKEN": "replicate-tok",
    "ANTHROPIC_API_KEY": "anthropic-key",
    "GELATO_API_KEY": "gelato-key",
    "GELATO_STORE_ID": "gelato-store",
    "ETSY_API_KEY": "etsy-key",
    "ETSY_API_SECRET": "etsy-secret",
    "ETSY_ACCESS_TOKEN": "etsy-token",
    "ETSY_SHOP_ID": "etsy-shop",
}


def _set_required_env(monkeypatch, skip=None):
    for key, value in REQUIRED_ENV.items():
        if key == skip:
            continue
        monkeypatch.setenv(key, value)


def test_main_returns_0_and_records_heartbeat_on_success(tmp_path, monkeypatch):
    db_path = _migrated_db(tmp_path)
    _set_required_env(monkeypatch)

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
    _set_required_env(monkeypatch)

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
    _set_required_env(monkeypatch)
    lock_path = tmp_path / "hourly.lock"

    with lock.acquire(lock_path):
        exit_code = run_hourly.main(db_path=db_path, lock_path=lock_path, load_dotenv=False)

    assert exit_code == 2


def test_main_returns_3_on_stale_schema(tmp_path, monkeypatch):
    db_path = tmp_path / "test.sqlite3"
    conn = db.get_connection(db_path)
    db.init_db(conn)
    conn.close()
    _set_required_env(monkeypatch)

    exit_code = run_hourly.main(db_path=db_path, lock_path=tmp_path / "hourly.lock", load_dotenv=False)

    assert exit_code == 3


def test_main_returns_1_when_required_env_var_missing(tmp_path, monkeypatch):
    db_path = _migrated_db(tmp_path)
    _set_required_env(monkeypatch, skip="TELEGRAM_ADMIN_CHAT_ID")

    exit_code = run_hourly.main(db_path=db_path, lock_path=tmp_path / "hourly.lock", load_dotenv=False)

    assert exit_code == 1
