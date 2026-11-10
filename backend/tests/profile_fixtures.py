"""档案测试共享的模型工厂。

不是 pytest 插件, 也不会被收集; 供模型层与仓储层测试复用同一份构造逻辑。
"""

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import keyring
from fastapi.testclient import TestClient

from app.adapters.base import ToolAdapter
from app.adapters.registry import ToolRegistry
from app.api.profiles import get_profile_service
from app.core.config import SecretBackendSetting
from app.main import create_app
from app.repositories.profiles import ProfileRepository
from app.repositories.secrets import (
    FileSecretStore,
    KeyringSecretStore,
    build_secret_store,
)
from app.schemas.profile import (
    ModelEntry,
    Profile,
    ProfileProtocol,
    ProfileStore,
    SecretBackend,
    SecretRef,
    ToolBinding,
)
from app.services.profile_service import ProfileService
from app.services.tool_discovery import ToolDiscoveryService

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)


class FakeKeyring:
    """最小 keyring 替身; 可分别注入读 / 写 / 删除失败。"""

    def __init__(self) -> None:
        self.values: dict[tuple[str, str], str] = {}
        self.fail_get = False
        self.fail_set = False
        self.fail_delete = False

    def get_password(self, service: str, username: str) -> str | None:
        if self.fail_get:
            raise RuntimeError("keyring read failed")
        return self.values.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        if self.fail_set:
            raise RuntimeError("keyring write failed")
        self.values[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        if self.fail_delete:
            raise RuntimeError("keyring delete failed")
        key = (service, username)
        if key not in self.values:
            raise keyring.errors.PasswordDeleteError("not found")
        del self.values[key]


def new_profile_id() -> str:
    return str(uuid.uuid4())


def make_secret_ref(
    profile_id: str,
    *,
    backend: SecretBackend = "keyring",
) -> SecretRef:
    return SecretRef(
        id=str(uuid.uuid4()),
        backend=backend,
        locator=profile_id,
    )


def make_profile(
    name: str = "默认档案",
    *,
    profile_id: str | None = None,
    protocol: ProfileProtocol = "anthropic",
    base_url: str = "https://api.anthropic.com",
    secret_ref: SecretRef | None = None,
    models: list[ModelEntry] | None = None,
    created_at: datetime = NOW,
    updated_at: datetime | None = None,
) -> Profile:
    return Profile(
        id=profile_id or new_profile_id(),
        name=name,
        protocol=protocol,
        base_url=base_url,
        secret_ref=secret_ref,
        models=models if models is not None else [],
        created_at=created_at,
        updated_at=updated_at if updated_at is not None else created_at,
    )


def make_binding(
    profile_id: str,
    tool_id: str = "claude-code",
    *,
    bound_at: datetime = NOW,
    active: bool = False,
    applied_at: datetime | None = None,
    snapshot_id: str | None = None,
) -> ToolBinding:
    return ToolBinding(
        tool_id=tool_id,
        profile_id=profile_id,
        bound_at=bound_at,
        active=active,
        applied_at=applied_at,
        snapshot_id=snapshot_id,
    )


@dataclass
class ProfileHarness:
    """API 测试替身: 临时数据目录 + 假 keyring + 注入的工具注册表。"""

    client: TestClient
    repository: ProfileRepository
    keyring: FakeKeyring
    data_dir: Path


def make_profile_harness(
    data_dir: Path,
    *adapters: ToolAdapter,
    mode: SecretBackendSetting = "auto",
) -> ProfileHarness:
    keyring = FakeKeyring()
    secrets = build_secret_store(
        data_dir,
        mode=mode,
        keyring_store=KeyringSecretStore(keyring),
        file_store=FileSecretStore(data_dir),
    )
    repository = ProfileRepository(data_dir)
    service = ProfileService(
        repository,
        secrets,
        ToolDiscoveryService(ToolRegistry(adapters)),
    )
    app = create_app()
    app.dependency_overrides[get_profile_service] = lambda: service
    return ProfileHarness(TestClient(app), repository, keyring, data_dir)


def profile_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": "默认档案",
        "protocol": "anthropic",
        "base_url": "https://api.anthropic.com",
        "models": [],
    }
    payload.update(overrides)
    return payload


def create_profile(harness: ProfileHarness, **overrides: object) -> dict[str, object]:
    response = harness.client.post("/api/profiles", json=profile_payload(**overrides))
    assert response.status_code == 201, response.text
    return response.json()


def bind_profile(
    harness: ProfileHarness,
    profile_id: str,
    tool_id: str,
) -> None:
    """绕过绑定端点直接落盘, 用于构造「已卸载工具仍占用」等前置状态。"""
    binding = make_binding(profile_id, tool_id)

    def change(store: ProfileStore) -> None:
        store.bindings.append(binding)

    harness.repository.mutate(change)


def stored_profile(harness: ProfileHarness, profile_id: str) -> dict[str, object]:
    raw = json.loads((harness.data_dir / "profiles.json").read_text(encoding="utf-8"))
    return next(profile for profile in raw["profiles"] if profile["id"] == profile_id)
