"""One-off: the second half of the v4.12 schema move (GL-22 session 2), on top of
migrate_group_products_candidate_id.py. Two changes:

  1. product_images.etsy_listing_image_id (nullable, additive) - records Etsy's own
     listing_image_id for a gallery image once it has been uploaded. patch_etsy_listing
     re-uploads the whole gallery on every call (no delta, no dedup), so without this a
     second call after a partial failure would duplicate every photo on the live
     listing. Rows carrying an id are skipped.

  2. 'stalled_skipped' added to the groups.status CHECK constraint ([D2]) - the state a
     secondary group is moved to when it sits undecided past
     config.GROUP_REVIEW_STALL_DAYS and the candidate publishes without it.

Change 2 is NOT additive: SQLite cannot alter a CHECK constraint in place, so `groups`
is rebuilt (create-copy-drop-rename, the standard 12-step). Flagged rather than done
quietly, because session 1's migration deliberately avoided a table rebuild. It is
safe here for a different reason than "additive": every existing row is copied
verbatim, no column is added, removed, reordered or retyped, and only the set of
values the CHECK admits widens - so no existing row can fail the new constraint and
nothing that reads `groups` sees a different shape. Rollback for both changes is
"stop calling the new code path"; the widened CHECK admits strictly more than before,
so old code keeps working against it unchanged.

Safe to run against any DB, any number of times.
"""
import sqlite3
import sys
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "db" / "qhoto.sqlite3"

NEW_COLUMNS = [
    ("product_images", "etsy_listing_image_id", "TEXT"),
]

GROUPS_TABLE_V412 = """
CREATE TABLE groups_v412_new (
  id INTEGER PRIMARY KEY,
  candidate_id INTEGER NOT NULL REFERENCES candidates(id),
  group_type TEXT NOT NULL CHECK(group_type IN ('primary','5x7','10x24')),
  decision TEXT CHECK(decision IN ('approved','edited','rejected')),
  decision_notes TEXT,
  decided_at TEXT,
  status TEXT NOT NULL CHECK(status IN (
    'pending_generation','pending_review','approved_published','rejected','failed_abandoned',
    'publish_failed','stalled_skipped'
  )),
  failed_reason TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(candidate_id, group_type)
)
"""

GROUPS_COLUMNS = (
    "id, candidate_id, group_type, decision, decision_notes, decided_at, status, "
    "failed_reason, created_at, updated_at"
)


def _groups_check_needs_widening(conn) -> bool:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'groups'"
    ).fetchone()
    return row is not None and "stalled_skipped" not in row[0]


def migrate(db_path) -> dict:
    conn = sqlite3.connect(db_path)
    try:
        added = []
        for table, column, coldef in NEW_COLUMNS:
            existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
            if column in existing:
                continue
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coldef}")
            added.append(f"{table}.{column}")

        rebuilt_groups = _groups_check_needs_widening(conn)
        if rebuilt_groups:
            # Foreign keys off for the swap: other tables reference groups(id) and would
            # otherwise see the table vanish mid-rebuild. Rows are copied verbatim.
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute(GROUPS_TABLE_V412)
            conn.execute(
                f"INSERT INTO groups_v412_new ({GROUPS_COLUMNS}) SELECT {GROUPS_COLUMNS} FROM groups"
            )
            conn.execute("DROP TABLE groups")
            conn.execute("ALTER TABLE groups_v412_new RENAME TO groups")
            conn.commit()
            conn.execute("PRAGMA foreign_keys = ON")

        conn.commit()
        return {"added_columns": added, "rebuilt_groups": rebuilt_groups}
    finally:
        conn.close()


def main():
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB_PATH
    result = migrate(db_path)
    if result["added_columns"]:
        print(f"added column(s): {', '.join(result['added_columns'])}")
    else:
        print("no columns added (already present)")
    print("groups.status CHECK widened for 'stalled_skipped'" if result["rebuilt_groups"]
          else "groups.status CHECK already admits 'stalled_skipped'")


if __name__ == "__main__":
    main()
