"""GL-45: record which file on disk is the canonical database.

The Telegram cursor is per bot token and global; the telegram_offset row is
per database file. A run pointed at a copy (a throwaway soak DB, a second
worktree, a restored .bak) polls with that copy's offset, receives the real
pending updates and confirms them - which deletes them for every consumer -
then writes the results somewhere nobody reads. From the canonical database's
point of view that is a perfect silent drop.

The identity is written once, here, as the absolute path of the file being
migrated, and is deliberately NOT rewritten by later migrate() calls: a copy
keeps pointing at the original, which is exactly what makes the copy
detectable. Promoting a different file (the GL-38 promote-and-swap) is a
deliberate act and gets a deliberate command: migrate.py --bless.
"""
import sqlite3
from pathlib import Path


def migrate(db_path) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS db_identity ("
            "id INTEGER PRIMARY KEY CHECK (id = 1), canonical_path TEXT NOT NULL)"
        )
        conn.execute(
            "INSERT OR IGNORE INTO db_identity (id, canonical_path) VALUES (1, ?)",
            (str(Path(db_path).resolve()),),
        )
        conn.commit()
    finally:
        conn.close()


def bless(db_path) -> str:
    """Make db_path the canonical file, whatever it said before. Used after a
    deliberate promote-and-swap."""
    resolved = str(Path(db_path).resolve())
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS db_identity ("
            "id INTEGER PRIMARY KEY CHECK (id = 1), canonical_path TEXT NOT NULL)"
        )
        conn.execute(
            "INSERT INTO db_identity (id, canonical_path) VALUES (1, ?) "
            "ON CONFLICT(id) DO UPDATE SET canonical_path = excluded.canonical_path",
            (resolved,),
        )
        conn.commit()
    finally:
        conn.close()
    return resolved
