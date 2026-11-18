"""应用数据库迁移; 与快照不同, 审计表可随 `db/app.sqlite3` 一起重建。"""

from app.core.db import Migration

AUDIT_ENTRIES_TABLE = "audit_entries"

APP_MIGRATIONS: tuple[Migration, ...] = (
    (
        1,
        """
        CREATE TABLE IF NOT EXISTS audit_entries (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            action TEXT NOT NULL,
            tool_id TEXT NOT NULL,
            profile_id TEXT,
            snapshot_id TEXT,
            files_json TEXT NOT NULL,
            fields_json TEXT NOT NULL,
            result TEXT NOT NULL,
            message TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_audit_entries_created_at
            ON audit_entries (created_at);
        """,
    ),
    (
        2,
        """
        DROP INDEX IF EXISTS idx_audit_entries_created_at;
        ALTER TABLE audit_entries RENAME TO audit_entries_legacy;
        CREATE TABLE audit_entries (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            action TEXT NOT NULL,
            tool_id TEXT,
            profile_id TEXT,
            snapshot_id TEXT,
            files_json TEXT NOT NULL,
            fields_json TEXT NOT NULL,
            result TEXT NOT NULL,
            message TEXT NOT NULL
        );
        INSERT INTO audit_entries (
            id, created_at, action, tool_id, profile_id, snapshot_id,
            files_json, fields_json, result, message
        )
        SELECT id, created_at, action, tool_id, profile_id, snapshot_id,
               files_json, fields_json, result, message
        FROM audit_entries_legacy;
        DROP TABLE audit_entries_legacy;
        CREATE INDEX IF NOT EXISTS idx_audit_entries_created_at
            ON audit_entries (created_at);
        """,
    ),
)
