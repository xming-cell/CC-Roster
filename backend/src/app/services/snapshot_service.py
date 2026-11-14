"""快照用例: 列表 / 详情 / pin / 回滚。

回滚前必须完整校验目标快照的所有块, 再为当前状态生成预回滚快照; 恢复后逐字节
回读。任一失败都用预回滚快照还原, 返回 `ROLLBACK_FAILED`。本层不依赖 FastAPI。
"""

from __future__ import annotations

import logging
import os
import uuid
from collections.abc import Sequence
from pathlib import Path

from app.core.atomic import write_bytes_atomic
from app.core.errors import AppError
from app.core.file_observation import FileSnapshotData, read_file_with_bytes
from app.core.locks import DEFAULT_LOCK_TIMEOUT_SECONDS, FileLock, LockTimeoutError
from app.repositories.audit import AuditRepository
from app.repositories.snapshots import SnapshotRepository
from app.schemas.audit import AuditResult
from app.schemas.snapshot import (
    RestoredFileView,
    RollbackResponse,
    Snapshot,
    SnapshotFile,
    SnapshotFileSource,
    SnapshotListResponse,
    SnapshotView,
)

logger = logging.getLogger(__name__)


class _RollbackError(Exception):
    def __init__(self, path: str, message: str) -> None:
        super().__init__(message)
        self.path = path


class SnapshotService:
    """快照的用例边界; 仓储与审计通过构造参数注入。"""

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

    def list_snapshots(
        self,
        *,
        tool_id: str | None = None,
        limit: int | None = None,
    ) -> SnapshotListResponse:
        listing = self._snapshots.list_snapshots(tool_id=tool_id, limit=limit)
        return SnapshotListResponse(
            snapshots=listing.snapshots,
            retention_limit=self._snapshots.retention_limit,
            warnings=listing.warnings,
        )

    def get_snapshot(self, snapshot_id: str) -> SnapshotView:
        _require_uuid4(snapshot_id)
        snapshot = self._snapshots.get(snapshot_id)
        if snapshot is None:
            raise _not_found(snapshot_id)
        return snapshot.to_view()

    def set_pinned(self, snapshot_id: str, pinned: bool) -> SnapshotView:
        _require_uuid4(snapshot_id)
        return self._snapshots.set_pinned(snapshot_id, pinned).to_view()

    def rollback(self, snapshot_id: str) -> RollbackResponse:
        _require_uuid4(snapshot_id)
        try:
            with FileLock(self._write_lock_path, timeout=self._lock_timeout):
                return self._rollback_locked(snapshot_id)
        except LockTimeoutError as exc:
            raise AppError(
                "WRITE_LOCK_TIMEOUT",
                "写入正在被其他操作占用, 请稍后重试",
                503,
            ) from exc

    def _rollback_locked(self, snapshot_id: str) -> RollbackResponse:
        target = self._snapshots.get(snapshot_id)
        if target is None:
            raise _not_found(snapshot_id)

        target_bytes = {
            file.path: self._snapshots.load_file_bytes(target, file)
            for file in target.files
            if file.existed
        }

        pre_sources: list[SnapshotFileSource] = []
        for snapshot_file in _sorted_files(target.files):
            try:
                current = read_file_with_bytes(Path(snapshot_file.path))
            except OSError as exc:
                message = f"无法读取回滚目标当前状态: {snapshot_file.path}"
                self._record_safely(target, snapshot_id=target.id, result="failed", message=message)
                raise AppError("ROLLBACK_FAILED", message, 500) from exc
            pre_sources.append(_to_source(snapshot_file.path, current))

        try:
            pre_rollback = self._snapshots.capture(
                tool_id=target.tool_id,
                profile_id=target.profile_id,
                files=pre_sources,
                reason="rollback",
                changes=[],
                protected_ids=[target.id],
            )
        except AppError as exc:
            self._record_safely(
                target,
                snapshot_id=target.id,
                result="failed",
                message=exc.message,
            )
            raise

        try:
            restored = self._restore_snapshot(target, target_bytes)
        except _RollbackError as exc:
            restore_ok = self._restore_quietly(pre_rollback)
            message = str(exc)
            if not restore_ok:
                message = f"{message}; 预回滚快照还原同样失败"
            self._record_safely(target, snapshot_id=target.id, result="failed", message=message)
            raise AppError("ROLLBACK_FAILED", message, 500) from exc

        try:
            self._audit.record(
                action="rollback",
                tool_id=target.tool_id,
                profile_id=target.profile_id,
                snapshot_id=target.id,
                files=[file.path for file in target.files],
                fields=[f"{change.path}.{change.field}" for change in target.changes],
                result="success",
                message=f"已回滚 {len(target.files)} 个文件",
            )
        except AppError as exc:
            restore_ok = self._restore_quietly(pre_rollback)
            message = "审计记录写入失败, 目标文件已还原"
            if not restore_ok:
                message = "审计记录写入失败, 且预回滚快照还原失败"
            raise AppError("AUDIT_WRITE_FAILED", message, 500) from exc

        return RollbackResponse(
            snapshot_id=target.id,
            pre_rollback_snapshot_id=pre_rollback.id,
            files=restored,
        )

    def _restore_snapshot(
        self,
        snapshot: Snapshot,
        data_by_path: dict[str, bytes],
    ) -> list[RestoredFileView]:
        results: list[RestoredFileView] = []
        for snapshot_file in _sorted_files(snapshot.files):
            path = Path(snapshot_file.path)
            current = _read_optional(path, snapshot_file.path)
            if snapshot_file.existed:
                data = data_by_path[snapshot_file.path]
                if current == data:
                    action = "unchanged"
                else:
                    try:
                        write_bytes_atomic(
                            path,
                            data,
                            mode=(
                                snapshot_file.mode
                                if os.name != "nt" and snapshot_file.mode is not None
                                else None
                            ),
                        )
                    except OSError as exc:
                        raise _RollbackError(
                            snapshot_file.path,
                            f"恢复文件失败: {snapshot_file.path}",
                        ) from exc
                    action = "restored"
            elif current is None:
                action = "unchanged"
            else:
                try:
                    path.unlink()
                except OSError as exc:
                    raise _RollbackError(
                        snapshot_file.path,
                        f"删除多余文件失败: {snapshot_file.path}",
                    ) from exc
                action = "deleted"

            results.append(
                RestoredFileView(
                    path=snapshot_file.path,
                    action=action,
                    sha256=snapshot_file.sha256,
                    size=snapshot_file.size,
                )
            )

        for snapshot_file in _sorted_files(snapshot.files):
            actual = _read_optional(Path(snapshot_file.path), snapshot_file.path)
            expected = data_by_path.get(snapshot_file.path)
            if snapshot_file.existed:
                if actual != expected:
                    raise _RollbackError(
                        snapshot_file.path,
                        f"回滚后回读校验失败: {snapshot_file.path}",
                    )
            elif actual is not None:
                raise _RollbackError(
                    snapshot_file.path,
                    f"回滚后文件仍然存在: {snapshot_file.path}",
                )
        return results

    def _restore_quietly(self, snapshot: Snapshot) -> bool:
        try:
            data_by_path = {
                file.path: self._snapshots.load_file_bytes(snapshot, file)
                for file in snapshot.files
                if file.existed
            }
            self._restore_snapshot(snapshot, data_by_path)
        except (AppError, _RollbackError):
            logger.warning("预回滚快照还原失败: %s", snapshot.id, exc_info=True)
            return False
        return True

    def _record_safely(
        self,
        snapshot: Snapshot,
        *,
        snapshot_id: str | None,
        result: AuditResult,
        message: str,
    ) -> None:
        try:
            self._audit.record(
                action="rollback",
                tool_id=snapshot.tool_id,
                profile_id=snapshot.profile_id,
                snapshot_id=snapshot_id,
                files=[file.path for file in snapshot.files],
                fields=[f"{change.path}.{change.field}" for change in snapshot.changes],
                result=result,
                message=message,
            )
        except Exception:
            logger.warning("审计记录写入失败, 已保留主错误", exc_info=True)


def _require_uuid4(snapshot_id: str) -> None:
    try:
        parsed = uuid.UUID(snapshot_id)
    except ValueError as exc:
        raise AppError("VALIDATION_ERROR", "快照 id 必须是 UUID4", 422) from exc
    if parsed.version != 4 or str(parsed) != snapshot_id:
        raise AppError("VALIDATION_ERROR", "快照 id 必须是规范小写的 UUID4", 422)


def _not_found(snapshot_id: str) -> AppError:
    return AppError("SNAPSHOT_NOT_FOUND", f"快照不存在: {snapshot_id}", 404)


def _sorted_files(files: Sequence[SnapshotFile]) -> list[SnapshotFile]:
    return sorted(files, key=lambda file: file.path)


def _read_optional(path: Path, label: str) -> bytes | None:
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise _RollbackError(label, f"无法读取文件: {label}") from exc


def _to_source(path: str, current: FileSnapshotData) -> SnapshotFileSource:
    if current.observation.exists:
        assert current.data is not None
        assert current.observation.mtime_ns is not None
        return SnapshotFileSource(
            path=path,
            existed=True,
            data=current.data,
            mtime_ns=current.observation.mtime_ns,
            mode=current.mode,
        )
    return SnapshotFileSource(path=path, existed=False)
