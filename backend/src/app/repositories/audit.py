"""审计仓储: SQLite 只存展示摘要, 不存文件原文或密钥。

每次操作通过 `bootstrap_database` 打开连接并应用 `APP_MIGRATIONS`, 因此删除
`db/app.sqlite3` 后下一次写入会自动重建表。SQL 只在本层出现。
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import cast

from app.core.clock import utc_now
from app.core.db import bootstrap_database
from app.core.errors import AppError
from app.core.redaction import redact_text
from app.repositories.migrations import APP_MIGRATIONS
from app.schemas.audit import AuditAction, AuditEntry, AuditResult

DEFAULT_AUDIT_LIMIT = 50


class AuditRepository:
    """`audit_entries` 的读写边界; 不做业务判断。"""

    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path)

    def record(
        self,
        *,
        action: AuditAction,
        tool_id: str,
        profile_id: str | None,
        snapshot_id: str | None,
        files: Sequence[str],
        fields: Sequence[str],
        result: AuditResult,
        message: str,
    ) -> AuditEntry:
        entry = AuditEntry(
            id=str(uuid.uuid4()),
            created_at=utc_now(),
            action=action,
            tool_id=tool_id,
            profile_id=profile_id,
            snapshot_id=snapshot_id,
            files=[redact_text(item) for item in files],
            fields=[redact_text(item) for item in fields],
            result=result,
            message=redact_text(message),
        )
        try:
            connection = self._connect()
            try:
                connection.execute(
                    """
                    INSERT INTO audit_entries (
                        id, created_at, action, tool_id, profile_id, snapshot_id,
                        files_json, fields_json, result, message
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entry.id,
                        entry.created_at.isoformat(),
                        entry.action,
                        entry.tool_id,
                        entry.profile_id,
                        entry.snapshot_id,
                        json.dumps(entry.files, ensure_ascii=False),
                        json.dumps(entry.fields, ensure_ascii=False),
                        entry.result,
                        entry.message,
                    ),
                )
            finally:
                connection.close()
        except (OSError, sqlite3.Error) as exc:
            raise AppError("AUDIT_WRITE_FAILED", "审计记录写入失败", 500) from exc
        return entry

    def list_recent(
        self,
        limit: int = DEFAULT_AUDIT_LIMIT,
        tool_id: str | None = None,
    ) -> list[AuditEntry]:
        if limit < 1:
            raise ValueError("limit must be positive")
        try:
            connection = self._connect()
            try:
                if tool_id is None:
                    rows = connection.execute(
                        """
                        SELECT id, created_at, action, tool_id, profile_id, snapshot_id,
                               files_json, fields_json, result, message
                        FROM audit_entries
                        ORDER BY created_at DESC, id DESC
                        LIMIT ?
                        """,
                        (limit,),
                    ).fetchall()
                else:
                    rows = connection.execute(
                        """
                        SELECT id, created_at, action, tool_id, profile_id, snapshot_id,
                               files_json, fields_json, result, message
                        FROM audit_entries
                        WHERE tool_id = ?
                        ORDER BY created_at DESC, id DESC
                        LIMIT ?
                        """,
                        (tool_id, limit),
                    ).fetchall()
            finally:
                connection.close()
        except (OSError, sqlite3.Error) as exc:
            raise AppError("AUDIT_UNREADABLE", "审计记录读取失败", 500) from exc

        try:
            return [_entry_from_row(row) for row in rows]
        except (ValueError, TypeError) as exc:
            raise AppError("AUDIT_UNREADABLE", "审计记录结构不合法", 500) from exc

    def _connect(self) -> sqlite3.Connection:
        return bootstrap_database(self._db_path, migrations=APP_MIGRATIONS)


def _entry_from_row(row: sqlite3.Row | tuple[object, ...]) -> AuditEntry:
    return AuditEntry(
        id=str(row[0]),
        created_at=datetime.fromisoformat(str(row[1])),
        action=cast(AuditAction, str(row[2])),
        tool_id=str(row[3]),
        profile_id=None if row[4] is None else str(row[4]),
        snapshot_id=None if row[5] is None else str(row[5]),
        files=_json_list(row[6]),
        fields=_json_list(row[7]),
        result=cast(AuditResult, str(row[8])),
        message=str(row[9]),
    )


def _json_list(value: object) -> list[str]:
    parsed = json.loads(str(value))
    if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
        raise ValueError("audit list column is not a list of strings")
    return parsed
