"""审计迁移、仓储与脱敏契约。

审计表必须随 `initialize_app_data` 自动创建, 删除数据库后能重建; 数据库里只存
脱敏后的展示摘要, 任何 fixture 明文密钥都不能出现。
"""

import sqlite3
from pathlib import Path

import pytest
from snapshot_fixtures import (
    make_audit,
    make_plan,
    make_repository,
    make_write_engine,
    planned_file,
)

from app.core.errors import AppError
from app.core.file_observation import observe_file
from app.main import initialize_app_data
from app.repositories.audit import AuditRepository
from app.schemas.snapshot import SnapshotChange
from app.services.snapshot_service import SnapshotService


def table_names(db_path: Path) -> set[str]:
    connection = sqlite3.connect(db_path)
    try:
        rows = connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    finally:
        connection.close()
    return {str(row[0]) for row in rows}


def test_initialize_app_data_applies_audit_migration(tmp_path: Path) -> None:
    data_dir = initialize_app_data(tmp_path / "CC-Roster")
    db_path = data_dir / "db" / "app.sqlite3"

    connection = sqlite3.connect(db_path)
    try:
        assert connection.execute("PRAGMA user_version").fetchone() == (1,)
        indexes = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            ).fetchall()
        }
    finally:
        connection.close()

    assert "audit_entries" in table_names(db_path)
    assert "idx_audit_entries_created_at" in indexes


def test_initialize_app_data_is_idempotent_with_migration(tmp_path: Path) -> None:
    first = initialize_app_data(tmp_path / "CC-Roster")
    second = initialize_app_data(tmp_path / "CC-Roster")

    assert first == second
    assert table_names(second / "db" / "app.sqlite3") == {"audit_entries"}


def test_deleting_database_rebuilds_audit_table(tmp_path: Path) -> None:
    data_dir = initialize_app_data(tmp_path / "CC-Roster")
    db_path = data_dir / "db" / "app.sqlite3"
    make_audit(data_dir).record(
        action="apply",
        tool_id="claude-code",
        profile_id=None,
        snapshot_id=None,
        files=[],
        fields=[],
        result="success",
        message="before delete",
    )

    db_path.unlink()
    initialize_app_data(data_dir)

    assert table_names(db_path) == {"audit_entries"}
    assert make_audit(data_dir).list_recent() == []


def test_audit_record_and_list_recent_roundtrip(tmp_path: Path) -> None:
    repository = make_audit(tmp_path)
    for index, tool_id in enumerate(["tool-a", "tool-b", "tool-a"]):
        entry = repository.record(
            action="apply",
            tool_id=tool_id,
            profile_id=f"profile-{index}" if index == 0 else None,
            snapshot_id=f"snapshot-{index}",
            files=[f"/tmp/file-{index}.json"],
            fields=[f"/tmp/file-{index}.json.model"],
            result="success",
            message=f"entry {index}",
        )
        assert entry.created_at.utcoffset() is not None
        assert entry.message == f"entry {index}"
        assert entry.files == [f"/tmp/file-{index}.json"]

    all_entries = repository.list_recent()
    filtered = repository.list_recent(tool_id="tool-a")
    limited = repository.list_recent(limit=2)

    assert len(all_entries) == 3
    assert {entry.tool_id for entry in all_entries} == {"tool-a", "tool-b"}
    assert [entry.tool_id for entry in filtered] == ["tool-a", "tool-a"]
    assert len(limited) == 2
    for entry in filtered:
        assert entry.action == "apply"
        assert entry.result == "success"


def test_audit_rejects_non_positive_limit(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        make_audit(tmp_path).list_recent(limit=0)


def test_audit_redacts_secret_in_message_files_and_fields(tmp_path: Path) -> None:
    secret = "sk-" + "a" * 32
    repository = make_audit(tmp_path)

    repository.record(
        action="apply",
        tool_id="claude-code",
        profile_id=None,
        snapshot_id=None,
        files=[f"/tmp/{secret}.json"],
        fields=[f"/tmp/{secret}.json.api_key"],
        result="failed",
        message=f"failed with Bearer {secret}",
    )

    connection = sqlite3.connect(tmp_path / "db" / "app.sqlite3")
    try:
        rows = connection.execute(
            "SELECT files_json, fields_json, message FROM audit_entries"
        ).fetchall()
    finally:
        connection.close()

    dumped = str(rows)
    assert secret not in dumped
    assert "****" in dumped


def test_audit_write_failure_reports_readable_error(tmp_path: Path) -> None:
    blocked = tmp_path / "db-file"
    blocked.write_text("not a directory", encoding="utf-8")
    repository = AuditRepository(blocked / "app.sqlite3")

    with pytest.raises(AppError) as excinfo:
        repository.record(
            action="apply",
            tool_id="claude-code",
            profile_id=None,
            snapshot_id=None,
            files=[],
            fields=[],
            result="failed",
            message="x",
        )

    assert excinfo.value.code == "AUDIT_WRITE_FAILED"
    assert excinfo.value.status_code == 500


def test_apply_and_rollback_audit_and_snapshot_meta_do_not_leak_secrets(
    tmp_path: Path,
) -> None:
    secret = "sk-" + "b" * 32
    target = tmp_path / "config.json"
    target.write_bytes(b"old")
    observation = observe_file(target)
    engine = make_write_engine(tmp_path)
    change = SnapshotChange(
        path=str(target.resolve()),
        field="api_key",
        action="set",
        before=None,
        after=f"Bearer {secret}",
    )

    result = engine.apply(
        make_plan(
            [
                planned_file(
                    target,
                    b"new",
                    observation=observation,
                    changes=[change],
                )
            ]
        )
    )
    repository = make_repository(tmp_path)
    service = SnapshotService(
        repository,
        make_audit(tmp_path),
        write_lock_path=tmp_path / "locks" / "write.lock",
    )
    service.rollback(result.snapshot_id)

    assert target.read_bytes() == b"old"
    db_path = tmp_path / "db" / "app.sqlite3"
    connection = sqlite3.connect(db_path)
    try:
        rows = connection.execute(
            "SELECT action, files_json, fields_json, message FROM audit_entries ORDER BY created_at"
        ).fetchall()
    finally:
        connection.close()
    assert [row[0] for row in rows] == ["apply", "rollback"]
    assert secret not in str(rows)

    meta_text = (repository.root / result.snapshot_id / "meta.json").read_text(encoding="utf-8")
    assert secret not in meta_text
    assert "****" in meta_text
