"""GL-131 (#139): the always-on ack listener carved out of ADR-0005.

Every test here defends the boundary the amendment is: the listener reads
getUpdates, checks the admin, records the decision and acks - and nothing else.
The slow work stays in the scheduled stage, which drains the queue the listener
writes.
"""
import os
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

import migrate
import pipeline.db as db
import pipeline.heartbeat as heartbeat
import pipeline.lock as lock
import pipeline.publish_primary_group as publish_primary_group
import run_hourly
import telegram_listener


def _migrated_db(tmp_path):
    db_path = tmp_path / "test.sqlite3"
    conn = db.get_connection(db_path)
    db.init_db(conn)
    conn.close()
    migrate.migrate(db_path)
    return db_path


def _callback_update(update_id=500, *, data="approve:1", user_id=987654321,
                     message_id=480, chat_id=987654321, callback_id="cbq1"):
    return {
        "update_id": update_id,
        "callback_query": {
            "id": callback_id,
            "from": {"id": user_id, "is_bot": False, "first_name": "Admin"},
            "message": {"message_id": message_id, "chat": {"id": chat_id, "type": "private"},
                        "date": 1234567890, "text": "Candidate #7 - Primary group"},
            "chat_instance": "abc123",
            "data": data,
        },
    }


def _seed_group(conn, *, group_type="primary", message_id=480, chat_id="987654321"):
    timestamp = "2026-08-17T09:00:00"
    candidate_id = conn.execute(
        "INSERT INTO candidates (created_at, niche, go_hold_kill, status, updated_at) "
        "VALUES (?, 'monstera', 'go', 'primary_review', ?)", (timestamp, timestamp),
    ).lastrowid
    group_id = conn.execute(
        "INSERT INTO groups (candidate_id, group_type, status, created_at, updated_at) "
        "VALUES (?, ?, 'pending_review', ?, ?)", (candidate_id, group_type, timestamp, timestamp),
    ).lastrowid
    conn.execute(
        "INSERT INTO group_messages (group_id, telegram_message_id, chat_id, sent_at) VALUES (?, ?, ?, ?)",
        (group_id, message_id, chat_id, timestamp),
    )
    conn.commit()
    return candidate_id, group_id


def _poll(conn, updates, **kwargs):
    """One listener poll over `updates`, with every outward Telegram call stubbed."""
    with patch("pipeline.telegram_client.get_updates", return_value=updates) as mock_get, \
         patch("pipeline.publish_primary_group.telegram_client.answer_callback_query") as mock_ack, \
         patch("pipeline.publish_primary_group.telegram_client.edit_message_reply_markup") as mock_markup:
        consumed = telegram_listener.poll_once(
            conn, admin_chat_id="987654321", bot_token="tok", **kwargs,
        )
    return consumed, mock_get, mock_ack, mock_markup


# --- the boundary ---------------------------------------------------------

def test_listener_records_the_decision_and_never_calls_gelato_or_etsy(tmp_path):
    conn = db.get_connection(tmp_path / "t.sqlite3")
    db.init_db(conn)
    _, group_id = _seed_group(conn)

    def _forbidden(*args, **kwargs):
        raise AssertionError("the listener must never reach Gelato or Etsy")

    # http.send is the single door every Gelato and Etsy call leaves by (the three
    # Telegram calls this path makes are stubbed above it, in _poll).
    with patch("pipeline.http.send", _forbidden), \
         patch("pipeline.publish_primary_group.handle_decision", _forbidden), \
         patch("pipeline.publish_group.handle_decision", _forbidden):
        _poll(conn, [_callback_update(data=f"approve:{group_id}")])

    assert conn.execute("SELECT decision FROM groups WHERE id = ?", (group_id,)).fetchone()["decision"] == "approved"
    assert conn.execute("SELECT COUNT(*) c FROM group_products").fetchone()["c"] == 0
    pending = conn.execute("SELECT * FROM pending_decisions").fetchall()
    assert [(row["group_id"], row["action"], row["dispatched_at"]) for row in pending] == [(group_id, "approve", None)]
    conn.close()


def test_listener_acknowledges_the_tap_and_edits_the_keyboard(tmp_path):
    conn = db.get_connection(tmp_path / "t.sqlite3")
    db.init_db(conn)
    _, group_id = _seed_group(conn)

    _, _, mock_ack, mock_markup = _poll(conn, [_callback_update(data=f"approve:{group_id}", callback_id="cbq9")])

    mock_ack.assert_called_once_with("cbq9", "Got it - approve...", bot_token="tok")
    assert mock_markup.call_args.args[2]["inline_keyboard"][0][0]["text"] == "✅ Approved"
    conn.close()


def test_listener_uses_a_long_poll(tmp_path):
    conn = db.get_connection(tmp_path / "t.sqlite3")
    db.init_db(conn)

    _, mock_get, _, _ = _poll(conn, [])

    assert mock_get.call_args.kwargs["timeout"] == telegram_listener.LONG_POLL_TIMEOUT
    conn.close()


def test_listener_reuses_the_admin_check(tmp_path):
    conn = db.get_connection(tmp_path / "t.sqlite3")
    db.init_db(conn)
    _, group_id = _seed_group(conn)

    _poll(conn, [_callback_update(data=f"approve:{group_id}", user_id=111)])

    assert conn.execute("SELECT decision FROM groups WHERE id = ?", (group_id,)).fetchone()["decision"] is None
    assert conn.execute("SELECT COUNT(*) c FROM pending_decisions").fetchone()["c"] == 0
    row = conn.execute("SELECT action_taken FROM telegram_events_log").fetchone()
    assert row["action_taken"] == "discarded: not admin"
    conn.close()


# --- restart survival -----------------------------------------------------

def test_listener_advances_the_offset_per_update(tmp_path):
    conn = db.get_connection(tmp_path / "t.sqlite3")
    db.init_db(conn)
    _, group_id = _seed_group(conn)

    _poll(conn, [_callback_update(500, data=f"approve:{group_id}"),
                 {"update_id": 501, "message": {"text": "hello", "from": {"id": 1}}}])

    assert publish_primary_group.get_telegram_offset(conn) == 501
    conn.close()


def test_a_redelivered_update_does_not_queue_the_decision_twice(tmp_path):
    # Killed between the enqueue and the offset advance, the update comes back. The
    # decision is already recorded, so GL-71's terminal guard discards it - and the
    # update_id is unique in the queue besides.
    conn = db.get_connection(tmp_path / "t.sqlite3")
    db.init_db(conn)
    _, group_id = _seed_group(conn)
    update = _callback_update(500, data=f"approve:{group_id}")

    _poll(conn, [update])
    _poll(conn, [update])

    assert conn.execute("SELECT COUNT(*) c FROM pending_decisions").fetchone()["c"] == 1
    conn.close()


def test_an_undecided_update_is_not_skipped_after_a_crash_mid_poll(tmp_path):
    # The other half of restart survival: an update whose processing raised must still
    # advance the offset (it left a durable error row) and must not be silently lost.
    conn = db.get_connection(tmp_path / "t.sqlite3")
    db.init_db(conn)
    _, group_id = _seed_group(conn)

    with patch("pipeline.publish_primary_group.record_decision", side_effect=RuntimeError("boom")):
        _poll(conn, [_callback_update(500, data=f"approve:{group_id}")])

    assert publish_primary_group.get_telegram_offset(conn) == 500
    assert conn.execute(
        "SELECT action_taken FROM telegram_events_log ORDER BY id DESC"
    ).fetchone()["action_taken"].startswith("error: ")
    conn.close()


# --- heartbeat and lifetime ----------------------------------------------

def test_run_records_a_heartbeat_every_poll(tmp_path):
    conn = db.get_connection(tmp_path / "t.sqlite3")
    db.init_db(conn)

    with patch("pipeline.telegram_client.get_updates", return_value=[]):
        telegram_listener.run(conn, admin_chat_id="987654321", bot_token="tok", stop=_stop_after(2))

    assert heartbeat.last(conn, telegram_listener.JOB_NAME)["ok"] is True
    conn.close()


def test_a_failing_poll_leaves_a_failed_heartbeat_and_keeps_polling(tmp_path):
    conn = db.get_connection(tmp_path / "t.sqlite3")
    db.init_db(conn)
    slept = []

    with patch("pipeline.telegram_client.get_updates", side_effect=RuntimeError("network down")):
        telegram_listener.run(conn, admin_chat_id="987654321", bot_token="tok",
                              sleep=slept.append, stop=_stop_after(2))

    row = heartbeat.last(conn, telegram_listener.JOB_NAME)
    assert row["ok"] is False and "network down" in row["detail"]
    assert slept == [telegram_listener.POLL_ERROR_BACKOFF_SECONDS] * 2
    conn.close()


def test_the_hourly_backstop_skips_polling_but_still_dispatches(tmp_path, monkeypatch):
    """GL-132: losing the cursor to a live listener must not cost the hourly its other
    two jobs. Before this, run_hourly took the token lock for its whole run and exited 2
    - so a resident listener meant nothing ever drained the queue it was filling."""
    db_path = _migrated_db(tmp_path)
    _set_required_env(monkeypatch)
    token_lock = tmp_path / "token.lock"

    conn = db.get_connection(db_path)
    _, group_id = _seed_group(conn)
    publish_primary_group.enqueue_decision(conn, group_id, "approve", 500)
    conn.close()

    with lock.acquire(token_lock):  # stands in for the live listener
        with patch("pipeline.telegram_client.get_updates") as mock_get,              patch("pipeline.publish_primary_group.handle_decision",
                   return_value={"action": "approve", "published": False}) as mock_handle,              patch("run_hourly.telegram_client.send_message"):
            exit_code = run_hourly.main(db_path=db_path, lock_path=tmp_path / "pipeline.lock",
                                        token_lock_path=token_lock, load_dotenv=False)

    assert exit_code == 0
    mock_get.assert_not_called()          # exactly one reader of the cursor
    mock_handle.assert_called_once()      # and the decision still got dispatched
    conn = db.get_connection(db_path)
    assert conn.execute("SELECT dispatched_at FROM pending_decisions").fetchone()["dispatched_at"]
    conn.close()


def test_the_hourly_polls_when_no_listener_holds_the_cursor(tmp_path, monkeypatch):
    db_path = _migrated_db(tmp_path)
    _set_required_env(monkeypatch)

    with patch("pipeline.telegram_client.get_updates", return_value=[]) as mock_get,          patch("run_hourly.telegram_client.send_message"):
        exit_code = run_hourly.main(db_path=db_path, lock_path=tmp_path / "pipeline.lock",
                                    token_lock_path=tmp_path / "token.lock", load_dotenv=False)

    assert exit_code == 0
    mock_get.assert_called_once()


def test_the_batch_runs_while_the_listener_holds_the_cursor(tmp_path, monkeypatch):
    """The #142 blocker: run_batch used to wrap its whole run in the TOKEN lock, so a
    resident listener stopped research, generation and the digest outright."""
    from contextlib import ExitStack

    import run_batch

    db_path = _migrated_db(tmp_path)
    _set_required_env(monkeypatch)

    with lock.acquire(lock.token_lock_path("tok")):  # the live listener
        with ExitStack() as stack:
            for target in _BATCH_STAGE_PATCHES:
                stack.enter_context(patch(target, return_value=[]))
            stack.enter_context(patch("run_batch.reconcile.run_reconcile", return_value={}))
            stack.enter_context(patch("run_batch.cleanup.run_cleanup", return_value={}))
            mock_digest = stack.enter_context(
                patch("run_batch.digest.run_digest_cycle", return_value=[]))
            exit_code = run_batch.main(db_path=db_path, lock_path=tmp_path / "pipeline.lock",
                                       load_dotenv=False)

    assert exit_code == 0
    mock_digest.assert_called_once()


_BATCH_STAGE_PATCHES = [
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


def test_the_lock_does_not_go_stale_under_a_live_listener(tmp_path, monkeypatch):
    # lock.acquire declares a holder stale purely on file age after an hour, whatever
    # its PID says - every holder before this one finished in minutes. A listener that
    # is merely blocked on a 25s long poll must not be robbed of the cursor.
    conn = db.get_connection(tmp_path / "t.sqlite3")
    db.init_db(conn)
    lock_path = tmp_path / "listener.lock"

    with lock.acquire(lock_path):
        old = time.time() - 7200
        os.utime(lock_path, (old, old))
        with patch("pipeline.telegram_client.get_updates", return_value=[]):
            telegram_listener.run(conn, admin_chat_id="987654321", bot_token="tok",
                                  lock_path=lock_path, stop=_stop_after(1))
        assert lock_path.stat().st_mtime > old
        with pytest.raises(lock.LockHeldError):
            with lock.acquire(lock_path):
                pass
    conn.close()


def test_refresh_does_not_touch_a_lock_owned_by_someone_else(tmp_path):
    lock_path = tmp_path / "other.lock"
    lock_path.write_text("999999")

    assert lock.refresh(lock_path) is False
    assert lock.refresh(tmp_path / "missing.lock") is False


def test_main_returns_2_when_the_lock_is_already_held(tmp_path, monkeypatch):
    db_path = _migrated_db(tmp_path)
    monkeypatch.setenv("TELEGRAM_ADMIN_CHAT_ID", "987654321")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    lock_path = tmp_path / "listener.lock"

    with lock.acquire(lock_path):
        exit_code = telegram_listener.main(db_path=db_path, lock_path=lock_path, load_dotenv=False,
                                           stop=_stop_after(1))

    assert exit_code == 2


def test_main_returns_3_on_a_stale_schema(tmp_path, monkeypatch):
    db_path = tmp_path / "t.sqlite3"
    conn = db.get_connection(db_path)
    db.init_db(conn)
    conn.close()
    monkeypatch.setenv("TELEGRAM_ADMIN_CHAT_ID", "987654321")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")

    assert telegram_listener.main(db_path=db_path, lock_path=tmp_path / "l.lock",
                                  load_dotenv=False, stop=_stop_after(1)) == 3


def test_main_returns_1_without_telegram_credentials(tmp_path, monkeypatch):
    db_path = _migrated_db(tmp_path)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setenv("TELEGRAM_ADMIN_CHAT_ID", "987654321")

    assert telegram_listener.main(db_path=db_path, lock_path=tmp_path / "l.lock",
                                  load_dotenv=False, stop=_stop_after(1)) == 1


def _stop_after(n):
    calls = []

    def stop():
        calls.append(1)
        return len(calls) > n

    return stop


# --- the scheduled stage drains the queue ---------------------------------

def test_scheduled_cycle_dispatches_a_pending_decision(tmp_path):
    conn = db.get_connection(tmp_path / "t.sqlite3")
    db.init_db(conn)
    candidate_id, group_id = _seed_group(conn)
    publish_primary_group.enqueue_decision(conn, group_id, "approve", 500,
                                           now=datetime(2026, 8, 17, 9, 0, 0))

    with patch("pipeline.publish_primary_group.handle_decision",
               return_value={"action": "approve", "published": True}) as mock_handle:
        dispatched = publish_primary_group.dispatch_pending_decisions(
            conn, now=datetime(2026, 8, 17, 9, 5, 0),
        )

    assert mock_handle.call_args.args[:4] == (conn, candidate_id, group_id, "approve")
    assert dispatched == [group_id]
    row = conn.execute("SELECT dispatched_at, error FROM pending_decisions").fetchone()
    assert row["dispatched_at"] == "2026-08-17T09:05:00" and row["error"] is None
    conn.close()


def test_a_pending_secondary_decision_routes_to_publish_group(tmp_path):
    conn = db.get_connection(tmp_path / "t.sqlite3")
    db.init_db(conn)
    candidate_id, group_id = _seed_group(conn, group_type="5x7")
    publish_primary_group.enqueue_decision(conn, group_id, "approve", 501)

    with patch("pipeline.publish_group.handle_decision", return_value={"action": "approve"}) as mock_handle:
        publish_primary_group.dispatch_pending_decisions(conn)

    assert mock_handle.call_args.args[:4] == (conn, candidate_id, group_id, "approve")
    conn.close()


def test_a_failed_dispatch_leaves_the_reason_on_the_row_and_fails_the_stage(tmp_path):
    # CLAUDE.md/GL-46: a swallowed per-item exception must leave a state change behind
    # AND still fail the stage once. The row stays pending, so the next cycle retries it.
    conn = db.get_connection(tmp_path / "t.sqlite3")
    db.init_db(conn)
    _, group_id = _seed_group(conn)
    publish_primary_group.enqueue_decision(conn, group_id, "approve", 500)

    with patch("pipeline.publish_primary_group.handle_decision", side_effect=RuntimeError("gelato 500")), \
         pytest.raises(publish_primary_group.PendingDecisionDispatchError):
        publish_primary_group.dispatch_pending_decisions(conn)

    row = conn.execute("SELECT dispatched_at, error FROM pending_decisions").fetchone()
    assert row["dispatched_at"] is None
    assert "gelato 500" in row["error"]
    conn.close()


def test_run_cycle_drains_the_queue_so_an_approved_group_still_publishes(tmp_path):
    conn = db.get_connection(tmp_path / "t.sqlite3")
    db.init_db(conn)
    _, group_id = _seed_group(conn)
    publish_primary_group.enqueue_decision(conn, group_id, "approve", 500)

    with patch("pipeline.telegram_client.get_updates", return_value=[]), \
         patch("pipeline.publish_primary_group.handle_decision",
               return_value={"action": "approve", "published": True}) as mock_handle:
        publish_primary_group.run_publish_primary_group_cycle(
            conn, admin_chat_id="987654321", bot_token="tok", static_config={},
        )

    mock_handle.assert_called_once()
    assert conn.execute("SELECT dispatched_at FROM pending_decisions").fetchone()["dispatched_at"] is not None
    conn.close()


# --- a dead listener is detectable ----------------------------------------

HOURLY_ENV = {
    "TELEGRAM_ADMIN_CHAT_ID": "987654321", "TELEGRAM_BOT_TOKEN": "tok",
    "REPLICATE_API_TOKEN": "x", "ANTHROPIC_API_KEY": "x", "GELATO_API_KEY": "x",
    "GELATO_STORE_ID": "x", "ETSY_API_KEY": "x", "ETSY_API_SECRET": "x",
    "ETSY_ACCESS_TOKEN": "x", "ETSY_SHOP_ID": "x",
}


def _set_required_env(monkeypatch):
    for key, value in HOURLY_ENV.items():
        monkeypatch.setenv(key, value)


def _hourly_run(db_path, tmp_path):
    with patch("run_hourly.publish_primary_group.run_publish_primary_group_cycle", return_value=[]), \
         patch("run_hourly.telegram_client.send_message") as mock_send:
        exit_code = run_hourly.main(db_path=db_path, lock_path=tmp_path / "h.lock", load_dotenv=False)
    return exit_code, mock_send


def _record_listener_heartbeat(db_path, minutes_ago, ok=True):
    conn = db.get_connection(db_path)
    heartbeat.record(conn, telegram_listener.JOB_NAME, ok=ok,
                     now=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=minutes_ago))
    conn.close()


def test_hourly_reports_a_dead_listener(tmp_path, monkeypatch):
    db_path = _migrated_db(tmp_path)
    _set_required_env(monkeypatch)
    _record_listener_heartbeat(db_path, minutes_ago=30)

    exit_code, mock_send = _hourly_run(db_path, tmp_path)

    assert exit_code == 0
    assert "listener-down" in mock_send.call_args[0][1]
    conn = db.get_connection(db_path)
    assert "listener-down" in heartbeat.last(conn, "hourly")["detail"]
    conn.close()


def test_hourly_is_silent_while_the_listener_is_alive(tmp_path, monkeypatch):
    db_path = _migrated_db(tmp_path)
    _set_required_env(monkeypatch)
    _record_listener_heartbeat(db_path, minutes_ago=1)

    exit_code, mock_send = _hourly_run(db_path, tmp_path)

    assert exit_code == 0
    mock_send.assert_not_called()


def test_hourly_starts_a_listener_on_a_database_that_has_never_had_one(tmp_path, monkeypatch):
    # This is the case that kept the listener off in practice: an empty heartbeats table
    # read as "nothing to be down", so no scheduled run ever started the first one.
    db_path = _migrated_db(tmp_path)
    _set_required_env(monkeypatch)

    with patch("telegram_listener._spawn", return_value=321) as mock_spawn:
        exit_code, mock_send = _hourly_run(db_path, tmp_path)

    assert exit_code == 0
    mock_spawn.assert_called_once()
    assert "started a new listener" in mock_send.call_args[0][1]


# --- ensure_alive: the batch keeps a listener up at digest time ------------

def _record_listener(conn, minutes_ago, ok=True, detail=None):
    heartbeat.record(conn, telegram_listener.JOB_NAME, ok=ok, detail=detail,
                     now=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=minutes_ago))


def test_ensure_alive_does_nothing_when_the_listener_is_breathing(tmp_path):
    conn = db.get_connection(tmp_path / "t.sqlite3")
    db.init_db(conn)
    _record_listener(conn, minutes_ago=0)
    spawned = []

    result = telegram_listener.ensure_alive(conn, bot_token="tok", spawn=lambda: spawned.append(1))

    assert result["status"] == "alive"
    assert spawned == []
    conn.close()


def test_ensure_alive_starts_one_when_the_heartbeat_is_stale(tmp_path):
    conn = db.get_connection(tmp_path / "t.sqlite3")
    db.init_db(conn)
    _record_listener(conn, minutes_ago=30)

    result = telegram_listener.ensure_alive(conn, bot_token="tok-nobody-holds", spawn=lambda: 4242)

    assert result["status"] == "started" and result["pid"] == 4242
    assert "listener-down" in result["detail"]
    conn.close()


def test_ensure_alive_does_not_start_a_second_listener_over_a_wedged_one(tmp_path):
    # A stale heartbeat with the token lock still held by a live process means wedged,
    # not absent. A second listener would only exit 2 - and would say "started" while
    # the button stayed dead, which is worse than saying nothing.
    conn = db.get_connection(tmp_path / "t.sqlite3")
    db.init_db(conn)
    _record_listener(conn, minutes_ago=30)
    spawned = []

    with lock.acquire(lock.token_lock_path("tok-held")):
        result = telegram_listener.ensure_alive(conn, bot_token="tok-held",
                                                spawn=lambda: spawned.append(1))

    assert result["status"] == "wedged"
    assert spawned == []
    conn.close()


def test_ensure_alive_reports_a_spawn_that_fails(tmp_path):
    conn = db.get_connection(tmp_path / "t.sqlite3")
    db.init_db(conn)
    _record_listener(conn, minutes_ago=30)

    def _boom():
        raise OSError("no python here")

    result = telegram_listener.ensure_alive(conn, bot_token="tok-nobody", spawn=_boom)

    assert result["status"] == "failed"
    assert "no python here" in result["detail"]
    conn.close()


def test_ensure_alive_starts_the_first_listener_a_database_has_ever_had(tmp_path):
    """Only ever RESTARTING one is not the same as keeping one running. An empty
    heartbeats table left the listener permanently off: every scheduled run concluded
    there was nothing to be down and did nothing, for an hour at a time, forever."""
    conn = db.get_connection(tmp_path / "t.sqlite3")
    db.init_db(conn)

    result = telegram_listener.ensure_alive(conn, bot_token="tok-nobody-holds", spawn=lambda: 77)

    assert result["status"] == "started" and result["pid"] == 77
    assert "has ever run" in result["detail"]
    conn.close()


def test_stale_detail_still_says_nothing_when_no_listener_has_ever_run(tmp_path):
    # The reporting path keeps its silence - an alarm about a listener that was never
    # installed is an alarm nobody keeps reading. Only the ensuring path acts on it.
    conn = db.get_connection(tmp_path / "t.sqlite3")
    db.init_db(conn)

    assert telegram_listener.stale_detail(conn) is None
    conn.close()


def test_the_batch_checks_the_listener_before_it_sends_a_digest(tmp_path, monkeypatch):
    """The owner's ask: a digest is a request for a decision, so the listener has to be
    alive at the moment the buttons go out, not five minutes later."""
    from contextlib import ExitStack

    import run_batch

    db_path = _migrated_db(tmp_path)
    _set_required_env(monkeypatch)
    order = []

    with ExitStack() as stack:
        for target in _BATCH_STAGE_PATCHES:
            stack.enter_context(patch(target, return_value=[]))
        stack.enter_context(patch("run_batch.reconcile.run_reconcile", return_value={}))
        stack.enter_context(patch("run_batch.cleanup.run_cleanup", return_value={}))
        stack.enter_context(patch("run_batch.digest.run_digest_cycle",
                                  side_effect=lambda *a, **k: order.append("digest") or []))
        stack.enter_context(patch("run_batch.telegram_listener.ensure_alive",
                                  side_effect=lambda *a, **k: order.append("ensure") or
                                  {"status": "alive", "detail": None}))
        exit_code = run_batch.main(db_path=db_path, lock_path=tmp_path / "pipeline.lock",
                                   load_dotenv=False)

    assert exit_code == 0
    assert order[:2] == ["ensure", "digest"]


def test_a_dead_listener_is_reported_but_does_not_hold_the_digest(tmp_path, monkeypatch):
    # A listener that cannot be started is a slow button, not a broken pipeline. Holding
    # the digest back would turn a latency problem into a starved shop.
    from contextlib import ExitStack

    import run_batch

    db_path = _migrated_db(tmp_path)
    _set_required_env(monkeypatch)

    with ExitStack() as stack:
        for target in _BATCH_STAGE_PATCHES:
            stack.enter_context(patch(target, return_value=[]))
        stack.enter_context(patch("run_batch.reconcile.run_reconcile", return_value={}))
        stack.enter_context(patch("run_batch.cleanup.run_cleanup", return_value={}))
        mock_digest = stack.enter_context(patch("run_batch.digest.run_digest_cycle", return_value=[]))
        stack.enter_context(patch("run_batch.telegram_listener.ensure_alive",
                                  return_value={"status": "failed", "detail": "listener-down: nope"}))
        mock_send = stack.enter_context(patch("run_batch.telegram_client.send_message"))
        exit_code = run_batch.main(db_path=db_path, lock_path=tmp_path / "pipeline.lock",
                                   load_dotenv=False)

    assert exit_code == 0
    mock_digest.assert_called_once()
    assert any("listener-down" in str(call) for call in mock_send.call_args_list)


# --- no supervisor task: the cron jobs are the supervisor ------------------

def test_the_hourly_starts_a_listener_that_is_not_running(tmp_path, monkeypatch):
    """#142 follow-up: a separate qhoto-listener task would only duplicate this. The
    hourly and the batch already run on a cadence, so whichever comes first restarts a
    dead listener - one mechanism, not two."""
    db_path = _migrated_db(tmp_path)
    _set_required_env(monkeypatch)
    conn = db.get_connection(db_path)
    _record_listener(conn, minutes_ago=30)
    conn.close()

    with patch("pipeline.telegram_client.get_updates", return_value=[]),          patch("telegram_listener._spawn", return_value=4242) as mock_spawn,          patch("run_hourly.telegram_client.send_message") as mock_send:
        exit_code = run_hourly.main(db_path=db_path, lock_path=tmp_path / "pipeline.lock",
                                    token_lock_path=tmp_path / "token.lock", load_dotenv=False)

    assert exit_code == 0
    mock_spawn.assert_called_once()
    assert any("started a new listener" in str(call) for call in mock_send.call_args_list)


def test_the_hourly_starts_the_listener_only_after_it_has_let_go_of_the_cursor(tmp_path, monkeypatch):
    """The ordering IS the feature: spawn while still holding the token lock and the new
    listener finds it held and exits 2 - a restart that silently never happens."""
    db_path = _migrated_db(tmp_path)
    _set_required_env(monkeypatch)
    conn = db.get_connection(db_path)
    _record_listener(conn, minutes_ago=30)
    conn.close()
    token_lock = tmp_path / "token.lock"
    held_at_spawn = {}

    def _spy():
        held_at_spawn["held"] = lock.is_held(token_lock)
        return 4242

    with patch("pipeline.telegram_client.get_updates", return_value=[]),          patch("telegram_listener._spawn", _spy),          patch("run_hourly.telegram_client.send_message"):
        run_hourly.main(db_path=db_path, lock_path=tmp_path / "pipeline.lock",
                        token_lock_path=token_lock, load_dotenv=False)

    assert held_at_spawn["held"] is False


def test_the_hourly_says_nothing_when_the_listener_is_alive(tmp_path, monkeypatch):
    db_path = _migrated_db(tmp_path)
    _set_required_env(monkeypatch)
    conn = db.get_connection(db_path)
    _record_listener(conn, minutes_ago=0)
    conn.close()

    with patch("pipeline.telegram_client.get_updates", return_value=[]),          patch("telegram_listener._spawn") as mock_spawn,          patch("run_hourly.telegram_client.send_message") as mock_send:
        exit_code = run_hourly.main(db_path=db_path, lock_path=tmp_path / "pipeline.lock",
                                    token_lock_path=tmp_path / "token.lock", load_dotenv=False)

    assert exit_code == 0
    mock_spawn.assert_not_called()
    mock_send.assert_not_called()
