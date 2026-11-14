"""008 切换测试共享的构造器; 不是 pytest 插件, 也不会被收集。

使用真实仓储 / 密钥存储 / 写引擎与真实 HTTP 路由, 只把工具配置目录、keyring 与
可访问性判断替换成临时实现。
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient
from profile_fixtures import FakeKeyring, make_profile

from app.adapters.claude_code import ClaudeCodeAdapter
from app.adapters.codex_cli import CodexCliAdapter
from app.adapters.registry import ToolRegistry
from app.api.audit import get_audit_service
from app.api.switch import get_switch_service
from app.main import create_app
from app.repositories.audit import AuditRepository
from app.repositories.profiles import ProfileRepository
from app.repositories.secrets import (
    FileSecretStore,
    KeyringSecretStore,
    SecretStore,
    build_secret_store,
)
from app.repositories.snapshots import SnapshotRepository
from app.schemas.profile import ModelEntry, Profile, ProfileProtocol
from app.services.audit_service import AuditService
from app.services.snapshot_service import SnapshotService
from app.services.switch_service import AccessFn, SwitchService
from app.services.write_engine import WriteEngine

NOW = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)
SECRET = "sk-switch-secret-1234567890abcdef"


@dataclass
class SwitchHarness:
    client: TestClient
    service: SwitchService
    registry: ToolRegistry
    profiles: ProfileRepository
    secrets: SecretStore
    keyring: FakeKeyring
    snapshots: SnapshotRepository
    audit: AuditRepository
    data_dir: Path
    claude_dir: Path
    codex_dir: Path


def make_switch_harness(
    data_dir: Path,
    *,
    access: AccessFn | None = None,
    lock_timeout: float = 5.0,
) -> SwitchHarness:
    data_dir.mkdir(parents=True, exist_ok=True)
    claude_dir = data_dir / "claude"
    codex_dir = data_dir / "codex"
    claude_dir.mkdir()
    codex_dir.mkdir()

    keyring = FakeKeyring()
    secrets = build_secret_store(
        data_dir,
        mode="keyring",
        keyring_store=KeyringSecretStore(keyring),
        file_store=FileSecretStore(data_dir),
    )
    registry = ToolRegistry(
        [
            ClaudeCodeAdapter(claude_dir, which=lambda _name: None),
            CodexCliAdapter(codex_dir, which=lambda _name: None),
        ]
    )
    profiles = ProfileRepository(data_dir)
    snapshots = SnapshotRepository(data_dir)
    audit = AuditRepository(data_dir / "db" / "app.sqlite3")
    lock_path = data_dir / "locks" / "write.lock"
    write_engine = WriteEngine(
        snapshots,
        audit,
        write_lock_path=lock_path,
        lock_timeout=lock_timeout,
    )
    snapshot_service = SnapshotService(
        snapshots,
        audit,
        write_lock_path=lock_path,
        lock_timeout=lock_timeout,
    )
    service = SwitchService(
        registry=registry,
        profiles=profiles,
        secrets=secrets,
        write_engine=write_engine,
        snapshots=snapshot_service,
        audit=audit,
        access=access,
    )
    app = create_app()
    app.dependency_overrides[get_switch_service] = lambda: service
    app.dependency_overrides[get_audit_service] = lambda: AuditService(audit)
    return SwitchHarness(
        client=TestClient(app),
        service=service,
        registry=registry,
        profiles=profiles,
        secrets=secrets,
        keyring=keyring,
        snapshots=snapshots,
        audit=audit,
        data_dir=data_dir,
        claude_dir=claude_dir,
        codex_dir=codex_dir,
    )


def add_profile(
    harness: SwitchHarness,
    *,
    name: str = "Claude 档案",
    protocol: ProfileProtocol = "anthropic",
    base_url: str = "https://relay.example.com",
    models: Sequence[str] = ("claude-sonnet-4", "claude-opus-4"),
    secret: str | None = SECRET,
) -> Profile:
    profile_id = str(uuid.uuid4())
    secret_ref = harness.secrets.put(profile_id, secret) if secret is not None else None
    profile = make_profile(
        name,
        profile_id=profile_id,
        protocol=protocol,
        base_url=base_url,
        secret_ref=secret_ref,
        models=[ModelEntry(id=model_id) for model_id in models],
        created_at=NOW,
        updated_at=NOW,
    )
    harness.profiles.mutate(lambda store: store.profiles.append(profile))
    return profile


def add_codex_profile(
    harness: SwitchHarness,
    *,
    name: str = "Codex 档案",
    base_url: str = "https://relay.example.com/v1",
    models: Sequence[str] = ("gpt-5-codex", "gpt-5"),
    secret: str | None = SECRET,
) -> Profile:
    return add_profile(
        harness,
        name=name,
        protocol="openai",
        base_url=base_url,
        models=models,
        secret=secret,
    )


def write_claude_settings(harness: SwitchHarness, content: str | bytes) -> Path:
    path = harness.claude_dir / "settings.json"
    data = content.encode() if isinstance(content, str) else content
    path.write_bytes(data)
    return path


def write_codex_files(
    harness: SwitchHarness,
    *,
    config: str | bytes | None,
    auth: str | bytes | None,
) -> tuple[Path, Path]:
    config_path = harness.codex_dir / "config.toml"
    auth_path = harness.codex_dir / "auth.json"
    if config is not None:
        config_path.write_bytes(config.encode() if isinstance(config, str) else config)
    if auth is not None:
        auth_path.write_bytes(auth.encode() if isinstance(auth, str) else auth)
    return config_path, auth_path


def post_preview(
    harness: SwitchHarness,
    profile_id: str,
    *,
    tool_id: str = "claude-code",
    model: str | None = None,
) -> object:
    payload: dict[str, object] = {
        "tool_id": tool_id,
        "profile_id": profile_id,
    }
    if model is not None:
        payload["model"] = model
    return harness.client.post("/api/switch/preview", json=payload)


def preview_json(
    harness: SwitchHarness,
    profile_id: str,
    *,
    tool_id: str = "claude-code",
    model: str | None = None,
) -> dict[str, object]:
    response = post_preview(harness, profile_id, tool_id=tool_id, model=model)
    assert response.status_code == 200, response.text
    return response.json()


def apply_payload(
    preview: dict[str, object],
    *,
    model: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "tool_id": preview["tool_id"],
        "profile_id": preview["profile_id"],
        "preview_digest": preview["preview_digest"],
        "observations": preview["observations"],
    }
    if model is not None:
        payload["model"] = model
    return payload
