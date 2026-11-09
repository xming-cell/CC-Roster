"""SQLite bootstrap: WAL, busy timeout, `PRAGMA user_version` 与可注入迁移。

本卡只提供迁移机制, 不预建任何业务表; 004 / 007 / 016 后续追加自己的迁移。
"""

import sqlite3
from collections.abc import Sequence
from pathlib import Path

DEFAULT_BUSY_TIMEOUT_MS = 5000

# (目标版本, SQL 脚本)。版本必须是严格递增的正整数。
Migration = tuple[int, str]


class DatabaseVersionError(RuntimeError):
    """数据库的 user_version 比当前代码支持的版本新。不降级、不猜测。"""


def _validate_migrations(migrations: Sequence[Migration]) -> None:
    previous = 0
    for version, _sql in migrations:
        if not isinstance(version, int) or version <= previous:
            raise ValueError("migration versions must be strictly increasing positive integers")
        previous = version


def _apply_migration(connection: sqlite3.Connection, version: int, sql: str) -> None:
    """整段迁移 + 版本号在同一个事务里提交; 失败时由调用方关闭连接回滚。"""
    connection.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version = {version};\nCOMMIT;")


def bootstrap_database(
    db_path: Path,
    *,
    migrations: Sequence[Migration] = (),
    busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
) -> sqlite3.Connection:
    """打开或创建数据库, 应用尚未执行的迁移, 返回调用方负责关闭的连接。

    幂等: 已处于目标版本的迁移不会重复执行。删除数据库文件后再次调用可重建。
    """
    _validate_migrations(migrations)
    if busy_timeout_ms < 0:
        raise ValueError("busy_timeout_ms must be non-negative")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path, isolation_level=None)
    try:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute(f"PRAGMA busy_timeout = {busy_timeout_ms}")

        row = connection.execute("PRAGMA user_version").fetchone()
        assert row is not None
        current_version = int(row[0])
        supported_version = migrations[-1][0] if migrations else 0
        if current_version > supported_version:
            raise DatabaseVersionError(
                f"database user_version {current_version} is newer than supported "
                f"{supported_version}: {db_path}"
            )

        for version, sql in migrations:
            if version <= current_version:
                continue
            _apply_migration(connection, version, sql)
            current_version = version
    except BaseException:
        connection.close()
        raise
    return connection
