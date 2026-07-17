import hashlib
from pathlib import Path

ARTWORK_CACHE_DIR = Path(__file__).resolve().parent.parent / "db" / "base_artwork"


def persist_base_artwork(candidate_id: int, raw_bytes: bytes) -> dict:
    """Archives a candidate's base artwork bytes locally, keyed by candidate_id.

    Idempotent: if the archive already holds bytes with the same sha256, the
    file is left untouched. A different hash for the same candidate_id (a
    generate-retry) overwrites it - last write wins, no versioning.

    Local-only for now (Task 1) - durable_url is just the local path until
    Task 2 adds an R2 backend to override it.
    """
    sha256 = hashlib.sha256(raw_bytes).hexdigest()

    ARTWORK_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    archive_path = ARTWORK_CACHE_DIR / f"{candidate_id}.png"

    if not archive_path.exists() or hashlib.sha256(archive_path.read_bytes()).hexdigest() != sha256:
        archive_path.write_bytes(raw_bytes)

    return {
        "durable_url": str(archive_path),
        "local_path": str(archive_path),
        "sha256": sha256,
    }
