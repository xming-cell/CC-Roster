import json
import os
import stat
from pathlib import Path

import pytest

from app.core.atomic import write_bytes_atomic, write_json_atomic


def _temp_files(directory: Path, target: Path) -> list[str]:
    return [path.name for path in directory.iterdir() if path.name != target.name]


def test_write_json_atomic_creates_parent_and_readable_json(tmp_path: Path) -> None:
    path = tmp_path / "data" / "profiles.json"

    write_json_atomic(path, {"name": "默认档案", "models": ["a", "b"]})

    text = path.read_text(encoding="utf-8")
    assert json.loads(text) == {"name": "默认档案", "models": ["a", "b"]}
    assert text.endswith("\n")


def test_write_json_atomic_replaces_existing_file(tmp_path: Path) -> None:
    path = tmp_path / "profiles.json"
    path.write_text('{"old": true}\n', encoding="utf-8")

    write_json_atomic(path, {"new": True})

    assert json.loads(path.read_text(encoding="utf-8")) == {"new": True}
    assert _temp_files(tmp_path, path) == []


def test_write_json_atomic_keeps_original_when_replace_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "profiles.json"
    original = '{"old": true}\n'
    path.write_text(original, encoding="utf-8")

    def fail_replace(src: Path, dst: Path) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("app.core.atomic.os.replace", fail_replace)

    with pytest.raises(OSError, match="disk full"):
        write_json_atomic(path, {"new": True})

    assert path.read_text(encoding="utf-8") == original
    assert _temp_files(tmp_path, path) == []


def test_write_json_atomic_keeps_original_when_serialization_fails(tmp_path: Path) -> None:
    path = tmp_path / "profiles.json"
    original = '{"old": true}\n'
    path.write_text(original, encoding="utf-8")

    with pytest.raises(TypeError):
        write_json_atomic(path, {"bad": object()})

    assert path.read_text(encoding="utf-8") == original
    assert _temp_files(tmp_path, path) == []


def test_write_bytes_atomic_creates_parent_and_writes_exact_bytes(tmp_path: Path) -> None:
    path = tmp_path / "snapshots" / "objects" / "blob"
    data = b"\x00\xffBOM\r\n\xe4\xb8\xad"

    write_bytes_atomic(path, data)

    assert path.read_bytes() == data
    assert _temp_files(path.parent, path) == []


def test_write_bytes_atomic_preserves_existing_mode(tmp_path: Path) -> None:
    if os.name == "nt":
        return
    path = tmp_path / "blob"
    path.write_bytes(b"old")
    path.chmod(0o640)

    write_bytes_atomic(path, b"new")

    assert path.read_bytes() == b"new"
    assert stat.S_IMODE(path.stat().st_mode) == 0o640


def test_write_bytes_atomic_new_file_is_private_on_unix(tmp_path: Path) -> None:
    if os.name == "nt":
        return
    path = tmp_path / "blob"

    write_bytes_atomic(path, b"secret")

    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_write_bytes_atomic_keeps_original_when_replace_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "blob"
    original = b"original"
    path.write_bytes(original)

    def fail_replace(_src: Path, _dst: Path) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("app.core.atomic.os.replace", fail_replace)

    with pytest.raises(OSError, match="disk full"):
        write_bytes_atomic(path, b"new")

    assert path.read_bytes() == original
    assert _temp_files(tmp_path, path) == []
