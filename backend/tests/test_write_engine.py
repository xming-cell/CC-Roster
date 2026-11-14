"""写引擎的原子性、冲突、回读校验与还原契约。

全部走真实文件系统; 只 monkeypatch 写入 / 回读边界模拟磁盘故障。
"""

import hashlib
import os
import stat
from pathlib import Path

import pytest
from pydantic import ValidationError
from snapshot_fixtures import (
    make_audit,
    make_plan,
    make_repository,
    make_write_engine,
    planned_file,
)

import app.services.write_engine as write_engine_module
from app.core.atomic import write_bytes_atomic
from app.core.errors import AppError, WriteConflict
from app.core.file_observation import observe_file
from app.core.locks import FileLock
from app.repositories.audit import AuditRepository
from app.schemas.snapshot import FileObservation, SnapshotChange
from app.schemas.write import PlannedFile, WritePlan


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def save_file(path: Path, data: bytes) -> FileObservation:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return observe_file(path)


def test_apply_writes_files_and_records_snapshot_and_audit(tmp_path: Path) -> None:
    engine = make_write_engine(tmp_path)
    existing = tmp_path / "config.json"
    created = tmp_path / "new" / "extra.toml"
    existing_observation = save_file(existing, b"old-content")
    change = SnapshotChange(
        path=str(existing.resolve()),
        field="api_key",
        action="set",
        before=None,
        after="****",
    )
    plan = make_plan(
        [
            planned_file(
                existing,
                b"new-content",
                observation=existing_observation,
                changes=[change],
            ),
            planned_file(created, b"brand-new"),
        ]
    )

    result = engine.apply(plan)

    assert existing.read_bytes() == b"new-content"
    assert created.read_bytes() == b"brand-new"
    assert [file.path for file in result.files] == sorted(
        [str(existing.resolve()), str(created.resolve())]
    )
    assert {file.action for file in result.files} == {"created", "updated"}
    assert result.files[0].sha256 == sha256(b"new-content")
    assert result.files[1].size == len(b"brand-new")

    repository = make_repository(tmp_path)
    snapshot = repository.get(result.snapshot_id)
    assert snapshot is not None
    assert snapshot.reason == "apply"
    assert snapshot.changes == [change]
    snapshots = {file.path: file for file in snapshot.files}
    assert snapshots[str(existing.resolve())].existed is True
    assert snapshots[str(created.resolve())].existed is False
    assert (
        repository.load_file_bytes(snapshot, snapshots[str(existing.resolve())]) == b"old-content"
    )

    entries = make_audit(tmp_path).list_recent()
    assert [entry.id for entry in entries] == [result.audit_id]
    assert entries[0].action == "apply"
    assert entries[0].result == "success"
    assert entries[0].snapshot_id == result.snapshot_id
    assert entries[0].files == [file.path for file in result.files]
    assert entries[0].fields == [f"{existing.resolve()}.api_key"]


def test_apply_conflict_writes_nothing_and_audits_conflict(tmp_path: Path) -> None:
    engine = make_write_engine(tmp_path)
    target = tmp_path / "config.json"
    observation = save_file(target, b"original")
    target.write_bytes(b"external-change")

    with pytest.raises(WriteConflict) as excinfo:
        engine.apply(make_plan([planned_file(target, b"expected", observation=observation)]))

    assert excinfo.value.conflicts[0].reason == "CONTENT_CHANGED"
    assert target.read_bytes() == b"external-change"
    assert make_repository(tmp_path).list_snapshots().snapshots == []
    entries = make_audit(tmp_path).list_recent()
    assert entries[0].result == "conflict"
    assert entries[0].snapshot_id is None


@pytest.mark.parametrize(
    ("starting", "final", "reason"),
    [(b"present", None, "MISSING"), (None, b"present", "CREATED")],
)
def test_apply_detects_missing_and_created_files(
    tmp_path: Path,
    starting: bytes | None,
    final: bytes | None,
    reason: str,
) -> None:
    engine = make_write_engine(tmp_path)
    target = tmp_path / "config.json"
    observation = save_file(target, starting) if starting is not None else observe_file(target)
    if final is not None:
        target.write_bytes(final)
    elif target.exists():
        target.unlink()

    with pytest.raises(WriteConflict) as excinfo:
        engine.apply(make_plan([planned_file(target, b"expected", observation=observation)]))

    assert excinfo.value.conflicts[0].reason == reason
    if final is None:
        assert not target.exists()
    else:
        assert target.read_bytes() == final


def test_apply_allows_mtime_only_change(tmp_path: Path) -> None:
    engine = make_write_engine(tmp_path)
    target = tmp_path / "config.json"
    observation = save_file(target, b"same-content")
    os.utime(
        target,
        ns=(observation.mtime_ns or 0, (observation.mtime_ns or 0) + 1_000_000_000),
    )

    result = engine.apply(make_plan([planned_file(target, b"updated", observation=observation)]))

    assert result.snapshot_id
    assert target.read_bytes() == b"updated"


def test_apply_restores_first_file_when_second_write_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = make_write_engine(tmp_path)
    first = tmp_path / "a.json"
    second = tmp_path / "b.json"
    first_observation = save_file(first, b"first-old")
    second_observation = save_file(second, b"second-old")

    def flaky_write(path: Path, data: bytes, *, mode: int | None = None) -> None:
        if path.name == "b.json":
            raise OSError("disk full")
        write_bytes_atomic(path, data, mode=mode)

    monkeypatch.setattr(write_engine_module, "write_bytes_atomic", flaky_write)

    with pytest.raises(AppError) as excinfo:
        engine.apply(
            make_plan(
                [
                    planned_file(first, b"first-new", observation=first_observation),
                    planned_file(second, b"second-new", observation=second_observation),
                ]
            )
        )

    assert excinfo.value.code == "WRITE_FAILED"
    assert first.read_bytes() == b"first-old"
    assert second.read_bytes() == b"second-old"
    assert list(tmp_path.glob(".*.tmp")) == []


def test_apply_readback_mismatch_restores_every_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = make_write_engine(tmp_path)
    first = tmp_path / "a.json"
    second = tmp_path / "b.json"
    first_observation = save_file(first, b"first-old")
    second_observation = save_file(second, b"second-old")
    real_read = write_engine_module.read_written_bytes
    calls = {"count": 0}

    def corrupted_read(path: Path) -> bytes:
        data = real_read(path)
        calls["count"] += 1
        if calls["count"] == 2:
            return data + b"!"
        return data

    monkeypatch.setattr(write_engine_module, "read_written_bytes", corrupted_read)

    with pytest.raises(AppError) as excinfo:
        engine.apply(
            make_plan(
                [
                    planned_file(first, b"first-new", observation=first_observation),
                    planned_file(second, b"second-new", observation=second_observation),
                ]
            )
        )

    assert excinfo.value.code == "WRITE_VERIFY_FAILED"
    assert sha256(b"second-new") in excinfo.value.message
    assert first.read_bytes() == b"first-old"
    assert second.read_bytes() == b"second-old"

    entries = make_audit(tmp_path).list_recent()
    assert entries[0].result == "failed"


def test_apply_restore_failure_reports_restore_failed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = make_write_engine(tmp_path)
    first = tmp_path / "a.json"
    second = tmp_path / "b.json"
    first_observation = save_file(first, b"first-old")
    second_observation = save_file(second, b"second-old")
    real_read = write_engine_module.read_written_bytes
    read_calls = {"count": 0}

    def corrupted_read(path: Path) -> bytes:
        data = real_read(path)
        read_calls["count"] += 1
        if read_calls["count"] == 1:
            return data + b"!"
        return data

    write_calls = {"count": 0}

    def failing_restore_write(path: Path, data: bytes, *, mode: int | None = None) -> None:
        write_calls["count"] += 1
        if write_calls["count"] > 2:
            raise OSError("disk full")
        write_bytes_atomic(path, data, mode=mode)

    monkeypatch.setattr(write_engine_module, "read_written_bytes", corrupted_read)
    monkeypatch.setattr(write_engine_module, "write_bytes_atomic", failing_restore_write)

    with pytest.raises(AppError) as excinfo:
        engine.apply(
            make_plan(
                [
                    planned_file(first, b"first-new", observation=first_observation),
                    planned_file(second, b"second-new", observation=second_observation),
                ]
            )
        )

    assert excinfo.value.code == "WRITE_RESTORE_FAILED"
    assert sha256(b"first-old") in excinfo.value.message
    assert sha256(b"first-new") in excinfo.value.message


def test_apply_audit_failure_restores_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = make_write_engine(tmp_path)
    target = tmp_path / "config.json"
    observation = save_file(target, b"old")

    def fail_record(self: AuditRepository, **kwargs: object) -> object:
        raise AppError("AUDIT_WRITE_FAILED", "database is locked", 500)

    monkeypatch.setattr(AuditRepository, "record", fail_record)

    with pytest.raises(AppError) as excinfo:
        engine.apply(make_plan([planned_file(target, b"new", observation=observation)]))

    assert excinfo.value.code == "AUDIT_WRITE_FAILED"
    assert target.read_bytes() == b"old"
    assert make_repository(tmp_path).list_snapshots().snapshots != []


def test_apply_snapshot_failure_writes_nothing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = make_write_engine(tmp_path)
    target = tmp_path / "config.json"
    observation = save_file(target, b"old")

    def fail_meta(_path: Path, _data: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("app.repositories.snapshots.write_json_atomic", fail_meta)

    with pytest.raises(AppError) as excinfo:
        engine.apply(make_plan([planned_file(target, b"new", observation=observation)]))

    assert excinfo.value.code == "SNAPSHOT_WRITE_FAILED"
    assert target.read_bytes() == b"old"


def test_apply_lock_timeout_reports_503(tmp_path: Path) -> None:
    engine = make_write_engine(tmp_path, lock_timeout=0.05)
    target = tmp_path / "config.json"
    observation = save_file(target, b"old")

    with (
        FileLock(tmp_path / "locks" / "write.lock", timeout=1.0),
        pytest.raises(AppError) as excinfo,
    ):
        engine.apply(make_plan([planned_file(target, b"new", observation=observation)]))

    assert excinfo.value.code == "WRITE_LOCK_TIMEOUT"
    assert excinfo.value.status_code == 503
    assert target.read_bytes() == b"old"


def test_second_apply_with_stale_observation_conflicts(tmp_path: Path) -> None:
    engine = make_write_engine(tmp_path)
    target = tmp_path / "config.json"
    observation = save_file(target, b"v0")

    engine.apply(make_plan([planned_file(target, b"v1", observation=observation)]))
    with pytest.raises(WriteConflict):
        engine.apply(make_plan([planned_file(target, b"v2", observation=observation)]))

    assert target.read_bytes() == b"v1"


def test_apply_restores_original_mode_on_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if os.name == "nt":
        return
    engine = make_write_engine(tmp_path)
    target = tmp_path / "config.json"
    observation = save_file(target, b"old")
    target.chmod(0o640)

    def fail_write(_path: Path, _data: bytes, *, mode: int | None = None) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(write_engine_module, "write_bytes_atomic", fail_write)

    with pytest.raises(AppError):
        engine.apply(make_plan([planned_file(target, b"new", observation=observation)]))

    assert stat.S_IMODE(target.stat().st_mode) == 0o640


def test_write_plan_rejects_duplicate_and_non_canonical_paths(tmp_path: Path) -> None:
    target = tmp_path / "config.json"
    observation = save_file(target, b"data")
    file = planned_file(target, b"new", observation=observation)

    with pytest.raises(ValidationError):
        WritePlan(tool_id="claude-code", files=[file, file])

    with pytest.raises(ValidationError):
        PlannedFile(
            path="relative.json",
            expected_bytes=b"data",
            observation=FileObservation(
                path=str(target.resolve()),
                exists=False,
                sha256=None,
                size=0,
                mtime_ns=None,
            ),
        )

    with pytest.raises(ValidationError):
        PlannedFile(
            path=str(target.resolve()),
            expected_bytes=b"data",
            observation=FileObservation(
                path=str((tmp_path / "other.json").resolve()),
                exists=False,
                sha256=None,
                size=0,
                mtime_ns=None,
            ),
        )
