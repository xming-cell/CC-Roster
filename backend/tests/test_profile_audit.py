"""供应商 CRUD / 绑定审计契约。

ADR-013: 审计覆盖供应商新增、编辑、复制、删除与绑定 / 解绑; 不记录读取,
任何记录都不得包含密钥明文。供应商级操作没有工具上下文, `tool_id` 必须为 null。
"""

import sqlite3
from pathlib import Path

from profile_fixtures import create_profile, make_profile_harness
from tool_fixtures import claude_adapter, seed_claude

from app.repositories.audit import AuditRepository
from app.repositories.migrations import APP_MIGRATIONS
from app.schemas.audit import AuditEntry

SECRET = "sk-" + "p" * 32


def _entries(harness) -> list[dict[str, object]]:
    response = harness.client.get("/api/audit")
    assert response.status_code == 200, response.text
    return list(response.json()["entries"])


def test_profile_create_is_audited_without_tool_or_secret(tmp_path: Path) -> None:
    harness = make_profile_harness(tmp_path)

    created = create_profile(harness, name="审计供应商", secret=SECRET)

    entries = _entries(harness)
    assert [entry["action"] for entry in entries] == ["profile_create"]
    entry = entries[0]
    assert entry["tool_id"] is None
    assert entry["profile_id"] == created["id"]
    assert entry["result"] == "success"
    assert "审计供应商" in str(entry["message"])
    assert "name" in entry["fields"]
    assert SECRET not in str(entries)


def test_profile_update_audits_changed_fields_without_secret_value(tmp_path: Path) -> None:
    harness = make_profile_harness(tmp_path)
    created = create_profile(harness, name="改名前", secret=SECRET)

    response = harness.client.patch(
        f"/api/profiles/{created['id']}",
        json={"name": "改名后", "secret": SECRET},
    )
    assert response.status_code == 200, response.text

    entries = _entries(harness)
    actions = [entry["action"] for entry in entries]
    assert actions == ["profile_update", "profile_create"]
    update = entries[0]
    assert update["tool_id"] is None
    assert sorted(update["fields"]) == ["name", "secret"]
    assert SECRET not in str(entries)


def test_profile_copy_and_delete_are_audited(tmp_path: Path) -> None:
    harness = make_profile_harness(tmp_path)
    created = create_profile(harness)

    copy_response = harness.client.post(f"/api/profiles/{created['id']}/copy", json={})
    assert copy_response.status_code == 201, copy_response.text
    copy_id = copy_response.json()["id"]

    delete_response = harness.client.delete(f"/api/profiles/{copy_id}")
    assert delete_response.status_code == 200, delete_response.text

    entries = _entries(harness)
    assert [entry["action"] for entry in entries] == [
        "profile_delete",
        "profile_copy",
        "profile_create",
    ]
    assert entries[0]["profile_id"] == copy_id
    assert entries[1]["profile_id"] == copy_id


def test_bind_and_unbind_are_audited_once(tmp_path: Path) -> None:
    claude_dir = tmp_path / "claude"
    seed_claude(claude_dir)
    harness = make_profile_harness(tmp_path, claude_adapter(claude_dir))
    created = create_profile(harness)
    profile_id = str(created["id"])

    first = harness.client.put(
        "/api/tools/claude-code/profile",
        json={"profile_id": profile_id},
    )
    second = harness.client.put(
        "/api/tools/claude-code/profile",
        json={"profile_id": profile_id},
    )
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text

    unbind = harness.client.delete(f"/api/tools/claude-code/profiles/{profile_id}")
    again = harness.client.delete(f"/api/tools/claude-code/profiles/{profile_id}")
    assert unbind.status_code == 200, unbind.text
    assert again.status_code == 200, again.text

    entries = _entries(harness)
    assert [entry["action"] for entry in entries] == [
        "profile_unbind",
        "profile_bind",
        "profile_create",
    ]
    bind_entry = next(entry for entry in entries if entry["action"] == "profile_bind")
    assert bind_entry["tool_id"] == "claude-code"


def test_audit_tool_filter_excludes_profile_level_entries(tmp_path: Path) -> None:
    claude_dir = tmp_path / "claude"
    seed_claude(claude_dir)
    harness = make_profile_harness(tmp_path, claude_adapter(claude_dir))
    created = create_profile(harness)
    harness.client.put(
        "/api/tools/claude-code/profile",
        json={"profile_id": created["id"]},
    )

    filtered = harness.client.get("/api/audit", params={"tool_id": "claude-code"})

    assert filtered.status_code == 200
    actions = [entry["action"] for entry in filtered.json()["entries"]]
    assert actions == ["profile_bind"]
    assert all(entry["tool_id"] == "claude-code" for entry in filtered.json()["entries"])


def test_migration_upgrades_v1_audit_table_to_nullable_tool_id(tmp_path: Path) -> None:
    db_path = tmp_path / "db" / "app.sqlite3"
    db_path.parent.mkdir(parents=True)
    connection = sqlite3.connect(db_path)
    try:
        connection.executescript(APP_MIGRATIONS[0][1])
        connection.execute(
            """
            INSERT INTO audit_entries (
                id, created_at, action, tool_id, profile_id, snapshot_id,
                files_json, fields_json, result, message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "legacy",
                "2026-11-17T10:00:00+00:00",
                "apply",
                "claude-code",
                None,
                None,
                "[]",
                "[]",
                "success",
                "旧记录",
            ),
        )
        connection.execute("PRAGMA user_version = 1")
        connection.commit()
    finally:
        connection.close()

    repository = AuditRepository(db_path)
    entries = repository.list_recent()
    assert [entry.id for entry in entries] == ["legacy"]

    recorded = repository.record(
        action="profile_create",
        tool_id=None,
        profile_id="profile-1",
        snapshot_id=None,
        files=[],
        fields=["name"],
        result="success",
        message="新增供应商",
    )
    assert isinstance(recorded, AuditEntry)
    assert recorded.tool_id is None

    connection = sqlite3.connect(db_path)
    try:
        assert connection.execute("PRAGMA user_version").fetchone() == (2,)
        names = {
            str(row[0])
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    finally:
        connection.close()
    assert "audit_entries_legacy" not in names
