"""E12 §5 - GL-75: bring candidates 77, 78, 79 back from failed_abandoned.

What happened to them: all three were abandoned on 2026-08-11 by the copy_only retry
loop, which had no hand-back path yet - three failed critic attempts marked the
candidate failed and the group failed_abandoned. GL-70 (E11) replaced that with
critic_pass.hand_back_to_owner, and GL-68 gave the drafter the master image it was
missing, which is why the copy contradicted the artwork in the first place
("the title/description promise a minimalist line-drawn leaf ... every image actually
shows a red cardinal"). So the restore is: undo the abandonment, then re-run the same
copy-only redraft under the fixed code.

    python scripts/e12_gl75_restore.py plan
    python scripts/e12_gl75_restore.py restore 77     # ONE at a time, spends tokens

The artwork is never regenerated (redraft, not edit) and the script proves it: the
on-disk sha256 is compared before AND after, and a change is fatal.

ponytail: throwaway, one candidate per invocation, no retry logic. Delete after E12.
"""
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pipeline.config as config
import pipeline.db as db
import pipeline.publish_primary_group as publish_primary_group

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "db" / "qhoto.sqlite3"
CANDIDATES = (77, 78, 79)
NOTES = "GL-75 restore (E12 §5)"
# The whole claim of the row: this artwork survives the restore.
EXPECTED_SHA = {
    77: "6a972e41e35bdd5a71ff667ae54f5c13750feb2f93d48f4371188f4b0d44972c",
    78: "841fe7d38204ebe0febb18c6f2cf777b936bc6865fea256b5797227fe0c7ddc3",
    79: "fb656b418da220ccd9ca55a18adfc60351756bb1b496e5d173e5715ee04b148c",
}


def _sha256(path):
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = ROOT / resolved
    return hashlib.sha256(resolved.read_bytes()).hexdigest() if resolved.exists() else f"MISSING:{resolved}"


def _state(conn, candidate_id):
    candidate = conn.execute(
        "SELECT status, failed_reason, base_image_local_path FROM candidates WHERE id = ?",
        (candidate_id,),
    ).fetchone()
    group = conn.execute(
        "SELECT id, status, decision, failed_reason FROM groups "
        "WHERE candidate_id = ? AND group_type = 'primary'",
        (candidate_id,),
    ).fetchone()
    return candidate, group


def plan(conn):
    for candidate_id in CANDIDATES:
        candidate, group = _state(conn, candidate_id)
        sha = _sha256(candidate["base_image_local_path"])
        print(f"candidate {candidate_id}: status={candidate['status']} "
              f"group={group['id']} ({group['status']}, decision={group['decision']!r})")
        print(f"  sha256 {'OK' if sha == EXPECTED_SHA[candidate_id] else 'MISMATCH'}: {sha}")
        print(f"  failed_reason: {group['failed_reason']}")


def restore(conn, candidate_id):
    if candidate_id not in CANDIDATES:
        raise SystemExit(f"{candidate_id} is not one of {CANDIDATES}")
    candidate, group = _state(conn, candidate_id)
    before = _sha256(candidate["base_image_local_path"])
    if before != EXPECTED_SHA[candidate_id]:
        raise SystemExit(f"candidate {candidate_id}: artwork sha256 is already wrong ({before}) - stop")
    print(f"BEFORE {candidate_id}: {candidate['status']}/{group['status']} sha={before}")

    timestamp = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    # Undo the abandonment. failed_abandoned is terminal - run_digest_cycle skips it and
    # handle_decision would draft into a group nothing will ever re-send.
    conn.execute(
        "UPDATE candidates SET status = 'primary_review', failed_reason = NULL, updated_at = ? "
        "WHERE id = ?", (timestamp, candidate_id),
    )
    conn.execute(
        "UPDATE groups SET status = 'pending_review', failed_reason = NULL, updated_at = ? "
        "WHERE id = ?", (timestamp, group["id"]),
    )
    conn.commit()

    # redraft, never edit: no generate call, no mockup re-render. It also resets the
    # retry budget by deleting critic_pass_attempts, which is what lets the three
    # exhausted attempts be re-run at all.
    result = publish_primary_group.handle_decision(
        conn, candidate_id, group["id"], "redraft", decision_notes=NOTES,
    )
    print(f"handle_decision -> {result}")

    candidate, group = _state(conn, candidate_id)
    after = _sha256(candidate["base_image_local_path"])
    if after != before:
        raise SystemExit(
            f"HARD CONSTRAINT VIOLATED: candidate {candidate_id} artwork changed\n"
            f"  before={before}\n  after ={after}"
        )
    print(f"AFTER  {candidate_id}: {candidate['status']}/{group['status']} sha={after} (unchanged)")

    texts = conn.execute(
        "SELECT title, description, tags FROM listing_texts WHERE candidate_id = ? "
        "ORDER BY id DESC LIMIT 1", (candidate_id,),
    ).fetchone()
    if texts is None:
        print("  no listing_texts row - the draft did not land, read the traceback above")
        return
    # Read the whole row, not just the seasonal field (GL-53 drift class (c)).
    print(f"  title: {texts['title']}")
    print(f"  tags:  {texts['tags']}")
    print(f"  description:\n{texts['description']}")


def main(argv):
    if len(argv) < 2:
        raise SystemExit(__doc__)
    config.load_env()
    conn = db.get_connection(DB_PATH)
    try:
        if argv[1] == "plan":
            plan(conn)
        elif argv[1] == "restore":
            if len(argv) != 3:
                raise SystemExit("restore takes exactly one candidate id")
            restore(conn, int(argv[2]))
        else:
            raise SystemExit(f"unknown command {argv[1]!r}")
    finally:
        conn.close()


if __name__ == "__main__":
    main(sys.argv)
