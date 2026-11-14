"""对话上下文本地存储: `chat_sessions.json`, 原子写 + 文件锁。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from pydantic import ValidationError

from app.core.atomic import write_json_atomic
from app.core.errors import AppError
from app.core.locks import DEFAULT_LOCK_TIMEOUT_SECONDS, FileLock, LockTimeoutError
from app.schemas.chat import ChatSession, ChatStore

T = TypeVar("T")
CHAT_FILE_NAME = "chat_sessions.json"
CHAT_LOCK_FILE_NAME = "chat_sessions.lock"


class ChatRepository:
    def __init__(
        self,
        data_dir: Path,
        *,
        lock_timeout: float = DEFAULT_LOCK_TIMEOUT_SECONDS,
    ) -> None:
        self._path = data_dir / CHAT_FILE_NAME
        self._lock_path = data_dir / CHAT_LOCK_FILE_NAME
        self._lock_timeout = lock_timeout

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> ChatStore:
        return self._read()

    def get(self, session_id: str) -> ChatSession | None:
        return next((item for item in self._read().sessions if item.id == session_id), None)

    def mutate(self, change: Callable[[ChatStore], T]) -> T:
        try:
            with FileLock(self._lock_path, timeout=self._lock_timeout):
                store = self._read()
                result = change(store)
                validated = ChatStore.model_validate(store.model_dump(mode="python"))
                write_json_atomic(self._path, validated.model_dump(mode="json"))
                return result
        except LockTimeoutError as exc:
            raise AppError(
                "CHAT_STORE_LOCK_TIMEOUT",
                "对话存储正在被其他操作占用, 请稍后重试",
                503,
            ) from exc
        except OSError as exc:
            raise AppError("CHAT_STORE_WRITE_FAILED", "对话记录写入失败", 500) from exc

    def _read(self) -> ChatStore:
        try:
            text = self._path.read_text(encoding="utf-8-sig")
        except FileNotFoundError:
            return ChatStore()
        except OSError as exc:
            raise AppError("CHAT_STORE_UNREADABLE", "对话记录无法读取", 500) from exc
        try:
            return ChatStore.model_validate_json(text)
        except (ValidationError, ValueError) as exc:
            raise AppError("CHAT_STORE_UNREADABLE", "对话记录结构不符合约定", 500) from exc
