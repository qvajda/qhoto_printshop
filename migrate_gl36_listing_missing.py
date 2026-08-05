"""GL-36: group_products.status gains 'listing_missing' - the state a reconcile
pass (pipeline/reconcile.py) sets when a row claims a published Etsy listing
that a live GET returns 404 for. SQLite cannot alter a CHECK constraint in
place, so group_products is rebuilt (create-copy-drop-rename), same pattern as
migrate_v412_gallery.py's groups rebuild: every existing row copied verbatim,
no column added/removed/reordered/retyped, only the set of values the CHECK
admits widens - so no existing row can fail the new constraint.

Safe to run against any DB, any number of times.
"""
import sqlite3
import sys
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "db" / "qhoto.sqlite3"

GROUP_PRODUCTS_TABLE_GL36 = """
CREATE TABLE group_products_gl36_new (
  id INTEGER PRIMARY KEY,
  group_id INTEGER NOT NULL REFERENCES groups(id),
  candidate_id INTEGER REFERENCES candidates(id),
  gelato_template_id TEXT NOT NULL,
  gelato_product_id TEXT,
  etsy_listing_id TEXT,
  title TEXT,
  status TEXT NOT NULL CHECK(status IN (
    'pending','created','mockup_failed','publish_failed','published','deleted','listing_missing'
  )),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
)
"""

GROUP_PRODUCTS_COLUMNS = (
    "id, group_id, candidate_id, gelato_template_id, gelato_product_id, etsy_listing_id, "
    "title, status, created_at, updated_at"
)


def _needs_widening(conn) -> bool:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'group_products'"
    ).fetchone()
    return row is not None and "listing_missing" not in row[0]


def migrate(db_path) -> dict:
    conn = sqlite3.connect(db_path)
    try:
        rebuilt = _needs_widening(conn)
        if rebuilt:
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute(GROUP_PRODUCTS_TABLE_GL36)
            conn.execute(
                f"INSERT INTO group_products_gl36_new ({GROUP_PRODUCTS_COLUMNS}) "
                f"SELECT {GROUP_PRODUCTS_COLUMNS} FROM group_products"
            )
            conn.execute("DROP TABLE group_products")
            conn.execute("ALTER TABLE group_products_gl36_new RENAME TO group_products")
            conn.commit()
            conn.execute("PRAGMA foreign_keys = ON")
        conn.commit()
        return {"rebuilt": rebuilt}
    finally:
        conn.close()


def main():
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB_PATH
    result = migrate(db_path)
    print("group_products.status widened for 'listing_missing'" if result["rebuilt"]
          else "group_products.status already admits 'listing_missing'")


if __name__ == "__main__":
    main()
