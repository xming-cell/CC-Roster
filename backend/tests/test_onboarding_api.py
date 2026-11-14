"""021 新手引导状态机: 安装 / 凭证 / 首条消息 / 恢复。"""

import uuid
from pathlib import Path

from fastapi.testclient import TestClient
from profile_fixtures import make_profile

from app.adapters.claude_code import ClaudeCodeAdapter
from app.adapters.codex_cli import CodexCliAdapter
from app.adapters.registry import ToolRegistry
from app.api.onboarding import get_onboarding_service
from app.core.clock import utc_now
from app.main import create_app
from app.repositories.chat import ChatRepository
from app.repositories.onboarding import OnboardingRepository
from app.repositories.profiles import ProfileRepository
from app.repositories.secrets import build_secret_store
from app.schemas.chat import ChatMessage, ChatSession
from app.services.onboarding_service import OnboardingService

PROFILE_ID = "11111111-1111-4111-8111-111111111111"
SECRET = "sk-onboarding-secret-123456"


def harness(tmp_path: Path, *, with_secret: bool = True, installed: bool = True):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    claude_dir = tmp_path / "claude"
    if installed:
        claude_dir.mkdir()
    codex_dir = tmp_path / "codex"
    codex_dir.mkdir()
    profiles = ProfileRepository(data_dir)
    secrets = build_secret_store(data_dir, mode="file")
    ref = secrets.put(PROFILE_ID, SECRET) if with_secret else None
    profiles.mutate(
        lambda store: store.profiles.append(
            make_profile(
                profile_id=PROFILE_ID,
                secret_ref=ref,
                models=[{"id": "claude-sonnet-4"}],
            )
        )
    )
    registry = ToolRegistry(
        [
            ClaudeCodeAdapter(claude_dir, which=lambda _name: None),
            CodexCliAdapter(codex_dir, which=lambda _name: None),
        ]
    )
    chats = ChatRepository(data_dir)
    repository = OnboardingRepository(data_dir)
    service = OnboardingService(repository, registry, profiles, secrets, chats)
    app = create_app()
    app.dependency_overrides[get_onboarding_service] = lambda: service
    project = tmp_path / "project"
    project.mkdir()
    return TestClient(app), service, repository, chats, project


def context(project: Path) -> dict[str, object]:
    return {
        "tool_id": "claude-code",
        "profile_id": PROFILE_ID,
        "project_dir": str(project),
    }


def test_install_then_credentials_then_first_message(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    client, _service, repository, chats, project = harness(tmp_path)

    installed = client.post("/api/onboarding/install/check", json=context(project))
    credentials = client.post("/api/onboarding/credentials/check", json=context(project))
    before_message = client.post("/api/onboarding/first-message/check", json=context(project))

    assert installed.json()["install"]["status"] == "done"
    assert installed.json()["current_step"] == "credentials"
    assert credentials.json()["credentials"]["status"] == "done"
    assert credentials.json()["current_step"] == "first_message"
    assert before_message.json()["first_message"]["status"] == "failed"
    assert "还没有完成一次对话" in before_message.json()["first_message"]["message"]
    assert repository.path.exists()

    session = ChatSession(
        id=str(uuid.uuid4()),
        tool_id="claude-code",
        profile_id=PROFILE_ID,
        project_dir=str(project),
        title="first",
        status="idle",
        messages=[
            ChatMessage(id="u1", role="user", content="hi", created_at=utc_now()),
            ChatMessage(id="a1", role="assistant", content="hello", created_at=utc_now()),
        ],
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    chats.mutate(lambda store: store.sessions.append(session))

    after_message = client.post("/api/onboarding/first-message/check", json=context(project))
    assert after_message.json()["first_message"]["status"] == "done"
    assert after_message.json()["current_step"] == "complete"
    assert "不代注册" in after_message.json()["compliance_note"]


def test_state_survives_new_service_instance(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    client, _service, _repository, _chats, project = harness(tmp_path)
    client.post("/api/onboarding/install/check", json=context(project))

    fresh = OnboardingService(
        OnboardingRepository(tmp_path / "data"),
        client.app.dependency_overrides[get_onboarding_service]()._registry,
        ProfileRepository(tmp_path / "data"),
        build_secret_store(tmp_path / "data", mode="file"),
        ChatRepository(tmp_path / "data"),
    )

    state = fresh.get()
    assert state.install.status == "done"
    assert state.tool_id == "claude-code"


def test_missing_tool_and_missing_secret_are_readable(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    client, _service, _repository, _chats, project = harness(
        tmp_path, with_secret=False, installed=False
    )

    install = client.post("/api/onboarding/install/check", json=context(project))
    credentials = client.post("/api/onboarding/credentials/check", json=context(project))

    assert install.json()["install"]["status"] == "failed"
    assert "安装 Claude Code" in install.json()["install"]["message"]
    assert credentials.json()["credentials"]["status"] == "failed"
    assert "密钥" in credentials.json()["credentials"]["message"]


def test_reset_and_context_change_clear_progress(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    client, _service, _repository, _chats, project = harness(tmp_path)
    client.post("/api/onboarding/install/check", json=context(project))

    switched = client.put("/api/onboarding", json={"tool_id": "codex-cli"})
    reset = client.post("/api/onboarding/reset")

    assert switched.json()["install"]["status"] == "pending"
    assert reset.json()["current_step"] == "install"
    assert reset.json()["tool_id"] is None


def test_unknown_tool_is_a_failed_step(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    client, _service, _repository, _chats, project = harness(tmp_path)

    response = client.post(
        "/api/onboarding/install/check",
        json={"tool_id": "nope", "profile_id": PROFILE_ID, "project_dir": str(project)},
    )

    assert response.json()["install"]["status"] == "failed"
    assert "未知工具" in response.json()["install"]["message"]
