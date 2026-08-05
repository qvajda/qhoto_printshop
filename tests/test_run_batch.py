from unittest.mock import patch

import pipeline.db as db
import pipeline.heartbeat as heartbeat
import migrate
import run_batch


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


STAGE_PATCHES = [
    "run_batch.generate.run_generate_cycle",
    "run_batch.primary_mockup.run_primary_mockup_cycle",
    "run_batch.compliance_draft.run_compliance_draft_cycle",
    "run_batch.critic_pass.run_critic_pass_cycle",
    "run_batch.digest.run_digest_cycle",
    "run_batch.publish_primary_group.run_publish_primary_group_cycle",
    "run_batch.group_mockup.run_group_mockup_cycle",
    "run_batch.group_critic_pass.run_group_critic_pass_cycle",
    "run_batch.group_digest.run_group_digest_cycle",
]


def _patch_all_stages_ok(stack):
    for target in STAGE_PATCHES:
        stack.enter_context(patch(target, return_value=[]))
    stack.enter_context(patch("run_batch.reconcile.run_reconcile", return_value={}))
    stack.enter_context(patch("run_batch.cleanup.run_cleanup", return_value={}))


def test_main_returns_0_when_every_stage_succeeds(tmp_path, monkeypatch):
    from contextlib import ExitStack

    db_path = _migrated_db(tmp_path)
    _set_required_env(monkeypatch)

    with ExitStack() as stack:
        _patch_all_stages_ok(stack)
        exit_code = run_batch.main(db_path=db_path, lock_path=tmp_path / "batch.lock", load_dotenv=False)

    assert exit_code == 0
    conn = db.get_connection(db_path)
    assert heartbeat.last(conn, "batch")["ok"] is True


def test_main_returns_1_when_one_stage_fails_but_runs_the_rest(tmp_path, monkeypatch):
    from contextlib import ExitStack

    db_path = _migrated_db(tmp_path)
    _set_required_env(monkeypatch)

    with ExitStack() as stack:
        _patch_all_stages_ok(stack)
        stack.enter_context(
            patch("run_batch.generate.run_generate_cycle", side_effect=RuntimeError("gen boom"))
        )
        mock_send = stack.enter_context(patch("run_batch.telegram_client.send_message"))
        mock_mockup = stack.enter_context(
            patch("run_batch.primary_mockup.run_primary_mockup_cycle", return_value=[])
        )

        exit_code = run_batch.main(db_path=db_path, lock_path=tmp_path / "batch.lock", load_dotenv=False)

    assert exit_code == 1
    mock_mockup.assert_called_once()  # downstream stages still ran
    assert any("gen boom" in str(call) for call in mock_send.call_args_list)


def test_main_returns_2_when_lock_held(tmp_path, monkeypatch):
    import pipeline.lock as lock

    db_path = _migrated_db(tmp_path)
    _set_required_env(monkeypatch)
    lock_path = tmp_path / "batch.lock"

    with lock.acquire(lock_path):
        exit_code = run_batch.main(db_path=db_path, lock_path=lock_path, load_dotenv=False)

    assert exit_code == 2


def test_main_returns_3_on_stale_schema(tmp_path, monkeypatch):
    db_path = tmp_path / "test.sqlite3"
    conn = db.get_connection(db_path)
    db.init_db(conn)
    conn.close()
    _set_required_env(monkeypatch)

    exit_code = run_batch.main(db_path=db_path, lock_path=tmp_path / "batch.lock", load_dotenv=False)

    assert exit_code == 3


def test_main_returns_1_when_required_env_var_missing(tmp_path, monkeypatch):
    db_path = _migrated_db(tmp_path)
    _set_required_env(monkeypatch, skip="TELEGRAM_ADMIN_CHAT_ID")

    exit_code = run_batch.main(db_path=db_path, lock_path=tmp_path / "batch.lock", load_dotenv=False)

    assert exit_code == 1
