import os
import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "db" / "schema.sql"


class NonCanonicalDBError(Exception):
    pass


def connected_file(conn: sqlite3.Connection) -> str:
    """Absolute path of the file behind the main database (empty for :memory:)."""
    return conn.execute("PRAGMA database_list").fetchone()[2] or ""


def assert_canonical(conn: sqlite3.Connection) -> None:
    """GL-45 guard: refuse to act as the Telegram consumer from a non-canonical
    database file.

    getUpdates has exactly one cursor per bot token, but telegram_offset lives in
    whichever SQLite file the process was pointed at. A run against a copy - a
    throwaway soak DB, a second worktree, a restored .bak - polls with that copy's
    offset, receives the real pending updates and confirms them (deleting them for
    every consumer), then writes the results where nobody reads. The canonical DB
    sees no processed row, no discarded row, and no update: a silent drop of the
    owner's tap. GL-7's process lock cannot see this - it is keyed on the script's
    directory, so a same-tree run against a copy takes the same lock and proceeds.

    Override with QHOTO_ALLOW_NONCANONICAL_DB=true for a deliberate offline read;
    re-point after a promote-and-swap with `python migrate.py <path> --bless`.
    """
    if os.environ.get("QHOTO_ALLOW_NONCANONICAL_DB", "").strip().lower() == "true":
        return
    try:
        row = conn.execute("SELECT canonical_path FROM db_identity WHERE id = 1").fetchone()
    except sqlite3.OperationalError:
        row = None
    if row is None or not row[0]:
        raise NonCanonicalDBError(
            "db_identity is unset - run `python migrate.py <db> --bless` on the canonical "
            "database before polling Telegram"
        )
    actual, canonical = connected_file(conn), row[0]
    if os.path.normcase(os.path.realpath(actual)) != os.path.normcase(os.path.realpath(canonical)):
        raise NonCanonicalDBError(
            f"{actual} is not the canonical database ({canonical}) - refusing to consume "
            "Telegram updates that the canonical database would never see"
        )


def get_connection(db_path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    schema_sql = SCHEMA_PATH.read_text()
    conn.executescript(schema_sql)
    conn.commit()
