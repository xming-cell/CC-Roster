"""保留策略、pin 与内容寻址对象的引用回收。"""

import hashlib
from pathlib import Path

import pytest
from snapshot_fixtures import (
    at,
    capture_one,
    make_repository,
    object_files,
    object_path,
)

from app.core.errors import AppError
from app.repositories.snapshots import SnapshotRepository


def snapshot_dir(repository: SnapshotRepository, snapshot_id: str) -> Path:
    return repository.root / snapshot_id


def test_retention_keeps_newest_unpinned_snapshots(tmp_path: Path) -> None:
    repository = make_repository(tmp_path, retention_limit=2)
    oldest = capture_one(repository, tmp_path / "one.json", b"one", created_at=at(0))
    middle = capture_one(repository, tmp_path / "two.json", b"two", created_at=at(1))
    newest = capture_one(repository, tmp_path / "three.json", b"three", created_at=at(2))

    listing = repository.list_snapshots()

    assert [item.id for item in listing.snapshots] == [newest.id, middle.id]
    assert not snapshot_dir(repository, oldest.id).exists()
    assert snapshot_dir(repository, middle.id).exists()
    assert snapshot_dir(repository, newest.id).exists()


def test_pinned_snapshot_is_never_pruned_even_over_limit(tmp_path: Path) -> None:
    repository = make_repository(tmp_path, retention_limit=2)
    oldest = capture_one(repository, tmp_path / "one.json", b"one", created_at=at(0))
    repository.set_pinned(oldest.id, True)
    middle = capture_one(repository, tmp_path / "two.json", b"two", created_at=at(1))
    newest = capture_one(repository, tmp_path / "three.json", b"three", created_at=at(2))

    listing = repository.list_snapshots()

    assert [item.id for item in listing.snapshots] == [newest.id, oldest.id]
    assert listing.snapshots[1].pinned is True
    assert not snapshot_dir(repository, middle.id).exists()


def test_all_pinned_snapshots_can_exceed_limit(tmp_path: Path) -> None:
    repository = make_repository(tmp_path, retention_limit=1)
    first = capture_one(repository, tmp_path / "one.json", b"one", created_at=at(0))
    repository.set_pinned(first.id, True)
    second = capture_one(repository, tmp_path / "two.json", b"two", created_at=at(1))
    repository.set_pinned(second.id, True)
    third = capture_one(repository, tmp_path / "three.json", b"three", created_at=at(2))
    repository.set_pinned(third.id, True)

    listing = repository.list_snapshots()

    assert [item.id for item in listing.snapshots] == [third.id, second.id, first.id]
    assert all(item.pinned for item in listing.snapshots)


def test_retention_is_isolated_per_tool(tmp_path: Path) -> None:
    repository = make_repository(tmp_path, retention_limit=1)
    old_a = capture_one(
        repository,
        tmp_path / "a-old.json",
        b"a-old",
        tool_id="tool-a",
        created_at=at(0),
    )
    old_b = capture_one(
        repository,
        tmp_path / "b-old.json",
        b"b-old",
        tool_id="tool-b",
        created_at=at(1),
    )
    new_a = capture_one(
        repository,
        tmp_path / "a-new.json",
        b"a-new",
        tool_id="tool-a",
        created_at=at(2),
    )
    new_b = capture_one(
        repository,
        tmp_path / "b-new.json",
        b"b-new",
        tool_id="tool-b",
        created_at=at(3),
    )

    assert not snapshot_dir(repository, old_a.id).exists()
    assert not snapshot_dir(repository, old_b.id).exists()
    assert snapshot_dir(repository, new_a.id).exists()
    assert snapshot_dir(repository, new_b.id).exists()
    assert len(repository.list_snapshots().snapshots) == 2


def test_pin_and_unpin_are_idempotent_and_keep_metadata(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    snapshot = capture_one(repository, tmp_path / "config.json", b"data")
    meta_path = snapshot_dir(repository, snapshot.id) / "meta.json"

    pinned = repository.set_pinned(snapshot.id, True)
    mtime_after_first_pin = meta_path.stat().st_mtime_ns
    pinned_again = repository.set_pinned(snapshot.id, True)

    assert pinned.pinned is True
    assert pinned_again.pinned is True
    assert pinned_again.created_at == snapshot.created_at
    assert pinned_again.files == snapshot.files
    assert meta_path.stat().st_mtime_ns == mtime_after_first_pin

    unpinned = repository.set_pinned(snapshot.id, False)
    assert unpinned.pinned is False
    assert unpinned.created_at == snapshot.created_at

    with pytest.raises(AppError) as excinfo:
        repository.set_pinned("not-a-uuid", True)
    assert excinfo.value.code == "SNAPSHOT_NOT_FOUND"


def test_rollback_target_survives_capture_prune(tmp_path: Path) -> None:
    repository = make_repository(tmp_path, retention_limit=1)
    target = capture_one(repository, tmp_path / "one.json", b"one", created_at=at(0))

    pre_rollback = capture_one(
        repository,
        tmp_path / "two.json",
        b"two",
        created_at=at(1),
        reason="rollback",
        protected_ids={target.id},
    )

    assert snapshot_dir(repository, target.id).exists()
    assert snapshot_dir(repository, pre_rollback.id).exists()
    assert len(repository.list_snapshots().snapshots) == 2

    tail = capture_one(repository, tmp_path / "three.json", b"three", created_at=at(2))

    assert snapshot_dir(repository, target.id).exists() is False
    assert snapshot_dir(repository, pre_rollback.id).exists() is False
    assert snapshot_dir(repository, tail.id).exists()


def test_objects_survive_until_last_reference_is_pruned(tmp_path: Path) -> None:
    repository = make_repository(tmp_path, retention_limit=1)
    data = b"same-content"
    first = capture_one(repository, tmp_path / "one.json", data, created_at=at(0))
    old_chunks = set(first.files[0].chunks)
    assert all(object_path(repository, digest).is_file() for digest in old_chunks)

    second = capture_one(repository, tmp_path / "two.json", data, created_at=at(1))

    assert not snapshot_dir(repository, first.id).exists()
    assert all(object_path(repository, digest).is_file() for digest in old_chunks)

    replacement = b"different!"
    third = capture_one(
        repository,
        tmp_path / "three.json",
        replacement,
        created_at=at(2),
    )

    assert not snapshot_dir(repository, second.id).exists()
    assert not any(object_path(repository, digest).exists() for digest in old_chunks)
    assert all(object_path(repository, digest).is_file() for digest in third.files[0].chunks)


def test_orphan_objects_are_collected_on_prune(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    snapshot = capture_one(repository, tmp_path / "config.json", b"keep-data")
    orphan_digest = hashlib.sha256(b"orphan-object").hexdigest()
    orphan = object_path(repository, orphan_digest)
    orphan.parent.mkdir(parents=True, exist_ok=True)
    orphan.write_bytes(b"orphan-object")

    repository.prune(tool_id="claude-code")

    assert not orphan.exists()
    assert not orphan.parent.exists()
    assert all(object_path(repository, digest).is_file() for digest in snapshot.files[0].chunks)


def test_object_referenced_by_another_tool_is_not_collected(tmp_path: Path) -> None:
    repository = make_repository(tmp_path, retention_limit=1)
    data = b"shared-across-tools"
    old_a = capture_one(
        repository,
        tmp_path / "a-old.json",
        data,
        tool_id="tool-a",
        created_at=at(0),
    )
    capture_one(
        repository,
        tmp_path / "b.json",
        data,
        tool_id="tool-b",
        created_at=at(1),
    )
    capture_one(
        repository,
        tmp_path / "a-new.json",
        b"a-new",
        tool_id="tool-a",
        created_at=at(2),
    )

    assert not snapshot_dir(repository, old_a.id).exists()
    remaining_objects = {path.name for path in object_files(repository)}
    assert set(old_a.files[0].chunks) <= remaining_objects


def test_capture_succeeds_when_retention_cleanup_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = make_repository(tmp_path, retention_limit=1)
    first = capture_one(repository, tmp_path / "one.json", b"one", created_at=at(0))

    def fail_rmtree(_path: str | Path) -> None:
        raise OSError("permission denied")

    monkeypatch.setattr("app.repositories.snapshots.shutil.rmtree", fail_rmtree)

    second = capture_one(repository, tmp_path / "two.json", b"two", created_at=at(1))

    assert snapshot_dir(repository, first.id).exists()
    assert snapshot_dir(repository, second.id).exists()
    assert len(repository.list_snapshots().snapshots) == 2
