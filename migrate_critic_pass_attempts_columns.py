"""One-off: add the S4-d per-criterion telemetry columns to an existing
critic_pass_attempts table (db/schema.sql's CREATE TABLE IF NOT EXISTS won't
retroactively add columns to a table that already exists). Safe to run
against any DB, any number of times - only missing columns are added.
"""
import sqlite3
import sys
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "db" / "qhoto.sqlite3"

NEW_COLUMNS = {
    "overall": "TEXT",
    "criteria_json": "TEXT",
    "cov": "REAL",
}


def migrate(db_path) -> list:
    """Adds any of NEW_COLUMNS missing from critic_pass_attempts. Returns the list of
    column names actually added (empty list = already up to date)."""
    conn = sqlite3.connect(db_path)
    try:
        existing = {row[1] for row in conn.execute("PRAGMA table_info(critic_pass_attempts)").fetchall()}
        added = []
        for column, col_type in NEW_COLUMNS.items():
            if column in existing:
                continue
            conn.execute(f"ALTER TABLE critic_pass_attempts ADD COLUMN {column} {col_type}")
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
