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
    "run_batch.research.run_research_cycle",
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


def test_per_candidate_generate_failure_reaches_the_telegram_path(tmp_path, monkeypatch):
    """GL-46: a swallowed per-candidate exception never reached _run_stage, so
    nothing was ever sent. Assert on the mock - send nothing."""
    from contextlib import ExitStack

    import pipeline.generate as generate

    db_path = _migrated_db(tmp_path)
    _set_required_env(monkeypatch)

    with ExitStack() as stack:
        _patch_all_stages_ok(stack)
        stack.enter_context(patch(
            "run_batch.generate.run_generate_cycle",
            side_effect=generate.GenerateCycleError("1 of 2 candidate(s) failed to generate - 7: boom"),
        ))
        mock_send = stack.enter_context(patch("run_batch.telegram_client.send_message"))

        exit_code = run_batch.main(db_path=db_path, lock_path=tmp_path / "batch.lock", load_dotenv=False)

    assert exit_code == 1
    assert any("failed to generate" in str(call) for call in mock_send.call_args_list)


def test_main_calls_research_before_generate(tmp_path, monkeypatch):
    # Regression: research.run_research_cycle (the only stage that inserts
    # new 'pending' candidates) was missing from run_batch's stage sequence
    # entirely - generate had nothing to ever pick up. Proves both that
    # research runs and that it runs before generate.
    from contextlib import ExitStack

    db_path = _migrated_db(tmp_path)
    _set_required_env(monkeypatch)
    call_order = []

    with ExitStack() as stack:
        for target in STAGE_PATCHES:
            if target == "run_batch.research.run_research_cycle":
                stack.enter_context(patch(
                    target, side_effect=lambda *a, **k: call_order.append("research") or []
                ))
            elif target == "run_batch.generate.run_generate_cycle":
                stack.enter_context(patch(
                    target, side_effect=lambda *a, **k: call_order.append("generate") or []
                ))
            else:
                stack.enter_context(patch(target, return_value=[]))
        stack.enter_context(patch("run_batch.reconcile.run_reconcile", return_value={}))
        stack.enter_context(patch("run_batch.cleanup.run_cleanup", return_value={}))

        exit_code = run_batch.main(db_path=db_path, lock_path=tmp_path / "batch.lock", load_dotenv=False)

    assert exit_code == 0
    assert call_order == ["research", "generate"]


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


def test_main_notifies_telegram_when_non_telegram_env_var_missing(tmp_path, monkeypatch):
    # I2: TELEGRAM_ADMIN_CHAT_ID/TELEGRAM_BOT_TOKEN present, so a Telegram
    # notification IS possible even though a later required var is missing.
    db_path = _migrated_db(tmp_path)
    _set_required_env(monkeypatch, skip="GELATO_API_KEY")

    with patch("run_batch.telegram_client.send_message") as mock_send:
        exit_code = run_batch.main(db_path=db_path, lock_path=tmp_path / "batch.lock", load_dotenv=False)

    assert exit_code == 1
    mock_send.assert_called_once()
    args, kwargs = mock_send.call_args
    assert args[0] == "admin1"
    assert "GELATO_API_KEY" in args[1]


def test_main_notifies_telegram_on_stale_schema(tmp_path, monkeypatch):
    # I2: migrate.check() runs after Telegram vars are resolved, so this path
    # must always notify.
    db_path = tmp_path / "test.sqlite3"
    conn = db.get_connection(db_path)
    db.init_db(conn)
    conn.close()
    _set_required_env(monkeypatch)

    with patch("run_batch.telegram_client.send_message") as mock_send:
        exit_code = run_batch.main(db_path=db_path, lock_path=tmp_path / "batch.lock", load_dotenv=False)

    assert exit_code == 3
    mock_send.assert_called_once()
    args, kwargs = mock_send.call_args
    assert args[0] == "admin1"
    assert "stale schema" in args[1]


def test_reconcile_drift_surfaces_in_heartbeat_detail(tmp_path, monkeypatch):
    # I4: _run_stage previously discarded fn()'s return value, so reconcile's
    # summary (real drift found) was computed and thrown away.
    from contextlib import ExitStack

    db_path = _migrated_db(tmp_path)
    _set_required_env(monkeypatch)

    with ExitStack() as stack:
        for target in STAGE_PATCHES:
            stack.enter_context(patch(target, return_value=[]))
        stack.enter_context(patch("run_batch.cleanup.run_cleanup", return_value={}))
        stack.enter_context(patch(
            "run_batch.reconcile.run_reconcile",
            return_value={
                "aged_out_candidates": [1, 2],
                "etsy_reconcile": {"marked_missing": ["g1"], "checked": 5, "skipped_errors": []},
            },
        ))

        exit_code = run_batch.main(db_path=db_path, lock_path=tmp_path / "batch.lock", load_dotenv=False)

    assert exit_code == 0
    conn = db.get_connection(db_path)
    detail = heartbeat.last(conn, "batch")["detail"]
    assert "2 candidates aged out" in detail
    assert "1 listing marked missing" in detail


def test_reconcile_no_drift_leaves_heartbeat_detail_none(tmp_path, monkeypatch):
    from contextlib import ExitStack

    db_path = _migrated_db(tmp_path)
    _set_required_env(monkeypatch)

    with ExitStack() as stack:
        _patch_all_stages_ok(stack)
        exit_code = run_batch.main(db_path=db_path, lock_path=tmp_path / "batch.lock", load_dotenv=False)

    assert exit_code == 0
    conn = db.get_connection(db_path)
    assert heartbeat.last(conn, "batch")["detail"] is None


def test_stall_predicate_fires_through_run_batch_when_constant_lowered(tmp_path, monkeypatch):
    # Proves publish_primary_group.candidate_publish_plan's stall clause ([D2]) actually
    # fires when driven through run_batch.main's real stage wiring, not just the unit
    # test that calls candidate_publish_plan directly. GL-7 PRD SS2 item 6: provable only
    # by temporarily lowering GROUP_REVIEW_STALL_DAYS, never by waiting 14 days.
    #
    # candidate_publish_plan is only reached from one place: publish_primary_group(),
    # which only runs off a real admin "approve" tap on the PRIMARY group (handle_decision
    # -> publish_primary_group -> candidate_publish_plan). So this test leaves
    # run_publish_primary_group_cycle UNstubbed (unlike every other stage) and drives it
    # with a synthetic Telegram callback update instead of mocking the function away.
    # telegram_client.get_updates/answer_callback_query are mocked (no real Telegram call),
    # and publish_primary_group.publish_candidate is mocked (no real Gelato/Etsy call) -
    # everything else in the approve path (record_decision, publish_primary_group,
    # candidate_publish_plan) runs for real.
    from contextlib import ExitStack
    from datetime import datetime, timedelta

    import pipeline.config as config
    import pipeline.publish_primary_group as publish_primary_group

    db_path = _migrated_db(tmp_path)
    _set_required_env(monkeypatch)
    monkeypatch.setattr(config, "GROUP_REVIEW_STALL_DAYS", 2)

    conn = db.get_connection(db_path)
    old = (datetime.now() - timedelta(days=3)).isoformat()
    conn.execute(
        "INSERT INTO candidates (id, created_at, niche, go_hold_kill, status, updated_at) "
        "VALUES (1, ?, 'test', 'go', 'primary_review', ?)", (old, old),
    )
    conn.execute(
        "INSERT INTO groups (id, candidate_id, group_type, status, created_at, updated_at) "
        "VALUES (1, 1, 'primary', 'pending_review', ?, ?)", (old, old),
    )
    conn.execute(
        "INSERT INTO groups (id, candidate_id, group_type, status, created_at, updated_at) "
        "VALUES (2, 1, '5x7', 'pending_review', ?, ?)", (old, old),
    )
    conn.execute(
        "INSERT INTO group_messages (group_id, telegram_message_id, chat_id, sent_at) "
        "VALUES (1, 202, 'admin1', ?)", (old,),
    )
    conn.commit()

    approve_update = {
        "update_id": 1,
        "callback_query": {
            "id": "cbq1",
            "from": {"id": "admin1"},
            "message": {"message_id": 202, "chat": {"id": "admin1"}},
            "data": "approve:1",
        },
    }

    stage_patches_without_publish_primary_group = [
        target for target in STAGE_PATCHES
        if target != "run_batch.publish_primary_group.run_publish_primary_group_cycle"
    ]

    with ExitStack() as stack:
        for target in stage_patches_without_publish_primary_group:
            stack.enter_context(patch(target, return_value=[]))
        stack.enter_context(patch("run_batch.reconcile.run_reconcile", return_value={}))
        stack.enter_context(patch("run_batch.cleanup.run_cleanup", return_value={}))
        stack.enter_context(
            patch("pipeline.telegram_client.get_updates", side_effect=[[approve_update], []])
        )
        stack.enter_context(patch("pipeline.telegram_client.answer_callback_query"))
        stack.enter_context(patch("pipeline.telegram_client.edit_message_reply_markup"))
        stack.enter_context(
            patch(
                "pipeline.publish_primary_group.publish_candidate",
                return_value={"etsy_listing_id": "fake-listing"},
            )
        )

        run_batch.main(db_path=db_path, lock_path=tmp_path / "batch.lock", load_dotenv=False)

    row = conn.execute("SELECT status FROM groups WHERE id = 2").fetchone()
    assert row["status"] == "stalled_skipped"
