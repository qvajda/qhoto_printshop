import os
import subprocess
import sys
import time

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


def test_acquire_steals_lock_older_than_stale_after_seconds(tmp_path):
    lock_path = tmp_path / "gl7.lock"
    lock_path.write_text(str(os.getpid()))
    old_time = time.time() - 7200
    os.utime(lock_path, (old_time, old_time))

    with lock.acquire(lock_path, stale_after_seconds=3600):
        assert lock_path.exists()

    assert not lock_path.exists()
