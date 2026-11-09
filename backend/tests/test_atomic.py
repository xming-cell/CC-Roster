import json
from pathlib import Path

import pytest

from app.core.atomic import write_json_atomic


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
