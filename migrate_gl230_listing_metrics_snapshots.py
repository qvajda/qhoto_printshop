"""#230: rebuild listing_metrics_snapshots so orders_count is nullable (getListing carries
no order count - a literal 0 would read as measured) and (group_product_id, snapshot_date)
is UNIQUE. The table has held 0 rows since it was declared, so the rebuild is lossless;
rows are copied anyway. Safe to run against any DB, any number of times.
"""
import sqlite3
import sys
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "db" / "qhoto.sqlite3"

_CREATE = """
CREATE TABLE {name} (
  id INTEGER PRIMARY KEY,
  group_product_id INTEGER NOT NULL REFERENCES group_products(id),
  snapshot_date TEXT NOT NULL,
  views INTEGER NOT NULL,
  num_favorers INTEGER NOT NULL,
  orders_count INTEGER,
  UNIQUE(group_product_id, snapshot_date)
)
"""


def migrate(db_path) -> bool:
    """Returns True if the table was rebuilt/created, False if already current."""
    conn = sqlite3.connect(db_path)
    try:
        cols = {r[1]: r for r in conn.execute("PRAGMA table_info(listing_metrics_snapshots)")}
        if cols and not cols["orders_count"][3]:
            return False
        if not cols:
            conn.execute(_CREATE.format(name="listing_metrics_snapshots"))
        else:
            conn.execute(_CREATE.format(name="listing_metrics_snapshots_new"))
            conn.execute(
                "INSERT INTO listing_metrics_snapshots_new "
                "(id, group_product_id, snapshot_date, views, num_favorers, orders_count) "
                "SELECT id, group_product_id, snapshot_date, views, num_favorers, orders_count "
                "FROM listing_metrics_snapshots"
            )
            conn.execute("DROP TABLE listing_metrics_snapshots")
            conn.execute("ALTER TABLE listing_metrics_snapshots_new RENAME TO listing_metrics_snapshots")
        conn.commit()
        return True
    finally:
        conn.close()


def main():
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB_PATH
    print("rebuilt listing_metrics_snapshots" if migrate(db_path) else "already current")


if __name__ == "__main__":
    main()
