import hashlib

import pipeline.artwork_store as artwork_store


def test_persist_base_artwork_writes_file_and_returns_correct_hash_and_path(tmp_path, monkeypatch):
    monkeypatch.setattr(artwork_store, "ARTWORK_CACHE_DIR", tmp_path)
    raw = b"fake png bytes"

    result = artwork_store.persist_base_artwork(candidate_id=42, raw_bytes=raw)

    expected_path = tmp_path / "42.png"
    assert expected_path.exists()
    assert expected_path.read_bytes() == raw
    assert result["sha256"] == hashlib.sha256(raw).hexdigest()
    assert result["local_path"] == str(expected_path)


def test_persist_base_artwork_is_idempotent_when_bytes_unchanged(tmp_path, monkeypatch):
    monkeypatch.setattr(artwork_store, "ARTWORK_CACHE_DIR", tmp_path)
    raw = b"same bytes every time"

    artwork_store.persist_base_artwork(candidate_id=7, raw_bytes=raw)
    archive_path = tmp_path / "7.png"
    first_mtime = archive_path.stat().st_mtime_ns

    result = artwork_store.persist_base_artwork(candidate_id=7, raw_bytes=raw)

    assert archive_path.stat().st_mtime_ns == first_mtime
    assert result["sha256"] == hashlib.sha256(raw).hexdigest()


def test_persist_base_artwork_overwrites_when_bytes_differ_for_same_candidate(tmp_path, monkeypatch):
    monkeypatch.setattr(artwork_store, "ARTWORK_CACHE_DIR", tmp_path)
    archive_path = tmp_path / "7.png"

    artwork_store.persist_base_artwork(candidate_id=7, raw_bytes=b"first generate attempt")
    result = artwork_store.persist_base_artwork(candidate_id=7, raw_bytes=b"retry produced new bytes")

    assert archive_path.read_bytes() == b"retry produced new bytes"
    assert result["sha256"] == hashlib.sha256(b"retry produced new bytes").hexdigest()


def test_persist_base_artwork_return_shape_has_expected_keys_and_types():
    result = artwork_store.persist_base_artwork(candidate_id=99, raw_bytes=b"shape check")

    assert isinstance(result["durable_url"], str)
    assert isinstance(result["local_path"], str)
    assert isinstance(result["sha256"], str)
    assert len(result["sha256"]) == 64
