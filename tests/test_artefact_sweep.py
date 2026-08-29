import subprocess
import sys
from pathlib import Path

import pipeline.artwork_store as artwork_store
import pipeline.db as db


def _db_with(tmp_path, candidates=(), product_images=()):
    path = tmp_path / "test.sqlite3"
    conn = db.get_connection(path)
    db.init_db(conn)
    now = "2026-08-28T00:00:00Z"
    for local_path in candidates:
        conn.execute(
            "INSERT INTO candidates "
            "(created_at, niche, go_hold_kill, base_image_local_path, status, updated_at) "
            "VALUES (?, 'niche', 'go', ?, 'pending', ?)",
            (now, local_path, now),
        )
    if product_images:
        conn.execute(
            "INSERT INTO candidates (id, created_at, niche, go_hold_kill, status, updated_at) "
            "VALUES (999, ?, 'niche', 'go', 'pending', ?)",
            (now, now),
        )
        conn.execute(
            "INSERT INTO groups (id, candidate_id, group_type, status, created_at, updated_at) "
            "VALUES (1, 999, 'primary', 'pending_review', ?, ?)",
            (now, now),
        )
        conn.execute(
            "INSERT INTO group_products (id, group_id, gelato_template_id, status, created_at, updated_at) "
            "VALUES (1, 1, 'tmpl', 'created', ?, ?)",
            (now, now),
        )
        for i, image_url in enumerate(product_images):
            conn.execute(
                "INSERT INTO product_images "
                "(group_product_id, group_id, image_url, alt_text, gallery_order, image_type) "
                "VALUES (1, 1, ?, 'alt', ?, 'flat_mockup')",
                (image_url, i),
            )
    conn.commit()
    conn.close()
    return path


def test_a_deleted_artefact_is_reported_missing_instead_of_passing_silently(tmp_path):
    gone = tmp_path / "gone.png"
    db_path = _db_with(tmp_path, candidates=[str(gone)])

    report = artwork_store.sweep_artefacts(db_path)

    assert report["missing"] == [{"table": "candidates", "row_id": 1, "value": str(gone)}]

    result = subprocess.run(
        [sys.executable, "migrate.py", "--check-artefacts", str(db_path)],
        cwd=Path(__file__).resolve().parent.parent,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "candidates 1" in result.stdout


def test_an_http_durable_url_is_skipped_not_reported_missing(tmp_path):
    db_path = _db_with(tmp_path, candidates=["https://r2.example.com/base/1.png"])

    report = artwork_store.sweep_artefacts(db_path)

    assert report["missing"] == []
    assert report["skipped"] == 1

    result = subprocess.run(
        [sys.executable, "migrate.py", "--check-artefacts", str(db_path)],
        cwd=Path(__file__).resolve().parent.parent,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0


def test_a_missing_product_images_row_is_reported_too(tmp_path):
    gone = tmp_path / "gone_mockup.png"
    db_path = _db_with(tmp_path, product_images=[str(gone)])

    report = artwork_store.sweep_artefacts(db_path)

    assert report["missing"] == [{"table": "product_images", "row_id": 1, "value": str(gone)}]


def test_an_existing_local_artefact_is_resolvable(tmp_path):
    present = tmp_path / "present.png"
    present.write_bytes(b"x")
    db_path = _db_with(tmp_path, candidates=[str(present)])

    report = artwork_store.sweep_artefacts(db_path)

    assert report["resolvable"] == 1
    assert report["missing"] == []


def test_a_relative_path_resolves_against_the_artefact_root_not_the_cwd(tmp_path, monkeypatch):
    """GL-51a regression: after #200 stored local values are relative to
    config.artefact_root(). Checking Path(value) raw resolved them against the
    CWD, so every migrated row was reported missing on a healthy DB."""
    root = tmp_path / "artefacts"
    root.mkdir()
    (root / "1.png").write_bytes(b"x")
    monkeypatch.setenv("ARTEFACT_ROOT", str(root))

    db_path = _db_with(tmp_path, candidates=["1.png"])

    report = artwork_store.sweep_artefacts(db_path)

    assert report["missing"] == []
    assert report["resolvable"] == 1
