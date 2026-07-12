from datetime import datetime

import pipeline.db as db
import pipeline.publish_primary_group as publish_primary_group


def _callback_update(update_id=100000001, user_id=987654321, data="approve:42",
                      message_id=202, chat_id=987654321, callback_id="cbq123"):
    return {
        "update_id": update_id,
        "callback_query": {
            "id": callback_id,
            "from": {"id": user_id, "is_bot": False, "first_name": "Admin"},
            "message": {
                "message_id": message_id,
                "chat": {"id": chat_id, "type": "private"},
                "date": 1234567890,
                "text": "Candidate #7 - Primary group (#42)",
            },
            "chat_instance": "abc123",
            "data": data,
        },
    }


def test_resolve_callback_parses_action_group_id_and_routing_fields():
    update = _callback_update()

    parsed = publish_primary_group.resolve_callback(update)

    assert parsed == {
        "telegram_user_id": 987654321,
        "callback_query_id": "cbq123",
        "action": "approve",
        "group_id": 42,
        "message_id": 202,
        "chat_id": 987654321,
    }


def test_resolve_callback_parses_edit_and_reject_actions():
    edit_parsed = publish_primary_group.resolve_callback(_callback_update(data="edit:7"))
    reject_parsed = publish_primary_group.resolve_callback(_callback_update(data="reject:7"))

    assert edit_parsed["action"] == "edit"
    assert reject_parsed["action"] == "reject"
    assert edit_parsed["group_id"] == 7


def test_resolve_callback_returns_none_for_non_callback_update():
    update = {"update_id": 5, "message": {"text": "/research botanical"}}

    assert publish_primary_group.resolve_callback(update) is None


def test_is_admin_true_when_ids_match_across_int_and_str():
    assert publish_primary_group.is_admin(987654321, "987654321") is True
    assert publish_primary_group.is_admin("987654321", 987654321) is True


def test_is_admin_false_when_ids_differ():
    assert publish_primary_group.is_admin(111111111, "987654321") is False


def _fresh_conn(tmp_path):
    conn = db.get_connection(tmp_path / "test.sqlite3")
    db.init_db(conn)
    return conn


def _insert_candidate(conn, niche="monstera line art", *, status="primary_review",
                       base_image_url="https://replicate.delivery/out.png"):
    timestamp = "2026-07-12T09:00:00"
    cursor = conn.execute(
        """
        INSERT INTO candidates (created_at, niche, go_hold_kill, status, base_image_url, updated_at)
        VALUES (?, ?, 'go', ?, ?, ?)
        """,
        (timestamp, niche, status, base_image_url, timestamp),
    )
    conn.commit()
    return cursor.lastrowid


def _insert_primary_group(conn, candidate_id, *, status="pending_review"):
    timestamp = "2026-07-12T09:05:00"
    cursor = conn.execute(
        "INSERT INTO groups (candidate_id, group_type, status, created_at, updated_at) "
        "VALUES (?, 'primary', ?, ?, ?)",
        (candidate_id, status, timestamp, timestamp),
    )
    conn.commit()
    return cursor.lastrowid


def test_log_telegram_event_writes_accepted_row(tmp_path):
    conn = _fresh_conn(tmp_path)

    event_id = publish_primary_group.log_telegram_event(
        conn, 987654321, {"update_id": 1}, True, "approve",
        now=datetime(2026, 7, 12, 9, 0, 0),
    )

    row = conn.execute("SELECT * FROM telegram_events_log WHERE id = ?", (event_id,)).fetchone()
    assert row["telegram_user_id"] == "987654321"
    assert row["accepted"] == 1
    assert row["action_taken"] == "approve"
    assert row["raw_payload"] == '{"update_id": 1}'
    assert row["received_at"] == "2026-07-12T09:00:00"
    conn.close()


def test_log_telegram_event_writes_discarded_row_with_no_action(tmp_path):
    conn = _fresh_conn(tmp_path)

    event_id = publish_primary_group.log_telegram_event(
        conn, 111111111, {"update_id": 2}, False, now=datetime(2026, 7, 12, 9, 0, 0),
    )

    row = conn.execute("SELECT * FROM telegram_events_log WHERE id = ?", (event_id,)).fetchone()
    assert row["accepted"] == 0
    assert row["action_taken"] is None
    conn.close()


def test_record_decision_writes_decision_notes_and_decided_at(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_primary_group(conn, candidate_id)

    publish_primary_group.record_decision(
        conn, group_id, "edited", "make it more pastel", now=datetime(2026, 7, 12, 9, 30, 0),
    )

    row = conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone()
    assert row["decision"] == "edited"
    assert row["decision_notes"] == "make it more pastel"
    assert row["decided_at"] == "2026-07-12T09:30:00"
    assert row["updated_at"] == "2026-07-12T09:30:00"
    conn.close()


def test_record_decision_allows_null_notes(tmp_path):
    conn = _fresh_conn(tmp_path)
    candidate_id = _insert_candidate(conn)
    group_id = _insert_primary_group(conn, candidate_id)

    publish_primary_group.record_decision(conn, group_id, "approved", now=datetime(2026, 7, 12, 9, 30, 0))

    row = conn.execute("SELECT decision, decision_notes FROM groups WHERE id = ?", (group_id,)).fetchone()
    assert row["decision"] == "approved"
    assert row["decision_notes"] is None
    conn.close()
