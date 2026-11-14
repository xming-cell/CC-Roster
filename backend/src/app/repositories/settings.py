"""`settings.json` 仓储; 只读开关必须跨进程可见, 因此走文件而不是进程内全局。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from pydantic import ValidationError

from app.core.atomic import write_json_atomic
from app.core.clock import utc_now
from app.core.errors import AppError
from app.core.locks import DEFAULT_LOCK_TIMEOUT_SECONDS, FileLock, LockTimeoutError
from app.schemas.settings import RuntimeSettings

T = TypeVar("T")
SETTINGS_FILE_NAME = "settings.json"
SETTINGS_LOCK_FILE_NAME = "settings.lock"


class SettingsRepository:
    def __init__(
        self,
        data_dir: Path,
        *,
        lock_timeout: float = DEFAULT_LOCK_TIMEOUT_SECONDS,
    ) -> None:
        self._path = data_dir / SETTINGS_FILE_NAME
        self._lock_path = data_dir / SETTINGS_LOCK_FILE_NAME
        self._lock_timeout = lock_timeout

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> RuntimeSettings:
        try:
            text = self._path.read_text(encoding="utf-8-sig")
        except FileNotFoundError:
            return RuntimeSettings(updated_at=utc_now())
        except OSError as exc:
            raise AppError("SETTINGS_UNREADABLE", "设置文件无法读取", 500) from exc
        try:
            return RuntimeSettings.model_validate_json(text)
        except (ValidationError, ValueError) as exc:
            raise AppError("SETTINGS_UNREADABLE", "设置文件结构不符合约定", 500) from exc

    def mutate(self, change: Callable[[RuntimeSettings], T]) -> T:
        try:
            with FileLock(self._lock_path, timeout=self._lock_timeout):
                settings = self.load()
                result = change(settings)
                write_json_atomic(self._path, settings.model_dump(mode="json"))
                return result
        except LockTimeoutError as exc:
            raise AppError("SETTINGS_LOCK_TIMEOUT", "设置正在被其他操作占用", 503) from exc
        except OSError as exc:
            raise AppError("SETTINGS_WRITE_FAILED", "设置写入失败", 500) from exc
