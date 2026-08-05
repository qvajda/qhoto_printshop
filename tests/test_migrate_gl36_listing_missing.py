import sqlite3

import migrate_gl36_listing_missing as migration
import pipeline.db as db


def _old_shape_db(tmp_path):
    """Simulates a pre-GL-36 DB: group_products.status CHECK does not admit
    'listing_missing' yet."""
    path = tmp_path / "test.sqlite3"
    conn = db.get_connection(path)
    db.init_db(conn)
    # init_db already applies the widened schema.sql from Task 2 Step 1, so
    # rebuild group_products with the OLD constraint to simulate pre-migration state.
    conn.execute("DROP TABLE group_products")
    conn.execute(
        """
        CREATE TABLE group_products (
          id INTEGER PRIMARY KEY,
          group_id INTEGER NOT NULL REFERENCES groups(id),
          candidate_id INTEGER REFERENCES candidates(id),
          gelato_template_id TEXT NOT NULL,
          gelato_product_id TEXT,
          etsy_listing_id TEXT,
          title TEXT,
          status TEXT NOT NULL CHECK(status IN (
            'pending','created','mockup_failed','publish_failed','published','deleted'
          )),
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()
    return path


def test_migrate_widens_check_to_admit_listing_missing(tmp_path):
    db_path = _old_shape_db(tmp_path)

    result = migration.migrate(db_path)

    assert result["rebuilt"] is True
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO group_products (id, group_id, gelato_template_id, status, created_at, updated_at) "
        "VALUES (99, 1, 'tmpl', 'listing_missing', 'x', 'x')"
    )
    conn.commit()
    row = conn.execute("SELECT status FROM group_products WHERE id = 99").fetchone()
    assert row[0] == "listing_missing"
    conn.close()


def test_migrate_is_idempotent(tmp_path):
    db_path = _old_shape_db(tmp_path)
    migration.migrate(db_path)

    result = migration.migrate(db_path)

    assert result["rebuilt"] is False


def test_migrate_preserves_existing_rows(tmp_path):
    db_path = _old_shape_db(tmp_path)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO group_products (id, group_id, gelato_template_id, status, created_at, updated_at) "
        "VALUES (1, 1, 'tmpl', 'published', 'x', 'x')"
    )
    conn.commit()
    conn.close()

    migration.migrate(db_path)

    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT status FROM group_products WHERE id = 1").fetchone()
    assert row[0] == "published"
    conn.close()
