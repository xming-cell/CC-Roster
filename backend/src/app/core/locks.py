"""跨平台文件锁, 带超时。

Windows 用 `msvcrt.locking`, 其他平台用 `fcntl.flock`。锁由操作系统在进程退出时释放,
锁文件本身可以保留, 不会成为无限阻塞源。
"""

import sys
import time
from pathlib import Path
from types import TracebackType
from typing import IO

DEFAULT_LOCK_TIMEOUT_SECONDS = 5.0
DEFAULT_POLL_INTERVAL_SECONDS = 0.05


class LockTimeoutError(TimeoutError):
    """在超时时间内没有拿到文件锁。"""


def _try_lock(handle: IO[bytes]) -> None:
    if sys.platform == "win32":
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock(handle: IO[bytes]) -> None:
    if sys.platform == "win32":
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class FileLock:
    """独占文件锁。用法: `with FileLock(path, timeout=1.0): ...`。"""

    def __init__(
        self,
        path: Path,
        *,
        timeout: float = DEFAULT_LOCK_TIMEOUT_SECONDS,
        poll_interval: float = DEFAULT_POLL_INTERVAL_SECONDS,
    ) -> None:
        if timeout < 0:
            raise ValueError("timeout must be non-negative")
        if poll_interval <= 0:
            raise ValueError("poll_interval must be positive")
        self._path = path
        self._timeout = timeout
        self._poll_interval = poll_interval
        self._handle: IO[bytes] | None = None

    def acquire(self) -> None:
        if self._handle is not None:
            raise RuntimeError("file lock is already acquired")

        self._path.parent.mkdir(parents=True, exist_ok=True)
        handle = self._path.open("a+b")
        handle.seek(0)
        deadline = time.monotonic() + self._timeout
        try:
            while True:
                try:
                    _try_lock(handle)
                except OSError:
                    if time.monotonic() >= deadline:
                        raise LockTimeoutError(
                            f"could not acquire file lock within {self._timeout:g}s: {self._path}"
                        ) from None
                    time.sleep(self._poll_interval)
                else:
                    self._handle = handle
                    return
        except BaseException:
            handle.close()
            raise

    def release(self) -> None:
        handle = self._handle
        if handle is None:
            return
        self._handle = None
        try:
            _unlock(handle)
        finally:
            handle.close()

    def __enter__(self) -> "FileLock":
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.release()
