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
import os
import sys
import time
from pathlib import Path


class LockHeldError(Exception):
    pass


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
