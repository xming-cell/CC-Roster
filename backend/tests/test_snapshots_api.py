"""快照 API 与回滚的集成契约。

全部通过 TestClient 走真实路由; 快照用仓储直接构造 (007 不暴露创建端点),
回滚断言目标文件逐字节一致、预回滚快照可再次恢复、失败时全部还原。
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path

import pytest
from snapshot_fixtures import (
    at,
    capture_one,
    file_source,
    make_snapshot_harness,
    missing_source,
    object_path,
)

import app.services.snapshot_service as snapshot_service_module
from app.core.atomic import write_bytes_atomic
from app.core.errors import AppError
from app.repositories.audit import AuditRepository
from app.repositories.snapshots import SnapshotRepository
from app.schemas.snapshot import Snapshot


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def meta_path(repository: SnapshotRepository, snapshot_id: str) -> Path:
    return repository.root / snapshot_id / "meta.json"


def capture_missing(
    repository: SnapshotRepository,
    path: Path,
    *,
    tool_id: str = "claude-code",
) -> Snapshot:
    return repository.capture(
        tool_id=tool_id,
        files=[missing_source(path)],
        reason="apply",
    )


def test_list_empty_returns_empty_and_does_not_create_directories(tmp_path: Path) -> None:
    data_dir = tmp_path / "CC-Roster"
    harness = make_snapshot_harness(data_dir)

    response = harness.client.get("/api/snapshots")

    assert response.status_code == 200
    assert response.json() == {"snapshots": [], "retention_limit": 20, "warnings": []}
    assert not data_dir.exists()


def test_list_is_newest_first_filters_and_limits(tmp_path: Path) -> None:
    harness = make_snapshot_harness(tmp_path)
    oldest = capture_one(
        harness.repository,
        tmp_path / "one.json",
        b"one",
        tool_id="tool-a",
        created_at=at(0),
    )
    middle = capture_one(
        harness.repository,
        tmp_path / "two.json",
        b"two",
        tool_id="tool-b",
        created_at=at(1),
    )
    newest = capture_one(
        harness.repository,
        tmp_path / "three.json",
        b"three",
        tool_id="tool-a",
        created_at=at(2),
    )

    all_items = harness.client.get("/api/snapshots").json()
    filtered = harness.client.get("/api/snapshots", params={"tool_id": "tool-a"}).json()
    limited = harness.client.get("/api/snapshots", params={"limit": 1}).json()
    unknown = harness.client.get("/api/snapshots", params={"tool_id": "nope"}).json()

    assert [item["id"] for item in all_items["snapshots"]] == [
        newest.id,
        middle.id,
        oldest.id,
    ]
    assert [item["id"] for item in filtered["snapshots"]] == [newest.id, oldest.id]
    assert [item["id"] for item in limited["snapshots"]] == [newest.id]
    assert unknown["snapshots"] == []
    assert all_items["retention_limit"] == 20
    assert "chunks" not in json.dumps(all_items)


@pytest.mark.parametrize("limit", ["0", "201", "-1", "abc"])
def test_list_rejects_invalid_limit(tmp_path: Path, limit: str) -> None:
    harness = make_snapshot_harness(tmp_path)

    response = harness.client.get("/api/snapshots", params={"limit": limit})

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_get_returns_view_without_content(tmp_path: Path) -> None:
    harness = make_snapshot_harness(tmp_path)
    secret = "sk-snapshot-secret-value"
    target = tmp_path / "config.json"
    snapshot = capture_one(harness.repository, target, f'{{"api_key": "{secret}"}}'.encode())

    response = harness.client.get(f"/api/snapshots/{snapshot.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == snapshot.id
    assert body["tool_id"] == "claude-code"
    assert body["reason"] == "apply"
    assert body["files"][0]["sha256"] == sha256(target.read_bytes())
    assert "chunks" not in body["files"][0]
    assert secret not in response.text


def test_get_unknown_and_invalid_ids(tmp_path: Path) -> None:
    harness = make_snapshot_harness(tmp_path)

    missing = harness.client.get("/api/snapshots/00000000-0000-4000-8000-000000000000")
    invalid = harness.client.get("/api/snapshots/not-a-uuid")

    assert missing.status_code == 404
    assert missing.json()["code"] == "SNAPSHOT_NOT_FOUND"
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "VALIDATION_ERROR"


def test_get_corrupt_snapshot_is_unreadable(tmp_path: Path) -> None:
    harness = make_snapshot_harness(tmp_path)
    snapshot = capture_one(harness.repository, tmp_path / "config.json", b"data")
    meta_path(harness.repository, snapshot.id).write_text("{", encoding="utf-8")

    response = harness.client.get(f"/api/snapshots/{snapshot.id}")

    assert response.status_code == 500
    assert response.json()["code"] == "SNAPSHOT_UNREADABLE"


def test_get_tampered_chunk_is_unreadable(tmp_path: Path) -> None:
    harness = make_snapshot_harness(tmp_path)
    snapshot = capture_one(harness.repository, tmp_path / "config.json", b"abcdefgh")
    object_path(harness.repository, snapshot.files[0].chunks[0]).write_bytes(b"bad")

    response = harness.client.get(f"/api/snapshots/{snapshot.id}")

    assert response.status_code == 500
    assert response.json()["code"] == "SNAPSHOT_UNREADABLE"


def test_patch_pin_is_idempotent_and_keeps_created_at(tmp_path: Path) -> None:
    harness = make_snapshot_harness(tmp_path)
    snapshot = capture_one(harness.repository, tmp_path / "config.json", b"data")

    first = harness.client.patch(f"/api/snapshots/{snapshot.id}", json={"pinned": True})
    second = harness.client.patch(f"/api/snapshots/{snapshot.id}", json={"pinned": True})
    unpinned = harness.client.patch(f"/api/snapshots/{snapshot.id}", json={"pinned": False})

    assert first.status_code == second.status_code == unpinned.status_code == 200
    assert first.json()["pinned"] is True
    assert second.json()["pinned"] is True
    assert unpinned.json()["pinned"] is False
    created_at = datetime.fromisoformat(first.json()["created_at"].replace("Z", "+00:00"))
    assert created_at == snapshot.created_at


def test_patch_unknown_and_invalid_body(tmp_path: Path) -> None:
    harness = make_snapshot_harness(tmp_path)

    missing = harness.client.patch(
        "/api/snapshots/00000000-0000-4000-8000-000000000000",
        json={"pinned": True},
    )
    invalid_uuid = harness.client.patch("/api/snapshots/not-a-uuid", json={"pinned": True})
    invalid_body = harness.client.patch(
        f"/api/snapshots/{capture_one(harness.repository, tmp_path / 'a.json', b'a').id}",
        json={"pinned": "yes"},
    )

    assert missing.status_code == 404
    assert invalid_uuid.status_code == 422
    assert invalid_body.status_code == 422
    assert invalid_body.json()["code"] == "VALIDATION_ERROR"


def test_rollback_restores_bytes_and_creates_pre_rollback_snapshot(tmp_path: Path) -> None:
    harness = make_snapshot_harness(tmp_path)
    target = tmp_path / "config.json"
    secret = "sk-rollback-secret-value"
    original = f'﻿{{"api_key": "{secret}"}}\r\n'.encode()
    snapshot = capture_one(harness.repository, target, original)
    modified = b'{"api_key": "new"}'
    target.write_bytes(modified)

    response = harness.client.post(f"/api/snapshots/{snapshot.id}/rollback")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["snapshot_id"] == snapshot.id
    assert body["files"][0]["path"] == str(target.resolve())
    assert body["files"][0]["action"] == "restored"
    assert body["files"][0]["sha256"] == sha256(original)
    assert target.read_bytes() == original
    assert secret not in response.text

    pre = harness.repository.get(body["pre_rollback_snapshot_id"])
    assert pre is not None
    assert pre.reason == "rollback"
    assert harness.repository.load_file_bytes(pre, pre.files[0]) == modified
    assert harness.repository.get(snapshot.id) is not None

    entries = harness.audit.list_recent()
    assert entries[0].action == "rollback"
    assert entries[0].result == "success"
    assert entries[0].snapshot_id == snapshot.id


def test_rollback_deletes_file_that_did_not_exist_at_capture(tmp_path: Path) -> None:
    harness = make_snapshot_harness(tmp_path)
    target = tmp_path / "new.json"
    snapshot = capture_missing(harness.repository, target)
    target.write_bytes(b"created later")

    response = harness.client.post(f"/api/snapshots/{snapshot.id}/rollback")

    assert response.status_code == 200
    assert response.json()["files"][0]["action"] == "deleted"
    assert response.json()["files"][0]["sha256"] is None
    assert not target.exists()


def test_rollback_restores_empty_file(tmp_path: Path) -> None:
    harness = make_snapshot_harness(tmp_path)
    target = tmp_path / "empty.json"
    snapshot = capture_one(harness.repository, target, b"")
    target.write_bytes(b"not empty")

    response = harness.client.post(f"/api/snapshots/{snapshot.id}/rollback")

    assert response.status_code == 200
    assert response.json()["files"][0]["action"] == "restored"
    assert target.read_bytes() == b""


def test_rollback_is_repeatable_and_second_run_is_unchanged(tmp_path: Path) -> None:
    harness = make_snapshot_harness(tmp_path)
    target = tmp_path / "config.json"
    snapshot = capture_one(harness.repository, target, b"original")
    target.write_bytes(b"modified")

    first = harness.client.post(f"/api/snapshots/{snapshot.id}/rollback").json()
    second = harness.client.post(f"/api/snapshots/{snapshot.id}/rollback").json()

    assert first["pre_rollback_snapshot_id"] != second["pre_rollback_snapshot_id"]
    assert second["files"][0]["action"] == "unchanged"
    assert target.read_bytes() == b"original"
    assert harness.repository.get(second["pre_rollback_snapshot_id"]) is not None


def test_rollback_handles_multiple_files(tmp_path: Path) -> None:
    harness = make_snapshot_harness(tmp_path)
    existing = tmp_path / "a.json"
    missing = tmp_path / "b.json"
    combined = harness.repository.capture(
        tool_id="claude-code",
        files=[file_source(existing, b"old-a"), missing_source(missing)],
        reason="apply",
    )
    existing.write_bytes(b"new-a")
    missing.write_bytes(b"new-b")

    response = harness.client.post(f"/api/snapshots/{combined.id}/rollback")

    assert response.status_code == 200
    assert existing.read_bytes() == b"old-a"
    assert not missing.exists()
    actions = {file["path"]: file["action"] for file in response.json()["files"]}
    assert actions[str(existing.resolve())] == "restored"
    assert actions[str(missing.resolve())] == "deleted"


def test_rollback_corrupt_snapshot_writes_nothing(tmp_path: Path) -> None:
    harness = make_snapshot_harness(tmp_path)
    target = tmp_path / "config.json"
    snapshot = capture_one(harness.repository, target, b"old")
    target.write_bytes(b"current")
    object_path(harness.repository, snapshot.files[0].chunks[0]).write_bytes(b"bad")

    response = harness.client.post(f"/api/snapshots/{snapshot.id}/rollback")

    assert response.status_code == 500
    assert response.json()["code"] == "SNAPSHOT_UNREADABLE"
    assert target.read_bytes() == b"current"


def test_rollback_restore_failure_restores_pre_rollback_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = make_snapshot_harness(tmp_path)
    target = tmp_path / "config.json"
    snapshot = capture_one(harness.repository, target, b"old")
    target.write_bytes(b"current")
    calls = {"count": 0}

    def flaky_write(path: Path, data: bytes, *, mode: int | None = None) -> None:
        calls["count"] += 1
        if calls["count"] == 1:
            raise OSError("disk full")
        write_bytes_atomic(path, data, mode=mode)

    monkeypatch.setattr(snapshot_service_module, "write_bytes_atomic", flaky_write)

    response = harness.client.post(f"/api/snapshots/{snapshot.id}/rollback")

    assert response.status_code == 500
    assert response.json()["code"] == "ROLLBACK_FAILED"
    assert target.read_bytes() == b"current"


def test_rollback_second_file_failure_restores_every_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = make_snapshot_harness(tmp_path)
    first = tmp_path / "a.json"
    second = tmp_path / "b.json"
    snapshot = harness.repository.capture(
        tool_id="claude-code",
        files=[file_source(first, b"old-a"), file_source(second, b"old-b")],
        reason="apply",
    )
    first.write_bytes(b"current-a")
    second.write_bytes(b"current-b")
    failed = {"done": False}

    def flaky_write(path: Path, data: bytes, *, mode: int | None = None) -> None:
        if path.name == "b.json" and not failed["done"]:
            failed["done"] = True
            raise OSError("disk full")
        write_bytes_atomic(path, data, mode=mode)

    monkeypatch.setattr(snapshot_service_module, "write_bytes_atomic", flaky_write)

    response = harness.client.post(f"/api/snapshots/{snapshot.id}/rollback")

    assert response.status_code == 500
    assert response.json()["code"] == "ROLLBACK_FAILED"
    assert first.read_bytes() == b"current-a"
    assert second.read_bytes() == b"current-b"


def test_rollback_audit_failure_restores_pre_rollback_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = make_snapshot_harness(tmp_path)
    target = tmp_path / "config.json"
    snapshot = capture_one(harness.repository, target, b"old")
    target.write_bytes(b"current")

    def fail_record(self: AuditRepository, **kwargs: object) -> object:
        raise AppError("AUDIT_WRITE_FAILED", "database is locked", 500)

    monkeypatch.setattr(AuditRepository, "record", fail_record)

    response = harness.client.post(f"/api/snapshots/{snapshot.id}/rollback")

    assert response.status_code == 500
    assert response.json()["code"] == "AUDIT_WRITE_FAILED"
    assert target.read_bytes() == b"current"


def test_rollback_retention_does_not_delete_target(tmp_path: Path) -> None:
    harness = make_snapshot_harness(tmp_path, retention_limit=1)
    target = tmp_path / "config.json"
    snapshot = capture_one(harness.repository, target, b"old")
    target.write_bytes(b"current")

    response = harness.client.post(f"/api/snapshots/{snapshot.id}/rollback")

    assert response.status_code == 200
    pre_id = response.json()["pre_rollback_snapshot_id"]
    assert harness.repository.get(snapshot.id) is not None
    assert harness.repository.get(pre_id) is not None


def test_list_skips_corrupt_snapshot_with_warning(tmp_path: Path) -> None:
    harness = make_snapshot_harness(tmp_path)
    valid = capture_one(harness.repository, tmp_path / "config.json", b"data")
    bad_id = "11111111-1111-4111-8111-111111111111"
    bad_dir = harness.repository.root / bad_id
    bad_dir.mkdir(parents=True)
    (bad_dir / "meta.json").write_text("{", encoding="utf-8")

    response = harness.client.get("/api/snapshots")

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body["snapshots"]] == [valid.id]
    assert body["warnings"][0]["code"] == "SNAPSHOT_UNREADABLE"


def test_pin_then_rollback_keeps_pinned_snapshot(tmp_path: Path) -> None:
    harness = make_snapshot_harness(tmp_path, retention_limit=1)
    target = tmp_path / "config.json"
    snapshot = capture_one(harness.repository, target, b"old")
    harness.client.patch(f"/api/snapshots/{snapshot.id}", json={"pinned": True})
    target.write_bytes(b"current")

    response = harness.client.post(f"/api/snapshots/{snapshot.id}/rollback")

    assert response.status_code == 200
    pinned = harness.repository.get(snapshot.id)
    assert pinned is not None
    assert pinned.pinned is True
    assert target.read_bytes() == b"old"


def test_rollback_unknown_snapshot(tmp_path: Path) -> None:
    harness = make_snapshot_harness(tmp_path)

    response = harness.client.post("/api/snapshots/00000000-0000-4000-8000-000000000000/rollback")

    assert response.status_code == 404
    assert response.json()["code"] == "SNAPSHOT_NOT_FOUND"
