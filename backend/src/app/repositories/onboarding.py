"""`onboarding.json` 仓储: 状态可跨重启恢复。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from pydantic import ValidationError

from app.core.atomic import write_json_atomic
from app.core.clock import utc_now
from app.core.errors import AppError
from app.core.locks import DEFAULT_LOCK_TIMEOUT_SECONDS, FileLock, LockTimeoutError
from app.schemas.onboarding import OnboardingState

T = TypeVar("T")
ONBOARDING_FILE_NAME = "onboarding.json"
ONBOARDING_LOCK_FILE_NAME = "onboarding.lock"


class OnboardingRepository:
    def __init__(
        self,
        data_dir: Path,
        *,
        lock_timeout: float = DEFAULT_LOCK_TIMEOUT_SECONDS,
    ) -> None:
        self._path = data_dir / ONBOARDING_FILE_NAME
        self._lock_path = data_dir / ONBOARDING_LOCK_FILE_NAME
        self._lock_timeout = lock_timeout

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> OnboardingState:
        try:
            text = self._path.read_text(encoding="utf-8-sig")
        except FileNotFoundError:
            return OnboardingState(updated_at=utc_now())
        except OSError as exc:
            raise AppError("ONBOARDING_UNREADABLE", "引导状态无法读取", 500) from exc
        try:
            return OnboardingState.model_validate_json(text)
        except (ValidationError, ValueError) as exc:
            raise AppError("ONBOARDING_UNREADABLE", "引导状态结构不符合约定", 500) from exc

    def mutate(self, change: Callable[[OnboardingState], T]) -> T:
        try:
            with FileLock(self._lock_path, timeout=self._lock_timeout):
                state = self.load()
                result = change(state)
                state.updated_at = utc_now()
                write_json_atomic(self._path, state.model_dump(mode="json"))
                return result
        except LockTimeoutError as exc:
            raise AppError("ONBOARDING_LOCK_TIMEOUT", "引导状态正在被占用", 503) from exc
        except OSError as exc:
            raise AppError("ONBOARDING_WRITE_FAILED", "引导状态写入失败", 500) from exc
