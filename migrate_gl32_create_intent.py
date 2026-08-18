"""GL-32: add group_products.gelato_create_intent_at - written and committed
right before the Gelato create-from-template POST, cleared by the same UPDATE
that records gelato_product_id. A crash between the POST returning and that
UPDATE committing leaves the intent timestamp set with no product id, which
pipeline/reconcile.find_unconfirmed_gelato_creates can find - the create
attempt itself was never written down before, so nothing could be checked
against. Safe to run against any DB, any number of times.
"""
import sqlite3
import sys
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "db" / "qhoto.sqlite3"

NEW_COLUMNS = {
    "gelato_create_intent_at": "TEXT",
}


def migrate(db_path) -> list:
    conn = sqlite3.connect(db_path)
    try:
        existing = {row[1] for row in conn.execute("PRAGMA table_info(group_products)").fetchall()}
        added = []
        for column, col_type in NEW_COLUMNS.items():
            if column in existing:
                continue
            conn.execute(f"ALTER TABLE group_products ADD COLUMN {column} {col_type}")
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
