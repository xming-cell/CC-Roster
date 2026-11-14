"""013 启动器测试: 命令构造、零副作用预览、注入防护与启动反馈。"""

from pathlib import Path

from fastapi.testclient import TestClient
from profile_fixtures import make_profile

from app.adapters.claude_code import ClaudeCodeAdapter
from app.adapters.codex_cli import CodexCliAdapter
from app.adapters.registry import ToolRegistry
from app.api.launcher import get_launch_service
from app.main import create_app
from app.repositories.profiles import ProfileRepository
from app.repositories.secrets import build_secret_store
from app.services.launcher import LaunchService, terminal_argv

SECRET = "sk-ant-launch-secret-123456"


class FakeSpawner:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], Path, dict[str, str]]] = []
        self.fail = False

    def spawn(self, command: list[str], cwd: Path, env: object) -> int:
        if self.fail:
            raise OSError("terminal missing")
        assert isinstance(env, dict)
        self.calls.append((list(command), cwd, env))
        return 4242


def harness(tmp_path: Path, *, which_found: bool = True, platform: str = "win32"):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    repository = ProfileRepository(data_dir)
    secrets = build_secret_store(data_dir, mode="file")
    profile_id = "11111111-1111-4111-8111-111111111111"
    ref = secrets.put(profile_id, SECRET)
    profile = make_profile(
        profile_id=profile_id,
        secret_ref=ref,
        models=[{"id": "claude-sonnet-4"}],
    )
    codex_profile = make_profile(
        name="Codex 档案",
        profile_id="22222222-2222-4222-8222-222222222222",
        protocol="openai",
        base_url="https://api.openai.com/v1",
        secret_ref=secrets.put("22222222-2222-4222-8222-222222222222", "sk-openai-launch-123456"),
        models=[{"id": "gpt-5-codex"}],
    )
    repository.mutate(lambda store: store.profiles.extend([profile, codex_profile]))

    registry = ToolRegistry(
        [
            ClaudeCodeAdapter(tmp_path / "claude", which=lambda _name: None),
            CodexCliAdapter(tmp_path / "codex", which=lambda _name: None),
        ]
    )
    spawner = FakeSpawner()
    which = (lambda name: f"/usr/bin/{name}") if which_found else (lambda name: None)
    service = LaunchService(
        registry,
        repository,
        secrets,
        which=which,
        spawner=spawner,
        platform=platform,
    )
    app = create_app()
    app.dependency_overrides[get_launch_service] = lambda: service
    project = tmp_path / "project & echo hacked"
    project.mkdir()
    return TestClient(app), spawner, project, profile_id, codex_profile.id


def test_preview_returns_command_and_never_starts_or_leaks_secret(tmp_path: Path) -> None:
    client, spawner, project, profile_id, _ = harness(tmp_path)

    response = client.post(
        "/api/launch/preview",
        json={
            "tool_id": "claude-code",
            "profile_id": profile_id,
            "project_dir": str(project),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["command"] == ["/usr/bin/claude"]
    assert body["environment_keys"] == [
        "ANTHROPIC_BASE_URL",
        "ANTHROPIC_AUTH_TOKEN",
        "ANTHROPIC_MODEL",
    ]
    assert body["can_launch"] is True
    assert body["model"] == "claude-sonnet-4"
    assert SECRET not in response.text
    assert spawner.calls == []


def test_launch_spawns_in_project_directory_with_profile_environment(tmp_path: Path) -> None:
    client, spawner, project, _, codex_id = harness(tmp_path)

    response = client.post(
        "/api/launch",
        json={
            "tool_id": "codex-cli",
            "profile_id": codex_id,
            "project_dir": str(project),
            "model": "gpt-5-codex",
        },
    )

    assert response.status_code == 200
    assert response.json()["launched"] is True
    assert response.json()["pid"] == 4242
    assert len(spawner.calls) == 1
    command, cwd, env = spawner.calls[0]
    assert command == ["/usr/bin/codex", "--model", "gpt-5-codex"]
    assert cwd == project
    assert env["OPENAI_BASE_URL"] == "https://api.openai.com/v1"
    assert env["OPENAI_API_KEY"] == "sk-openai-launch-123456"
    assert "sk-openai-launch-123456" not in response.text


def test_missing_tool_secret_and_bad_directory_are_readable_blockers(tmp_path: Path) -> None:
    client, spawner, _project, profile_id, _ = harness(tmp_path, which_found=False)
    bad_dir = client.post(
        "/api/launch/preview",
        json={
            "tool_id": "claude-code",
            "profile_id": profile_id,
            "project_dir": str(tmp_path / "missing"),
        },
    )
    file_path = tmp_path / "a-file"
    file_path.write_text("x", encoding="utf-8")
    not_dir = client.post(
        "/api/launch/preview",
        json={
            "tool_id": "claude-code",
            "profile_id": profile_id,
            "project_dir": str(file_path),
        },
    )

    assert bad_dir.status_code == 200
    codes = {item["code"] for item in bad_dir.json()["blockers"]}
    assert {"TOOL_NOT_INSTALLED", "PROJECT_DIR_NOT_FOUND"} <= codes
    assert bad_dir.json()["can_launch"] is False
    assert any(item["code"] == "PROJECT_DIR_NOT_DIRECTORY" for item in not_dir.json()["blockers"])
    assert spawner.calls == []


def test_protocol_mismatch_and_missing_secret_block_launch(tmp_path: Path) -> None:
    client, spawner, project, profile_id, _ = harness(tmp_path)

    mismatch = client.post(
        "/api/launch/preview",
        json={
            "tool_id": "codex-cli",
            "profile_id": profile_id,
            "project_dir": str(project),
        },
    )
    assert any(item["code"] == "PROTOCOL_MISMATCH" for item in mismatch.json()["blockers"])

    data_dir = tmp_path / "data"
    repository = ProfileRepository(data_dir)
    no_secret_id = "33333333-3333-4333-8333-333333333333"
    no_secret = make_profile(
        profile_id=no_secret_id,
        secret_ref=None,
        models=[{"id": "claude-sonnet-4"}],
    )
    repository.mutate(lambda store: store.profiles.append(no_secret))
    response = client.post(
        "/api/launch/preview",
        json={
            "tool_id": "claude-code",
            "profile_id": no_secret_id,
            "project_dir": str(project),
        },
    )
    assert any(item["code"] == "SECRET_MISSING" for item in response.json()["blockers"])
    assert spawner.calls == []


def test_launch_failure_and_blocked_launch_return_error_envelope(tmp_path: Path) -> None:
    client, spawner, project, profile_id, _ = harness(tmp_path)
    spawner.fail = True

    failed = client.post(
        "/api/launch",
        json={
            "tool_id": "claude-code",
            "profile_id": profile_id,
            "project_dir": str(project),
        },
    )
    blocked = client.post(
        "/api/launch",
        json={
            "tool_id": "claude-code",
            "profile_id": profile_id,
            "project_dir": str(tmp_path / "missing"),
        },
    )

    assert failed.status_code == 500
    assert failed.json()["code"] == "LAUNCH_FAILED"
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "LAUNCH_BLOCKED"


def test_unknown_profile_and_relative_path_are_rejected(tmp_path: Path) -> None:
    client, spawner, project, _, _ = harness(tmp_path)

    unknown = client.post(
        "/api/launch/preview",
        json={
            "tool_id": "claude-code",
            "profile_id": "44444444-4444-4444-8444-444444444444",
            "project_dir": str(project),
        },
    )
    relative = client.post(
        "/api/launch/preview",
        json={
            "tool_id": "claude-code",
            "profile_id": "11111111-1111-4111-8111-111111111111",
            "project_dir": "relative/path",
        },
    )

    assert unknown.status_code == 404
    assert unknown.json()["code"] == "PROFILE_NOT_FOUND"
    assert relative.status_code == 422
    assert spawner.calls == []


def test_terminal_argv_wraps_cmd_shims_and_quotes_posix_scripts(tmp_path: Path) -> None:
    win = terminal_argv(["C:/npm/claude.CMD"], "win32", tmp_path)
    mac = terminal_argv(["claude"], "darwin", tmp_path / "a b")
    linux = terminal_argv(["claude"], "linux", tmp_path / "a b")

    assert win[-1].endswith("claude.CMD")
    assert win[1:3] == ["/d", "/c"]
    assert mac[0] == "osascript"
    assert "a b" in mac[2]
    assert "&& exec claude" in mac[2]
    assert linux[:4] == ["x-terminal-emulator", "-e", "sh", "-c"]
    assert "a b" in linux[4]
    assert "&& exec claude" in linux[4]


def test_model_with_shell_metacharacters_is_rejected(tmp_path: Path) -> None:
    client, _spawner, project, profile_id, _ = harness(tmp_path)

    response = client.post(
        "/api/launch/preview",
        json={
            "tool_id": "claude-code",
            "profile_id": profile_id,
            "project_dir": str(project),
            "model": "claude & calc",
        },
    )

    assert response.status_code == 422
