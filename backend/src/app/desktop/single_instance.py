"""单实例: 用跨平台文件锁占住数据目录里的桌面锁。"""

from pathlib import Path

from app.core.locks import FileLock, LockTimeoutError

DESKTOP_LOCK_FILE_NAME = "desktop.lock"


class DesktopAlreadyRunning(RuntimeError):
    """已有桌面实例持有锁。"""


class SingleInstance:
    def __init__(self, data_dir: Path, *, timeout: float = 0.1) -> None:
        self._lock = FileLock(data_dir / DESKTOP_LOCK_FILE_NAME, timeout=timeout)

    def acquire(self) -> None:
        try:
            self._lock.acquire()
        except LockTimeoutError as exc:
            raise DesktopAlreadyRunning("CC-Roster 桌面窗口已经在运行") from exc

    def release(self) -> None:
        self._lock.release()

    def __enter__(self) -> "SingleInstance":
        self.acquire()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.release()
