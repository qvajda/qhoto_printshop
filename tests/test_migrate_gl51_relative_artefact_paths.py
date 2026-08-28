import shutil
import sqlite3
from pathlib import Path

import migrate_gl51_relative_artefact_paths as migration
import pipeline.artwork_store as artwork_store
import pipeline.config as config
import pipeline.db as db


def _db_with_rows(tmp_path, *, local_path, image_url):
    path = tmp_path / "test.sqlite3"
    conn = db.get_connection(path)
    db.init_db(conn)
    conn.execute(
        "INSERT INTO candidates (id, created_at, niche, go_hold_kill, base_image_local_path, status, updated_at) "
        "VALUES (1, 'x', 'niche', 'go', ?, 'pending', 'x')",
        (local_path,),
    )
    conn.execute(
        "INSERT INTO groups (id, candidate_id, group_type, status, created_at, updated_at) "
        "VALUES (1, 1, 'primary', 'pending_review', 'x', 'x')"
    )
    conn.execute(
        "INSERT INTO group_products (id, group_id, candidate_id, gelato_template_id, status, created_at, updated_at) "
        "VALUES (1, 1, 1, 'tmpl', 'pending', 'x', 'x')"
    )
    conn.execute(
        "INSERT INTO product_images (id, group_product_id, group_id, image_url, alt_text, gallery_order, image_type) "
        "VALUES (1, 1, 1, ?, 'alt', 1, 'flat_mockup')",
        (image_url,),
    )
    conn.commit()
    conn.close()
    return path


def test_the_migration_rewrites_absolute_values_and_leaves_r2_urls_alone(tmp_path, monkeypatch):
    root = tmp_path / "artefacts"
    root.mkdir()
    (root / "1.png").write_bytes(b"master")
    monkeypatch.setenv("ARTEFACT_ROOT", str(root))

    db_path = _db_with_rows(
        tmp_path,
        local_path=str(root / "1.png"),
        image_url="https://cdn.example.com/base/1.png",
    )

    result = migration.migrate(db_path)

    assert result["unresolved"] == []
    conn = sqlite3.connect(db_path)
    candidate = conn.execute("SELECT base_image_local_path FROM candidates WHERE id = 1").fetchone()
    assert candidate[0] == "1.png"
    image = conn.execute("SELECT image_url FROM product_images WHERE id = 1").fetchone()
    assert image[0] == "https://cdn.example.com/base/1.png"
    conn.close()


def test_the_migration_reports_a_value_it_cannot_re_root(tmp_path, monkeypatch):
    root = tmp_path / "artefacts"
    root.mkdir()
    monkeypatch.setenv("ARTEFACT_ROOT", str(root))
    elsewhere = tmp_path / "elsewhere" / "1.png"

    db_path = _db_with_rows(tmp_path, local_path=str(elsewhere), image_url="1.png")

    result = migration.migrate(db_path)

    assert len(result["unresolved"]) == 1
    assert result["unresolved"][0]["table"] == "candidates"
    conn = sqlite3.connect(db_path)
    candidate = conn.execute("SELECT base_image_local_path FROM candidates WHERE id = 1").fetchone()
    assert candidate[0] == str(elsewhere)
    conn.close()


def test_the_migration_is_idempotent(tmp_path, monkeypatch):
    root = tmp_path / "artefacts"
    root.mkdir()
    (root / "1.png").write_bytes(b"master")
    monkeypatch.setenv("ARTEFACT_ROOT", str(root))
    db_path = _db_with_rows(tmp_path, local_path=str(root / "1.png"), image_url="1.png")

    migration.migrate(db_path)
    result = migration.migrate(db_path)

    assert result["unresolved"] == []
    conn = sqlite3.connect(db_path)
    candidate = conn.execute("SELECT base_image_local_path FROM candidates WHERE id = 1").fetchone()
    assert candidate[0] == "1.png"
    conn.close()


def test_a_db_written_under_one_artefact_root_resolves_under_another(tmp_path, monkeypatch):
    root_a = tmp_path / "root_a"
    root_b = tmp_path / "root_b"
    root_a.mkdir()
    monkeypatch.setenv("ARTEFACT_ROOT", str(root_a))
    monkeypatch.setattr(artwork_store, "ARTWORK_CACHE_DIR", root_a)

    persisted = artwork_store.persist_base_artwork(candidate_id=1, raw_bytes=b"master bytes")
    db_path = _db_with_rows(tmp_path, local_path=persisted["local_path"], image_url=persisted["local_path"])
    migration.migrate(db_path)

    # Move the whole artefact root - simulates the pipeline changing host.
    shutil.move(str(root_a), str(root_b))
    monkeypatch.setenv("ARTEFACT_ROOT", str(root_b))

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    candidate = conn.execute("SELECT base_image_local_path FROM candidates WHERE id = 1").fetchone()
    image = conn.execute("SELECT image_url FROM product_images WHERE id = 1").fetchone()
    conn.close()

    resolved_candidate = artwork_store.resolve_artefact_path(candidate["base_image_local_path"])
    resolved_image = artwork_store.resolve_artefact_path(image["image_url"])

    assert config.artefact_root() == root_b
    assert Path(resolved_candidate).exists()
    assert Path(resolved_image).exists()
