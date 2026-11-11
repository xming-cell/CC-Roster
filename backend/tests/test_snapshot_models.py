"""快照领域模型的校验与视图边界。

覆盖 UUID / 绝对路径、空文件与缺失文件的一致性、chunk 数量、变更脱敏与截断,
以及视图绝不暴露 chunk 内容。
"""

import hashlib
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.snapshot import (
    MAX_CHANGE_VALUE_LENGTH,
    Snapshot,
    SnapshotChange,
    SnapshotFile,
    SnapshotFileSource,
    SnapshotFileView,
    SnapshotSummary,
    SnapshotView,
)

EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
NOW = datetime(2026, 11, 11, 8, 0, tzinfo=UTC)


def make_file(path: Path, data: bytes = b"abcdef", *, chunk_size: int = 4) -> SnapshotFile:
    chunks = [
        hashlib.sha256(data[start : start + chunk_size]).hexdigest()
        for start in range(0, len(data), chunk_size)
    ]
    return SnapshotFile(
        path=str(path),
        existed=True,
        sha256=hashlib.sha256(data).hexdigest(),
        size=len(data),
        mtime_ns=1,
        mode=0o600,
        chunks=chunks,
        chunk_size=chunk_size,
    )


def make_snapshot(path: Path) -> Snapshot:
    return Snapshot(
        id=str(uuid.uuid4()),
        tool_id="claude-code",
        profile_id=None,
        created_at=NOW,
        reason="apply",
        pinned=False,
        files=[
            make_file(path),
            SnapshotFile(
                path=str(path.parent / "missing.json"),
                existed=False,
                size=0,
                chunks=[],
                chunk_size=4,
            ),
        ],
        changes=[],
    )


def test_snapshot_roundtrips_json_and_views_hide_chunk_hashes(tmp_path: Path) -> None:
    snapshot = make_snapshot(tmp_path / "config.json")

    restored = Snapshot.model_validate(snapshot.model_dump(mode="json"))
    view = restored.to_view()
    summary = restored.to_summary()

    assert restored == snapshot
    assert isinstance(view, SnapshotView)
    assert isinstance(view.files[0], SnapshotFileView)
    assert not hasattr(view.files[0], "chunks")
    assert not hasattr(view.files[0], "chunk_size")
    assert isinstance(summary, SnapshotSummary)
    assert summary.file_count == 2
    assert summary.total_size == 6
    assert [file.existed for file in summary.files] == [True, False]


@pytest.mark.parametrize(
    "snapshot_id",
    ["not-a-uuid", str(uuid.uuid1()), str(uuid.uuid4()).upper()],
)
def test_snapshot_rejects_non_canonical_uuid4_ids(
    tmp_path: Path,
    snapshot_id: str,
) -> None:
    with pytest.raises(ValidationError):
        Snapshot(
            id=snapshot_id,
            tool_id="claude-code",
            created_at=NOW,
            reason="apply",
            files=[make_file(tmp_path / "config.json")],
        )


@pytest.mark.parametrize("suffix", ["config.json", "../config.json"])
def test_snapshot_file_rejects_relative_and_parent_paths(
    tmp_path: Path,
    suffix: str,
) -> None:
    with pytest.raises(ValidationError):
        SnapshotFile(
            path=suffix,
            existed=True,
            sha256=EMPTY_SHA256,
            size=0,
            mtime_ns=1,
            chunks=[],
            chunk_size=4,
        )


def test_empty_file_is_valid_without_chunks(tmp_path: Path) -> None:
    snapshot_file = SnapshotFile(
        path=str(tmp_path / "empty.txt"),
        existed=True,
        sha256=EMPTY_SHA256,
        size=0,
        mtime_ns=1,
        mode=0o600,
        chunks=[],
        chunk_size=4,
    )

    assert snapshot_file.existed is True
    assert snapshot_file.chunks == []
    assert snapshot_file.sha256 == EMPTY_SHA256


@pytest.mark.parametrize(
    "overrides",
    [
        {"existed": False, "sha256": EMPTY_SHA256},
        {"existed": False, "size": 3},
        {"existed": False, "mode": 0o600},
        {"existed": True, "sha256": None},
        {"existed": True, "mtime_ns": None},
        {"existed": True, "size": 5, "chunks": []},
        {"existed": True, "size": 0, "chunks": [EMPTY_SHA256]},
    ],
)
def test_snapshot_file_rejects_inconsistent_content(
    tmp_path: Path,
    overrides: dict[str, object],
) -> None:
    base: dict[str, object] = {
        "path": str(tmp_path / "config.json"),
        "existed": True,
        "sha256": EMPTY_SHA256,
        "size": 0,
        "mtime_ns": 1,
        "chunks": [],
        "chunk_size": 4,
    }
    base.update(overrides)

    with pytest.raises(ValidationError):
        SnapshotFile.model_validate(base)


def test_snapshot_rejects_duplicate_file_paths(tmp_path: Path) -> None:
    path = str(tmp_path / "config.json")
    with pytest.raises(ValidationError):
        Snapshot(
            id=str(uuid.uuid4()),
            tool_id="claude-code",
            created_at=NOW,
            reason="apply",
            files=[make_file(Path(path)), make_file(Path(path))],
        )


def test_snapshot_change_redacts_secret_and_truncates_long_values(tmp_path: Path) -> None:
    secret = "sk-" + "a" * 32
    change = SnapshotChange(
        path=str(tmp_path / "config.json"),
        field="api_key",
        action="set",
        before=f"Bearer {secret}",
        after="x" * (MAX_CHANGE_VALUE_LENGTH + 50),
    )

    assert secret not in (change.before or "")
    assert "****" in (change.before or "")
    assert change.after is not None
    assert len(change.after) == MAX_CHANGE_VALUE_LENGTH + 1
    assert change.after.endswith("…")


def test_snapshot_change_requires_absolute_path_and_non_blank_field(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValidationError):
        SnapshotChange(
            path="config.json",
            field="api_key",
            action="set",
            after="value",
        )
    with pytest.raises(ValidationError):
        SnapshotChange(
            path=str(tmp_path / "config.json"),
            field="   ",
            action="set",
            after="value",
        )


@pytest.mark.parametrize(
    "overrides",
    [
        {"existed": True, "data": None},
        {"existed": True, "mtime_ns": None},
        {"existed": False, "data": b"content"},
        {"existed": False, "mtime_ns": 1},
        {"existed": False, "mode": 0o600},
    ],
)
def test_snapshot_file_source_requires_bytes_for_existing_files(
    tmp_path: Path,
    overrides: dict[str, object],
) -> None:
    base: dict[str, object] = {
        "path": str(tmp_path / "config.json"),
        "existed": False,
    }
    base.update(overrides)

    with pytest.raises(ValidationError):
        SnapshotFileSource.model_validate(base)
