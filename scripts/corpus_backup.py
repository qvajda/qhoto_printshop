"""GL-30 one-off: back up the untracked half of the mockup corpus to R2.

Every scene ever generated exists only on this desktop *except* the bundles git
tracks, which are safe on `origin` (the repo is public by decision). This backs
up the difference - the untracked files under outputs/gl6_* and
assets/mockups/inflow/ - reusing the uploader that already exists
(pipeline.artwork_store._r2_put_object). Selection is `git ls-files`, not
.gitignore: for backup purposes untracked is untracked, and inflow/ is mixed
(51 of 71 files tracked, per-file selection).

    corpus_backup.py [--upload] [--repo-root DIR] [--extra-root DIR ...]
                     [--manifest PATH]

Dry-run is the default; --upload is the only thing that PUTs bytes.

Key scheme: mockup-corpus/<path relative to repo root>, one key per file,
write-once - a path whose bytes changed since the manifest recorded it is a
hard error, never an overwrite. sha256 of every file is in the manifest, so
GL-30b can keep using the same keys.

Resume: the manifest is the skip list. Re-running uploads only records that are
missing or not yet status="uploaded"; a clean re-run uploads zero bytes.
"""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline import artwork_store                    # noqa: E402
from pipeline import config                           # noqa: E402

KEY_PREFIX = "mockup-corpus"
DEFAULT_ROOTS = ("outputs", "assets/mockups/inflow")
# Only gl6_* batches are in scope under outputs/ (the rest is scratch renders).
OUTPUTS_PREFIX = "outputs/gl6_"
SKIP_PARTS = {"__pycache__", ".git"}
VERDICT_NAMES = ("screen.json", "meta.json", "scene.json")


def tracked_paths(repo_root: Path) -> set:
    out = subprocess.run(
        ["git", "ls-files"], cwd=repo_root, capture_output=True, text=True, check=True
    ).stdout
    return set(out.splitlines())


def in_scope(rel: str) -> bool:
    if rel.startswith("outputs/"):
        return rel.startswith(OUTPUTS_PREFIX)
    return True


def select_files(repo_root: Path, extra_roots: list) -> list:
    """Every file under the corpus roots that `git ls-files` does not return.
    Extra roots (material parked outside the tree) are always in scope - git
    knows nothing about them."""
    tracked = tracked_paths(repo_root)
    selected = []

    for root in DEFAULT_ROOTS:
        base = repo_root / root
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or SKIP_PARTS & set(path.parts):
                continue
            rel = path.relative_to(repo_root).as_posix()
            if rel in tracked or not in_scope(rel):
                continue
            selected.append((rel, path))

    for extra in extra_roots:
        base = Path(extra).resolve()
        for path in sorted(base.rglob("*") if base.is_dir() else [base]):
            if not path.is_file() or SKIP_PARTS & set(path.parts):
                continue
            selected.append((f"extra/{base.name}/{path.relative_to(base).as_posix()}", path))

    return selected


def verdict_key_for(rel: str, path: Path, selected_rels: set) -> str | None:
    """The sidecar that makes this image meaningful: same-stem .json first, then
    the directory's screen.json/meta.json/scene.json. Only counts if that file
    is itself in the backup set - a verdict on `origin` needs no second copy."""
    if path.suffix.lower() == ".json":
        return None
    parent = rel.rsplit("/", 1)[0]
    candidates = [f"{rel.rsplit('.', 1)[0]}.json"] + [f"{parent}/{name}" for name in VERDICT_NAMES]
    for candidate in candidates:
        if candidate in selected_rels:
            return key_for(candidate)
    return None


def key_for(rel: str) -> str:
    return f"{KEY_PREFIX}/{rel}"


def load_manifest(manifest_path: Path) -> dict:
    if not manifest_path.exists():
        return {}
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {record["path"]: record for record in data.get("files", [])}


def build_records(repo_root: Path, extra_roots: list, previous: dict) -> tuple:
    """Returns (records, {relative path -> file on disk})."""
    selected = select_files(repo_root, extra_roots)
    selected_rels = {rel for rel, _ in selected}
    records = []
    for rel, path in selected:
        raw = path.read_bytes()
        sha256 = hashlib.sha256(raw).hexdigest()
        prior = previous.get(rel)
        if prior and prior.get("status") == "uploaded" and prior["sha256"] != sha256:
            raise SystemExit(
                f"REFUSING TO OVERWRITE: {rel} already backed up with sha256 "
                f"{prior['sha256']}, on disk it is now {sha256}. Write-once keys - "
                "give the changed file a new path or a new prefix."
            )
        records.append({
            "path": rel,
            "size": len(raw),
            "sha256": sha256,
            "key": key_for(rel),
            "verdict_key": verdict_key_for(rel, path, selected_rels),
            "status": "uploaded" if prior and prior.get("status") == "uploaded" else "pending",
        })
    return records, dict(selected)


def run(repo_root: Path, extra_roots: list, manifest_path: Path, upload: bool) -> int:
    # Fail closed before reading a single file - a partial upload is worse than none.
    if upload and not config.is_r2_configured():
        raise SystemExit(
            "R2 is not configured (need all of: " + ", ".join(config.R2_ENV_VARS) + ")"
        )

    previous = load_manifest(manifest_path)
    records, paths = build_records(repo_root, extra_roots, previous)
    pending = [record for record in records if record["status"] == "pending"]
    total = sum(record["size"] for record in pending)

    print(f"{len(records)} files in scope, {len(pending)} to upload, {total / 1e6:.1f} MB")
    if not upload:
        for record in pending:
            print(f"  DRY-RUN {record['key']}  {record['size'] / 1e6:.2f} MB")
        _write_manifest(manifest_path, records, dry_run=True)
        return 0

    r2 = artwork_store._r2_config()
    failed = None
    for index, record in enumerate(pending, 1):
        try:
            artwork_store._r2_put_object(record["key"], paths[record["path"]].read_bytes(), r2)
        except Exception as exc:                       # noqa: BLE001 - manifest first, then re-raise
            record["status"] = "failed"
            failed = exc
            break
        record["status"] = "uploaded"
        print(f"  [{index}/{len(pending)}] {record['key']}  {record['size'] / 1e6:.2f} MB")

    _write_manifest(manifest_path, records, dry_run=False)
    if failed is not None:
        print(f"FAILED on {record['path']}: {failed}", file=sys.stderr)
        print("Manifest written with what landed; re-run to resume.", file=sys.stderr)
        return 1
    print(f"Manifest: {manifest_path}")
    return 0


def _write_manifest(manifest_path: Path, records: list, dry_run: bool) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps({
        "key_scheme": f"{KEY_PREFIX}/<path relative to repo root>, write-once, sha256 per file",
        "bucket": (artwork_store._r2_config() or {}).get("R2_BUCKET"),
        "dry_run": dry_run,
        "files": records,
    }, indent=2) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upload", action="store_true", help="actually PUT (default: dry-run)")
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--extra-root", action="append", default=[],
                        help="material parked outside the repo tree")
    parser.add_argument("--manifest", default=None)
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    config.load_env(repo_root / ".env")
    manifest = Path(args.manifest) if args.manifest else (
        repo_root / "docs" / "data" / "2026-08-08-mockup-corpus-manifest.json"
    )
    return run(repo_root, args.extra_root, manifest, args.upload)


if __name__ == "__main__":
    sys.exit(main())
