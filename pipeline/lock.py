"""GL-7 Phase 2, 'the sharp part': the hourly poll and the twice-daily batch
must never interleave writes to db/qhoto.sqlite3, and only one process may
ever call Telegram getUpdates (a second reader silently eats the first
reader's offset). A single lock file, guarded by PID liveness and an age
ceiling, gives both cadences a shared gate without a DB table (which would
itself need locking to be race-free) or a third-party dependency.

A stale lock from a killed process must not wedge the pipeline forever - two
independent escape hatches: the recorded PID is checked for liveness
(os.kill(pid, 0), the standard no-op existence probe), and the file's mtime
is checked against stale_after_seconds regardless of PID liveness (covers PID
reuse by an unrelated process). Either one being true means the lock is stolen,
not respected.
"""
import contextlib
import os
import time
from pathlib import Path


class LockHeldError(Exception):
    pass


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    except ValueError:
        return False
    return True


def _is_stale(lock_path: Path, stale_after_seconds: float, now: float) -> bool:
    try:
        mtime = lock_path.stat().st_mtime
    except FileNotFoundError:
        return True
    if now - mtime > stale_after_seconds:
        return True
    try:
        pid = int(lock_path.read_text().strip())
    except (ValueError, FileNotFoundError):
        return True
    return not _pid_alive(pid)


@contextlib.contextmanager
def acquire(lock_path, *, stale_after_seconds: float = 3600, now=None):
    lock_path = Path(lock_path)
    now_ts = now if now is not None else time.time()

    if lock_path.exists() and not _is_stale(lock_path, stale_after_seconds, now_ts):
        raise LockHeldError(f"{lock_path} is held by a live process")

    lock_path.write_text(str(os.getpid()))
    try:
        yield
    finally:
        lock_path.unlink(missing_ok=True)
