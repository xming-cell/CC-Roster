"""018 群聊对比: 并发、隔离、超时、取消与限流。"""

import threading
import time
import uuid
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path

from fastapi.testclient import TestClient
from profile_fixtures import make_profile

from app.adapters.claude_code import ClaudeCodeAdapter
from app.adapters.codex_cli import CodexCliAdapter
from app.adapters.registry import ToolRegistry
from app.api.group_chat import get_group_chat_service
from app.main import create_app
from app.repositories.profiles import ProfileRepository
from app.repositories.secrets import build_secret_store
from app.services.chat_executor import RawChatEvent
from app.services.group_chat import GroupChatService
from app.services.launcher import LaunchService

SECRET = "sk-group-secret-123456789012"
CLAUDE_ID = "11111111-1111-4111-8111-111111111111"
CODEX_ID = "22222222-2222-4222-8222-222222222222"


class FakeSpawner:
    def spawn(self, command: Sequence[str], cwd: Path, env: Mapping[str, str]) -> int:
        return 1


class GroupFakeExecutor:
    def __init__(self, *, slow: bool = False, fail_codex: bool = False) -> None:
        self.slow = slow
        self.fail_codex = fail_codex
        self.release = threading.Event()
        self.cancelled: list[str] = []
        self.active = 0
        self.max_active = 0
        self.lock = threading.Lock()

    def stream(
        self,
        *,
        session_id: str,
        command: Sequence[str],
        cwd: Path,
        env: Mapping[str, str],
    ) -> Iterator[RawChatEvent]:
        with self.lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        try:
            if self.slow:
                self.release.wait(timeout=5)
                return
            if self.fail_codex and "codex" in command[0]:
                raise RuntimeError("codex exploded")
            yield RawChatEvent(type="token", content=f"answer from {Path(command[0]).name}")
        finally:
            with self.lock:
                self.active -= 1

    def cancel(self, session_id: str) -> bool:
        self.cancelled.append(session_id)
        self.release.set()
        return True

    def was_cancelled(self, session_id: str) -> bool:
        return session_id in self.cancelled


def harness(tmp_path: Path, executor: GroupFakeExecutor, *, min_interval: float = 0):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    repository = ProfileRepository(data_dir)
    secrets = build_secret_store(data_dir, mode="file")
    repository.mutate(
        lambda store: store.profiles.extend(
            [
                make_profile(
                    profile_id=CLAUDE_ID,
                    secret_ref=secrets.put(CLAUDE_ID, SECRET),
                    models=[{"id": "claude-sonnet-4"}],
                ),
                make_profile(
                    name="Codex",
                    profile_id=CODEX_ID,
                    protocol="openai",
                    base_url="https://api.openai.com/v1",
                    secret_ref=secrets.put(CODEX_ID, SECRET),
                    models=[{"id": "gpt-5-codex"}],
                ),
            ]
        )
    )
    registry = ToolRegistry(
        [
            ClaudeCodeAdapter(tmp_path / "claude", which=lambda _name: None),
            CodexCliAdapter(tmp_path / "codex", which=lambda _name: None),
        ]
    )
    launcher = LaunchService(
        registry,
        repository,
        secrets,
        which=lambda name: f"/usr/bin/{name}",
        spawner=FakeSpawner(),
        platform="win32",
    )
    service = GroupChatService(launcher, executor, min_interval_seconds=min_interval)
    app = create_app()
    app.dependency_overrides[get_group_chat_service] = lambda: service
    project = tmp_path / "project"
    project.mkdir()
    return TestClient(app), service, executor, project


def payload(
    project: Path, participants: list[dict[str, object]] | None = None
) -> dict[str, object]:
    return {
        "group_id": str(uuid.uuid4()),
        "project_dir": str(project),
        "question": "同一个问题",
        "participants": participants
        or [
            {"tool_id": "claude-code", "profile_id": CLAUDE_ID},
            {"tool_id": "codex-cli", "profile_id": CODEX_ID},
        ],
    }


def test_partial_failure_keeps_successful_result_and_order(tmp_path: Path) -> None:
    executor = GroupFakeExecutor(fail_codex=True)
    client, _service, _executor, project = harness(tmp_path, executor)

    response = client.post("/api/group-chat", json=payload(project))

    assert response.status_code == 200
    results = response.json()["results"]
    assert [item["tool_id"] for item in results] == ["claude-code", "codex-cli"]
    assert results[0]["status"] == "success"
    assert results[0]["content"] == "answer from claude"
    assert results[1]["status"] == "failed"
    assert "RuntimeError" in results[1]["error"]
    assert SECRET not in response.text


def test_timeout_cancels_participant_and_returns_others(tmp_path: Path) -> None:
    executor = GroupFakeExecutor(slow=True)
    client, _service, _executor, project = harness(tmp_path, executor)
    body = payload(project, [{"tool_id": "claude-code", "profile_id": CLAUDE_ID}])
    body["timeout_seconds"] = 1

    started = time.perf_counter()
    response = client.post("/api/group-chat", json=body)
    elapsed = time.perf_counter() - started

    assert response.status_code == 200
    assert response.json()["results"][0]["status"] == "timeout"
    assert elapsed < 3
    assert executor.cancelled


def test_validation_and_rate_limit(tmp_path: Path) -> None:
    executor = GroupFakeExecutor()
    client, _service, _executor, project = harness(tmp_path, executor, min_interval=60)

    empty = client.post(
        "/api/group-chat",
        json={**payload(project), "question": "   "},
    )
    too_many = client.post(
        "/api/group-chat",
        json=payload(
            project,
            [
                {"tool_id": "claude-code", "profile_id": CLAUDE_ID},
                {"tool_id": "claude-code", "profile_id": CLAUDE_ID},
            ],
        ),
    )
    first = client.post("/api/group-chat", json=payload(project))
    second = client.post("/api/group-chat", json=payload(project))

    assert empty.status_code == 422
    assert too_many.status_code == 422
    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["code"] == "GROUP_RATE_LIMITED"


def test_unknown_participant_is_isolated_failure(tmp_path: Path) -> None:
    executor = GroupFakeExecutor()
    client, _service, _executor, project = harness(tmp_path, executor)

    response = client.post(
        "/api/group-chat",
        json=payload(
            project,
            [
                {"tool_id": "claude-code", "profile_id": CLAUDE_ID},
                {"tool_id": "not-a-tool", "profile_id": CLAUDE_ID},
            ],
        ),
    )

    assert response.status_code == 200
    assert response.json()["results"][0]["status"] == "success"
    assert response.json()["results"][1]["status"] == "failed"


def test_cancel_endpoint_is_idempotent(tmp_path: Path) -> None:
    executor = GroupFakeExecutor()
    client, _service, _executor, _project = harness(tmp_path, executor)
    group_id = str(uuid.uuid4())

    first = client.post(f"/api/group-chat/{group_id}/cancel")
    second = client.post(f"/api/group-chat/{group_id}/cancel")

    assert first.json()["cancelled"] is False
    assert second.json()["cancelled"] is False
