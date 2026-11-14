"""外部改动检测内核, 规则见 `specs/007-snapshot-kernel/spec.md`。

观察只读、不落库; 写引擎在持有写锁后用它比较预览时的值。内容 hash 相同、仅
mtime 变化不算冲突。冲突详情由调用方映射成 409 `WRITE_CONFLICT`。
"""

import hashlib
import os
import stat
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from app.core.errors import AppError, FileConflict, FileConflictReason, WriteConflict
from app.core.paths import resolve_absolute_path
from app.schemas.snapshot import FileObservation

_READ_CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True)
class FileSnapshotData:
    """一次读取同时得到观察值、字节与权限; 写引擎用它避免 TOCTOU。"""

    observation: FileObservation
    data: bytes | None
    mode: int | None


def read_file_with_bytes(path: str | Path) -> FileSnapshotData:
    """读取文件字节与 stat; 文件缺失返回 `exists=false`。读取失败抛 OSError。"""
    resolved = resolve_absolute_path(Path(path), label="文件路径")
    try:
        with resolved.open("rb") as handle:
            file_stat = os.fstat(handle.fileno())
            data = handle.read()
    except FileNotFoundError:
        return FileSnapshotData(
            observation=FileObservation(
                path=str(resolved),
                exists=False,
                sha256=None,
                size=0,
                mtime_ns=None,
            ),
            data=None,
            mode=None,
        )
    return FileSnapshotData(
        observation=FileObservation(
            path=str(resolved),
            exists=True,
            sha256=hashlib.sha256(data).hexdigest(),
            size=len(data),
            mtime_ns=file_stat.st_mtime_ns,
        ),
        data=data,
        mode=None if os.name == "nt" else stat.S_IMODE(file_stat.st_mode),
    )


def observe_file(path: str | Path) -> FileObservation:
    """只读观察一个文件; 解析 symlink, 缺失返回 `exists=false`。"""
    resolved = resolve_absolute_path(Path(path), label="文件路径")
    try:
        with resolved.open("rb") as handle:
            file_stat = os.fstat(handle.fileno())
            hasher = hashlib.sha256()
            size = 0
            while True:
                chunk = handle.read(_READ_CHUNK_SIZE)
                if not chunk:
                    break
                hasher.update(chunk)
                size += len(chunk)
    except FileNotFoundError:
        return FileObservation(
            path=str(resolved),
            exists=False,
            sha256=None,
            size=0,
            mtime_ns=None,
        )
    except OSError as exc:
        raise AppError(
            "FILE_OBSERVE_FAILED",
            f"无法读取文件状态: {resolved}",
            500,
        ) from exc

    return FileObservation(
        path=str(resolved),
        exists=True,
        sha256=hasher.hexdigest(),
        size=size,
        mtime_ns=file_stat.st_mtime_ns,
    )


def compare_observations(
    expected: FileObservation,
    actual: FileObservation,
) -> FileConflict | None:
    """比较预览值与当前值; 仅 mtime 变化不算冲突。"""
    reason: FileConflictReason | None = None
    if expected.exists and not actual.exists:
        reason = "MISSING"
    elif not expected.exists and actual.exists:
        reason = "CREATED"
    elif expected.exists and actual.exists and expected.sha256 != actual.sha256:
        reason = "CONTENT_CHANGED"
    if reason is None:
        return None
    return FileConflict(
        path=expected.path,
        reason=reason,
        expected=expected,
        actual=actual,
    )


def detect_conflicts(
    observations: Sequence[FileObservation],
) -> list[FileConflict]:
    """重新观察每个文件, 返回所有冲突; 不写盘、不抛业务异常。"""
    conflicts: list[FileConflict] = []
    for expected in observations:
        conflict = compare_observations(expected, observe_file(Path(expected.path)))
        if conflict is not None:
            conflicts.append(conflict)
    return conflicts


def ensure_observations_current(
    observations: Sequence[FileObservation],
) -> None:
    """写前最终校验; 任一文件变化就抛 `WriteConflict` (409)。"""
    conflicts = detect_conflicts(observations)
    if conflicts:
        raise WriteConflict(conflicts)
