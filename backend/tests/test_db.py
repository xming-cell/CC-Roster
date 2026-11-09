import sqlite3
from pathlib import Path

import pytest

from app.core.db import DatabaseVersionError, Migration, bootstrap_database

MIGRATIONS: list[Migration] = [
    (1, "CREATE TABLE tools (id TEXT PRIMARY KEY);"),
    (2, "CREATE TABLE profiles (id TEXT PRIMARY KEY);"),
]


def _table_names(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    return {str(row[0]) for row in rows}


def test_bootstrap_configures_wal_busy_timeout_and_user_version(tmp_path: Path) -> None:
    db_path = tmp_path / "db" / "app.sqlite3"

    connection = bootstrap_database(db_path)
    try:
        assert db_path.is_file()
        assert connection.execute("PRAGMA journal_mode").fetchone() == ("wal",)
        assert connection.execute("PRAGMA busy_timeout").fetchone() == (5000,)
        assert connection.execute("PRAGMA user_version").fetchone() == (0,)
    finally:
        connection.close()


def test_bootstrap_applies_injected_migrations(tmp_path: Path) -> None:
    db_path = tmp_path / "app.sqlite3"

    connection = bootstrap_database(db_path, migrations=MIGRATIONS)
    try:
        assert connection.execute("PRAGMA user_version").fetchone() == (2,)
        assert _table_names(connection) == {"tools", "profiles"}
    finally:
        connection.close()


def test_bootstrap_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "app.sqlite3"
    first = bootstrap_database(db_path, migrations=MIGRATIONS)
    first.execute("INSERT INTO tools (id) VALUES ('claude-code')")
    first.close()

    second = bootstrap_database(db_path, migrations=MIGRATIONS)
    try:
        assert second.execute("PRAGMA user_version").fetchone() == (2,)
        assert second.execute("SELECT id FROM tools").fetchall() == [("claude-code",)]
    finally:
        second.close()


def test_bootstrap_rebuilds_after_database_file_deleted(tmp_path: Path) -> None:
    db_path = tmp_path / "db" / "app.sqlite3"
    bootstrap_database(db_path, migrations=MIGRATIONS).close()

    db_path.unlink()
    rebuilt = bootstrap_database(db_path, migrations=MIGRATIONS)
    try:
        assert rebuilt.execute("PRAGMA user_version").fetchone() == (2,)
        assert _table_names(rebuilt) == {"tools", "profiles"}
    finally:
        rebuilt.close()


def test_bootstrap_rejects_newer_user_version_without_downgrading(tmp_path: Path) -> None:
    db_path = tmp_path / "app.sqlite3"
    raw = sqlite3.connect(db_path)
    raw.execute("PRAGMA user_version = 99")
    raw.close()

    with pytest.raises(DatabaseVersionError, match="99"):
        bootstrap_database(db_path, migrations=MIGRATIONS)

    reopened = sqlite3.connect(db_path)
    try:
        assert reopened.execute("PRAGMA user_version").fetchone() == (99,)
    finally:
        reopened.close()


def test_failed_migration_rolls_back_whole_script(tmp_path: Path) -> None:
    db_path = tmp_path / "app.sqlite3"
    broken = [(1, "CREATE TABLE ok (id INTEGER); CREATE TABLE nope (")]

    with pytest.raises(sqlite3.OperationalError):
        bootstrap_database(db_path, migrations=broken)

    reopened = sqlite3.connect(db_path)
    try:
        assert reopened.execute("PRAGMA user_version").fetchone() == (0,)
        assert _table_names(reopened) == set()
    finally:
        reopened.close()


@pytest.mark.parametrize(
    "migrations",
    [
        [(0, "SELECT 1;")],
        [(2, "SELECT 1;"), (1, "SELECT 2;")],
        [(1, "SELECT 1;"), (1, "SELECT 2;")],
    ],
)
def test_bootstrap_rejects_invalid_migration_versions(
    tmp_path: Path,
    migrations: list[Migration],
) -> None:
    with pytest.raises(ValueError, match="strictly increasing"):
        bootstrap_database(tmp_path / "app.sqlite3", migrations=migrations)


def test_bootstrap_rejects_negative_busy_timeout(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="non-negative"):
        bootstrap_database(tmp_path / "app.sqlite3", busy_timeout_ms=-1)
