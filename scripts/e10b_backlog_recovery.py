"""E10b backlog recovery - throwaway, owner-run, one candidate at a time.

Four candidates (77, 78, 79, 81) sit at primary_review with pre-GL-56 copy and a
pre-GL-56 three-button keyboard already sent. run_digest_cycle will not re-send
them (its selection excludes any group with a group_messages row), so they have
no '📝 Redo copy only' button and their live '✏️ Edit' button would regenerate
the artwork - the exact loss GL-56 was built to prevent.

handle_decision(..., 'redraft') is the whole recovery: it deletes the
group_messages row itself, so the next digest cycle re-sends the entry with the
new two-row keyboard. See docs/2026-08-11-e10-kickoff.md §2.

Usage (from the repo root, with .env loaded as the entrypoints load it):

    python scripts/e10b_backlog_recovery.py plan
    python scripts/e10b_backlog_recovery.py collapse
    python scripts/e10b_backlog_recovery.py redraft 77

'plan' touches nothing. 'collapse' clears the four stale keyboards (Telegram
only, no DB write). 'redraft' takes ONE candidate id and calls the real
compliance_draft + critic_pass, so it spends Anthropic tokens - read the result
before running the next one.

ponytail: throwaway. No argparse subcommand framework, no retry logic, no
progress bar. Delete after E10b.
"""
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pipeline.config as config
import pipeline.db as db
import pipeline.publish_primary_group as publish_primary_group
import pipeline.telegram_client as telegram_client

CANDIDATES = (77, 78, 79, 81)
NOTES = "E10b backlog recovery (GL-55/GL-56)"
DB_PATH = Path(__file__).resolve().parent.parent / "db" / "qhoto.sqlite3"


def _sha256(path):
    """The on-disk artwork bytes. The hard constraint (a design is only ever
    image-generated once) is asserted by a test; this observes it on the real data."""
    if not path:
        return None
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = DB_PATH.parent.parent / resolved
    if not resolved.exists():
        return f"MISSING:{resolved}"
    return hashlib.sha256(resolved.read_bytes()).hexdigest()


def _primary_group(conn, candidate_id):
    return conn.execute(
        "SELECT id, status, decision FROM groups "
        "WHERE candidate_id = ? AND group_type = 'primary'",
        (candidate_id,),
    ).fetchone()


def _fingerprint(conn, candidate_id):
    """Everything that must NOT change across a redraft."""
    row = conn.execute(
        "SELECT niche, status, base_image_url, base_image_local_path, base_image_sha256, "
        "base_replicate_prediction_id FROM candidates WHERE id = ?",
        (candidate_id,),
    ).fetchone()
    if row is None:
        return None
    return {
        "niche": row["niche"],
        "status": row["status"],
        "base_image_url": row["base_image_url"],
        "base_image_local_path": row["base_image_local_path"],
        "base_image_sha256": row["base_image_sha256"],
        "base_replicate_prediction_id": row["base_replicate_prediction_id"],
        "disk_sha256": _sha256(row["base_image_local_path"]),
    }


def _messages(conn, group_id):
    return conn.execute(
        "SELECT id, chat_id, telegram_message_id FROM group_messages WHERE group_id = ?",
        (group_id,),
    ).fetchall()


def plan(conn):
    for candidate_id in CANDIDATES:
        group = _primary_group(conn, candidate_id)
        fingerprint = _fingerprint(conn, candidate_id)
        if group is None or fingerprint is None:
            print(f"candidate {candidate_id}: NOT FOUND - stop and re-check the DB")
            continue
        messages = _messages(conn, group["id"])
        print(f"candidate {candidate_id}: status={fingerprint['status']} "
              f"group={group['id']} ({group['status']}, decision={group['decision']!r})")
        print(f"  niche(raw) = {fingerprint['niche']!r}")
        print(f"  artwork    = {fingerprint['base_image_local_path']}")
        print(f"  disk sha   = {fingerprint['disk_sha256']}")
        for message in messages:
            print(f"  group_messages id={message['id']} "
                  f"telegram_message_id={message['telegram_message_id']}")
        if not messages:
            print("  no group_messages row - already redrafted, or never sent")


def collapse(conn, bot_token):
    """Clear the stale keyboards. Clearing beats a 'noop' label: these messages are
    about to be superseded by a fresh digest entry, not decided."""
    for candidate_id in CANDIDATES:
        group = _primary_group(conn, candidate_id)
        if group is None:
            print(f"candidate {candidate_id}: no primary group, skipped")
            continue
        for message in _messages(conn, group["id"]):
            message_id = message["telegram_message_id"]
            try:
                telegram_client.edit_message_reply_markup(
                    message["chat_id"], message_id, None, bot_token=bot_token,
                )
                print(f"candidate {candidate_id}: cleared keyboard on message {message_id}")
            except Exception as exc:
                # Not fatal: a message whose keyboard is already gone reports
                # 'message is not modified', which is the state we wanted anyway.
                print(f"candidate {candidate_id}: message {message_id} NOT cleared: {exc}")


def redraft(conn, candidate_id, bot_token):
    if candidate_id not in CANDIDATES:
        raise SystemExit(f"{candidate_id} is not one of the four E10b candidates {CANDIDATES}")

    group = _primary_group(conn, candidate_id)
    if group is None:
        raise SystemExit(f"candidate {candidate_id}: no primary group")

    before = _fingerprint(conn, candidate_id)
    print(f"BEFORE {candidate_id}: sha={before['base_image_sha256']} "
          f"disk={before['disk_sha256']} status={before['status']}")

    result = publish_primary_group.handle_decision(
        conn, candidate_id, group["id"], "redraft", decision_notes=NOTES,
    )
    print(f"handle_decision -> {result}")

    after = _fingerprint(conn, candidate_id)
    print(f"AFTER  {candidate_id}: sha={after['base_image_sha256']} "
          f"disk={after['disk_sha256']} status={after['status']}")

    for field in ("base_image_url", "base_image_local_path", "base_image_sha256",
                  "base_replicate_prediction_id", "disk_sha256"):
        if before[field] != after[field]:
            # Loud, because this would mean the copy-only path regenerated artwork.
            raise SystemExit(
                f"HARD CONSTRAINT VIOLATED: {field} changed for candidate {candidate_id}\n"
                f"  before={before[field]!r}\n  after={after[field]!r}"
            )
    print(f"candidate {candidate_id}: artwork provably unchanged, copy redrafted")

    texts = conn.execute(
        "SELECT title, description, tags FROM listing_texts WHERE candidate_id = ? "
        "ORDER BY id DESC LIMIT 1", (candidate_id,),
    ).fetchone()
    if texts is None:
        print("  no listing_texts row - the draft did not land, read the traceback above")
    else:
        # Read the whole row, not just the seasonal field (GL-53 drift class (c)).
        print(f"  title: {texts['title']}")
        print(f"  tags:  {texts['tags']}")
        print(f"  description:\n{texts['description']}")


def main(argv):
    if len(argv) < 2:
        raise SystemExit(__doc__)
    command = argv[1]
    conn = db.get_connection(DB_PATH)
    try:
        if command == "plan":
            plan(conn)
        elif command == "collapse":
            collapse(conn, config.require_env("TELEGRAM_BOT_TOKEN"))
        elif command == "redraft":
            if len(argv) != 3:
                raise SystemExit("redraft takes exactly one candidate id")
            redraft(conn, int(argv[2]), config.require_env("TELEGRAM_BOT_TOKEN"))
        else:
            raise SystemExit(f"unknown command {command!r}")
    finally:
        conn.close()


if __name__ == "__main__":
    main(sys.argv)
