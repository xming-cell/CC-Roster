from pathlib import Path, PurePosixPath, PureWindowsPath

import pytest

from app.core.paths import ensure_data_dirs, resolve_data_dir


def test_resolve_data_dir_windows_uses_local_app_data() -> None:
    resolved = resolve_data_dir(
        platform="win32",
        environ={"LOCALAPPDATA": r"C:\Users\me\AppData\Local"},
        home=PureWindowsPath(r"C:\Users\me"),
    )

    assert resolved == PureWindowsPath(r"C:\Users\me\AppData\Local\CC-Roster")


def test_resolve_data_dir_windows_falls_back_when_local_app_data_missing() -> None:
    resolved = resolve_data_dir(
        platform="win32",
        environ={},
        home=PureWindowsPath(r"C:\Users\me"),
    )

    assert resolved == PureWindowsPath(r"C:\Users\me\AppData\Local\CC-Roster")


def test_resolve_data_dir_macos_uses_application_support() -> None:
    resolved = resolve_data_dir(
        platform="darwin",
        environ={},
        home=PurePosixPath("/Users/me"),
    )

    assert resolved == PurePosixPath("/Users/me/Library/Application Support/CC-Roster")


def test_resolve_data_dir_linux_prefers_xdg_data_home() -> None:
    resolved = resolve_data_dir(
        platform="linux",
        environ={"XDG_DATA_HOME": "/srv/data"},
        home=PurePosixPath("/home/me"),
    )

    assert resolved == PurePosixPath("/srv/data/cc-roster")


def test_resolve_data_dir_linux_falls_back_when_xdg_data_home_missing() -> None:
    resolved = resolve_data_dir(
        platform="linux",
        environ={},
        home=PurePosixPath("/home/me"),
    )

    assert resolved == PurePosixPath("/home/me/.local/share/cc-roster")


def test_resolve_data_dir_linux_falls_back_when_xdg_data_home_is_empty() -> None:
    resolved = resolve_data_dir(
        platform="linux",
        environ={"XDG_DATA_HOME": ""},
        home=PurePosixPath("/home/me"),
    )

    assert resolved == PurePosixPath("/home/me/.local/share/cc-roster")


def test_resolve_data_dir_linux_ignores_relative_xdg_data_home() -> None:
    resolved = resolve_data_dir(
        platform="linux",
        environ={"XDG_DATA_HOME": "relative/data"},
        home=PurePosixPath("/home/me"),
    )

    assert resolved == PurePosixPath("/home/me/.local/share/cc-roster")


@pytest.mark.parametrize("platform", ["freebsd", "cygwin", "linux2", ""])
def test_resolve_data_dir_rejects_unknown_platform(platform: str) -> None:
    with pytest.raises(ValueError, match="unsupported platform"):
        resolve_data_dir(platform=platform, environ={}, home=PurePosixPath("/home/me"))


def test_ensure_data_dirs_creates_root_db_and_logs(tmp_path: Path) -> None:
    data_dir = tmp_path / "CC-Roster"

    result = ensure_data_dirs(data_dir)

    assert result == data_dir
    assert (data_dir / "db").is_dir()
    assert (data_dir / "logs").is_dir()


def test_ensure_data_dirs_is_idempotent_and_keeps_existing_files(tmp_path: Path) -> None:
    data_dir = tmp_path / "CC-Roster"
    ensure_data_dirs(data_dir)
    marker = data_dir / "logs" / "keep.log"
    marker.write_text("keep", encoding="utf-8")

    ensure_data_dirs(data_dir)

    assert marker.read_text(encoding="utf-8") == "keep"


def test_ensure_data_dirs_fails_when_root_is_a_file(tmp_path: Path) -> None:
    data_dir = tmp_path / "CC-Roster"
    data_dir.write_text("not a directory", encoding="utf-8")

    with pytest.raises(FileExistsError):
        ensure_data_dirs(data_dir)
