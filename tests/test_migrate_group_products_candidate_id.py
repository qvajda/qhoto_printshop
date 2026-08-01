import sqlite3

import migrate_group_products_candidate_id as migration


def _pre_v412_db(db_path):
    """The three tables as they stood before v4.12, with one GL-9-shaped published row."""
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE group_products (
          id INTEGER PRIMARY KEY,
          group_id INTEGER NOT NULL,
          gelato_template_id TEXT NOT NULL,
          gelato_product_id TEXT,
          etsy_listing_id TEXT,
          title TEXT,
          status TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE group_product_variants (
          id INTEGER PRIMARY KEY,
          group_product_id INTEGER NOT NULL,
          size TEXT NOT NULL,
          orientation TEXT NOT NULL,
          gelato_template_variant_id TEXT NOT NULL,
          price_eur REAL NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE TABLE product_images (
          id INTEGER PRIMARY KEY,
          group_product_id INTEGER NOT NULL,
          image_url TEXT NOT NULL,
          alt_text TEXT NOT NULL,
          gallery_order INTEGER NOT NULL,
          image_type TEXT NOT NULL
        );
        """
    )
    timestamp = "2026-07-25T09:00:00"
    conn.execute(
        "INSERT INTO group_products (id, group_id, gelato_template_id, gelato_product_id, "
        "etsy_listing_id, status, created_at, updated_at) "
        "VALUES (10, 37, 'tmpl', '49f115f2', '4542159277', 'published', ?, ?)",
        (timestamp, timestamp),
    )
    conn.execute(
        "INSERT INTO group_product_variants (id, group_product_id, size, orientation, "
        "gelato_template_variant_id, price_eur, created_at) "
        "VALUES (1, 10, '8x12', 'portrait', 'tv-1', 24.0, ?)",
        (timestamp,),
    )
    conn.execute(
        "INSERT INTO product_images (id, group_product_id, image_url, alt_text, gallery_order, image_type) "
        "VALUES (1, 10, 'file:///a.png', '', 0, 'flat_mockup')"
    )
    conn.commit()
    conn.close()


def _columns(conn, table):
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def test_migrate_adds_the_three_nullable_columns(tmp_path):
    db_path = tmp_path / "old.sqlite3"
    _pre_v412_db(db_path)

    result = migration.migrate(db_path)

    assert result["added_columns"] == [
        "group_products.candidate_id",
        "group_product_variants.group_id",
        "product_images.group_id",
    ]
    conn = sqlite3.connect(db_path)
    assert "candidate_id" in _columns(conn, "group_products")
    assert "group_id" in _columns(conn, "group_product_variants")
    assert "group_id" in _columns(conn, "product_images")
    conn.close()


def test_migrate_is_idempotent(tmp_path):
    db_path = tmp_path / "old.sqlite3"
    _pre_v412_db(db_path)

    migration.migrate(db_path)
    second = migration.migrate(db_path)

    assert second["added_columns"] == []


def test_migrate_does_not_backfill_existing_rows(tmp_path):
    # The GL-9-era rows must keep resolving under the old (group-owns-product) path:
    # candidate_id NULL is the gate the v4.12 code uses to tell old rows from new.
    db_path = tmp_path / "old.sqlite3"
    _pre_v412_db(db_path)

    migration.migrate(db_path)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = dict(conn.execute("SELECT * FROM group_products WHERE id = 10").fetchone())
    assert row["candidate_id"] is None
    assert row["group_id"] == 37
    assert row["etsy_listing_id"] == "4542159277"
    assert row["status"] == "published"
    assert conn.execute(
        "SELECT group_id FROM group_product_variants WHERE id = 1"
    ).fetchone()["group_id"] is None
    assert conn.execute(
        "SELECT group_id FROM product_images WHERE id = 1"
    ).fetchone()["group_id"] is None
    conn.close()
