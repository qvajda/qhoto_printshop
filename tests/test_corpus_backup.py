"""GL-30 corpus backup. Guards the four things that make it a backup rather
than a copy: tracked files are excluded per-file (inflow/ is mixed), the R2 env
gate fails closed before anything is read, a re-run uploads zero bytes, and a
path whose bytes changed is refused rather than overwritten.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import corpus_backup                                  # noqa: E402


@pytest.fixture
def repo(tmp_path):
    """A real git repo: one tracked inflow image, one untracked next to it, one
    untracked gl6 batch with a screen.json, one out-of-scope outputs/ dir."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "assets" / "mockups" / "inflow").mkdir(parents=True)
    (tmp_path / "assets/mockups/inflow/tracked.png").write_bytes(b"tracked")
    (tmp_path / "assets/mockups/inflow/loose.png").write_bytes(b"loose")
    (tmp_path / "outputs" / "gl6_keyed").mkdir(parents=True)
    (tmp_path / "outputs/gl6_keyed/a.png").write_bytes(b"a")
    (tmp_path / "outputs/gl6_keyed/screen.json").write_text('{"verdict": "pass"}')
    (tmp_path / "outputs" / "mockup_qa").mkdir(parents=True)
    (tmp_path / "outputs/mockup_qa/sheet.png").write_bytes(b"sheet")
    subprocess.run(["git", "add", "assets/mockups/inflow/tracked.png"], cwd=tmp_path, check=True)
    return tmp_path


def paths_of(records):
    return sorted(record["path"] for record in records)


def test_selection_excludes_tracked_files_and_out_of_scope_dirs(repo):
    records, _ = corpus_backup.build_records(repo, [], {})
    assert paths_of(records) == [
        "assets/mockups/inflow/loose.png",
        "outputs/gl6_keyed/a.png",
        "outputs/gl6_keyed/screen.json",
    ]


def test_image_records_carry_their_verdict_key(repo):
    records, _ = corpus_backup.build_records(repo, [], {})
    by_path = {record["path"]: record for record in records}
    assert by_path["outputs/gl6_keyed/a.png"]["verdict_key"] == (
        "mockup-corpus/outputs/gl6_keyed/screen.json"
    )
    assert by_path["outputs/gl6_keyed/screen.json"]["verdict_key"] is None


def test_upload_fails_closed_when_r2_is_not_configured(repo, monkeypatch):
    for key in corpus_backup.config.R2_ENV_VARS:
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(SystemExit):
        corpus_backup.run(repo, [], repo / "manifest.json", upload=True)


def test_rerun_uploads_zero_bytes(repo, monkeypatch):
    manifest = repo / "manifest.json"
    puts = []
    monkeypatch.setattr(corpus_backup.config, "is_r2_configured", lambda: True)
    monkeypatch.setattr(corpus_backup.artwork_store, "_r2_config", lambda: {"R2_BUCKET": "b"})
    monkeypatch.setattr(corpus_backup.artwork_store, "_r2_put_object",
                        lambda key, raw, r2: puts.append(key))

    assert corpus_backup.run(repo, [], manifest, upload=True) == 0
    assert len(puts) == 3
    assert all(record["status"] == "uploaded"
               for record in json.loads(manifest.read_text())["files"])

    puts.clear()
    assert corpus_backup.run(repo, [], manifest, upload=True) == 0
    assert puts == []


def test_changed_bytes_are_refused_not_overwritten(repo, monkeypatch):
    manifest = repo / "manifest.json"
    monkeypatch.setattr(corpus_backup.config, "is_r2_configured", lambda: True)
    monkeypatch.setattr(corpus_backup.artwork_store, "_r2_config", lambda: {"R2_BUCKET": "b"})
    monkeypatch.setattr(corpus_backup.artwork_store, "_r2_put_object", lambda key, raw, r2: None)
    corpus_backup.run(repo, [], manifest, upload=True)

    (repo / "outputs/gl6_keyed/a.png").write_bytes(b"different")
    with pytest.raises(SystemExit, match="REFUSING TO OVERWRITE"):
        corpus_backup.run(repo, [], manifest, upload=True)


def test_dry_run_uploads_nothing_and_writes_a_dry_run_manifest(repo, monkeypatch):
    manifest = repo / "manifest.json"
    monkeypatch.setattr(corpus_backup.artwork_store, "_r2_put_object",
                        lambda *a, **k: pytest.fail("dry-run must not PUT"))
    assert corpus_backup.run(repo, [], manifest, upload=False) == 0
    assert json.loads(manifest.read_text())["dry_run"] is True
