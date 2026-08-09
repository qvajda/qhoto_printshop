import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

import pipeline.lock as lock


def test_acquire_creates_and_removes_lock_file(tmp_path):
    lock_path = tmp_path / "gl7.lock"

    with lock.acquire(lock_path):
        assert lock_path.exists()

    assert not lock_path.exists()


def test_acquire_removes_lock_file_even_on_exception(tmp_path):
    lock_path = tmp_path / "gl7.lock"

    with pytest.raises(ValueError):
        with lock.acquire(lock_path):
            raise ValueError("boom")

    assert not lock_path.exists()


def test_second_acquire_raises_while_first_process_alive(tmp_path):
    lock_path = tmp_path / "gl7.lock"
    lock_path.write_text(str(os.getpid()))  # our own PID - always "alive"

    with pytest.raises(lock.LockHeldError):
        with lock.acquire(lock_path):
            pass


def test_acquire_steals_lock_with_dead_pid(tmp_path):
    lock_path = tmp_path / "gl7.lock"
    lock_path.write_text("999999999")  # never a real PID

    with lock.acquire(lock_path):
        assert lock_path.exists()

    assert not lock_path.exists()


def test_second_acquire_raises_while_real_cross_process_pid_alive(tmp_path):
    # Regression for the Windows os.kill(pid, 0) bug: that call is
    # special-cased to CTRL_C_EVENT on Windows and does not reliably detect
    # liveness of a real, unrelated process. A same-process PID (as used in
    # test_second_acquire_raises_while_first_process_alive above) doesn't
    # exercise that path - only a genuinely separate OS process does.
    lock_path = tmp_path / "gl7.lock"
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(5)"]
    )
    try:
        lock_path.write_text(str(proc.pid))

        with pytest.raises(lock.LockHeldError):
            with lock.acquire(lock_path):
                pass
    finally:
        proc.terminate()
        proc.wait(timeout=5)

    # Now that the process is dead, the lock should be stealable.
    with lock.acquire(lock_path):
        assert lock_path.exists()

    assert not lock_path.exists()


def test_acquire_stale_lock_twice_in_sequence_succeeds_cleanly(tmp_path):
    # Regression for the contested-stale-reclaim race: an unconditional
    # unlink-then-create let a second reclaimer silently delete the first
    # reclaimer's freshly-created, ACTIVE lock (no content check on the
    # unlink), so both believed they held it. Sequential reclaims of the
    # same stale lock must each succeed cleanly with no leftover/corrupted
    # state and no spurious LockHeldError.
    lock_path = tmp_path / "gl7.lock"
    lock_path.write_text("999999999")  # dead PID - stale from the start

    with lock.acquire(lock_path):
        assert lock_path.read_text().strip() == str(os.getpid())
    assert not lock_path.exists()

    lock_path.write_text("999999999")  # stale again
    with lock.acquire(lock_path):
        assert lock_path.read_text().strip() == str(os.getpid())
    assert not lock_path.exists()


def test_acquire_fails_closed_when_genuinely_contested(tmp_path, monkeypatch):
    # Directly exercises the retry loop's fail-closed path: the O_EXCL
    # create keeps losing (another process keeps winning the reclaim race),
    # and the staleness re-check inside the except block is genuinely fresh
    # (re-evaluated each attempt, not cached from the check made before the
    # loop) - simulated here by a lock file that's stale but whose recreation
    # always loses the O_EXCL race. After exhausting retries this must raise
    # LockHeldError, not loop forever or silently delete a live lock.
    lock_path = tmp_path / "gl7.lock"
    lock_path.write_text("999999999")  # stale (dead PID) at first

    def always_contested_open(path, flags):
        # Simulate another (live) process having just recreated the file
        # with ITS own (real, live) PID the instant before our O_EXCL
        # attempt - every single time. The retry loop's fresh staleness
        # re-check must see this as no-longer-stale and back off, never
        # unlink it and never loop forever.
        Path(path).write_text(str(os.getpid()))
        raise FileExistsError(17, "File exists")

    monkeypatch.setattr(lock.os, "open", always_contested_open)

    with pytest.raises(lock.LockHeldError):
        with lock.acquire(lock_path):
            pass

    # The lock file a live competitor "recreated" is left alone, not
    # silently wiped by our losing side.
    assert lock_path.exists()
    assert lock_path.read_text().strip() == str(os.getpid())


def test_acquire_steals_lock_older_than_stale_after_seconds(tmp_path):
    lock_path = tmp_path / "gl7.lock"
    lock_path.write_text(str(os.getpid()))
    old_time = time.time() - 7200
    os.utime(lock_path, (old_time, old_time))

    with lock.acquire(lock_path, stale_after_seconds=3600):
        assert lock_path.exists()

    assert not lock_path.exists()
