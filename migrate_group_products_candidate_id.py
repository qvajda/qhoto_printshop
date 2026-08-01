"""One-off: additive v4.12 schema migration on an existing DB whose schema
predates it. v4.12 moves the Gelato product / Etsy listing from being owned
by an aspect-ratio *group* to being owned by the *candidate* (one listing per
artwork, sizes as variants). This adds three nullable columns:

  - group_products.candidate_id: the product now belongs to the candidate,
    not the group.
  - group_product_variants.group_id: each variant records which group
    contributed that size.
  - product_images.group_id: each image records which group contributed it -
    this is what makes a later *scoped* gallery rebuild possible at all;
    without it, rebuilding one group's images would wipe another group's
    already-uploaded images.

No backfill. Existing rows keep candidate_id/group_id NULL and stay on the
old (group-owns-product) code path; `candidate_id IS NOT NULL` is the gate
the new v4.12 code path uses to distinguish new rows from old. This also
means the five real GL-9 rows (group_products ids 9-13, id 10 published with
real Etsy listing 4542159277) are left byte-identical.

group_products.group_id stays NOT NULL - a v4.12 row still records which
group first created the product - so this migration never rebuilds that
table (SQLite can't drop/loosen a NOT NULL without a full table rebuild,
which is exactly the non-additive change the rollback story below avoids).

Purely additive: no row is rewritten, no table is rebuilt. Rollback is
"stop calling the new code path" (i.e. revert the code that reads/writes
these columns) - there is no down-migration, because there's nothing to
undo at the data level. Safe to run against any DB, any number of times.
"""
import sqlite3
import sys
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "db" / "qhoto.sqlite3"

NEW_COLUMNS = [
    ("group_products", "candidate_id", "INTEGER REFERENCES candidates(id)"),
    ("group_product_variants", "group_id", "INTEGER REFERENCES groups(id)"),
    ("product_images", "group_id", "INTEGER REFERENCES groups(id)"),
]


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
        conn.commit()
        return {"added_columns": added}
    finally:
        conn.close()


def main():
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB_PATH
    result = migrate(db_path)
    if result["added_columns"]:
        print(f"added {len(result['added_columns'])} column(s): {', '.join(result['added_columns'])}")
    else:
        print("no columns added (already present)")


if __name__ == "__main__":
    main()
