"""用户显式外观覆盖的独立 JSON 仓储。"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Final

from pydantic import ValidationError

from app.core.atomic import write_json_atomic
from app.core.errors import AppError
from app.core.locks import DEFAULT_LOCK_TIMEOUT_SECONDS, FileLock, LockTimeoutError
from app.schemas.appearance import APPEARANCE_SCHEMA_VERSION, AppearanceOverride, AppearanceStore

APPEARANCES_FILE_NAME: Final = "appearances.json"
APPEARANCES_LOCK_FILE_NAME: Final = "appearances.lock"


class AppearanceRepository:
    def __init__(
        self,
        data_dir: Path,
        *,
        lock_timeout: float = DEFAULT_LOCK_TIMEOUT_SECONDS,
    ) -> None:
        self._path = Path(data_dir) / APPEARANCES_FILE_NAME
        self._lock_path = Path(data_dir) / "locks" / APPEARANCES_LOCK_FILE_NAME
        self._lock_timeout = lock_timeout

    @property
    def path(self) -> Path:
        return self._path

    def list(self) -> AppearanceStore:
        return self._read()

    def save(self, tool_id: str, appearance: AppearanceOverride) -> None:
        with self._locked():
            store = self._read()
            store.appearances[tool_id] = appearance
            self._write(store)

    def reset(self, tool_id: str) -> None:
        with self._locked():
            store = self._read()
            if tool_id not in store.appearances:
                return
            del store.appearances[tool_id]
            self._write(store)

    def _read(self) -> AppearanceStore:
        try:
            raw = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return AppearanceStore()
        except OSError as exc:
            raise AppError("APPEARANCE_READ_FAILED", "无法读取好友外观存储", 500) from exc
        except UnicodeDecodeError as exc:
            raise AppError("APPEARANCE_STORE_INVALID", "好友外观存储不是有效 UTF-8", 500) from exc

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AppError("APPEARANCE_STORE_INVALID", "好友外观存储不是有效 JSON", 500) from exc

        if isinstance(payload, dict) and payload.get("schema_version") != APPEARANCE_SCHEMA_VERSION:
            raise AppError(
                "APPEARANCE_VERSION_UNSUPPORTED",
                "好友外观存储版本不受支持",
                500,
            )
        try:
            return AppearanceStore.model_validate(payload)
        except ValidationError as exc:
            raise AppError("APPEARANCE_STORE_INVALID", "好友外观存储结构不合法", 500) from exc

    def _write(self, store: AppearanceStore) -> None:
        try:
            write_json_atomic(self._path, store.model_dump(mode="json"))
        except OSError as exc:
            raise AppError("APPEARANCE_WRITE_FAILED", "无法保存好友外观", 500) from exc

    @contextmanager
    def _locked(self) -> Iterator[None]:
        try:
            with FileLock(self._lock_path, timeout=self._lock_timeout):
                yield
        except LockTimeoutError as exc:
            raise AppError(
                "APPEARANCE_LOCK_TIMEOUT",
                "外观存储正在被占用, 请稍后重试",
                503,
            ) from exc
