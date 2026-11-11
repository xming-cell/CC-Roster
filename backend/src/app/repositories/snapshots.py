"""快照仓储: 内容寻址分块存储、保留策略与 pin。

布局见 ADR-007 / `specs/007-snapshot-kernel/spec.md`:

- `<data>/snapshots/<snapshot_id>/meta.json` (原子写)
- `<data>/snapshots/objects/<sha256[:2]>/<sha256>` (内容寻址块)
- `<data>/snapshots/.lock` (`FileLock`)

读取不创建目录; 捕获 / pin / 清理在文件锁内串行化。原始块只供内部恢复,
任何方法都不把块内容返回给 API 层。
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import os
import shutil
import stat
import uuid
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from app.core.atomic import write_bytes_atomic, write_json_atomic
from app.core.clock import utc_now
from app.core.errors import AppError
from app.core.locks import DEFAULT_LOCK_TIMEOUT_SECONDS, FileLock, LockTimeoutError
from app.core.paths import resolve_absolute_path
from app.core.redaction import redact_text
from app.schemas.snapshot import (
    SNAPSHOT_SCHEMA_VERSION,
    Snapshot,
    SnapshotChange,
    SnapshotFile,
    SnapshotFileSource,
    SnapshotReason,
    SnapshotSummary,
    SnapshotWarning,
    SnapshotWarningCode,
)

logger = logging.getLogger(__name__)

SNAPSHOTS_DIR_NAME = "snapshots"
OBJECTS_DIR_NAME = "objects"
META_FILE_NAME = "meta.json"
LOCK_FILE_NAME = ".lock"
DEFAULT_CHUNK_SIZE = 1024 * 1024
MIN_RETENTION_LIMIT = 1
MAX_RETENTION_LIMIT = 1000


@dataclass(frozen=True)
class SnapshotListing:
    """列表结果: 可读快照摘要 + 被跳过的损坏快照提示。"""

    snapshots: list[SnapshotSummary]
    warnings: list[SnapshotWarning]


class _MetaReadError(Exception):
    """单份 meta 不可读; 列表降级为 warning, 详情转成 SNAPSHOT_UNREADABLE。"""

    def __init__(self, code: SnapshotWarningCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _is_uuid4(value: str) -> bool:
    try:
        parsed = uuid.UUID(value)
    except ValueError:
        return False
    return parsed.version == 4 and str(parsed) == value


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class SnapshotRepository:
    """快照的数据访问边界; 业务编排留给 service / write engine。"""

    def __init__(
        self,
        data_dir: Path,
        *,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        retention_limit: int = 20,
        lock_timeout: float = DEFAULT_LOCK_TIMEOUT_SECONDS,
    ) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if not MIN_RETENTION_LIMIT <= retention_limit <= MAX_RETENTION_LIMIT:
            raise ValueError(
                f"retention_limit must be between {MIN_RETENTION_LIMIT} and {MAX_RETENTION_LIMIT}"
            )
        self._data_dir = Path(data_dir)
        self._root = self._data_dir / SNAPSHOTS_DIR_NAME
        self._objects_dir = self._root / OBJECTS_DIR_NAME
        self._lock_path = self._root / LOCK_FILE_NAME
        self._chunk_size = chunk_size
        self._retention_limit = retention_limit
        self._lock_timeout = lock_timeout

    @property
    def root(self) -> Path:
        return self._root

    @property
    def objects_dir(self) -> Path:
        return self._objects_dir

    @property
    def lock_path(self) -> Path:
        return self._lock_path

    @property
    def chunk_size(self) -> int:
        return self._chunk_size

    @property
    def retention_limit(self) -> int:
        return self._retention_limit

    def capture(
        self,
        *,
        tool_id: str,
        files: Sequence[SnapshotFileSource],
        reason: SnapshotReason,
        profile_id: str | None = None,
        changes: Sequence[SnapshotChange] = (),
        created_at: datetime | None = None,
        protected_ids: Collection[str] = (),
    ) -> Snapshot:
        """用调用方提供的同一份字节创建快照, 并按保留策略清理旧快照。

        目标文件路径必须绝对、无 `..`、无重复; symlink 在这里解析。所有对象块
        先于 meta 写入, 写 meta 失败时删除空的快照目录, 对象留给下次清理回收。
        """
        if not tool_id.strip():
            raise AppError("SNAPSHOT_INVALID", "tool_id 不能为空", 400)

        resolved_sources: list[tuple[Path, SnapshotFileSource]] = []
        seen_paths: set[str] = set()
        for source in files:
            try:
                resolved = resolve_absolute_path(Path(source.path), label="快照文件路径")
            except ValueError as exc:
                raise AppError(
                    "SNAPSHOT_INVALID",
                    f"快照文件路径不合法: {source.path}",
                    400,
                ) from exc
            key = str(resolved)
            if key in seen_paths:
                raise AppError("SNAPSHOT_INVALID", f"快照文件路径重复: {key}", 400)
            seen_paths.add(key)
            resolved_sources.append((resolved, source))
        resolved_sources.sort(key=lambda item: str(item[0]))

        try:
            self._ensure_store_dirs()
        except OSError as exc:
            raise AppError(
                "SNAPSHOT_WRITE_FAILED",
                "无法创建快照存储目录",
                500,
            ) from exc

        try:
            with FileLock(self._lock_path, timeout=self._lock_timeout):
                return self._capture_locked(
                    tool_id=tool_id,
                    profile_id=profile_id,
                    reason=reason,
                    resolved_sources=resolved_sources,
                    changes=changes,
                    created_at=created_at,
                    protected_ids=protected_ids,
                )
        except LockTimeoutError as exc:
            raise AppError(
                "SNAPSHOT_LOCK_TIMEOUT",
                "快照存储正在被其他操作占用, 请稍后重试",
                503,
            ) from exc

    def _capture_locked(
        self,
        *,
        tool_id: str,
        profile_id: str | None,
        reason: SnapshotReason,
        resolved_sources: Sequence[tuple[Path, SnapshotFileSource]],
        changes: Sequence[SnapshotChange],
        created_at: datetime | None,
        protected_ids: Collection[str],
    ) -> Snapshot:
        snapshot_files: list[SnapshotFile] = []
        for path, source in resolved_sources:
            snapshot_files.append(self._store_source(path, source))

        snapshot = Snapshot(
            id=str(uuid.uuid4()),
            tool_id=tool_id,
            profile_id=profile_id,
            created_at=created_at if created_at is not None else utc_now(),
            reason=reason,
            pinned=False,
            files=snapshot_files,
            changes=self._redact_changes(changes),
        )

        try:
            self._write_meta(snapshot)
        except AppError:
            self._discard_snapshot_dir(snapshot.id)
            raise

        try:
            self._prune_locked(
                tool_id,
                protected_ids=set(protected_ids) | {snapshot.id},
            )
        except OSError:
            logger.warning(
                "快照保留清理失败, 已保留本次快照: %s",
                snapshot.id,
                exc_info=True,
            )
        return snapshot

    def _store_source(self, path: Path, source: SnapshotFileSource) -> SnapshotFile:
        if not source.existed:
            return SnapshotFile(
                path=str(path),
                existed=False,
                sha256=None,
                size=0,
                mtime_ns=None,
                mode=None,
                chunks=[],
                chunk_size=self._chunk_size,
            )

        data = source.data
        mtime_ns = source.mtime_ns
        if data is None or mtime_ns is None:
            raise AppError(
                "SNAPSHOT_INVALID",
                f"存在的文件缺少内容或 mtime_ns: {path}",
                400,
            )

        chunk_hashes: list[str] = []
        for start in range(0, len(data), self._chunk_size):
            chunk = data[start : start + self._chunk_size]
            digest = _sha256(chunk)
            self._write_object(digest, chunk)
            chunk_hashes.append(digest)

        return SnapshotFile(
            path=str(path),
            existed=True,
            sha256=_sha256(data),
            size=len(data),
            mtime_ns=mtime_ns,
            mode=source.mode,
            chunks=chunk_hashes,
            chunk_size=self._chunk_size,
        )

    def _write_object(self, digest: str, data: bytes) -> None:
        object_path = self._object_path(digest)
        if object_path.is_file():
            return
        try:
            shard = object_path.parent
            shard.mkdir(parents=True, exist_ok=True)
            if os.name != "nt":
                shard.chmod(0o700)
            write_bytes_atomic(object_path, data, mode=0o600)
        except OSError as exc:
            raise AppError(
                "SNAPSHOT_WRITE_FAILED",
                f"快照内容块写入失败: {digest}",
                500,
            ) from exc

    def _redact_changes(
        self,
        changes: Sequence[SnapshotChange],
    ) -> list[SnapshotChange]:
        # 模型构造时已脱敏一次; 仓储写 meta 前再脱敏, 防止调用方绕过模型校验。
        return [
            SnapshotChange(
                path=change.path,
                field=change.field,
                action=change.action,
                before=None if change.before is None else redact_text(change.before),
                after=None if change.after is None else redact_text(change.after),
            )
            for change in changes
        ]

    def list_snapshots(
        self,
        *,
        tool_id: str | None = None,
        limit: int | None = None,
    ) -> SnapshotListing:
        """按创建时间倒序列出可读快照; 损坏 / 未知版本的快照跳过并附 warning。"""
        if limit is not None and limit < 1:
            raise ValueError("limit must be positive")

        try:
            entries = sorted(self._root.iterdir(), key=lambda item: item.name)
        except FileNotFoundError:
            return SnapshotListing(snapshots=[], warnings=[])
        except OSError as exc:
            raise AppError(
                "SNAPSHOT_STORE_UNREADABLE",
                f"快照存储无法读取: {self._root}",
                500,
            ) from exc

        summaries: list[SnapshotSummary] = []
        warnings: list[SnapshotWarning] = []
        for entry in entries:
            if entry.name in {OBJECTS_DIR_NAME, LOCK_FILE_NAME}:
                continue
            if not entry.is_dir():
                continue
            if not _is_uuid4(entry.name):
                warnings.append(
                    SnapshotWarning(
                        code="SNAPSHOT_UNREADABLE",
                        message=f"快照目录名不是规范 UUID, 已跳过: {entry.name}",
                    )
                )
                continue
            try:
                snapshot = self._read_meta(entry.name)
            except _MetaReadError as exc:
                warnings.append(SnapshotWarning(code=exc.code, message=exc.message))
                continue
            if tool_id is not None and snapshot.tool_id != tool_id:
                continue
            summaries.append(snapshot.to_summary())

        summaries.sort(key=lambda item: (item.created_at, item.id), reverse=True)
        if limit is not None:
            summaries = summaries[:limit]
        return SnapshotListing(snapshots=summaries, warnings=warnings)

    def get(
        self,
        snapshot_id: str,
        *,
        verify_content: bool = True,
    ) -> Snapshot | None:
        """读取详情; 未知 id 返回 None, 损坏 / 未知版本抛 SNAPSHOT_UNREADABLE。"""
        snapshot = self._get_existing(snapshot_id)
        if snapshot is None:
            return None
        if verify_content:
            self._verify_snapshot(snapshot)
        return snapshot

    def load_file_bytes(self, snapshot: Snapshot, snapshot_file: SnapshotFile) -> bytes:
        """读取并校验单个文件的所有块; 只在回滚 / 测试内部使用。"""
        if not snapshot_file.existed:
            raise ValueError("不存在的文件没有可恢复内容")
        return self._load_file_bytes(snapshot.id, snapshot_file)

    def set_pinned(self, snapshot_id: str, pinned: bool) -> Snapshot:
        """幂等设置 pin; 只重写 meta, 不改变时间、不复制块。"""
        if not _is_uuid4(snapshot_id):
            raise AppError("SNAPSHOT_NOT_FOUND", f"快照不存在: {snapshot_id}", 404)
        try:
            with FileLock(self._lock_path, timeout=self._lock_timeout):
                snapshot = self._get_existing(snapshot_id)
                if snapshot is None:
                    raise AppError(
                        "SNAPSHOT_NOT_FOUND",
                        f"快照不存在: {snapshot_id}",
                        404,
                    )
                if snapshot.pinned == pinned:
                    return snapshot
                updated = snapshot.model_copy(update={"pinned": pinned})
                self._write_meta(updated)
                return updated
        except LockTimeoutError as exc:
            raise AppError(
                "SNAPSHOT_LOCK_TIMEOUT",
                "快照存储正在被其他操作占用, 请稍后重试",
                503,
            ) from exc

    def prune(
        self,
        *,
        tool_id: str,
        protected_ids: Collection[str] = (),
    ) -> list[str]:
        """公开的清理入口; 返回被删除的快照 id。"""
        try:
            self._root.stat()
        except FileNotFoundError:
            return []
        except OSError as exc:
            raise AppError(
                "SNAPSHOT_STORE_UNREADABLE",
                f"快照存储无法读取: {self._root}",
                500,
            ) from exc

        try:
            with FileLock(self._lock_path, timeout=self._lock_timeout):
                return self._prune_locked(tool_id, protected_ids=protected_ids)
        except LockTimeoutError as exc:
            raise AppError(
                "SNAPSHOT_LOCK_TIMEOUT",
                "快照存储正在被其他操作占用, 请稍后重试",
                503,
            ) from exc

    def _prune_locked(
        self,
        tool_id: str,
        *,
        protected_ids: Collection[str],
    ) -> list[str]:
        snapshots = self._list_tool_snapshots(tool_id)
        snapshots.sort(key=lambda item: (item.created_at, item.id))
        protected = set(protected_ids)
        remaining = len(snapshots)
        deleted: list[str] = []

        for snapshot in snapshots:
            if remaining <= self._retention_limit:
                break
            if snapshot.pinned or snapshot.id in protected:
                continue
            try:
                shutil.rmtree(self._snapshot_dir(snapshot.id))
            except FileNotFoundError:
                remaining -= 1
                deleted.append(snapshot.id)
                continue
            except OSError:
                logger.warning(
                    "快照清理失败, 保留该快照: %s",
                    snapshot.id,
                    exc_info=True,
                )
                continue
            remaining -= 1
            deleted.append(snapshot.id)

        self._collect_orphan_objects()
        return deleted

    def _list_tool_snapshots(self, tool_id: str) -> list[Snapshot]:
        snapshots: list[Snapshot] = []
        for entry in sorted(self._root.iterdir(), key=lambda item: item.name):
            if entry.name in {OBJECTS_DIR_NAME, LOCK_FILE_NAME}:
                continue
            if not entry.is_dir() or not _is_uuid4(entry.name):
                continue
            try:
                snapshot = self._read_meta(entry.name)
            except _MetaReadError:
                # 损坏的快照不参与自动清理, 避免误删仍可人工恢复的数据。
                continue
            if snapshot.tool_id == tool_id:
                snapshots.append(snapshot)
        return snapshots

    def _collect_orphan_objects(self) -> None:
        try:
            referenced = self._referenced_chunks()
            shards = list(self._objects_dir.iterdir())
        except FileNotFoundError:
            return
        except OSError:
            logger.warning("快照对象清理扫描失败, 本次不回收", exc_info=True)
            return

        for shard in shards:
            if not shard.is_dir():
                continue
            try:
                objects = list(shard.iterdir())
            except OSError:
                logger.warning("快照对象分片无法读取: %s", shard, exc_info=True)
                continue
            for object_path in objects:
                if object_path.name in referenced or not object_path.is_file():
                    continue
                try:
                    object_path.unlink()
                except OSError:
                    logger.warning(
                        "孤立快照对象删除失败: %s",
                        object_path,
                        exc_info=True,
                    )
            with contextlib.suppress(OSError):
                shard.rmdir()

    def _referenced_chunks(self) -> set[str]:
        referenced: set[str] = set()
        for entry in self._root.iterdir():
            if entry.name in {OBJECTS_DIR_NAME, LOCK_FILE_NAME}:
                continue
            if not entry.is_dir() or not _is_uuid4(entry.name):
                continue
            try:
                snapshot = self._read_meta(entry.name)
            except _MetaReadError as exc:
                # 无法确认损坏快照的引用时, 宁可放弃回收, 也不误删对象。
                raise OSError(f"无法确认快照引用: {entry.name}") from exc
            for snapshot_file in snapshot.files:
                referenced.update(snapshot_file.chunks)
        return referenced

    def _get_existing(self, snapshot_id: str) -> Snapshot | None:
        if not _is_uuid4(snapshot_id):
            return None
        try:
            directory_stat = self._snapshot_dir(snapshot_id).stat()
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise AppError(
                "SNAPSHOT_STORE_UNREADABLE",
                f"快照存储无法读取: {self._snapshot_dir(snapshot_id)}",
                500,
            ) from exc
        if not stat.S_ISDIR(directory_stat.st_mode):
            return None
        try:
            return self._read_meta(snapshot_id)
        except _MetaReadError as exc:
            raise AppError("SNAPSHOT_UNREADABLE", exc.message, 500) from exc

    def _read_meta(self, snapshot_id: str) -> Snapshot:
        meta_path = self._snapshot_dir(snapshot_id) / META_FILE_NAME
        try:
            text = meta_path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise _MetaReadError(
                "SNAPSHOT_UNREADABLE",
                f"快照缺少 meta.json: {snapshot_id}",
            ) from exc
        except UnicodeDecodeError as exc:
            raise _MetaReadError(
                "SNAPSHOT_UNREADABLE",
                f"快照 meta.json 不是 UTF-8: {snapshot_id}",
            ) from exc
        except OSError as exc:
            raise _MetaReadError(
                "SNAPSHOT_UNREADABLE",
                f"快照 meta.json 无法读取: {snapshot_id}",
            ) from exc

        try:
            raw = json.loads(text)
        except json.JSONDecodeError as exc:
            raise _MetaReadError(
                "SNAPSHOT_UNREADABLE",
                f"快照 meta.json 不是合法 JSON: {snapshot_id}",
            ) from exc
        if not isinstance(raw, dict):
            raise _MetaReadError(
                "SNAPSHOT_UNREADABLE",
                f"快照 meta.json 顶层必须是对象: {snapshot_id}",
            )

        version = raw.get("schema_version")
        if isinstance(version, bool) or not isinstance(version, int):
            raise _MetaReadError(
                "SNAPSHOT_UNREADABLE",
                f"快照 meta.json 缺少合法 schema_version: {snapshot_id}",
            )
        if version != SNAPSHOT_SCHEMA_VERSION:
            raise _MetaReadError(
                "SNAPSHOT_VERSION_UNSUPPORTED",
                f"快照版本 {version} 不受支持: {snapshot_id}",
            )

        try:
            snapshot = Snapshot.model_validate(raw)
        except ValidationError as exc:
            raise _MetaReadError(
                "SNAPSHOT_UNREADABLE",
                f"快照 meta.json 结构不符合约定: {snapshot_id}",
            ) from exc

        if snapshot.id != snapshot_id:
            raise _MetaReadError(
                "SNAPSHOT_UNREADABLE",
                f"快照 id 与目录名不一致: {snapshot_id}",
            )

        for snapshot_file in snapshot.files:
            try:
                resolved = resolve_absolute_path(
                    Path(snapshot_file.path),
                    label="快照文件路径",
                )
            except ValueError as exc:
                raise _MetaReadError(
                    "SNAPSHOT_UNREADABLE",
                    f"快照文件路径不合法: {snapshot_id}",
                ) from exc
            if str(resolved) != snapshot_file.path:
                raise _MetaReadError(
                    "SNAPSHOT_UNREADABLE",
                    f"快照文件路径未规范化: {snapshot_id}",
                )
        return snapshot

    def _write_meta(self, snapshot: Snapshot) -> None:
        meta_path = self._snapshot_dir(snapshot.id) / META_FILE_NAME
        try:
            write_json_atomic(meta_path, snapshot.model_dump(mode="json"))
        except OSError as exc:
            raise AppError(
                "SNAPSHOT_WRITE_FAILED",
                f"快照元数据写入失败: {snapshot.id}",
                500,
            ) from exc

    def _verify_snapshot(self, snapshot: Snapshot) -> None:
        for snapshot_file in snapshot.files:
            if snapshot_file.existed:
                self._load_file_bytes(snapshot.id, snapshot_file)

    def _load_file_bytes(self, snapshot_id: str, snapshot_file: SnapshotFile) -> bytes:
        chunks: list[bytes] = []
        for digest in snapshot_file.chunks:
            object_path = self._object_path(digest)
            try:
                chunk = object_path.read_bytes()
            except FileNotFoundError as exc:
                raise AppError(
                    "SNAPSHOT_UNREADABLE",
                    f"快照内容块缺失: {snapshot_id}",
                    500,
                ) from exc
            except OSError as exc:
                raise AppError(
                    "SNAPSHOT_UNREADABLE",
                    f"快照内容块无法读取: {snapshot_id}",
                    500,
                ) from exc
            if _sha256(chunk) != digest:
                raise AppError(
                    "SNAPSHOT_UNREADABLE",
                    f"快照内容块校验失败: {snapshot_id}",
                    500,
                )
            chunks.append(chunk)

        data = b"".join(chunks)
        if len(data) != snapshot_file.size or _sha256(data) != snapshot_file.sha256:
            raise AppError(
                "SNAPSHOT_UNREADABLE",
                f"快照文件校验失败: {snapshot_id}",
                500,
            )
        return data

    def _ensure_store_dirs(self) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        self._objects_dir.mkdir(parents=True, exist_ok=True)
        if os.name != "nt":
            self._root.chmod(0o700)
            self._objects_dir.chmod(0o700)

    def _discard_snapshot_dir(self, snapshot_id: str) -> None:
        try:
            shutil.rmtree(self._snapshot_dir(snapshot_id))
        except OSError:
            logger.debug("清理失败的快照目录未删除: %s", snapshot_id, exc_info=True)

    def _snapshot_dir(self, snapshot_id: str) -> Path:
        parsed = uuid.UUID(snapshot_id)
        if parsed.version != 4 or str(parsed) != snapshot_id:
            raise ValueError("snapshot id must be a canonical UUID4")
        return self._root / snapshot_id

    def _object_path(self, digest: str) -> Path:
        return self._objects_dir / digest[:2] / digest
