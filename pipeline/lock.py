"""GL-7 Phase 2, 'the sharp part': the hourly poll and the twice-daily batch
must never interleave writes to db/qhoto.sqlite3, and only one process may
ever call Telegram getUpdates (a second reader silently eats the first
reader's offset). A single lock file, guarded by PID liveness and an age
ceiling, gives both cadences a shared gate without a DB table (which would
itself need locking to be race-free) or a third-party dependency.

A stale lock from a killed process must not wedge the pipeline forever - two
independent escape hatches: the recorded PID is checked for liveness
(os.kill(pid, 0) on POSIX; OpenProcess via ctypes on Windows, since Windows
special-cases signal 0 to a console-event broadcast rather than a liveness
probe), and the file's mtime is checked against stale_after_seconds
regardless of PID liveness (covers PID reuse by an unrelated process). Either
one being true means the lock is stolen, not respected.
"""
import contextlib
import hashlib
import os
import sys
import tempfile
import time
from pathlib import Path


class LockHeldError(Exception):
    pass


def token_lock_path(bot_token: str) -> Path:
    """GL-45: key the lock on the bot token, not on the script's directory.

    The original <tree>/db/gl7.lock satisfied "one poller" within a tree and
    violated it between trees - two checkouts took two different locks and both
    consumed from the same, single, server-side cursor. A path derived from the
    token puts every process using that token behind one lock, whatever
    directory or database it was started from. The token is hashed, never
    written: lock files are world-readable on a shared temp dir.
    """
    digest = hashlib.sha256(bot_token.encode("utf-8")).hexdigest()[:16]
    return Path(tempfile.gettempdir()) / f"qhoto-telegram-{digest}.lock"


def pipeline_lock_path(db_path) -> Path:
    """GL-132 (#142): the OTHER thing the single lock was doing.

    `token_lock_path` says "one reader of the Telegram cursor". That was also, by
    accident of there being one lock, saying "one writer of the database" - which is
    what kept the hourly poll and the twice-daily batch from interleaving stages. The
    always-on listener holds the token lock for its lifetime, so a batch that waits on
    the same lock never runs at all: research, generation and the digest all stop
    because a button got faster.

    Two locks, because they are two properties. The listener takes the token lock only
    (it never runs a stage). The batch takes this one only (it never polls). The hourly
    takes this one, then tries the token lock on top for its poll - and simply skips
    polling if a live listener already owns the cursor.

    Keyed on the database it protects, resolved to an absolute path, for the same
    reason token_lock_path is keyed on the token: two checkouts sharing one DB must
    take one lock, and two DBs must not share one.
    """
    digest = hashlib.sha256(str(Path(db_path).resolve()).encode("utf-8")).hexdigest()[:16]
    return Path(tempfile.gettempdir()) / f"qhoto-pipeline-{digest}.lock"


def is_held(lock_path, *, stale_after_seconds: float = 3600, now=None) -> bool:
    """True if a live process holds this lock. The read-only half of acquire's own
    check - for a caller that needs to know without taking it (GL-132: the batch asks
    'is a listener alive?' before deciding to start one)."""
    lock_path = Path(lock_path)
    now_ts = now if now is not None else time.time()
    return lock_path.exists() and not _is_stale(lock_path, stale_after_seconds, now_ts)


def _pid_alive(pid: int) -> bool:
    if sys.platform == "win32":
        # os.kill(pid, 0) on Windows is special-cased to CTRL_C_EVENT (a
        # process-group broadcast), not a liveness probe - it does not
        # reliably raise for a dead cross-process PID. Use OpenProcess
        # directly instead.
        import ctypes
        import ctypes.wintypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        handle = ctypes.windll.kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, pid
        )
        if not handle:
            return False
        try:
            # A terminated process's object can stay openable while another
            # process (e.g. its parent, via subprocess.Popen) still holds a
            # handle to it - OpenProcess succeeding alone doesn't mean the
            # process is running. Check its exit code too.
            exit_code = ctypes.wintypes.DWORD()
            ok = ctypes.windll.kernel32.GetExitCodeProcess(
                handle, ctypes.byref(exit_code)
            )
            return bool(ok) and exit_code.value == STILL_ACTIVE
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
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


def refresh(lock_path) -> bool:
    """Push the lock's mtime forward so a long-lived holder is not declared stale by
    the age ceiling in _is_stale (GL-131).

    The ceiling exists because a killed process leaves its file behind, and every
    holder until now finished in minutes. The always-on listener does not: after
    stale_after_seconds it would be robbed of the lock *while still polling*, giving
    the single Telegram cursor two readers - the exact hazard the lock exists to
    prevent. A holder that is alive says so by touching the file each loop.

    No-op (returns False) if the file is gone or already belongs to someone else, so
    a holder whose lock WAS stolen cannot keep the new owner's lock alive by accident.
    """
    lock_path = Path(lock_path)
    try:
        if lock_path.read_text().strip() != str(os.getpid()):
            return False
        os.utime(lock_path, None)
    except (FileNotFoundError, OSError):
        return False
    return True


@contextlib.contextmanager
def acquire(lock_path, *, stale_after_seconds: float = 3600, now=None):
    lock_path = Path(lock_path)
    now_ts = now if now is not None else time.time()

    if lock_path.exists() and not _is_stale(lock_path, stale_after_seconds, now_ts):
        raise LockHeldError(f"{lock_path} is held by a live process")

    # Bounded retry, fail closed. A single unconditional unlink-then-create
    # is itself a race: if two processes both see the lock as stale, one
    # unlinks and creates first, then the second's unlink would silently
    # delete the WINNER's freshly-created live lock (unlink doesn't check
    # content), letting both believe they hold it. So each retry re-checks
    # staleness fresh (not the value computed above - time has passed and
    # another process may have already reclaimed and be holding it now)
    # immediately before unlinking, and gives up with LockHeldError rather
    # than looping forever if it keeps losing the race.
    fd = None
    for _ in range(3):
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            if lock_path.exists() and not _is_stale(
                lock_path, stale_after_seconds, now_ts
            ):
                raise LockHeldError(f"{lock_path} is held by a live process")
            lock_path.unlink(missing_ok=True)
    if fd is None:
        raise LockHeldError(f"{lock_path} is contested - could not acquire after retries")

    with os.fdopen(fd, "w") as f:
        f.write(str(os.getpid()))

    try:
        yield
    finally:
        # Only remove the file if it still holds our own PID - a slow
        # holder whose lock was stolen (by age) while still alive must not
        # delete the new holder's active lock out from under it.
        try:
            current = lock_path.read_text().strip()
        except FileNotFoundError:
            current = None
        if current == str(os.getpid()):
            lock_path.unlink(missing_ok=True)
