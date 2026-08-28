"""GL-51a (#200): rewrites candidates.base_image_local_path and the local rows of
product_images.image_url from absolute, machine-specific paths to paths relative to
the configured artefact root (pipeline.config.artefact_root). An http(s) value (an
R2-hosted row) is left untouched - only local rows change meaning.

Idempotent: a value already relative, empty, or http(s) is a no-op. A value that
does not live under the configured root cannot be safely re-rooted (guessing would
silently point it at the wrong file) - it is left as-is and reported, not dropped.
"""
import sqlite3
import sys
from pathlib import Path

from pipeline import config

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "db" / "qhoto.sqlite3"


def _rewrite_value(value, root: Path):
    """Returns (new_value, unresolvable). unresolvable=True means value is an
    absolute local path that does not live under root - left untouched, reported
    by the caller rather than guessed at."""
    if not value or value.startswith(("http://", "https://")):
        return value, False
    path = Path(value)
    if not path.is_absolute():
        return value, False
    try:
        return path.relative_to(root).as_posix(), False
    except ValueError:
        return value, True


def _migrate_table(conn, table: str, column: str, root: Path, unresolved: list) -> None:
    rows = conn.execute(f"SELECT id, {column} FROM {table}").fetchall()
    for row in rows:
        new_value, unresolvable = _rewrite_value(row[column], root)
        if unresolvable:
            unresolved.append({"table": table, "id": row["id"], "value": row[column]})
            continue
        if new_value != row[column]:
            conn.execute(f"UPDATE {table} SET {column} = ? WHERE id = ?", (new_value, row["id"]))


def migrate(db_path) -> dict:
    root = config.artefact_root()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    unresolved = []
    try:
        _migrate_table(conn, "candidates", "base_image_local_path", root, unresolved)
        _migrate_table(conn, "product_images", "image_url", root, unresolved)
        conn.commit()
    finally:
        conn.close()
    return {"unresolved": unresolved}


def main():
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB_PATH
    result = migrate(db_path)
    if result["unresolved"]:
        print(f"gl51_relative_artefact_paths: {len(result['unresolved'])} value(s) could not be re-rooted:")
        for item in result["unresolved"]:
            print(f"  {item['table']}.id={item['id']}: {item['value']!r}")
    else:
        print("gl51_relative_artefact_paths: all local paths re-rooted")


if __name__ == "__main__":
    main()
