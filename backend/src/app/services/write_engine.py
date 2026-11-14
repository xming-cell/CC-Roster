"""原子写引擎: 冲突检查 → 预快照 → 原子写 → 回读校验 → 审计。

全程持有 `<data>/locks/write.lock`。任一文件失败或回读不一致时, 用本次预快照
已持有的同一份字节还原全部目标文件; 还原失败明确返回 `WRITE_RESTORE_FAILED`,
绝不报告成功。规则见 `specs/007-snapshot-kernel/spec.md`。
"""

from __future__ import annotations

import logging
import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from app.core.atomic import write_bytes_atomic
from app.core.errors import AppError, FileConflict, WriteConflict
from app.core.file_observation import (
    compare_observations,
    observe_file,
    read_file_with_bytes,
)
from app.core.locks import DEFAULT_LOCK_TIMEOUT_SECONDS, FileLock, LockTimeoutError
from app.repositories.audit import AuditRepository
from app.repositories.snapshots import SnapshotRepository
from app.schemas.audit import AuditResult
from app.schemas.snapshot import FileObservation, SnapshotFileSource
from app.schemas.write import (
    PlannedFile,
    WritePlan,
    WriteResult,
    WrittenFileView,
    sha256_hex,
)

logger = logging.getLogger(__name__)


def read_written_bytes(path: Path) -> bytes:
    """回读入口; 单独成函数便于测试注入损坏 / 读取失败。"""
    return path.read_bytes()


@dataclass(frozen=True)
class _CurrentFile:
    observation: FileObservation
    data: bytes | None
    mode: int | None


@dataclass(frozen=True)
class _SnapshotSource:
    path: str
    existed: bool
    data: bytes | None
    mtime_ns: int | None
    mode: int | None

    def to_model(self) -> SnapshotFileSource:
        if self.existed:
            assert self.data is not None
            assert self.mtime_ns is not None
            return SnapshotFileSource(
                path=self.path,
                existed=True,
                data=self.data,
                mtime_ns=self.mtime_ns,
                mode=self.mode,
            )
        return SnapshotFileSource(path=self.path, existed=False)


class _WriteFailure(Exception):
    def __init__(self, path: str, message: str) -> None:
        super().__init__(message)
        self.path = path


class _VerifyFailure(Exception):
    def __init__(self, path: str, expected: str, actual: str | None) -> None:
        actual_text = actual if actual is not None else "缺失"
        super().__init__(f"回读校验失败: {path} (期望 {expected}, 实际 {actual_text})")
        self.path = path
        self.expected = expected
        self.actual = actual


class _RestoreFailure(Exception):
    def __init__(self, path: str, expected: str | None, actual: str | None) -> None:
        super().__init__(f"还原失败: {path}")
        self.path = path
        self.expected = expected
        self.actual = actual


class WriteEngine:
    """把 `WritePlan` 落到磁盘; 仓储与审计通过构造参数注入。"""

    def __init__(
        self,
        snapshots: SnapshotRepository,
        audit: AuditRepository,
        *,
        write_lock_path: Path,
        lock_timeout: float = DEFAULT_LOCK_TIMEOUT_SECONDS,
    ) -> None:
        self._snapshots = snapshots
        self._audit = audit
        self._write_lock_path = Path(write_lock_path)
        self._lock_timeout = lock_timeout

    def apply(self, plan: WritePlan) -> WriteResult:
        try:
            with FileLock(self._write_lock_path, timeout=self._lock_timeout):
                return self._apply_locked(plan)
        except LockTimeoutError as exc:
            raise AppError(
                "WRITE_LOCK_TIMEOUT",
                "写入正在被其他操作占用, 请稍后重试",
                503,
            ) from exc

    def _apply_locked(self, plan: WritePlan) -> WriteResult:
        planned = sorted(plan.files, key=lambda item: item.path)

        current: dict[str, _CurrentFile] = {
            item.path: _read_current(Path(item.path)) for item in planned
        }
        conflicts = _detect_plan_conflicts(planned, current)
        if conflicts:
            self._record_safely(
                plan,
                snapshot_id=None,
                result="conflict",
                message=f"{len(conflicts)} 个文件在预览后发生变化, 已拒绝写入",
            )
            raise WriteConflict(conflicts)

        sources = [_source_from_current(item, current[item.path]) for item in planned]
        try:
            snapshot = self._snapshots.capture(
                tool_id=plan.tool_id,
                profile_id=plan.profile_id,
                files=[source.to_model() for source in sources],
                reason="apply",
                changes=[change for item in planned for change in item.changes],
            )
        except AppError as exc:
            self._record_safely(
                plan,
                snapshot_id=None,
                result="failed",
                message=exc.message,
            )
            raise

        written: list[WrittenFileView] = []
        try:
            for item in planned:
                conflict = compare_observations(
                    item.observation,
                    observe_file(Path(item.path)),
                )
                if conflict is not None:
                    raise WriteConflict([conflict])
                try:
                    write_bytes_atomic(Path(item.path), item.expected_bytes)
                except OSError as exc:
                    raise _WriteFailure(item.path, "目标文件原子写入失败") from exc
                written.append(
                    WrittenFileView(
                        path=item.path,
                        action="created" if not item.observation.exists else "updated",
                        sha256=sha256_hex(item.expected_bytes),
                        size=len(item.expected_bytes),
                    )
                )
            self._verify_written(planned)
        except WriteConflict as exc:
            self._restore_or_raise(plan, sources, snapshot_id=snapshot.id)
            self._record_safely(
                plan,
                snapshot_id=snapshot.id,
                result="conflict",
                message=exc.message,
            )
            raise
        except _VerifyFailure as exc:
            self._restore_or_raise(plan, sources, snapshot_id=snapshot.id)
            self._record_safely(
                plan,
                snapshot_id=snapshot.id,
                result="failed",
                message=str(exc),
            )
            raise AppError("WRITE_VERIFY_FAILED", str(exc), 500) from exc
        except _WriteFailure as exc:
            self._restore_or_raise(plan, sources, snapshot_id=snapshot.id)
            self._record_safely(
                plan,
                snapshot_id=snapshot.id,
                result="failed",
                message=f"文件写入失败: {exc.path}",
            )
            raise AppError("WRITE_FAILED", f"文件写入失败: {exc.path}", 500) from exc

        try:
            entry = self._audit.record(
                action="apply",
                tool_id=plan.tool_id,
                profile_id=plan.profile_id,
                snapshot_id=snapshot.id,
                files=[item.path for item in planned],
                fields=_plan_fields(planned),
                result="success",
                message=f"已应用 {len(planned)} 个文件",
            )
        except AppError as exc:
            self._restore_or_raise(plan, sources, snapshot_id=snapshot.id)
            raise AppError(
                "AUDIT_WRITE_FAILED",
                "审计记录写入失败, 目标文件已还原",
                500,
            ) from exc

        return WriteResult(
            snapshot_id=snapshot.id,
            audit_id=entry.id,
            files=written,
        )

    def _verify_written(self, planned: Sequence[PlannedFile]) -> None:
        for item in planned:
            try:
                actual = read_written_bytes(Path(item.path))
            except OSError:
                actual_bytes: bytes | None = None
            else:
                actual_bytes = actual
            expected_hash = sha256_hex(item.expected_bytes)
            actual_hash = None if actual_bytes is None else sha256_hex(actual_bytes)
            if actual_bytes != item.expected_bytes:
                raise _VerifyFailure(item.path, expected_hash, actual_hash)

    def _restore_or_raise(
        self,
        plan: WritePlan,
        sources: Sequence[_SnapshotSource],
        *,
        snapshot_id: str | None,
    ) -> None:
        try:
            _restore_sources(sources)
        except _RestoreFailure as exc:
            message = (
                f"写入失败后还原失败: {exc.path} "
                f"(期望 {exc.expected or '缺失'}, 实际 {exc.actual or '缺失'})"
            )
            self._record_safely(
                plan,
                snapshot_id=snapshot_id,
                result="failed",
                message=message,
            )
            raise AppError("WRITE_RESTORE_FAILED", message, 500) from exc

    def _record_safely(
        self,
        plan: WritePlan,
        *,
        snapshot_id: str | None,
        result: AuditResult,
        message: str,
    ) -> None:
        try:
            self._audit.record(
                action="apply",
                tool_id=plan.tool_id,
                profile_id=plan.profile_id,
                snapshot_id=snapshot_id,
                files=[item.path for item in plan.files],
                fields=_plan_fields(plan.files),
                result=result,
                message=message,
            )
        except Exception:
            logger.warning("审计记录写入失败, 已保留主错误", exc_info=True)


def _detect_plan_conflicts(
    planned: Sequence[PlannedFile],
    current: dict[str, _CurrentFile],
) -> list[FileConflict]:
    conflicts: list[FileConflict] = []
    for item in planned:
        conflict = compare_observations(item.observation, current[item.path].observation)
        if conflict is not None:
            conflicts.append(conflict)
    return conflicts


def _plan_fields(planned: Sequence[PlannedFile]) -> list[str]:
    return [f"{item.path}.{change.field}" for item in planned for change in item.changes]


def _read_current(path: Path) -> _CurrentFile:
    try:
        snapshot_data = read_file_with_bytes(path)
    except OSError as exc:
        raise AppError("WRITE_FAILED", f"无法读取目标文件: {path}", 500) from exc
    return _CurrentFile(
        observation=snapshot_data.observation,
        data=snapshot_data.data,
        mode=snapshot_data.mode,
    )


def _source_from_current(item: PlannedFile, current: _CurrentFile) -> _SnapshotSource:
    if current.observation.exists:
        return _SnapshotSource(
            path=item.path,
            existed=True,
            data=current.data,
            mtime_ns=current.observation.mtime_ns,
            mode=current.mode,
        )
    return _SnapshotSource(
        path=item.path,
        existed=False,
        data=None,
        mtime_ns=None,
        mode=None,
    )


def _restore_sources(sources: Sequence[_SnapshotSource]) -> None:
    for source in sources:
        path = Path(source.path)
        if source.existed:
            assert source.data is not None
            try:
                current = read_written_bytes(path)
            except FileNotFoundError:
                current = None
            except OSError as exc:
                raise _RestoreFailure(path=source.path, expected=None, actual=None) from exc
            if current == source.data:
                continue
            try:
                write_bytes_atomic(
                    path,
                    source.data,
                    mode=source.mode if os.name != "nt" else None,
                )
            except OSError as exc:
                raise _RestoreFailure(
                    path=source.path,
                    expected=sha256_hex(source.data),
                    actual=None if current is None else sha256_hex(current),
                ) from exc
        else:
            try:
                path.unlink()
            except FileNotFoundError:
                continue
            except OSError as exc:
                raise _RestoreFailure(path=source.path, expected=None, actual=None) from exc

    for source in sources:
        path = Path(source.path)
        try:
            actual = read_written_bytes(path)
        except FileNotFoundError:
            actual = None
        except OSError as exc:
            raise _RestoreFailure(path=source.path, expected=None, actual=None) from exc
        expected = sha256_hex(source.data) if source.data is not None else None
        if source.existed:
            if source.data is None or actual != source.data:
                raise _RestoreFailure(
                    path=source.path,
                    expected=expected,
                    actual=None if actual is None else sha256_hex(actual),
                )
        elif actual is not None:
            raise _RestoreFailure(
                path=source.path,
                expected=None,
                actual=sha256_hex(actual),
            )
