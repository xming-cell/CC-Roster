"""档案仓储: 读写 `<data>/profiles.json`, 规则见 ADR-007。

- 读取不加锁、不创建目录、不修改文件; 原子替换保证读到的要么是旧文件, 要么是新文件。
- 写入先拿文件锁, 在锁内重新读取 → 应用变更 → 校验 → 原子写, 避免并发丢更新。
- 损坏 / 未知版本只报可读错误, 绝不覆盖原文件。
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from pydantic import ValidationError

from app.core.atomic import write_json_atomic
from app.core.errors import AppError
from app.core.locks import DEFAULT_LOCK_TIMEOUT_SECONDS, FileLock, LockTimeoutError
from app.schemas.profile import (
    PROFILE_STORE_SCHEMA_VERSION,
    Profile,
    ProfileStore,
    ToolBinding,
)

PROFILES_FILE_NAME = "profiles.json"
PROFILES_LOCK_FILE_NAME = "profiles.lock"

T = TypeVar("T")


def _unreadable(path: Path, reason: str) -> AppError:
    return AppError("PROFILE_STORE_UNREADABLE", f"{reason}: {path}", 500)


class ProfileRepository:
    """`profiles.json` 的数据访问边界; 业务判断留给 service。"""

    def __init__(
        self,
        data_dir: Path,
        *,
        lock_timeout: float = DEFAULT_LOCK_TIMEOUT_SECONDS,
    ) -> None:
        self._data_dir = Path(data_dir)
        self._path = self._data_dir / PROFILES_FILE_NAME
        self._lock_path = self._data_dir / PROFILES_LOCK_FILE_NAME
        self._lock_timeout = lock_timeout

    @property
    def path(self) -> Path:
        """档案库文件路径; 供备份说明与测试使用。"""
        return self._path

    @property
    def lock_path(self) -> Path:
        """写锁文件路径; 锁文件可以长期保留, 不参与备份。"""
        return self._lock_path

    def load(self) -> ProfileStore:
        """读取完整档案库; 文件缺失视为空库, 且不会创建任何文件。"""
        return self._read()

    def list_profiles(self) -> list[Profile]:
        return list(self._read().profiles)

    def list_bindings(self) -> list[ToolBinding]:
        return list(self._read().bindings)

    def get_profile(self, profile_id: str) -> Profile | None:
        """找不到时返回 None, 由 service 决定对应的业务错误。"""
        return next(
            (profile for profile in self._read().profiles if profile.id == profile_id),
            None,
        )

    def get_binding(self, tool_id: str) -> ToolBinding | None:
        return next(
            (binding for binding in self._read().bindings if binding.tool_id == tool_id),
            None,
        )

    def mutate(self, change: Callable[[ProfileStore], T]) -> T:
        """在文件锁内重新读取, 应用 `change` 后原子写回。

        `change` 抛异常时不写文件; 变更结果会重新校验, 防止 service 写入不一致数据。
        """
        try:
            with FileLock(self._lock_path, timeout=self._lock_timeout):
                store = self._read()
                result = change(store)
                validated = ProfileStore.model_validate(store.model_dump(mode="python"))
                self._write(validated)
                return result
        except LockTimeoutError as exc:
            raise AppError(
                "PROFILE_STORE_LOCK_TIMEOUT",
                "档案库正在被其他操作占用, 请稍后重试",
                503,
            ) from exc

    def _read(self) -> ProfileStore:
        try:
            text = self._path.read_text(encoding="utf-8-sig")
        except FileNotFoundError:
            return ProfileStore()
        except UnicodeDecodeError as exc:
            raise _unreadable(self._path, "档案库文件不是 UTF-8 文本") from exc
        except OSError as exc:
            raise _unreadable(self._path, "档案库文件无法读取") from exc

        try:
            raw = json.loads(text)
        except json.JSONDecodeError as exc:
            raise _unreadable(self._path, "档案库文件不是合法 JSON") from exc

        self._check_schema_version(raw)
        try:
            return ProfileStore.model_validate(raw)
        except ValidationError as exc:
            raise _unreadable(self._path, "档案库文件结构不符合约定") from exc

    def _check_schema_version(self, raw: object) -> None:
        if not isinstance(raw, dict):
            raise _unreadable(self._path, "档案库文件顶层必须是对象")
        version = raw.get("schema_version")
        if isinstance(version, bool) or not isinstance(version, int):
            raise _unreadable(self._path, "档案库文件缺少合法的 schema_version")
        if version != PROFILE_STORE_SCHEMA_VERSION:
            raise AppError(
                "PROFILE_STORE_VERSION_UNSUPPORTED",
                f"档案库版本 {version} 不受支持"
                f" (当前支持 {PROFILE_STORE_SCHEMA_VERSION}): {self._path}",
                500,
            )

    def _write(self, store: ProfileStore) -> None:
        try:
            write_json_atomic(self._path, store.model_dump(mode="json"))
        except OSError as exc:
            raise AppError(
                "PROFILE_STORE_WRITE_FAILED",
                f"档案库写入失败, 原文件未修改: {self._path}",
                500,
            ) from exc
