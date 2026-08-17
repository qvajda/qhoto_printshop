"""GL-131 (#139): the pending_decisions queue the always-on Telegram listener
writes and the scheduled stage drains.

The listener records the decision and acks; it never calls Gelato or Etsy
(ADR-0005 amendment, 2026-08-17). This table is the seam between the two: one
row per accepted tap, claimed by the scheduled cycle. update_id is UNIQUE so a
listener killed between the enqueue and the offset advance re-processes the
re-delivered update without queueing the same decision twice.

Idempotent; safe to run any number of times.
"""
import sqlite3
import sys
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "db" / "qhoto.sqlite3"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS pending_decisions (
  id INTEGER PRIMARY KEY,
  group_id INTEGER NOT NULL REFERENCES groups(id),
  action TEXT NOT NULL,
  update_id INTEGER UNIQUE,
  created_at TEXT NOT NULL,
  dispatched_at TEXT,
  error TEXT
)
"""


def migrate(db_path) -> dict:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(CREATE_TABLE_SQL)
        conn.commit()
        return {"created": "pending_decisions"}
    finally:
        conn.close()


def main():
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB_PATH
    migrate(db_path)
    print("pending_decisions ready")


if __name__ == "__main__":
    main()
