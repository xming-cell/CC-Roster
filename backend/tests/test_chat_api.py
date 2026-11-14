"""014 应用内对话: 上下文、SSE、错误与中断测试。"""

import json
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path

from fastapi.testclient import TestClient
from profile_fixtures import make_profile

from app.adapters.claude_code import ClaudeCodeAdapter
from app.adapters.codex_cli import CodexCliAdapter
from app.adapters.registry import ToolRegistry
from app.api.chat import get_chat_service
from app.main import create_app
from app.repositories.chat import ChatRepository
from app.repositories.profiles import ProfileRepository
from app.repositories.secrets import build_secret_store
from app.schemas.chat import ChatStore
from app.services.chat import ChatService
from app.services.chat_executor import RawChatEvent, parse_json_event, parse_output_line
from app.services.launcher import LaunchService

SECRET = "sk-ant-chat-secret-1234567890"
PROFILE_ID = "11111111-1111-4111-8111-111111111111"


class FakeSpawner:
    def spawn(self, command: Sequence[str], cwd: Path, env: Mapping[str, str]) -> int:
        return 1


class FakeExecutor:
    def __init__(self, events: list[RawChatEvent] | None = None) -> None:
        self.events = events or []
        self.calls: list[tuple[list[str], Path, dict[str, str]]] = []
        self.cancelled = False
        self.cancel_result = False
        self.cancel_on_first = False
        self.raise_error: Exception | None = None

    def stream(
        self,
        *,
        session_id: str,
        command: Sequence[str],
        cwd: Path,
        env: Mapping[str, str],
    ) -> Iterator[RawChatEvent]:
        self.calls.append((list(command), cwd, dict(env)))
        if self.raise_error is not None:
            raise self.raise_error
        for index, event in enumerate(self.events):
            yield event
            if self.cancel_on_first and index == 0:
                self.cancelled = True
                return

    def cancel(self, session_id: str) -> bool:
        self.cancelled = True
        return self.cancel_result

    def was_cancelled(self, session_id: str) -> bool:
        return self.cancelled


def harness(tmp_path: Path, executor: FakeExecutor | None = None):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    repository = ProfileRepository(data_dir)
    secrets = build_secret_store(data_dir, mode="file")
    ref = secrets.put(PROFILE_ID, SECRET)
    repository.mutate(
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
    fake = executor or FakeExecutor(
        [
            RawChatEvent(type="status", message="思考中"),
            RawChatEvent(type="token", content="你好"),
            RawChatEvent(type="tool", tool_name="Bash", content="ls"),
            RawChatEvent(type="token", content="完成"),
        ]
    )
    chat_repository = ChatRepository(data_dir)
    service = ChatService(chat_repository, launcher, fake)
    app = create_app()
    app.dependency_overrides[get_chat_service] = lambda: service
    project = tmp_path / "project"
    project.mkdir()
    return TestClient(app), service, fake, project, chat_repository


def create_session(client: TestClient, project: Path) -> dict[str, object]:
    response = client.post(
        "/api/chat/sessions",
        json={
            "tool_id": "claude-code",
            "profile_id": PROFILE_ID,
            "project_dir": str(project),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def sse_events(text: str) -> list[dict[str, object]]:
    return [
        json.loads(line.removeprefix("data: "))
        for line in text.splitlines()
        if line.startswith("data: ")
    ]


def test_create_list_get_and_persist_context(tmp_path: Path) -> None:
    client, _service, _fake, project, repository = harness(tmp_path)

    created = create_session(client, project)
    listed = client.get("/api/chat/sessions")
    fetched = client.get(f"/api/chat/sessions/{created['id']}")

    assert created["tool_id"] == "claude-code"
    assert created["status"] == "idle"
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["sessions"]] == [created["id"]]
    assert fetched.json()["project_dir"] == str(project)
    assert repository.path.exists()
    assert SECRET not in repository.path.read_text(encoding="utf-8")


def test_stream_maps_tokens_tools_and_done(tmp_path: Path) -> None:
    client, _service, fake, project, _repository = harness(tmp_path)
    session = create_session(client, project)

    response = client.post(
        f"/api/chat/sessions/{session['id']}/messages",
        json={"content": "帮我改一个文件"},
    )

    assert response.status_code == 200
    events = sse_events(response.text)
    assert [event["type"] for event in events] == [
        "status",
        "status",
        "token",
        "tool",
        "token",
        "done",
    ]
    assert events[2]["content"] == "你好"
    assert events[3]["tool_name"] == "Bash"
    assert len(fake.calls) == 1
    command, cwd, env = fake.calls[0]
    assert command == [
        "/usr/bin/claude",
        "-p",
        "帮我改一个文件",
        "--output-format",
        "stream-json",
        "--verbose",
    ]
    assert cwd == project
    assert env["ANTHROPIC_MODEL"] == "claude-sonnet-4"

    stored = client.get(f"/api/chat/sessions/{session['id']}").json()
    assert [message["role"] for message in stored["messages"]] == ["user", "tool", "assistant"]
    assert stored["messages"][-1]["content"] == "你好完成"
    assert stored["title"] == "帮我改一个文件"
    assert stored["status"] == "idle"


def test_cancel_marks_session_and_is_idempotent(tmp_path: Path) -> None:
    executor = FakeExecutor(
        [
            RawChatEvent(type="token", content="部分输出"),
            RawChatEvent(type="token", content="不会到"),
        ]
    )
    executor.cancel_on_first = True
    client, _service, _fake, project, _repository = harness(tmp_path, executor)
    session = create_session(client, project)

    response = client.post(
        f"/api/chat/sessions/{session['id']}/messages",
        json={"content": "开始"},
    )
    repeated = client.post(f"/api/chat/sessions/{session['id']}/cancel")

    events = sse_events(response.text)
    assert events[-1]["type"] == "cancelled"
    stored = client.get(f"/api/chat/sessions/{session['id']}").json()
    assert stored["status"] == "cancelled"
    assert stored["messages"][-1]["content"] == "部分输出"
    assert repeated.status_code == 200
    assert repeated.json()["cancelled"] is False


def test_failure_keeps_user_input_and_returns_readable_error(tmp_path: Path) -> None:
    executor = FakeExecutor()
    executor.raise_error = RuntimeError("boom")
    client, _service, _fake, project, _repository = harness(tmp_path, executor)
    session = create_session(client, project)

    response = client.post(
        f"/api/chat/sessions/{session['id']}/messages",
        json={"content": "保留我"},
    )

    events = sse_events(response.text)
    assert events[-1]["type"] == "error"
    assert "RuntimeError" in str(events[-1]["message"])
    stored = client.get(f"/api/chat/sessions/{session['id']}").json()
    assert stored["status"] == "failed"
    assert stored["messages"][0]["content"] == "保留我"
    assert stored["messages"][-1]["is_error"] is True


def test_validation_errors_and_busy_session_return_envelopes(tmp_path: Path) -> None:
    client, _service, _fake, project, repository = harness(tmp_path)
    session = create_session(client, project)

    empty = client.post(f"/api/chat/sessions/{session['id']}/messages", json={"content": "   "})
    missing = client.post(
        "/api/chat/sessions",
        json={
            "tool_id": "claude-code",
            "profile_id": PROFILE_ID,
            "project_dir": str(tmp_path / "missing"),
        },
    )
    unknown = client.get("/api/chat/sessions/22222222-2222-4222-8222-222222222222")

    def mark_running(store: ChatStore) -> None:
        for item in store.sessions:
            if item.id == session["id"]:
                item.status = "running"

    repository.mutate(mark_running)
    busy = client.post(
        f"/api/chat/sessions/{session['id']}/messages",
        json={"content": "再来"},
    )

    assert empty.status_code == 422
    assert missing.status_code == 400
    assert missing.json()["code"] == "CHAT_CONTEXT_INVALID"
    assert unknown.status_code == 404
    assert busy.status_code == 409
    assert busy.json()["code"] == "CHAT_BUSY"


def test_secret_in_output_is_redacted_before_sse_and_storage(tmp_path: Path) -> None:
    executor = FakeExecutor([RawChatEvent(type="token", content=f"key={SECRET}")])
    client, _service, _fake, project, repository = harness(tmp_path, executor)
    session = create_session(client, project)

    response = client.post(
        f"/api/chat/sessions/{session['id']}/messages",
        json={"content": "看这个 key " + SECRET},
    )

    assert SECRET not in response.text
    assert SECRET not in repository.path.read_text(encoding="utf-8")
    assert "sk-a****" in response.text


def test_unknown_cli_events_degrade_to_readable_status_and_text() -> None:
    statuses = list(parse_json_event({"type": "mystery.event"}))
    plain = list(parse_output_line("not json at all"))

    assert statuses[0].type == "status"
    assert "未识别事件" in (statuses[0].message or "")
    assert plain[0].type == "token"
    assert plain[0].content == "not json at all"


def test_cancel_without_running_process_is_idempotent(tmp_path: Path) -> None:
    client, _service, _fake, project, _repository = harness(tmp_path)
    session = create_session(client, project)

    first = client.post(f"/api/chat/sessions/{session['id']}/cancel")
    second = client.post(f"/api/chat/sessions/{session['id']}/cancel")

    assert first.json()["cancelled"] is False
    assert second.json()["cancelled"] is False
