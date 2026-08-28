"""GL-31: add groups.reminder_sent_at - written in the same commit as the
stall reminder re-send, read before any further send so the ping fires at
most once per group. Safe to run against any DB, any number of times.
"""
import sqlite3
import sys
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "db" / "qhoto.sqlite3"

NEW_COLUMNS = {
    "reminder_sent_at": "TEXT",
}


def migrate(db_path) -> list:
    conn = sqlite3.connect(db_path)
    try:
        existing = {row[1] for row in conn.execute("PRAGMA table_info(groups)").fetchall()}
        added = []
        for column, col_type in NEW_COLUMNS.items():
            if column in existing:
                continue
            conn.execute(f"ALTER TABLE groups ADD COLUMN {column} {col_type}")
            added.append(column)
        conn.commit()
        return added
    finally:
        conn.close()


def main():
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB_PATH
    added = migrate(db_path)
    if added:
        print(f"added {len(added)} column(s): {', '.join(added)}")
    else:
        print("already present: no columns added")


if __name__ == "__main__":
    main()
