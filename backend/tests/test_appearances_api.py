import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.repositories.appearances as appearances_repository_module
from app.api.appearances import get_appearance_service
from app.core.errors import AppError
from app.main import create_app
from app.repositories.appearances import AppearanceRepository
from app.schemas.appearance import AppearanceOverride
from app.services.appearance_service import AppearanceService


def make_client(data_dir: Path, *, lock_timeout: float = 5.0) -> TestClient:
    app = create_app()
    repository = AppearanceRepository(data_dir, lock_timeout=lock_timeout)
    app.dependency_overrides[get_appearance_service] = lambda: AppearanceService(repository)
    return TestClient(app)


def test_missing_store_is_empty_and_read_has_no_filesystem_side_effect(tmp_path: Path) -> None:
    data_dir = tmp_path / "not-created"
    client = make_client(data_dir)

    response = client.get("/api/appearances")

    assert response.status_code == 200
    assert response.json() == {"schema_version": 1, "appearances": {}}
    assert not data_dir.exists()


def test_save_list_and_reset_only_affect_the_requested_tool(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    appearance = {
        "accent_color": "#12AB34",
        "background_color": "#F0E1D2",
        "bubble_preset": "rounded",
    }

    first = client.put("/api/appearances/claude-code", json=appearance)
    second = client.put(
        "/api/appearances/codex-cli",
        json={"accent_color": "#345678", "background_color": None, "bubble_preset": "soft"},
    )
    listed = client.get("/api/appearances")
    reset = client.delete("/api/appearances/claude-code")
    remaining = client.get("/api/appearances")

    assert first.status_code == second.status_code == 200
    assert first.json() == {"tool_id": "claude-code", **appearance}
    assert listed.json()["appearances"]["claude-code"] == appearance
    assert reset.json() == {"tool_id": "claude-code", "reset": True}
    assert remaining.json()["appearances"] == {
        "codex-cli": {"accent_color": "#345678", "background_color": None, "bubble_preset": "soft"}
    }
    assert client.delete("/api/appearances/claude-code").status_code == 200


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"accent_color": "red"},
        {"background_color": "#12345G"},
        {"bubble_preset": "unknown"},
        {"accent_color": "#123456", "unknown": "value"},
    ],
)
def test_save_rejects_empty_or_invalid_overrides_without_writing(
    tmp_path: Path,
    body: dict[str, object],
) -> None:
    client = make_client(tmp_path)

    response = client.put("/api/appearances/claude-code", json=body)

    assert response.status_code == 422
    assert not (tmp_path / "appearances.json").exists()


def test_save_rejects_empty_body_and_invalid_tool_ids(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    empty = client.put("/api/appearances/claude-code", content=b"")
    too_long = client.put(
        f"/api/appearances/{'x' * 121}",
        json={"accent_color": "#123456"},
    )

    assert empty.status_code == too_long.status_code == 422
    assert not (tmp_path / "appearances.json").exists()


@pytest.mark.parametrize(
    ("contents", "error_code"),
    [
        ("{", "APPEARANCE_STORE_INVALID"),
        ('{"schema_version":2,"appearances":{}}', "APPEARANCE_VERSION_UNSUPPORTED"),
        ('{"schema_version":1,"appearances":{"bad":{"unknown":true}}}', "APPEARANCE_STORE_INVALID"),
    ],
)
def test_corrupt_or_unknown_store_is_reported_and_not_overwritten(
    tmp_path: Path,
    contents: str,
    error_code: str,
) -> None:
    path = tmp_path / "appearances.json"
    path.write_text(contents, encoding="utf-8")
    client = make_client(tmp_path)

    read = client.get("/api/appearances")
    write = client.put("/api/appearances/claude-code", json={"accent_color": "#123456"})

    assert read.status_code == write.status_code == 500
    assert read.json()["code"] == write.json()["code"] == error_code
    assert path.read_text(encoding="utf-8") == contents


def test_concurrent_saves_keep_both_tool_overrides(tmp_path: Path) -> None:
    repository = AppearanceRepository(tmp_path)
    overrides = [
        ("claude-code", AppearanceOverride(accent_color="#123456")),
        ("codex-cli", AppearanceOverride(bubble_preset="compact")),
    ]

    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(lambda item: repository.save(*item), overrides))

    saved = repository.list().appearances
    assert saved == {tool_id: appearance for tool_id, appearance in overrides}


def test_write_failure_returns_error_and_preserves_old_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_client(tmp_path)
    old = {"schema_version": 1, "appearances": {"codex-cli": {"accent_color": "#123456"}}}
    path = tmp_path / "appearances.json"
    path.write_text(json.dumps(old), encoding="utf-8")

    def fail_write(_path: Path, _payload: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(appearances_repository_module, "write_json_atomic", fail_write)
    response = client.put("/api/appearances/claude-code", json={"accent_color": "#ABCDEF"})

    assert response.status_code == 500
    assert response.json()["code"] == "APPEARANCE_WRITE_FAILED"
    assert json.loads(path.read_text(encoding="utf-8")) == old


def test_lock_timeout_is_a_visible_service_error(tmp_path: Path) -> None:
    repository = AppearanceRepository(tmp_path, lock_timeout=0)
    lock_path = tmp_path / "locks" / "appearances.lock"
    lock = appearances_repository_module.FileLock(lock_path)
    lock.acquire()
    try:
        with pytest.raises(AppError) as error:
            repository.save("claude-code", AppearanceOverride(accent_color="#123456"))
    finally:
        lock.release()

    assert error.value.code == "APPEARANCE_LOCK_TIMEOUT"
