import json
from datetime import datetime, timezone

import pipeline.compliance_draft as compliance_draft
import pipeline.config as config
import pipeline.critic_pass as critic_pass
import pipeline.db as db
import pipeline.generate as generate
import pipeline.group_product as group_product
import pipeline.primary_mockup as primary_mockup
import pipeline.publish_group as publish_group
import pipeline.telegram_client as telegram_client


def resolve_callback(update: dict) -> dict | None:
    callback_query = update.get("callback_query")
    if callback_query is None:
        return None

    action, _, group_id = callback_query["data"].partition(":")
    return {
        "telegram_user_id": callback_query["from"]["id"],
        "callback_query_id": callback_query["id"],
        "action": action,
        "group_id": int(group_id),
        "message_id": callback_query["message"]["message_id"],
        "chat_id": callback_query["message"]["chat"]["id"],
    }


# GL-45: a tap that lands must look like it landed. The toast is transient, so the
# keyboard is edited to a single non-actionable label carrying the decision - which
# also makes a second tap on an already-decided message harmless (action 'noop').
NOOP_ACTION = "noop"
_DECIDED_LABELS = {"approve": "✅ Approved", "edit": "✏️ Edit requested",
                   "reject": "\U0001f6ab Rejected"}


def _ack(callback_query_id, text, *, bot_token) -> None:
    """Acknowledge a tap. Never raises: the decision is already durably recorded by
    the time this is called, so a stale/expired callback query is a lost spinner,
    not a lost decision."""
    try:
        telegram_client.answer_callback_query(callback_query_id, text, bot_token=bot_token)
    except Exception as exc:
        print(f"answer_callback_query failed for {callback_query_id}: {exc}")


def _mark_decided(parsed, *, bot_token) -> None:
    label = _DECIDED_LABELS.get(parsed["action"], parsed["action"])
    markup = {"inline_keyboard": [[
        {"text": label, "callback_data": f"{NOOP_ACTION}:{parsed['group_id']}"}
    ]]}
    try:
        telegram_client.edit_message_reply_markup(
            parsed["chat_id"], parsed["message_id"], markup, bot_token=bot_token,
        )
    except Exception as exc:
        print(f"edit_message_reply_markup failed for group {parsed['group_id']}: {exc}")


def is_admin(telegram_user_id, admin_chat_id) -> bool:
    return str(telegram_user_id) == str(admin_chat_id)


def log_telegram_event(conn, telegram_user_id, raw_payload, accepted, action_taken=None, *, now=None) -> int:
    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()
    cursor = conn.execute(
        """
        INSERT INTO telegram_events_log (received_at, telegram_user_id, raw_payload, accepted, action_taken)
        VALUES (?, ?, ?, ?, ?)
        """,
        (timestamp, str(telegram_user_id), json.dumps(raw_payload), 1 if accepted else 0, action_taken),
    )
    conn.commit()
    return cursor.lastrowid


def record_decision(conn, group_id, decision, decision_notes=None, *, now=None) -> None:
    timestamp = now if isinstance(now, str) else (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()
    conn.execute(
        "UPDATE groups SET decision = ?, decision_notes = ?, decided_at = ?, updated_at = ? WHERE id = ?",
        (decision, decision_notes, timestamp, timestamp, group_id),
    )
    conn.commit()


_SECONDARY_GROUP_TYPES = ("5x7", "10x24")

# A group is done being reviewed when the owner approved or rejected it, or when it ran
# out of retries / aged out. 'edited' is deliberately NOT terminal: it means "redo this
# one", and the decision is overwritten by the next tap.
_TERMINAL_DECISIONS = ("approved", "rejected")
_TERMINAL_STATUSES = ("rejected", "failed_abandoned", "stalled_skipped")


def _age_days(reference: str, now_dt) -> float:
    try:
        return (now_dt - datetime.fromisoformat(reference)).total_seconds() / 86400
    except (ValueError, TypeError):
        return 0.0


def candidate_publish_plan(conn, candidate_id, static_config, *, now=None) -> dict:
    """v4.12 [D1] publish gate: the candidate's single listing is created once, when every
    group has reached a terminal decision, carrying only the sizes that were validated.

    [D2] adds the stall clause: a group left undecided past
    config.GROUP_REVIEW_STALL_DAYS stops the candidate waiting - it is marked
    'stalled_skipped' and the listing publishes without it. Measured off
    groups.updated_at (a group with no row yet is measured off the primary group's
    decision, so a secondary group that never renders can't hang the candidate forever).
    This only fires when something evaluates the gate; until GL-7 runs it on a cadence
    the effective behaviour is wait-indefinitely."""
    now_dt = now if isinstance(now, datetime) else (
        datetime.fromisoformat(now) if isinstance(now, str)
        else (now or datetime.now(timezone.utc).replace(tzinfo=None))
    )
    timestamp = now_dt.isoformat()

    rows = {
        row["group_type"]: row for row in conn.execute(
            "SELECT id, group_type, decision, status, updated_at FROM groups WHERE candidate_id = ?",
            (candidate_id,),
        ).fetchall()
    }
    primary = rows.get("primary")
    if primary is None or primary["decision"] != "approved":
        return {"ready": False, "waiting_on": ["primary"], "stalled": []}

    waiting_on, stalled = [], []
    for group_type in _SECONDARY_GROUP_TYPES:
        if not config.get_mockup_templates(static_config, group_type, "portrait"):
            # No scene bundles authored for this group type - group_mockup never creates
            # a row for it, so waiting on one would deadlock the candidate.
            continue
        row = rows.get(group_type)
        if row is not None and (row["decision"] in _TERMINAL_DECISIONS
                                or row["status"] in _TERMINAL_STATUSES):
            continue
        reference = row["updated_at"] if row is not None else primary["updated_at"]
        if _age_days(reference, now_dt) < config.GROUP_REVIEW_STALL_DAYS:
            waiting_on.append(group_type)
            continue
        stalled.append(group_type)
        if row is not None:
            conn.execute(
                "UPDATE groups SET status = 'stalled_skipped', updated_at = ? WHERE id = ?",
                (timestamp, row["id"]),
            )
    if stalled:
        conn.commit()

    return {"ready": not waiting_on, "waiting_on": waiting_on, "stalled": stalled}


def publish_candidate(conn, candidate_id, *, static_config=None, store_id=None,
                       gelato_api_key=None, shop_id=None, etsy_api_key=None,
                       etsy_api_secret=None, etsy_access_token=None, dry_run=None, now=None) -> dict:
    """v4.12: creates the candidate's ONE Gelato product with every validated size as a
    variant, then patches the Etsy listing Gelato pushes. Called once, from the publish
    gate - never per group."""
    static_config = static_config if static_config is not None else config.load_static_config()
    timestamp = now if isinstance(now, str) else (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()

    candidate_row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    if candidate_row is None:
        raise ValueError(f"No candidate with id {candidate_id}")
    candidate = dict(candidate_row)

    listing_text_row = conn.execute(
        "SELECT * FROM listing_texts WHERE candidate_id = ?", (candidate_id,)
    ).fetchone()
    if listing_text_row is None:
        raise ValueError(f"No listing_texts row for candidate {candidate_id}")
    listing_text = dict(listing_text_row)

    group_ids = group_product.included_group_ids(conn, candidate_id)

    def attempt():
        result = group_product.create_candidate_gelato_product(
            conn, candidate_id, candidate, static_config, listing_text["title"],
            store_id=store_id, api_key=gelato_api_key, now=now,
        )
        return group_product.patch_etsy_listing(
            conn, result["group_product_id"], listing_text, static_config,
            shop_id=shop_id, etsy_api_key=etsy_api_key, etsy_api_secret=etsy_api_secret,
            etsy_access_token=etsy_access_token, dry_run=dry_run, now=now,
        )

    placeholders = ", ".join("?" * len(group_ids))
    try:
        try:
            etsy_listing_id = attempt()
        except Exception:
            etsy_listing_id = attempt()
    except Exception:
        conn.execute(
            f"UPDATE groups SET status = 'publish_failed', updated_at = ? WHERE id IN ({placeholders})",
            (timestamp, *group_ids),
        )
        conn.commit()
        raise

    conn.execute(
        f"UPDATE groups SET status = 'approved_published', updated_at = ? WHERE id IN ({placeholders})",
        (timestamp, *group_ids),
    )
    conn.execute(
        "UPDATE candidates SET status = 'completed', updated_at = ? WHERE id = ?",
        (timestamp, candidate_id),
    )
    conn.commit()

    return {"etsy_listing_id": etsy_listing_id}


def publish_primary_group(conn, candidate_id, *, static_config=None, store_id=None,
                           gelato_api_key=None, shop_id=None, etsy_api_key=None,
                           etsy_api_secret=None, etsy_access_token=None, dry_run=None, now=None) -> dict:
    """Evaluates the v4.12 publish gate for a candidate and publishes if it is ready.
    Kept under its old name because it is still the entry point every approve path and
    the M1 harness call - but approving the primary group no longer publishes anything
    on its own; the listing waits for the 5x7/10x24 decisions ([D1])."""
    static_config = static_config if static_config is not None else config.load_static_config()
    plan = candidate_publish_plan(conn, candidate_id, static_config, now=now)
    if not plan["ready"]:
        return {"etsy_listing_id": None, "published": False, "waiting_on": plan["waiting_on"]}
    result = publish_candidate(
        conn, candidate_id, static_config=static_config, store_id=store_id,
        gelato_api_key=gelato_api_key, shop_id=shop_id, etsy_api_key=etsy_api_key,
        etsy_api_secret=etsy_api_secret, etsy_access_token=etsy_access_token,
        dry_run=dry_run, now=now,
    )
    return {**result, "published": True, "stalled": plan["stalled"]}


def handle_decision(conn, candidate_id, group_id, action, decision_notes=None, *,
                     static_config=None, store_id=None, gelato_api_key=None, shop_id=None,
                     etsy_api_key=None, etsy_api_secret=None, etsy_access_token=None,
                     replicate_api_token=None, anthropic_api_key=None, dry_run=None, now=None) -> dict:
    timestamp = (now or datetime.now(timezone.utc).replace(tzinfo=None)).isoformat()

    if action == "approve":
        record_decision(conn, group_id, "approved", decision_notes, now=now)
        result = publish_primary_group(
            conn, candidate_id, static_config=static_config, store_id=store_id,
            gelato_api_key=gelato_api_key, shop_id=shop_id, etsy_api_key=etsy_api_key,
            etsy_api_secret=etsy_api_secret, etsy_access_token=etsy_access_token,
            dry_run=dry_run, now=now,
        )
        return {"action": "approve", **result}

    if action == "edit":
        record_decision(conn, group_id, "edited", decision_notes, now=now)
        resolved_static_config = static_config if static_config is not None else config.load_static_config()

        publish_group._discard_group_contribution(
            conn, candidate_id, group_id, store_id=store_id, gelato_api_key=gelato_api_key,
        )
        conn.execute("DELETE FROM critic_pass_attempts WHERE group_id = ?", (group_id,))
        conn.execute("DELETE FROM listing_texts WHERE candidate_id = ?", (candidate_id,))
        conn.execute("DELETE FROM group_messages WHERE group_id = ?", (group_id,))
        conn.commit()

        generate.generate_for_candidate(
            conn, candidate_id, correction_note=decision_notes, api_token=replicate_api_token, now=now,
        )
        primary_mockup.create_primary_mockup(
            conn, candidate_id, static_config=resolved_static_config, store_id=store_id,
            api_key=gelato_api_key, now=now,
        )
        compliance_draft.build_compliance_draft(
            conn, candidate_id, static_config=resolved_static_config,
            anthropic_api_key=anthropic_api_key, now=now,
        )
        return {"action": "edit"}

    if action == "reject":
        record_decision(conn, group_id, "rejected", decision_notes, now=now)

        publish_group._discard_group_contribution(
            conn, candidate_id, group_id, store_id=store_id, gelato_api_key=gelato_api_key,
        )

        conn.execute(
            "UPDATE groups SET status = 'rejected', updated_at = ? WHERE id = ?",
            (timestamp, group_id),
        )
        conn.execute(
            "UPDATE candidates SET status = 'failed', failed_reason = 'primary group rejected', "
            "updated_at = ? WHERE id = ?",
            (timestamp, candidate_id),
        )
        conn.commit()
        return {"action": "reject"}

    raise ValueError(f"Unknown action {action!r}")


def get_telegram_offset(conn) -> int | None:
    row = conn.execute("SELECT last_update_id FROM telegram_offset WHERE id = 1").fetchone()
    return row["last_update_id"] if row is not None else None


def set_telegram_offset(conn, last_update_id: int) -> None:
    conn.execute(
        "INSERT INTO telegram_offset (id, last_update_id) VALUES (1, ?) "
        "ON CONFLICT(id) DO UPDATE SET last_update_id = excluded.last_update_id",
        (last_update_id,),
    )
    conn.commit()


def process_update(conn, update, *, admin_chat_id=None, bot_token=None, static_config=None,
                    store_id=None, gelato_api_key=None, shop_id=None, etsy_api_key=None,
                    etsy_api_secret=None, etsy_access_token=None, replicate_api_token=None,
                    anthropic_api_key=None, dry_run=None, now=None) -> dict | None:
    admin_chat_id = admin_chat_id or config.require_env("TELEGRAM_ADMIN_CHAT_ID")
    parsed = resolve_callback(update)
    if parsed is None:
        # GL-45: this was the one path that consumed an update_id and left no row.
        # It made every gap in the logged update_id sequence ambiguous - "an outside
        # consumer ate it" and "it was an ordinary message" looked identical. Log it,
        # and a gap becomes proof.
        sender = (update.get("message") or {}).get("from") or {}
        log_telegram_event(conn, sender.get("id"), update, False,
                            "ignored: no callback_query", now=now)
        return None

    if not is_admin(parsed["telegram_user_id"], admin_chat_id):
        log_telegram_event(conn, parsed["telegram_user_id"], update, False,
                            "discarded: not admin", now=now)
        _ack(parsed["callback_query_id"], "Not authorised.", bot_token=bot_token)
        return None

    if parsed["action"] == NOOP_ACTION:
        log_telegram_event(conn, parsed["telegram_user_id"], update, False,
                            "ignored: already decided", now=now)
        _ack(parsed["callback_query_id"], "Already decided.", bot_token=bot_token)
        return None

    # Match the callback against ANY group_messages row for this group, not just the
    # first (M1): if a duplicate gallery ever produced two rows, a tap on the second
    # message must still resolve. The chat-id + message-id pair still has to match a
    # real row (chat_id str-compared as before, since it may be stored as int), so the
    # admin-only access guarantee is unchanged.
    message_rows = conn.execute(
        "SELECT chat_id, telegram_message_id FROM group_messages WHERE group_id = ?",
        (parsed["group_id"],),
    ).fetchall()
    match = any(
        str(row["chat_id"]) == str(parsed["chat_id"]) and row["telegram_message_id"] == parsed["message_id"]
        for row in message_rows
    )
    if not match:
        log_telegram_event(conn, parsed["telegram_user_id"], update, False,
                            "discarded: callback does not match a known group_messages row", now=now)
        _ack(parsed["callback_query_id"], "This message is no longer tracked - tap a current one.",
             bot_token=bot_token)
        return None

    group_row = conn.execute(
        "SELECT candidate_id, group_type FROM groups WHERE id = ?", (parsed["group_id"],)
    ).fetchone()
    candidate_id = group_row["candidate_id"]

    log_telegram_event(conn, parsed["telegram_user_id"], update, True, parsed["action"], now=now)

    # Acknowledge BEFORE dispatching: handle_decision can spend minutes in Gelato and
    # Etsy, and a callback query the bot answers that late has usually expired - which
    # is how a decision that landed still looked dropped for two days (GL-45 §5).
    _ack(parsed["callback_query_id"], f"Got it - {parsed['action']}...", bot_token=bot_token)
    _mark_decided(parsed, bot_token=bot_token)

    if group_row["group_type"] == "primary":
        result = handle_decision(
            conn, candidate_id, parsed["group_id"], parsed["action"], static_config=static_config,
            store_id=store_id, gelato_api_key=gelato_api_key, shop_id=shop_id, etsy_api_key=etsy_api_key,
            etsy_api_secret=etsy_api_secret, etsy_access_token=etsy_access_token,
            replicate_api_token=replicate_api_token, anthropic_api_key=anthropic_api_key,
            dry_run=dry_run, now=now,
        )
    else:
        result = publish_group.handle_decision(
            conn, candidate_id, parsed["group_id"], parsed["action"], static_config=static_config,
            store_id=store_id, gelato_api_key=gelato_api_key, shop_id=shop_id, etsy_api_key=etsy_api_key,
            etsy_api_secret=etsy_api_secret, etsy_access_token=etsy_access_token,
            dry_run=dry_run, now=now,
        )

    return {"candidate_id": candidate_id, "group_id": parsed["group_id"], **result}


def retry_publish_failed_groups(conn, *, static_config=None, store_id=None, gelato_api_key=None,
                                 shop_id=None, etsy_api_key=None, etsy_api_secret=None,
                                 etsy_access_token=None, dry_run=None, now=None) -> list:
    """Re-attempt publishing any candidate stuck at publish_failed - once per poll cycle
    (H1: publish_failed isn't a dead end). v4.12: the unit of retry is the CANDIDATE, not
    the group, because one listing carries every group. publish_candidate is idempotent:
    a Gelato product that was already created is reused, never re-created, and gallery
    images that already uploaded are not uploaded twice. Returns the candidate ids
    retried."""
    static_config = static_config if static_config is not None else config.load_static_config()

    candidate_ids = [
        row["candidate_id"] for row in conn.execute(
            "SELECT DISTINCT candidate_id FROM groups "
            "WHERE status = 'publish_failed' AND decision = 'approved' ORDER BY candidate_id"
        ).fetchall()
    ]

    retried = []
    for candidate_id in candidate_ids:
        try:
            publish_candidate(
                conn, candidate_id, static_config=static_config, store_id=store_id,
                gelato_api_key=gelato_api_key, shop_id=shop_id, etsy_api_key=etsy_api_key,
                etsy_api_secret=etsy_api_secret, etsy_access_token=etsy_access_token,
                dry_run=dry_run, now=now,
            )
        except Exception as exc:
            print(f"publish_failed retry failed for candidate {candidate_id}: {exc}")
            continue
        retried.append(candidate_id)
    return retried


def run_publish_primary_group_cycle(conn, *, admin_chat_id=None, bot_token=None, static_config=None,
                                     store_id=None, gelato_api_key=None, shop_id=None,
                                     etsy_api_key=None, etsy_api_secret=None, etsy_access_token=None,
                                     replicate_api_token=None, anthropic_api_key=None,
                                     dry_run=None, now=None) -> list:
    # GL-45: this is the only place in the pipeline that consumes the bot's single,
    # server-side update cursor. A poll from a copy of the database deletes updates
    # the canonical database will never see, so the identity check belongs here,
    # ahead of the call, not in each of the three entrypoints that route through it.
    db.assert_canonical(conn)

    last_offset = get_telegram_offset(conn)
    offset = last_offset + 1 if last_offset is not None else None
    updates = telegram_client.get_updates(offset=offset, bot_token=bot_token)

    processed = []
    for update in updates:
        update_id = update["update_id"]
        try:
            result = process_update(
                conn, update, admin_chat_id=admin_chat_id, bot_token=bot_token, static_config=static_config,
                store_id=store_id, gelato_api_key=gelato_api_key, shop_id=shop_id, etsy_api_key=etsy_api_key,
                etsy_api_secret=etsy_api_secret, etsy_access_token=etsy_access_token,
                replicate_api_token=replicate_api_token, anthropic_api_key=anthropic_api_key,
                dry_run=dry_run, now=now,
            )
        except Exception as exc:
            # process_update can raise after resolve_callback succeeds but before/during
            # handle_decision — this cron has no console to watch, so a print() alone leaves
            # no durable trace that the admin's tap was dropped. accepted=True distinguishes
            # "this was a real event that failed" from the accepted=False discard-path rows
            # log_telegram_event already writes for non-admin/unknown-group callbacks.
            telegram_user_id = update.get("callback_query", {}).get("from", {}).get("id")
            log_telegram_event(conn, telegram_user_id, update, True, f"error: {exc}", now=now)
            print(f"process_update failed for update {update_id}: {exc}")
        else:
            if result is not None:
                processed.append(result)
        # GL-45: advance per update, not once after the loop. A run killed mid-publish
        # used to re-deliver everything it had already handled on the next poll -
        # update_ids 365-367 appear twice in the log, ten minutes apart, the second time
        # as an error. Either the update is handled or its outcome is logged; both mean
        # it must not come back.
        set_telegram_offset(conn, update_id)

    # Once per poll cycle, re-attempt any group stuck at publish_failed after an
    # approved decision - a transient patch failure shouldn't strand it forever (H1).
    try:
        retry_publish_failed_groups(
            conn, static_config=static_config, store_id=store_id, gelato_api_key=gelato_api_key,
            shop_id=shop_id, etsy_api_key=etsy_api_key,
            etsy_api_secret=etsy_api_secret, etsy_access_token=etsy_access_token,
            dry_run=dry_run, now=now,
        )
    except Exception as exc:
        print(f"retry_publish_failed_groups failed: {exc}")

    return processed
