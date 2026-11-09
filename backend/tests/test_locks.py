import time
from pathlib import Path

import pytest

from app.core.locks import FileLock, LockTimeoutError


def test_file_lock_blocks_second_acquirer_and_times_out(tmp_path: Path) -> None:
    path = tmp_path / "profiles.lock"
    holder = FileLock(path, timeout=1.0)
    holder.acquire()
    try:
        started = time.monotonic()
        with pytest.raises(LockTimeoutError, match=r"profiles\.lock"):
            FileLock(path, timeout=0.2).acquire()
        elapsed = time.monotonic() - started
        assert elapsed >= 0.15
        assert elapsed < 2.0
    finally:
        holder.release()


def test_file_lock_can_be_reacquired_after_release(tmp_path: Path) -> None:
    path = tmp_path / "profiles.lock"
    first = FileLock(path, timeout=0.5)
    first.acquire()
    first.release()

    second = FileLock(path, timeout=0.5)
    second.acquire()
    second.release()


def test_file_lock_context_manager_releases_on_exit(tmp_path: Path) -> None:
    path = tmp_path / "profiles.lock"

    with FileLock(path, timeout=0.5), pytest.raises(LockTimeoutError):
        FileLock(path, timeout=0.05).acquire()

    with FileLock(path, timeout=0.5):
        pass


def test_file_lock_rejects_double_acquire_on_same_instance(tmp_path: Path) -> None:
    lock = FileLock(tmp_path / "profiles.lock", timeout=0.1)
    lock.acquire()
    try:
        with pytest.raises(RuntimeError, match="already acquired"):
            lock.acquire()
    finally:
        lock.release()


def test_file_lock_creates_missing_parent_directory(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "dir" / "profiles.lock"

    with FileLock(path, timeout=0.5):
        assert path.is_file()

    with FileLock(path, timeout=0.5):
        pass
