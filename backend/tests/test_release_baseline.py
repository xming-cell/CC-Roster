"""017 发布基线: 离线只读、索引重建、启动性能与 CI 矩阵。"""

import hashlib
import socket
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.paths import ensure_data_dirs
from app.main import create_app, initialize_app_data


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_offline_read_paths_do_not_need_network(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "empty-claude"))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "empty-codex"))

    def no_network(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("unexpected network access")

    monkeypatch.setattr(socket, "create_connection", no_network)
    client = TestClient(create_app())

    assert client.get("/api/health").status_code == 200
    assert client.get("/api/settings").status_code == 200
    assert client.get("/api/tools").status_code == 200
    assert client.get("/api/profiles").status_code == 200
    assert client.get("/api/chat/sessions").status_code == 200
    assert client.get("/api/sessions").status_code == 200


def test_rebuild_index_and_cache_keeps_user_data(tmp_path: Path) -> None:
    data_dir = ensure_data_dirs(tmp_path / "data")
    profiles = data_dir / "profiles.json"
    chats = data_dir / "chat_sessions.json"
    appearances = data_dir / "appearances.json"
    profiles.write_text('{"schema_version":1,"profiles":[],"bindings":[]}', encoding="utf-8")
    chats.write_text('{"schema_version":1,"sessions":[]}', encoding="utf-8")
    appearances.write_text('{"schema_version":1,"appearances":{}}', encoding="utf-8")
    before = {path.name: digest(path) for path in (profiles, chats, appearances)}

    for name in ("db", "logs"):
        for child in (data_dir / name).rglob("*"):
            if child.is_file():
                child.unlink()
    initialize_app_data(data_dir)

    assert (data_dir / "db" / "app.sqlite3").exists()
    assert {path.name: digest(path) for path in (profiles, chats, appearances)} == before


def test_startup_health_is_under_one_second(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    started = time.perf_counter()
    response = TestClient(create_app()).get("/api/health")
    elapsed = time.perf_counter() - started

    assert response.status_code == 200
    assert elapsed < 1.0


def test_ci_runs_the_same_check_on_three_platforms() -> None:
    root = Path(__file__).resolve().parents[2]
    workflow = (root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "ubuntu-latest" in workflow
    assert "macos-latest" in workflow
    assert "windows-latest" in workflow
    assert "scripts/check.py" in workflow
