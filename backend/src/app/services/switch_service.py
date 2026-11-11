"""008 一键切换: 只读预览与受保护的应用。

预览完全无状态: 读取档案 / 密钥 / 目标文件, 让适配器生成纯内存计划, 渲染并校验
后返回逐字段变更与 `preview_digest`; 不建快照、不写审计、不创建目录。

应用按同样输入重新生成计划并复核:
1. 请求观察值与当前文件不一致 → `WRITE_CONFLICT` (交给 007 的冲突模型);
2. digest 不一致 (档案 / 模型 / 密钥在预览后变化) → `SWITCH_PREVIEW_STALE`;
3. 仍有 blocker → `SWITCH_BLOCKED`;
4. 其余交给 007 `WriteEngine` 完成写锁、预快照、原子写、回读与审计;
5. 绑定保存失败时用本次快照自动回滚, 绝不报告假成功。
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.adapters.base import ToolAdapter, ToolCurrentFile, ToolPlanFile, WriteBlockerCode
from app.adapters.registry import ToolRegistry
from app.core.clock import utc_now
from app.core.errors import AppError, ErrorDetails, FileConflict, WriteConflict
from app.core.file_observation import (
    FileSnapshotData,
    compare_observations,
    read_file_with_bytes,
)
from app.core.paths import resolve_absolute_path
from app.repositories.audit import AuditRepository
from app.repositories.profiles import ProfileRepository
from app.repositories.secrets import SecretStore
from app.schemas.audit import AuditResult
from app.schemas.profile import BindingView, Profile, ProfileStore, ToolBinding
from app.schemas.snapshot import FileObservation
from app.schemas.switch import (
    SwitchApplyRequest,
    SwitchApplyResponse,
    SwitchBlocker,
    SwitchFilePreview,
    SwitchPreviewRequest,
    SwitchPreviewResponse,
    SwitchWarning,
)
from app.schemas.write import PlannedFile, WritePlan, sha256_hex
from app.services.snapshot_service import SnapshotService
from app.services.write_engine import WriteEngine

logger = logging.getLogger(__name__)

AccessFn = Callable[[Path, int], bool]

_DEFAULT_RESTART_MESSAGE = "应用后需要重启工具才会读取新的配置"
_STALE_CODES = frozenset({"PROFILE_NOT_FOUND", "SWITCH_MODEL_UNKNOWN"})


@dataclass(frozen=True)
class _PreparedFile:
    """一个可写文件的完整内存状态; 路径已解析 symlink 并规范化。"""

    plan_file: ToolPlanFile
    path: str
    observation: FileObservation
    original_bytes: bytes
    expected_bytes: bytes


@dataclass(frozen=True)
class _Prepared:
    tool_id: str
    profile: Profile
    model: str | None
    planned: tuple[_PreparedFile, ...]
    observations: tuple[FileObservation, ...]
    blockers: tuple[SwitchBlocker, ...]
    warnings: tuple[SwitchWarning, ...]
    restart_required: bool
    restart_message: str
    digest: str


@dataclass(frozen=True)
class _SecretRead:
    value: str | None
    ok: bool


class _ProfileStale(Exception):
    """绑定保存前发现档案在预览后被修改; 由 apply 转成可读错误。"""


class SwitchService:
    """切换用例边界; 仓储、密钥、写引擎与快照服务都通过构造参数注入。"""

    def __init__(
        self,
        *,
        registry: ToolRegistry,
        profiles: ProfileRepository,
        secrets: SecretStore,
        write_engine: WriteEngine,
        snapshots: SnapshotService,
        audit: AuditRepository,
        access: AccessFn | None = None,
    ) -> None:
        self._registry = registry
        self._profiles = profiles
        self._secrets = secrets
        self._write_engine = write_engine
        self._snapshots = snapshots
        self._audit = audit
        self._access = os.access if access is None else access

    def preview(self, payload: SwitchPreviewRequest) -> SwitchPreviewResponse:
        prepared = self._prepare(
            payload.tool_id,
            payload.profile_id,
            payload.model,
        )
        return self._preview_response(prepared)

    def apply(self, payload: SwitchApplyRequest) -> SwitchApplyResponse:
        try:
            prepared = self._prepare(
                payload.tool_id,
                payload.profile_id,
                payload.model,
            )
        except AppError as exc:
            if exc.code in _STALE_CODES:
                raise _stale_error(
                    [observation.path for observation in payload.observations]
                ) from exc
            raise

        conflicts = _observation_conflicts(payload.observations, prepared.observations)
        if conflicts:
            self._record_conflict(prepared, conflicts)
            raise WriteConflict(conflicts)
        if payload.preview_digest != prepared.digest:
            raise _stale_error(
                [item.path for item in prepared.planned]
                or [observation.path for observation in prepared.observations]
            )
        if prepared.blockers:
            raise AppError(
                "SWITCH_BLOCKED",
                "存在阻止应用的项: " + "; ".join(blocker.message for blocker in prepared.blockers),
                409,
            )
        if not prepared.planned:
            raise AppError("SWITCH_BLOCKED", "没有可写入的文件", 409)

        result = self._write_engine.apply(
            WritePlan(
                tool_id=prepared.tool_id,
                profile_id=prepared.profile.id,
                files=[
                    PlannedFile(
                        path=item.path,
                        expected_bytes=item.expected_bytes,
                        observation=item.observation,
                        changes=item.plan_file.changes,
                    )
                    for item in prepared.planned
                ],
            )
        )

        applied_at = utc_now()
        try:
            binding = self._save_binding(
                prepared,
                snapshot_id=result.snapshot_id,
                applied_at=applied_at,
            )
        except _ProfileStale as exc:
            rollback_error = self._rollback_after_binding_failure(
                prepared,
                snapshot_id=result.snapshot_id,
                reason="档案在预览后被修改",
            )
            if rollback_error is not None:
                raise rollback_error from exc
            raise _stale_error([item.path for item in prepared.planned]) from exc
        except Exception as exc:
            rollback_error = self._rollback_after_binding_failure(
                prepared,
                snapshot_id=result.snapshot_id,
                reason=type(exc).__name__,
            )
            if rollback_error is not None:
                raise rollback_error from exc
            raise AppError(
                "BINDING_WRITE_FAILED",
                "配置文件已写入, 但绑定保存失败, 已自动还原配置文件",
                500,
            ) from exc

        return SwitchApplyResponse(
            tool_id=prepared.tool_id,
            profile_id=prepared.profile.id,
            snapshot_id=result.snapshot_id,
            audit_id=result.audit_id,
            files=result.files,
            binding=binding,
            warnings=list(prepared.warnings),
            restart_required=prepared.restart_required,
            restart_message=prepared.restart_message,
            applied_at=applied_at,
        )

    # ------------------------------------------------------------------
    # 计划生成
    # ------------------------------------------------------------------

    def _prepare(
        self,
        tool_id: str,
        profile_id: str,
        model: str | None,
    ) -> _Prepared:
        adapter = self._installed_adapter(tool_id)
        profile = self._profiles.get_profile(profile_id)
        if profile is None:
            raise AppError("PROFILE_NOT_FOUND", f"档案不存在: {profile_id}", 404)

        blockers: list[SwitchBlocker] = []
        warnings: list[SwitchWarning] = []
        selected_model = _resolve_model(profile, model)
        if not profile.models:
            warnings.append(
                SwitchWarning(
                    code="NO_MODELS",
                    message="档案没有模型清单, 保持工具当前模型",
                )
            )

        protocol_matches = profile.protocol in adapter.supported_protocols
        if not protocol_matches:
            expected = " / ".join(adapter.supported_protocols)
            blockers.append(
                SwitchBlocker(
                    code="PROTOCOL_MISMATCH",
                    message=(
                        f"档案协议 {profile.protocol} 与工具 {adapter.display_name} "
                        f"支持的协议 ({expected}) 不匹配"
                    ),
                )
            )

        secret_read = self._read_secret(profile, blockers)
        current, observations, snapshots, blocked_paths = self._read_managed_files(
            adapter, blockers
        )

        planned: list[_PreparedFile] = []
        restart_required = True
        restart_message = _DEFAULT_RESTART_MESSAGE
        if protocol_matches and secret_read.ok:
            tool_plan = adapter.plan(
                profile,
                secret=secret_read.value,
                model=selected_model,
                current=current,
            )
            restart_required = tool_plan.restart_required
            restart_message = tool_plan.restart_message
            for blocker in tool_plan.blockers:
                blockers.append(
                    SwitchBlocker(
                        code=blocker.code,
                        message=blocker.message,
                        path=blocker.path,
                    )
                )
                if blocker.path is not None:
                    blocked_paths.add(blocker.path)
            warnings.extend(
                SwitchWarning(code=warning.code, message=warning.message)
                for warning in tool_plan.warnings
            )
            planned = self._render_files(
                adapter,
                tool_plan.files,
                observations,
                snapshots,
                blocked_paths,
                blockers,
            )

        prepared = _Prepared(
            tool_id=tool_id,
            profile=profile,
            model=selected_model,
            planned=tuple(planned),
            observations=tuple(observations[path] for path in sorted(observations)),
            blockers=tuple(_dedupe_blockers(blockers)),
            warnings=tuple(_dedupe_warnings(warnings)),
            restart_required=restart_required,
            restart_message=restart_message,
            digest=_preview_digest(
                tool_id,
                profile,
                selected_model,
                planned,
            ),
        )
        return prepared

    def _installed_adapter(self, tool_id: str) -> ToolAdapter:
        adapter = self._registry.get(tool_id)
        try:
            detection = adapter.detect()
        except Exception as exc:  # 适配器契约: 未知异常归一成可读错误
            raise AppError(
                "ADAPTER_ERROR",
                f"适配器 {tool_id} 检测失败: {type(exc).__name__}",
                500,
            ) from exc
        if not detection.installed:
            raise AppError("TOOL_NOT_FOUND", f"工具未安装: {tool_id}", 404)
        return adapter

    def _read_secret(
        self,
        profile: Profile,
        blockers: list[SwitchBlocker],
    ) -> _SecretRead:
        if profile.secret_ref is None:
            return _SecretRead(None, True)
        try:
            secret = self._secrets.get(profile.secret_ref)
        except AppError as exc:
            blockers.append(SwitchBlocker(code="SECRET_STORE_ERROR", message=exc.message))
            return _SecretRead(None, False)
        if secret is None or not secret.strip():
            blockers.append(
                SwitchBlocker(
                    code="SECRET_MISSING",
                    message="档案引用的密钥不存在, 无法写入工具配置",
                )
            )
            return _SecretRead(None, False)
        return _SecretRead(secret, True)

    def _read_managed_files(
        self,
        adapter: ToolAdapter,
        blockers: list[SwitchBlocker],
    ) -> tuple[
        dict[str, ToolCurrentFile],
        dict[str, FileObservation],
        dict[str, FileSnapshotData],
        set[str],
    ]:
        """每个托管路径只读一次; 读 / 写权限问题变成 blocker, 预览不创建任何目录。"""
        current: dict[str, ToolCurrentFile] = {}
        observations: dict[str, FileObservation] = {}
        snapshots: dict[str, FileSnapshotData] = {}
        blocked_paths: set[str] = set()
        for managed_path in adapter.managed_paths:
            resolved = resolve_absolute_path(managed_path)
            path_key = str(resolved)
            try:
                snapshot = read_file_with_bytes(resolved)
            except OSError:
                blockers.append(
                    SwitchBlocker(
                        code="PERMISSION_DENIED",
                        message=f"无法读取目标文件: {path_key}",
                        path=path_key,
                    )
                )
                blocked_paths.add(path_key)
                current[str(managed_path)] = ToolCurrentFile(
                    path=path_key,
                    exists=False,
                )
                continue
            observations[path_key] = snapshot.observation
            snapshots[path_key] = snapshot
            current[str(managed_path)] = ToolCurrentFile(
                path=path_key,
                exists=snapshot.observation.exists,
                data=snapshot.data,
            )
            permission = self._permission_blocker(
                resolved,
                exists=snapshot.observation.exists,
            )
            if permission is not None:
                blockers.append(permission)
                blocked_paths.add(path_key)
        return current, observations, snapshots, blocked_paths

    def _permission_blocker(
        self,
        path: Path,
        *,
        exists: bool,
    ) -> SwitchBlocker | None:
        if exists and not self._access(path, os.W_OK):
            return SwitchBlocker(
                code="FILE_NOT_WRITABLE",
                message=f"目标文件不可写: {path}",
                path=str(path),
            )
        directory = path.parent if exists else _nearest_existing_directory(path.parent)
        if directory is None or not directory.is_dir():
            return SwitchBlocker(
                code="DIRECTORY_NOT_WRITABLE",
                message=f"目标目录不存在或不是目录: {path.parent}",
                path=str(path),
            )
        if not self._access(directory, os.W_OK | os.X_OK):
            return SwitchBlocker(
                code="DIRECTORY_NOT_WRITABLE",
                message=f"目标目录不可写: {directory}",
                path=str(path),
            )
        return None

    def _render_files(
        self,
        adapter: ToolAdapter,
        plan_files: Sequence[ToolPlanFile],
        observations: dict[str, FileObservation],
        snapshots: dict[str, FileSnapshotData],
        blocked_paths: set[str],
        blockers: list[SwitchBlocker],
    ) -> list[_PreparedFile]:
        planned: list[_PreparedFile] = []
        for plan_file in plan_files:
            try:
                resolved = str(resolve_absolute_path(Path(plan_file.path)))
            except ValueError:
                blockers.append(
                    SwitchBlocker(
                        code="UNSAFE_WRITE",
                        message="适配器计划了不合法的写入路径",
                    )
                )
                continue
            if resolved in blocked_paths:
                continue
            snapshot = snapshots.get(resolved)
            observation = observations.get(resolved)
            if snapshot is None or observation is None:
                blockers.append(
                    SwitchBlocker(
                        code="UNSAFE_WRITE",
                        message=f"适配器计划了未读取的文件: {resolved}",
                        path=resolved,
                    )
                )
                continue
            original = snapshot.data if snapshot.data is not None else b""
            try:
                expected = adapter.render(plan_file, original)
                adapter.verify(plan_file, original, expected)
            except AppError as exc:
                blockers.append(_render_blocker(exc, resolved))
                continue
            planned.append(
                _PreparedFile(
                    plan_file=plan_file,
                    path=resolved,
                    observation=observation,
                    original_bytes=original,
                    expected_bytes=expected,
                )
            )
        return planned

    # ------------------------------------------------------------------
    # 预览响应
    # ------------------------------------------------------------------

    @staticmethod
    def _preview_response(prepared: _Prepared) -> SwitchPreviewResponse:
        return SwitchPreviewResponse(
            tool_id=prepared.tool_id,
            profile_id=prepared.profile.id,
            model=prepared.model,
            available_models=prepared.profile.models,
            files=[_file_preview(item) for item in prepared.planned],
            blockers=list(prepared.blockers),
            warnings=list(prepared.warnings),
            restart_required=prepared.restart_required,
            restart_message=prepared.restart_message,
            observations=list(prepared.observations),
            preview_digest=prepared.digest,
            can_apply=not prepared.blockers,
        )

    # ------------------------------------------------------------------
    # 绑定与回滚
    # ------------------------------------------------------------------

    def _save_binding(
        self,
        prepared: _Prepared,
        *,
        snapshot_id: str,
        applied_at: datetime,
    ) -> BindingView:
        def change(store: ProfileStore) -> BindingView:
            current = next(
                (profile for profile in store.profiles if profile.id == prepared.profile.id),
                None,
            )
            if current is None or current.updated_at != prepared.profile.updated_at:
                raise _ProfileStale()
            existing = next(
                (binding for binding in store.bindings if binding.tool_id == prepared.tool_id),
                None,
            )
            binding = ToolBinding(
                tool_id=prepared.tool_id,
                profile_id=prepared.profile.id,
                bound_at=existing.bound_at if existing is not None else applied_at,
                active=True,
                applied_at=applied_at,
                snapshot_id=snapshot_id,
            )
            store.bindings = [
                stored for stored in store.bindings if stored.tool_id != prepared.tool_id
            ]
            store.bindings.append(binding)
            return BindingView.model_validate(binding.model_dump())

        return self._profiles.mutate(change)

    def _rollback_after_binding_failure(
        self,
        prepared: _Prepared,
        *,
        snapshot_id: str,
        reason: str,
    ) -> AppError | None:
        rollback_message: str | None = None
        try:
            self._snapshots.rollback(snapshot_id)
        except AppError as exc:
            rollback_message = exc.message

        if rollback_message is None:
            message = f"绑定保存失败 ({reason}), 已用快照 {snapshot_id} 自动还原配置文件"
            error: AppError | None = None
        else:
            message = (
                f"绑定保存失败 ({reason}), 且用快照 {snapshot_id} 自动回滚失败: {rollback_message}"
            )
            error = AppError(
                "APPLY_ROLLBACK_FAILED",
                f"配置文件已写入, 但绑定保存失败且自动回滚失败, "
                f"请人工检查快照 {snapshot_id}: {rollback_message}",
                500,
            )
        self._record_binding_failure(prepared, snapshot_id=snapshot_id, message=message)
        return error

    def _record_binding_failure(
        self,
        prepared: _Prepared,
        *,
        snapshot_id: str,
        message: str,
    ) -> None:
        self._record_safely(
            prepared,
            snapshot_id=snapshot_id,
            result="failed",
            message=message,
        )

    def _record_conflict(
        self,
        prepared: _Prepared,
        conflicts: Sequence[FileConflict],
    ) -> None:
        self._record_safely(
            prepared,
            snapshot_id=None,
            result="conflict",
            message=f"{len(conflicts)} 个文件在预览后发生变化, 已拒绝写入",
        )

    def _record_safely(
        self,
        prepared: _Prepared,
        *,
        snapshot_id: str | None,
        result: AuditResult,
        message: str,
    ) -> None:
        try:
            self._audit.record(
                action="apply",
                tool_id=prepared.tool_id,
                profile_id=prepared.profile.id,
                snapshot_id=snapshot_id,
                files=[item.path for item in prepared.planned],
                fields=_planned_fields(prepared.planned),
                result=result,
                message=message,
            )
        except Exception:
            logger.warning("切换审计写入失败, 已保留主错误", exc_info=True)


def _resolve_model(profile: Profile, requested: str | None) -> str | None:
    if requested is not None:
        if not any(item.id == requested for item in profile.models):
            raise AppError(
                "SWITCH_MODEL_UNKNOWN",
                f"模型不在档案清单中: {requested}",
                422,
            )
        return requested
    if profile.models:
        return profile.models[0].id
    return None


def _preview_digest(
    tool_id: str,
    profile: Profile,
    model: str | None,
    planned: Sequence[_PreparedFile],
) -> str:
    payload = {
        "tool_id": tool_id,
        "profile_id": profile.id,
        "profile_updated_at": profile.updated_at.isoformat(),
        "model": model,
        "files": [
            {
                "path": item.path,
                "exists": item.observation.exists,
                "sha256": item.observation.sha256,
                "size": item.observation.size,
                "expected_sha256": sha256_hex(item.expected_bytes),
            }
            for item in sorted(planned, key=lambda entry: entry.path)
        ],
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _observation_conflicts(
    requested: Sequence[FileObservation],
    fresh: Sequence[FileObservation],
) -> list[FileConflict]:
    requested_by_path = {observation.path: observation for observation in requested}
    fresh_by_path = {observation.path: observation for observation in fresh}
    conflicts: list[FileConflict] = []
    for path in sorted(set(requested_by_path) | set(fresh_by_path)):
        expected = requested_by_path.get(path)
        actual = fresh_by_path.get(path)
        if expected is None:
            expected = FileObservation(path=path, exists=False)
        if actual is None:
            conflicts.append(
                FileConflict(
                    path=path,
                    reason="MISSING",
                    expected=expected,
                    actual=FileObservation(path=path, exists=False),
                )
            )
            continue
        conflict = compare_observations(expected, actual)
        if conflict is not None:
            conflicts.append(conflict)
    return conflicts


def _file_preview(item: _PreparedFile) -> SwitchFilePreview:
    if not item.observation.exists:
        action = "created"
    elif item.expected_bytes != item.original_bytes:
        action = "updated"
    else:
        action = "unchanged"
    return SwitchFilePreview(
        path=item.path,
        format=item.plan_file.format,
        action=action,
        before_sha256=item.observation.sha256,
        after_sha256=sha256_hex(item.expected_bytes),
        before_size=item.observation.size,
        after_size=len(item.expected_bytes),
        changes=item.plan_file.changes,
    )


def _render_blocker(exc: AppError, path: str) -> SwitchBlocker:
    code: WriteBlockerCode
    if exc.code == "PARSE_ERROR":
        code = "PARSE_ERROR"
    elif exc.code == "UNSUPPORTED_VERSION":
        code = "UNSUPPORTED_VERSION"
    elif exc.code == "PERMISSION_DENIED":
        code = "PERMISSION_DENIED"
    else:
        code = "UNSAFE_WRITE"
    return SwitchBlocker(code=code, message=exc.message, path=path)


def _stale_error(stale_paths: Sequence[str]) -> AppError:
    message = "预览已过期, 档案或模型在预览后发生变化, 请重新预览"
    return AppError(
        "SWITCH_PREVIEW_STALE",
        message,
        409,
        details=ErrorDetails(stale_paths=list(stale_paths)),
    )


def _planned_fields(planned: Sequence[_PreparedFile]) -> list[str]:
    return [f"{item.path}.{change.field}" for item in planned for change in item.plan_file.changes]


def _dedupe_blockers(blockers: Sequence[SwitchBlocker]) -> list[SwitchBlocker]:
    result: list[SwitchBlocker] = []
    seen: set[tuple[str, str, str | None]] = set()
    for blocker in blockers:
        key = (blocker.code, blocker.message, blocker.path)
        if key in seen:
            continue
        seen.add(key)
        result.append(blocker)
    return result


def _dedupe_warnings(warnings: Sequence[SwitchWarning]) -> list[SwitchWarning]:
    result: list[SwitchWarning] = []
    seen: set[tuple[str, str]] = set()
    for warning in warnings:
        key = (warning.code, warning.message)
        if key in seen:
            continue
        seen.add(key)
        result.append(warning)
    return result


def _nearest_existing_directory(path: Path) -> Path | None:
    candidate = path
    while not candidate.exists():
        parent = candidate.parent
        if parent == candidate:
            return None
        candidate = parent
    return candidate
