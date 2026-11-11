"""008 T5: 审计列表 API 的过滤、分页边界、排序与脱敏。"""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.audit import get_audit_service
from app.core.errors import AppError
from app.main import create_app
from app.repositories.audit import AuditRepository
from app.services.audit_service import AuditService

NOW = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)
SECRET = "sk-live-abcdefghijklmnop"


class IncrementingClock:
    def __init__(self) -> None:
        self._value = NOW

    def __call__(self) -> datetime:
        self._value += timedelta(milliseconds=1)
        return self._value


def make_client(tmp_path: Path) -> tuple[TestClient, AuditRepository]:
    audit = AuditRepository(tmp_path / "db" / "app.sqlite3")
    app = create_app()
    app.dependency_overrides[get_audit_service] = lambda: AuditService(audit)
    return TestClient(app), audit


def record(
    audit: AuditRepository,
    *,
    tool_id: str = "claude-code",
    result: str = "success",
    action: str = "apply",
    message: str = "应用成功",
    profile_id: str | None = "profile-1",
    snapshot_id: str | None = "snapshot-1",
    files: list[str] | None = None,
    fields: list[str] | None = None,
) -> str:
    entry = audit.record(
        action=action,
        tool_id=tool_id,
        profile_id=profile_id,
        snapshot_id=snapshot_id,
        files=files if files is not None else ["/tmp/settings.json"],
        fields=fields if fields is not None else ["env.ANTHROPIC_BASE_URL"],
        result=result,
        message=message,
    )
    return entry.id


def test_empty_database_returns_empty_entries(tmp_path: Path) -> None:
    client, _audit = make_client(tmp_path)

    response = client.get("/api/audit")

    assert response.status_code == 200
    assert response.json() == {"entries": []}


def test_list_returns_success_failed_and_conflict_entries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.repositories.audit.utc_now", IncrementingClock())
    client, audit = make_client(tmp_path)
    success_id = record(audit, result="success", message="应用成功")
    failed_id = record(
        audit,
        result="failed",
        message="绑定保存失败",
        snapshot_id="snapshot-2",
    )
    conflict_id = record(
        audit,
        result="conflict",
        message="文件在预览后发生变化",
        snapshot_id=None,
        action="apply",
    )

    response = client.get("/api/audit")

    assert response.status_code == 200
    entries = response.json()["entries"]
    assert [entry["id"] for entry in entries] == [
        conflict_id,
        failed_id,
        success_id,
    ]
    assert [entry["result"] for entry in entries] == [
        "conflict",
        "failed",
        "success",
    ]
    assert entries[0]["snapshot_id"] is None
    assert entries[1]["snapshot_id"] == "snapshot-2"
    assert entries[2]["profile_id"] == "profile-1"
    assert entries[2]["action"] == "apply"
    assert entries[2]["files"] == ["/tmp/settings.json"]
    assert entries[2]["fields"] == ["env.ANTHROPIC_BASE_URL"]
    assert entries[2]["created_at"] == "2026-11-11T12:00:00.001000Z"


def test_tool_filter_returns_only_matching_entries(tmp_path: Path) -> None:
    client, audit = make_client(tmp_path)
    claude_id = record(audit, tool_id="claude-code")
    codex_id = record(audit, tool_id="codex-cli", action="rollback")
    record(audit, tool_id="claude-code", result="conflict")

    response = client.get("/api/audit", params={"tool_id": "codex-cli"})

    assert response.status_code == 200
    entries = response.json()["entries"]
    assert [entry["id"] for entry in entries] == [codex_id]
    assert entries[0]["tool_id"] == "codex-cli"
    assert entries[0]["action"] == "rollback"
    assert claude_id not in [entry["id"] for entry in entries]

    unknown = client.get("/api/audit", params={"tool_id": "unknown-tool"})
    assert unknown.status_code == 200
    assert unknown.json() == {"entries": []}


def test_default_limit_is_fifty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.repositories.audit.utc_now", IncrementingClock())
    client, audit = make_client(tmp_path)
    ids = [record(audit, message=f"第 {index} 次") for index in range(51)]

    response = client.get("/api/audit")

    assert response.status_code == 200
    entries = response.json()["entries"]
    assert len(entries) == 50
    assert entries[0]["id"] == ids[-1]
    assert entries[-1]["id"] == ids[1]
    assert ids[0] not in [entry["id"] for entry in entries]


@pytest.mark.parametrize(("limit", "expected"), [(1, 1), (2, 2), (200, 3)])
def test_limit_accepts_valid_range(
    tmp_path: Path,
    limit: int,
    expected: int,
) -> None:
    client, audit = make_client(tmp_path)
    for index in range(3):
        record(audit, message=f"第 {index} 次")

    response = client.get("/api/audit", params={"limit": limit})

    assert response.status_code == 200
    assert len(response.json()["entries"]) == expected


@pytest.mark.parametrize("limit", [0, -1, 201, "abc"])
def test_limit_outside_range_is_validation_error(
    tmp_path: Path,
    limit: object,
) -> None:
    client, _audit = make_client(tmp_path)

    response = client.get("/api/audit", params={"limit": limit})

    assert response.status_code == 422
    body = response.json()
    assert set(body) == {"code", "message"}
    assert body["code"] == "VALIDATION_ERROR"


def test_unreadable_database_returns_readable_500(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, audit = make_client(tmp_path)

    def fail_list_recent(**_kwargs: object) -> object:
        raise AppError("AUDIT_UNREADABLE", "审计记录读取失败", 500)

    monkeypatch.setattr(audit, "list_recent", fail_list_recent)

    response = client.get("/api/audit")

    assert response.status_code == 500
    assert response.json() == {
        "code": "AUDIT_UNREADABLE",
        "message": "审计记录读取失败",
    }


def test_response_is_redacted(tmp_path: Path) -> None:
    client, audit = make_client(tmp_path)
    record(
        audit,
        message=f"密钥 {SECRET} 写入失败",
        files=[f"/tmp/{SECRET}/settings.json"],
        fields=[f"env.{SECRET}"],
    )

    response = client.get("/api/audit")

    assert response.status_code == 200
    assert SECRET not in response.text
    entries = response.json()["entries"]
    assert len(entries) == 1
    assert "sk-l****mnop" in entries[0]["message"]
    assert all(SECRET not in item for item in entries[0]["files"])
    assert all(SECRET not in item for item in entries[0]["fields"])
