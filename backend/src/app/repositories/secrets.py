"""密钥存储: OS keyring 优先, `<data>/secrets.json` 0600 回退 (ADR-006)。

- 档案只保存 `SecretRef`; 本模块负责按引用真正读写 / 删除密钥。
- 读取按 `SecretRef.backend` 路由, 因此旧的 file 引用在钥匙串恢复后仍可读。
- 写入使用当前可用后端; 显式 `keyring` 不可用时拒绝写入, 不静默回退。
- 所有错误消息固定文案, 不回显密钥原文。
"""

import json
import os
import sys
import uuid
from pathlib import Path
from typing import Final, Literal, Protocol

import keyring

from app.core.atomic import write_json_atomic
from app.core.config import SecretBackendSetting
from app.core.errors import AppError
from app.core.locks import DEFAULT_LOCK_TIMEOUT_SECONDS, FileLock, LockTimeoutError
from app.schemas.profile import SecretRef, SecretStoreStatus

KEYRING_SERVICE_NAME = "cc-roster"
SECRETS_FILE_NAME = "secrets.json"
SECRETS_LOCK_FILE_NAME = "secrets.lock"
SECRETS_FILE_SCHEMA_VERSION: Final[Literal[1]] = 1


class KeyringBackend(Protocol):
    """`keyring` 模块中真正被用到的最小接口, 便于测试注入假实现。"""

    def get_password(self, service: str, username: str) -> str | None: ...

    def set_password(self, service: str, username: str, password: str) -> None: ...

    def delete_password(self, service: str, username: str) -> None: ...


class KeyringModuleBackend:
    """把 `keyring` 模块收窄成可替换边界。"""

    def get_password(self, service: str, username: str) -> str | None:
        return keyring.get_password(service, username)

    def set_password(self, service: str, username: str, password: str) -> None:
        keyring.set_password(service, username, password)

    def delete_password(self, service: str, username: str) -> None:
        keyring.delete_password(service, username)


def _default_keyring_available() -> bool:
    """fail.Keyring 的 priority 为 0; 有真实后端时为正数。"""
    try:
        backend = keyring.get_keyring()
    except Exception:  # 后端探测失败不能阻止应用启动
        return False
    return getattr(backend, "priority", 0) > 0


class KeyringSecretStore:
    """OS 凭据库实现; `available=False` 表示探测不到可用后端。"""

    def __init__(
        self,
        backend: KeyringBackend | None = None,
        *,
        available: bool | None = None,
    ) -> None:
        if backend is None:
            self._backend: KeyringBackend = KeyringModuleBackend()
            detected = _default_keyring_available()
        else:
            self._backend = backend
            detected = True
        self._available = detected if available is None else available

    @property
    def available(self) -> bool:
        return self._available

    def get(self, ref: SecretRef) -> str | None:
        self._require_available()
        try:
            return self._backend.get_password(KEYRING_SERVICE_NAME, ref.locator)
        except Exception as exc:
            raise AppError("SECRET_STORE_ERROR", "系统钥匙串读取失败", 500) from exc

    def put(self, profile_id: str, secret: str) -> SecretRef:
        self._require_available()
        try:
            self._backend.set_password(KEYRING_SERVICE_NAME, profile_id, secret)
        except Exception as exc:
            raise AppError("SECRET_STORE_ERROR", "系统钥匙串写入失败", 500) from exc
        return SecretRef(id=str(uuid.uuid4()), backend="keyring", locator=profile_id)

    def delete(self, ref: SecretRef) -> None:
        """删除不存在的条目视为成功, 保证删除档案可重试。"""
        self._require_available()
        try:
            self._backend.delete_password(KEYRING_SERVICE_NAME, ref.locator)
        except keyring.errors.PasswordDeleteError:
            return
        except Exception as exc:
            raise AppError("SECRET_STORE_ERROR", "系统钥匙串删除失败", 500) from exc

    def _require_available(self) -> None:
        if not self._available:
            raise AppError("SECRET_STORE_ERROR", "系统钥匙串不可用", 500)


class FileSecretStore:
    """`<data>/secrets.json` 明文回退; Unix 权限固定为 0600, 不加密。"""

    def __init__(
        self,
        data_dir: Path,
        *,
        lock_timeout: float = DEFAULT_LOCK_TIMEOUT_SECONDS,
    ) -> None:
        self._data_dir = Path(data_dir)
        self._path = self._data_dir / SECRETS_FILE_NAME
        self._lock_path = self._data_dir / SECRETS_LOCK_FILE_NAME
        self._lock_timeout = lock_timeout

    @property
    def path(self) -> Path:
        return self._path

    @property
    def lock_path(self) -> Path:
        return self._lock_path

    def is_available(self) -> bool:
        """数据目录可创建即可用; 这里会创建目录, 与 `ensure_data_dirs` 幂等。"""
        try:
            self._data_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            return False
        return self._data_dir.is_dir()

    def get(self, ref: SecretRef) -> str | None:
        return self._read().get(ref.locator)

    def put(self, profile_id: str, secret: str) -> SecretRef:
        self._require_available()
        try:
            with FileLock(self._lock_path, timeout=self._lock_timeout):
                secrets = self._read()
                secrets[profile_id] = secret
                self._write(secrets)
        except LockTimeoutError as exc:
            raise AppError(
                "SECRET_STORE_ERROR",
                "本机密钥文件正在被其他操作占用, 请稍后重试",
                500,
            ) from exc
        return SecretRef(id=str(uuid.uuid4()), backend="file", locator=profile_id)

    def delete(self, ref: SecretRef) -> None:
        self._require_available()
        try:
            with FileLock(self._lock_path, timeout=self._lock_timeout):
                secrets = self._read()
                if ref.locator not in secrets:
                    return
                del secrets[ref.locator]
                self._write(secrets)
        except LockTimeoutError as exc:
            raise AppError(
                "SECRET_STORE_ERROR",
                "本机密钥文件正在被其他操作占用, 请稍后重试",
                500,
            ) from exc

    def _read(self) -> dict[str, str]:
        try:
            text = self._path.read_text(encoding="utf-8-sig")
        except FileNotFoundError:
            return {}
        except UnicodeDecodeError as exc:
            raise AppError("SECRET_STORE_ERROR", "本机密钥文件不是 UTF-8 文本", 500) from exc
        except OSError as exc:
            raise AppError("SECRET_STORE_ERROR", "本机密钥文件无法读取", 500) from exc

        try:
            raw = json.loads(text)
        except json.JSONDecodeError as exc:
            raise AppError("SECRET_STORE_ERROR", "本机密钥文件不是合法 JSON", 500) from exc

        if not isinstance(raw, dict):
            raise AppError("SECRET_STORE_ERROR", "本机密钥文件结构不符合约定", 500)
        version = raw.get("schema_version")
        if isinstance(version, bool) or version != SECRETS_FILE_SCHEMA_VERSION:
            raise AppError("SECRET_STORE_ERROR", "本机密钥文件结构不符合约定", 500)

        stored = raw.get("secrets")
        if not isinstance(stored, dict):
            raise AppError("SECRET_STORE_ERROR", "本机密钥文件结构不符合约定", 500)

        secrets: dict[str, str] = {}
        for key, value in stored.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise AppError("SECRET_STORE_ERROR", "本机密钥文件结构不符合约定", 500)
            secrets[key] = value
        return secrets

    def _write(self, secrets: dict[str, str]) -> None:
        try:
            write_json_atomic(
                self._path,
                {"schema_version": SECRETS_FILE_SCHEMA_VERSION, "secrets": secrets},
            )
        except OSError as exc:
            raise AppError("SECRET_STORE_ERROR", "本机密钥文件写入失败", 500) from exc

        if sys.platform != "win32":
            try:
                os.chmod(self._path, 0o600)
            except OSError as exc:
                raise AppError(
                    "SECRET_STORE_ERROR",
                    "本机密钥文件权限设置失败",
                    500,
                ) from exc

    def _require_available(self) -> None:
        if not self.is_available():
            raise AppError("SECRET_STORE_ERROR", "本机密钥文件不可用", 500)


class SecretStore(Protocol):
    """服务层只依赖这个边界; 测试可以注入任意假实现。"""

    def status(self) -> SecretStoreStatus: ...

    def get(self, ref: SecretRef) -> str | None: ...

    def put(self, profile_id: str, secret: str) -> SecretRef: ...

    def delete(self, ref: SecretRef) -> None: ...


class CompositeSecretStore:
    """按设置选择写入后端; 读取始终按 `SecretRef.backend` 路由。"""

    def __init__(
        self,
        *,
        mode: SecretBackendSetting,
        keyring_store: KeyringSecretStore,
        file_store: FileSecretStore,
    ) -> None:
        self._mode = mode
        self._keyring = keyring_store
        self._file = file_store

    def status(self) -> SecretStoreStatus:
        if self._mode == "file":
            if self._file.is_available():
                return SecretStoreStatus(
                    backend="file",
                    fallback=True,
                    message="已按 CC_ROSTER_SECRET_BACKEND=file 使用本机文件保存密钥",
                )
            return SecretStoreStatus(
                backend="unavailable",
                fallback=False,
                message="已配置使用本机密钥文件, 但数据目录不可写",
            )

        if self._keyring.available:
            return SecretStoreStatus(backend="keyring", fallback=False)

        if self._mode == "keyring":
            return SecretStoreStatus(
                backend="unavailable",
                fallback=False,
                message="已显式要求使用系统钥匙串, 但当前不可用",
            )

        if self._file.is_available():
            return SecretStoreStatus(
                backend="file",
                fallback=True,
                message="系统钥匙串不可用, 密钥将保存在本机文件 secrets.json (权限 0600)",
            )
        return SecretStoreStatus(
            backend="unavailable",
            fallback=False,
            message="系统钥匙串与本机密钥文件均不可用, 无法保存密钥",
        )

    def get(self, ref: SecretRef) -> str | None:
        if ref.backend == "keyring":
            return self._keyring.get(ref)
        return self._file.get(ref)

    def put(self, profile_id: str, secret: str) -> SecretRef:
        status = self.status()
        if status.backend == "keyring":
            return self._keyring.put(profile_id, secret)
        if status.backend == "file":
            return self._file.put(profile_id, secret)
        raise AppError(
            "SECRET_STORE_ERROR",
            status.message or "密钥存储不可用",
            500,
        )

    def delete(self, ref: SecretRef) -> None:
        if ref.backend == "keyring":
            self._keyring.delete(ref)
            return
        self._file.delete(ref)


def build_secret_store(
    data_dir: Path,
    *,
    mode: SecretBackendSetting = "auto",
    keyring_store: KeyringSecretStore | None = None,
    file_store: FileSecretStore | None = None,
) -> SecretStore:
    """生产用工厂; 测试传入假 keyring / 文件 store 即可完全隔离系统钥匙串。"""
    return CompositeSecretStore(
        mode=mode,
        keyring_store=keyring_store if keyring_store is not None else KeyringSecretStore(),
        file_store=file_store if file_store is not None else FileSecretStore(data_dir),
    )


def rollback_secret(
    store: SecretStore,
    new_ref: SecretRef,
    previous_secret: str | None,
) -> None:
    """档案保存失败后的补偿: 有旧密钥就写回, 否则删除刚写入的密钥。"""
    if previous_secret is None:
        store.delete(new_ref)
        return
    store.put(new_ref.locator, previous_secret)
