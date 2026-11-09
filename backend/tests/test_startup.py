from pathlib import Path

from app.main import initialize_app_data


def test_initialize_app_data_creates_database_and_logs_dirs(tmp_path: Path) -> None:
    data_dir = initialize_app_data(tmp_path / "CC-Roster")

    assert (data_dir / "db" / "app.sqlite3").is_file()
    assert (data_dir / "logs").is_dir()


def test_initialize_app_data_is_idempotent(tmp_path: Path) -> None:
    first = initialize_app_data(tmp_path / "CC-Roster")
    second = initialize_app_data(tmp_path / "CC-Roster")

    assert first == second
    assert (second / "db" / "app.sqlite3").is_file()
