"""外部改动检测: 观察、冲突分类与写前最终校验。

只使用真实文件系统; 并发用例用一个测试内锁模拟写引擎持有的跨进程锁。
"""

import hashlib
import os
import threading
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.atomic import write_bytes_atomic
from app.core.errors import AppError, WriteConflict
from app.core.file_observation import (
    detect_conflicts,
    ensure_observations_current,
    observe_file,
)
from app.schemas.snapshot import FileObservation


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_observe_existing_file_returns_absolute_path_and_hash(tmp_path: Path) -> None:
    target = tmp_path / "config.json"
    data = b'{"api_key": "value"}\n'
    target.write_bytes(data)

    observation = observe_file(target)

    assert observation.path == str(target.resolve())
    assert observation.exists is True
    assert observation.sha256 == sha256(data)
    assert observation.size == len(data)
    assert observation.mtime_ns == target.stat().st_mtime_ns


def test_observe_missing_file_returns_not_exists(tmp_path: Path) -> None:
    target = tmp_path / "missing" / "config.json"

    observation = observe_file(target)

    assert observation.path == str(target.resolve())
    assert observation.exists is False
    assert observation.sha256 is None
    assert observation.size == 0
    assert observation.mtime_ns is None


def test_observe_resolves_symlink(tmp_path: Path) -> None:
    if os.name == "nt":
        return
    target = tmp_path / "real.json"
    target.write_bytes(b"symlink-content")
    link = tmp_path / "link.json"
    link.symlink_to(target)

    observation = observe_file(link)

    assert observation.path == str(target.resolve())
    assert observation.sha256 == sha256(b"symlink-content")


def test_observe_rejects_relative_path_and_reports_unreadable_target(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError):
        observe_file("relative.json")

    with pytest.raises(AppError) as excinfo:
        observe_file(tmp_path)
    assert excinfo.value.code == "FILE_OBSERVE_FAILED"


def test_observe_is_read_only(tmp_path: Path) -> None:
    target = tmp_path / "config.json"
    target.write_bytes(b"unchanged")
    before = target.stat()

    observe_file(target)
    observe_file(target)

    after = target.stat()
    assert after.st_size == before.st_size
    assert after.st_mtime_ns == before.st_mtime_ns


def test_mtime_only_change_is_not_a_conflict(tmp_path: Path) -> None:
    target = tmp_path / "config.json"
    target.write_bytes(b"same-content")
    observation = observe_file(target)
    current = target.stat()
    os.utime(target, ns=(current.st_atime_ns, current.st_mtime_ns + 1_000_000_000))

    assert detect_conflicts([observation]) == []
    ensure_observations_current([observation])


def test_content_change_reports_structured_conflict(tmp_path: Path) -> None:
    target = tmp_path / "config.json"
    original = b"original-content"
    changed = b"changed-content"
    target.write_bytes(original)
    observation = observe_file(target)
    target.write_bytes(changed)

    conflicts = detect_conflicts([observation])

    assert len(conflicts) == 1
    conflict = conflicts[0]
    assert conflict.path == str(target.resolve())
    assert conflict.reason == "CONTENT_CHANGED"
    assert conflict.expected.sha256 == sha256(original)
    assert conflict.actual.sha256 == sha256(changed)
    assert conflict.actual.mtime_ns == target.stat().st_mtime_ns

    with pytest.raises(WriteConflict) as excinfo:
        ensure_observations_current([observation])
    assert excinfo.value.code == "WRITE_CONFLICT"
    assert excinfo.value.status_code == 409
    assert excinfo.value.conflicts == conflicts


def test_deleted_file_reports_missing_conflict(tmp_path: Path) -> None:
    target = tmp_path / "config.json"
    target.write_bytes(b"original")
    observation = observe_file(target)
    target.unlink()

    conflicts = detect_conflicts([observation])

    assert len(conflicts) == 1
    assert conflicts[0].reason == "MISSING"
    assert conflicts[0].expected.exists is True
    assert conflicts[0].actual.exists is False
    assert conflicts[0].actual.sha256 is None


def test_created_file_reports_created_conflict(tmp_path: Path) -> None:
    target = tmp_path / "config.json"
    observation = observe_file(target)
    target.write_bytes(b"created")

    conflicts = detect_conflicts([observation])

    assert len(conflicts) == 1
    assert conflicts[0].reason == "CREATED"
    assert conflicts[0].expected.exists is False
    assert conflicts[0].actual.exists is True
    assert conflicts[0].actual.sha256 == sha256(b"created")


def test_conflict_message_does_not_leak_file_contents(tmp_path: Path) -> None:
    target = tmp_path / "config.json"
    secret = b"sk-" + b"a" * 32
    target.write_bytes(secret)
    observation = observe_file(target)
    target.write_bytes(b"replaced")

    with pytest.raises(WriteConflict) as excinfo:
        ensure_observations_current([observation])

    assert secret.decode() not in str(excinfo.value)
    assert excinfo.value.code == "WRITE_CONFLICT"


def test_second_writer_with_stale_observation_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "config.json"
    target.write_bytes(b"initial")
    observation = observe_file(target)
    write_lock = threading.Lock()
    outcomes: list[str] = []

    def writer(payload: bytes) -> None:
        with write_lock:
            try:
                ensure_observations_current([observation])
                write_bytes_atomic(target, payload)
            except WriteConflict:
                outcomes.append("conflict")
            else:
                outcomes.append("success")

    threads = [
        threading.Thread(target=writer, args=(b"writer-one",)),
        threading.Thread(target=writer, args=(b"writer-two",)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert not any(thread.is_alive() for thread in threads)
    assert sorted(outcomes) == ["conflict", "success"]
    assert target.read_bytes() in {b"writer-one", b"writer-two"}
    assert target.read_bytes() != b"initial"


@pytest.mark.parametrize(
    "overrides",
    [
        {"exists": True, "sha256": None, "mtime_ns": 1},
        {"exists": True, "sha256": hashlib.sha256(b"").hexdigest(), "mtime_ns": None},
        {"exists": False, "sha256": hashlib.sha256(b"").hexdigest()},
        {"exists": False, "mtime_ns": 1},
        {"exists": False, "size": 3},
    ],
)
def test_file_observation_rejects_inconsistent_values(
    tmp_path: Path,
    overrides: dict[str, object],
) -> None:
    payload: dict[str, object] = {"path": str(tmp_path / "config.json"), "exists": False}
    payload.update(overrides)

    with pytest.raises(ValidationError):
        FileObservation.model_validate(payload)


def test_file_observation_rejects_relative_path() -> None:
    with pytest.raises(ValidationError):
        FileObservation.model_validate({"path": "relative.json", "exists": False})
