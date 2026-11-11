"""快照测试共享的构造器; 不是 pytest 插件, 也不会被收集。"""

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.snapshots import get_snapshot_service
from app.core.file_observation import read_file_with_bytes
from app.main import create_app
from app.repositories.audit import AuditRepository
from app.repositories.snapshots import SnapshotRepository
from app.schemas.snapshot import (
    FileObservation,
    Snapshot,
    SnapshotChange,
    SnapshotFileSource,
    SnapshotReason,
)
from app.schemas.write import PlannedFile, WritePlan
from app.services.snapshot_service import SnapshotService
from app.services.write_engine import WriteEngine

NOW = datetime(2026, 11, 11, 8, 0, tzinfo=UTC)
DEFAULT_CHUNK_SIZE = 4


def make_repository(
    data_dir: Path,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    retention_limit: int = 20,
    lock_timeout: float = 5.0,
) -> SnapshotRepository:
    return SnapshotRepository(
        data_dir,
        chunk_size=chunk_size,
        retention_limit=retention_limit,
        lock_timeout=lock_timeout,
    )


def file_source(
    path: Path,
    data: bytes,
    *,
    mtime_ns: int | None = None,
    mode: int | None = None,
) -> SnapshotFileSource:
    """把 `data` 落到临时目标, 再构造与调用方观察一致的来源。"""
    resolved = path.resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_bytes(data)
    stat_result = resolved.stat()
    return SnapshotFileSource(
        path=str(resolved),
        existed=True,
        data=data,
        mtime_ns=stat_result.st_mtime_ns if mtime_ns is None else mtime_ns,
        mode=mode,
    )


def missing_source(path: Path) -> SnapshotFileSource:
    return SnapshotFileSource(path=str(path.resolve()), existed=False)


def capture_one(
    repository: SnapshotRepository,
    path: Path,
    data: bytes,
    *,
    tool_id: str = "claude-code",
    created_at: datetime = NOW,
    reason: SnapshotReason = "apply",
    changes: Sequence[SnapshotChange] = (),
    protected_ids: Collection[str] = (),
) -> Snapshot:
    return repository.capture(
        tool_id=tool_id,
        files=[file_source(path, data)],
        reason=reason,
        created_at=created_at,
        changes=changes,
        protected_ids=protected_ids,
    )


def at(seconds: int) -> datetime:
    return NOW + timedelta(seconds=seconds)


def object_path(repository: SnapshotRepository, digest: str) -> Path:
    return repository.objects_dir / digest[:2] / digest


def object_files(repository: SnapshotRepository) -> list[Path]:
    return sorted(path for path in repository.objects_dir.glob("*/*") if path.is_file())


def make_audit(data_dir: Path) -> AuditRepository:
    return AuditRepository(data_dir / "db" / "app.sqlite3")


def make_write_engine(
    data_dir: Path,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    retention_limit: int = 20,
    lock_timeout: float = 5.0,
) -> WriteEngine:
    return WriteEngine(
        make_repository(
            data_dir,
            chunk_size=chunk_size,
            retention_limit=retention_limit,
            lock_timeout=lock_timeout,
        ),
        make_audit(data_dir),
        write_lock_path=data_dir / "locks" / "write.lock",
        lock_timeout=lock_timeout,
    )


def planned_file(
    path: Path,
    data: bytes,
    *,
    observation: FileObservation | None = None,
    changes: Sequence[SnapshotChange] = (),
) -> PlannedFile:
    """构造与「预览时观察值」一致的计划项; 默认观察当前文件。"""
    resolved = path.resolve()
    if observation is None:
        observation = read_file_with_bytes(resolved).observation
    return PlannedFile(
        path=str(resolved),
        expected_bytes=data,
        observation=observation,
        changes=list(changes),
    )


def make_plan(
    files: Sequence[PlannedFile],
    *,
    tool_id: str = "claude-code",
    profile_id: str | None = None,
) -> WritePlan:
    return WritePlan(tool_id=tool_id, profile_id=profile_id, files=list(files))


@dataclass
class SnapshotHarness:
    """API 测试替身: 临时数据目录 + 注入的 snapshot service。"""

    client: TestClient
    repository: SnapshotRepository
    service: SnapshotService
    audit: AuditRepository
    data_dir: Path


def make_snapshot_harness(
    data_dir: Path,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    retention_limit: int = 20,
) -> SnapshotHarness:
    repository = make_repository(
        data_dir,
        chunk_size=chunk_size,
        retention_limit=retention_limit,
    )
    audit = make_audit(data_dir)
    service = SnapshotService(
        repository,
        audit,
        write_lock_path=data_dir / "locks" / "write.lock",
    )
    app = create_app()
    app.dependency_overrides[get_snapshot_service] = lambda: service
    return SnapshotHarness(
        client=TestClient(app),
        repository=repository,
        service=service,
        audit=audit,
        data_dir=data_dir,
    )
