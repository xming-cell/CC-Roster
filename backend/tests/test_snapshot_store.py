"""快照仓储的持久化契约。

全部走真实文件系统: 分块边界、内容去重、空 / 缺失文件、损坏降级、路径防穿越、
原子写与 Unix 私有权限。只 monkeypatch 写入边界模拟磁盘失败。
"""

import hashlib
import json
import os
import stat
import uuid
from pathlib import Path

import pytest
from snapshot_fixtures import (
    NOW,
    at,
    capture_one,
    file_source,
    make_repository,
    missing_source,
    object_files,
    object_path,
)

from app.core.errors import AppError
from app.core.locks import FileLock
from app.repositories.snapshots import SnapshotRepository
from app.schemas.snapshot import SnapshotChange


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def meta_path(repository: SnapshotRepository, snapshot_id: str) -> Path:
    return repository.root / snapshot_id / "meta.json"


def write_meta(repository: SnapshotRepository, snapshot_id: str, payload: object) -> None:
    path = meta_path(repository, snapshot_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


@pytest.mark.parametrize("size", [0, 4, 5, 8, 9])
def test_capture_roundtrips_chunk_boundaries(tmp_path: Path, size: int) -> None:
    repository = make_repository(tmp_path, chunk_size=4)
    target = tmp_path / "config.bin"
    data = bytes(range(size))

    snapshot = capture_one(repository, target, data)
    snapshot_file = snapshot.files[0]
    loaded = repository.get(snapshot.id)

    assert loaded == snapshot
    assert loaded is not None
    assert snapshot_file.existed is True
    assert snapshot_file.sha256 == sha256(data)
    assert snapshot_file.size == size
    assert snapshot_file.chunk_size == 4
    assert len(snapshot_file.chunks) == (size + 3) // 4
    assert repository.load_file_bytes(loaded, loaded.files[0]) == data
    assert len(object_files(repository)) == len(set(snapshot_file.chunks))
    raw_meta = json.loads(meta_path(repository, snapshot.id).read_text(encoding="utf-8"))
    assert raw_meta["schema_version"] == 1
    assert raw_meta["files"][0]["path"] == str(target.resolve())


def test_capture_uses_caller_bytes_instead_of_rereading_target(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    target = tmp_path / "config.json"
    source = file_source(target, b"before-snapshot")
    target.write_bytes(b"changed-after-observation")

    snapshot = repository.capture(
        tool_id="claude-code",
        files=[source],
        reason="apply",
        created_at=NOW,
    )

    assert repository.load_file_bytes(snapshot, snapshot.files[0]) == b"before-snapshot"
    assert target.read_bytes() == b"changed-after-observation"


def test_capture_records_missing_file_without_touching_target(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    target = tmp_path / "not-created" / "config.json"

    snapshot = repository.capture(
        tool_id="claude-code",
        files=[missing_source(target)],
        reason="apply",
        created_at=NOW,
    )
    snapshot_file = snapshot.files[0]

    assert snapshot_file.existed is False
    assert snapshot_file.sha256 is None
    assert snapshot_file.size == 0
    assert snapshot_file.mtime_ns is None
    assert snapshot_file.chunks == []
    assert not target.exists()
    assert not target.parent.exists()
    loaded = repository.get(snapshot.id)
    assert loaded is not None
    assert loaded.files[0].existed is False


def test_content_addressed_objects_are_shared(tmp_path: Path) -> None:
    repository = make_repository(tmp_path, chunk_size=4)
    data = b"shared-content"

    first = capture_one(repository, tmp_path / "one.json", data)
    objects_after_first = {path.name for path in object_files(repository)}
    second = capture_one(repository, tmp_path / "two.json", data)

    assert objects_after_first == set(first.files[0].chunks)
    assert {path.name for path in object_files(repository)} == objects_after_first
    assert second.files[0].chunks == first.files[0].chunks

    same_snapshot = repository.capture(
        tool_id="claude-code",
        files=[
            file_source(tmp_path / "three.json", data),
            file_source(tmp_path / "four.json", data),
        ],
        reason="apply",
        created_at=NOW,
    )
    assert same_snapshot.files[0].chunks == first.files[0].chunks
    assert {path.name for path in object_files(repository)} == objects_after_first


def test_list_returns_newest_first_and_filters_by_tool(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    oldest = capture_one(
        repository,
        tmp_path / "one.json",
        b"one",
        tool_id="tool-a",
        created_at=at(0),
    )
    middle = capture_one(
        repository,
        tmp_path / "two.json",
        b"two",
        tool_id="tool-b",
        created_at=at(1),
    )
    newest = capture_one(
        repository,
        tmp_path / "three.json",
        b"three",
        tool_id="tool-a",
        created_at=at(2),
    )

    listing = repository.list_snapshots()
    filtered = repository.list_snapshots(tool_id="tool-a")
    limited = repository.list_snapshots(limit=1)

    assert [item.id for item in listing.snapshots] == [
        newest.id,
        middle.id,
        oldest.id,
    ]
    assert [item.id for item in filtered.snapshots] == [newest.id, oldest.id]
    assert [item.id for item in limited.snapshots] == [newest.id]
    assert listing.warnings == []
    assert repository.list_snapshots(tool_id="unknown").snapshots == []


def test_list_missing_store_returns_empty_without_creating_directories(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "CC-Roster"
    repository = make_repository(data_dir)

    listing = repository.list_snapshots()

    assert listing.snapshots == []
    assert listing.warnings == []
    assert not data_dir.exists()


def test_list_skips_corrupt_snapshots_and_warns(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    valid = capture_one(repository, tmp_path / "config.json", b"valid")
    bad_json_id = str(uuid.uuid4())
    version_id = str(uuid.uuid4())
    missing_meta_id = str(uuid.uuid4())
    (repository.root / bad_json_id).mkdir()
    (repository.root / bad_json_id / "meta.json").write_text("{", encoding="utf-8")
    write_meta(repository, version_id, {"schema_version": 2})
    (repository.root / missing_meta_id).mkdir()
    (repository.root / "not-a-snapshot").mkdir()

    listing = repository.list_snapshots()

    assert [item.id for item in listing.snapshots] == [valid.id]
    codes = {warning.code for warning in listing.warnings}
    assert codes == {"SNAPSHOT_UNREADABLE", "SNAPSHOT_VERSION_UNSUPPORTED"}
    assert len(listing.warnings) == 4


def test_get_rejects_tampered_chunk(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    snapshot = capture_one(repository, tmp_path / "config.json", b"abcdefgh")
    chunk_path = object_path(repository, snapshot.files[0].chunks[0])
    chunk_path.write_bytes(b"tampered")

    with pytest.raises(AppError) as excinfo:
        repository.get(snapshot.id)

    assert excinfo.value.code == "SNAPSHOT_UNREADABLE"


def test_get_rejects_deleted_chunk(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    snapshot = capture_one(repository, tmp_path / "config.json", b"abcdefgh")
    object_path(repository, snapshot.files[0].chunks[0]).unlink()

    with pytest.raises(AppError) as excinfo:
        repository.get(snapshot.id)

    assert excinfo.value.code == "SNAPSHOT_UNREADABLE"


@pytest.mark.parametrize("version", [2, 99])
def test_get_rejects_unsupported_schema_version(
    tmp_path: Path,
    version: int,
) -> None:
    repository = make_repository(tmp_path)
    snapshot = capture_one(repository, tmp_path / "config.json", b"data")
    raw = json.loads(meta_path(repository, snapshot.id).read_text(encoding="utf-8"))
    raw["schema_version"] = version
    write_meta(repository, snapshot.id, raw)

    with pytest.raises(AppError) as excinfo:
        repository.get(snapshot.id)

    assert excinfo.value.code == "SNAPSHOT_UNREADABLE"


@pytest.mark.parametrize(
    "tampered_path",
    ["relative.json", "../escape.json", "/tmp/../escape.json"],
)
def test_get_rejects_tampered_file_paths(
    tmp_path: Path,
    tampered_path: str,
) -> None:
    repository = make_repository(tmp_path)
    snapshot = capture_one(repository, tmp_path / "config.json", b"data")
    raw = json.loads(meta_path(repository, snapshot.id).read_text(encoding="utf-8"))
    raw["files"][0]["path"] = tampered_path
    write_meta(repository, snapshot.id, raw)

    with pytest.raises(AppError) as excinfo:
        repository.get(snapshot.id)

    assert excinfo.value.code == "SNAPSHOT_UNREADABLE"


def test_get_unknown_or_invalid_id_returns_none_without_traversal(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "data"
    repository = make_repository(data_dir)

    assert repository.get("../../outside") is None
    assert repository.get("not-a-uuid") is None
    assert repository.get(str(uuid.uuid4())) is None
    assert not (tmp_path / "outside").exists()
    assert not data_dir.exists()


def test_capture_rejects_duplicate_paths(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    target = tmp_path / "config.json"
    source = file_source(target, b"data")

    with pytest.raises(AppError) as excinfo:
        repository.capture(
            tool_id="claude-code",
            files=[source, source],
            reason="apply",
        )

    assert excinfo.value.code == "SNAPSHOT_INVALID"


def test_capture_lock_timeout_reports_readable_error(tmp_path: Path) -> None:
    repository = make_repository(tmp_path, lock_timeout=0.1)

    with FileLock(repository.lock_path, timeout=1.0), pytest.raises(AppError) as excinfo:
        capture_one(repository, tmp_path / "config.json", b"data")

    assert excinfo.value.code == "SNAPSHOT_LOCK_TIMEOUT"
    assert repository.list_snapshots().snapshots == []


def test_capture_meta_write_failure_leaves_no_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = make_repository(tmp_path)

    def fail_write(_path: Path, _data: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("app.repositories.snapshots.write_json_atomic", fail_write)

    with pytest.raises(AppError) as excinfo:
        capture_one(repository, tmp_path / "config.json", b"data")

    assert excinfo.value.code == "SNAPSHOT_WRITE_FAILED"
    assert repository.list_snapshots().snapshots == []


def test_capture_object_write_failure_leaves_no_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = make_repository(tmp_path)

    def fail_write(_path: Path, _data: bytes, *, mode: int | None = None) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("app.repositories.snapshots.write_bytes_atomic", fail_write)

    with pytest.raises(AppError) as excinfo:
        capture_one(repository, tmp_path / "config.json", b"data")

    assert excinfo.value.code == "SNAPSHOT_WRITE_FAILED"
    assert repository.list_snapshots().snapshots == []


def test_capture_redacts_changes_in_meta(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    secret = "sk-" + "a" * 32
    change = SnapshotChange(
        path=str((tmp_path / "config.json").resolve()),
        field="api_key",
        action="set",
        before=None,
        after=f"Bearer {secret}",
    )

    snapshot = capture_one(
        repository,
        tmp_path / "config.json",
        b"data",
        changes=[change],
    )
    meta_text = meta_path(repository, snapshot.id).read_text(encoding="utf-8")

    assert secret not in meta_text
    assert "****" in meta_text
    assert secret not in (snapshot.changes[0].after or "")
    assert list(repository.root.rglob("*.tmp")) == []


def test_capture_uses_private_unix_permissions(tmp_path: Path) -> None:
    if os.name == "nt":
        return
    repository = make_repository(tmp_path)
    snapshot = capture_one(repository, tmp_path / "config.json", b"private")

    assert stat.S_IMODE(repository.root.stat().st_mode) == 0o700
    assert stat.S_IMODE(repository.objects_dir.stat().st_mode) == 0o700
    assert stat.S_IMODE(meta_path(repository, snapshot.id).stat().st_mode) == 0o600
    objects = object_files(repository)
    assert objects
    assert all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in objects)


def test_store_root_that_is_a_file_reports_unreadable(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "snapshots").write_text("not a directory", encoding="utf-8")
    repository = make_repository(data_dir)

    with pytest.raises(AppError) as excinfo:
        repository.list_snapshots()

    assert excinfo.value.code == "SNAPSHOT_STORE_UNREADABLE"
