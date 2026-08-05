import os
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


def test_acquire_steals_lock_older_than_stale_after_seconds(tmp_path):
    lock_path = tmp_path / "gl7.lock"
    lock_path.write_text(str(os.getpid()))
    old_time = time.time() - 7200
    os.utime(lock_path, (old_time, old_time))

    with lock.acquire(lock_path, stale_after_seconds=3600):
        assert lock_path.exists()

    assert not lock_path.exists()
