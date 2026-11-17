"""本地导入供应商: 解析、逐条校验、去重预览与全或无写入。

文件是版本化 JSON; 校验规则复用 `ProfileCreate`, 不另写一套。
任何非法条目都会让整批导入失败, 不产生部分写入。
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Iterable
from typing import Any

from pydantic import ValidationError
from pydantic_core import ErrorDetails

from app.core.clock import utc_now
from app.core.errors import AppError
from app.repositories.audit import AuditRepository
from app.repositories.profiles import ProfileRepository
from app.repositories.secrets import SecretStore
from app.schemas.profile import Profile, ProfileCreate, ProfileStore, SecretRef
from app.schemas.profile_import import (
    MAX_IMPORT_ITEMS,
    SUPPORTED_IMPORT_VERSION,
    ImportPolicy,
    ProfileImportItem,
    ProfileImportPreview,
    ProfileImportRequest,
    ProfileImportResult,
    ProfileImportTotals,
)

logger = logging.getLogger(__name__)

_DedupeKey = tuple[str, str, str]


class ProfileImportService:
    """导入用例边界; 仓储、密钥与审计通过构造参数注入。"""

    def __init__(
        self,
        repository: ProfileRepository,
        secrets: SecretStore,
        audit: AuditRepository,
    ) -> None:
        self._repository = repository
        self._secrets = secrets
        self._audit = audit

    def preview(self, request: ProfileImportRequest) -> ProfileImportPreview:
        parsed = _parse_content(request.content)
        store = self._repository.load()
        items, _candidates = _analyze(parsed, store.profiles)
        totals = _totals(items)
        return ProfileImportPreview(
            schema_version=SUPPORTED_IMPORT_VERSION,
            items=items,
            totals=totals,
            can_import=totals.invalid == 0,
        )

    def import_profiles(self, request: ProfileImportRequest) -> ProfileImportResult:
        parsed = _parse_content(request.content)
        store = self._repository.load()
        items, candidates = _analyze(parsed, store.profiles)
        totals = _totals(items)
        if totals.invalid > 0:
            reasons = "; ".join(
                f"第 {item.index + 1} 条: {' / '.join(item.reasons)}"
                for item in items
                if item.status == "invalid"
            )
            raise AppError(
                "IMPORT_HAS_INVALID_ITEMS", f"存在非法条目, 已取消整批导入: {reasons}", 422
            )

        creates, overwrites = _plan(items, candidates, store.profiles, request.policy)
        now = utc_now()
        created_secret_refs: list[SecretRef] = []
        created_profiles: list[tuple[_DedupeKey, Profile]] = []
        overwritten_profiles: list[tuple[str, Profile, SecretRef | None]] = []

        try:
            for key, candidate in creates:
                profile_id = str(uuid.uuid4())
                secret_ref = self._put_secret(profile_id, candidate)
                if secret_ref is not None:
                    created_secret_refs.append(secret_ref)
                created_profiles.append(
                    (
                        key,
                        Profile(
                            id=profile_id,
                            name=candidate.name,
                            protocol=candidate.protocol,
                            base_url=candidate.base_url,
                            secret_ref=secret_ref,
                            models=candidate.models,
                            created_at=now,
                            updated_at=now,
                        ),
                    )
                )

            for existing_id, candidate in overwrites:
                existing = _find(existing_id, store.profiles)
                new_ref = self._put_secret(existing_id, candidate)
                if new_ref is not None:
                    created_secret_refs.append(new_ref)
                overwritten_profiles.append(
                    (
                        existing_id,
                        existing.model_copy(
                            update={
                                "models": candidate.models,
                                "secret_ref": new_ref
                                if new_ref is not None
                                else existing.secret_ref,
                                "updated_at": now,
                            }
                        ),
                        new_ref,
                    )
                )

            def change(current: ProfileStore) -> None:
                existing_keys = {
                    _key(profile.name, profile.protocol, profile.base_url)
                    for profile in current.profiles
                }
                for key, profile in created_profiles:
                    if key in existing_keys:
                        raise AppError(
                            "IMPORT_CONFLICT", f"供应商在导入过程中被创建: {profile.name}", 409
                        )
                    current.profiles.append(profile)
                replacements = {
                    existing_id: profile for existing_id, profile, _ref in overwritten_profiles
                }
                current.profiles = [
                    replacements.get(profile.id, profile) for profile in current.profiles
                ]

            self._repository.mutate(change)
        except Exception:
            for ref in created_secret_refs:
                try:
                    self._secrets.delete(ref)
                except Exception:  # 补偿失败不能掩盖主错误
                    logger.warning("导入失败后清理密钥失败", exc_info=True)
            raise

        skipped = totals.duplicate if request.policy == "skip" else 0
        self._record_audit(
            imported=len(created_profiles),
            overwritten=len(overwritten_profiles),
            skipped=skipped,
        )
        return ProfileImportResult(
            imported=len(created_profiles),
            overwritten=len(overwritten_profiles),
            skipped=skipped,
            profile_ids=[profile.id for _key_value, profile in created_profiles]
            + [existing_id for existing_id, _profile, _ref in overwritten_profiles],
        )

    def _put_secret(self, profile_id: str, candidate: ProfileCreate) -> SecretRef | None:
        if candidate.secret is None:
            return None
        if not candidate.secret.strip():
            raise AppError("VALIDATION_ERROR", "密钥不能为空", 422)
        return self._secrets.put(profile_id, candidate.secret)

    def _record_audit(self, *, imported: int, overwritten: int, skipped: int) -> None:
        """审计是旁路; 写入失败只告警, 不影响导入结果。"""
        try:
            self._audit.record(
                action="profile_import",
                tool_id=None,
                profile_id=None,
                snapshot_id=None,
                files=[],
                fields=[],
                result="success",
                message=f"导入供应商: 新增 {imported}、覆盖 {overwritten}、跳过 {skipped}",
            )
        except Exception:
            logger.warning("供应商导入审计写入失败", exc_info=True)


def _parse_content(content: str) -> list[Any]:
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise AppError("IMPORT_INVALID_JSON", "文件不是合法 JSON", 422) from exc
    if not isinstance(data, dict):
        raise AppError("IMPORT_INVALID_SHAPE", "导入文件顶层必须是 JSON 对象", 422)
    version = data.get("schema_version")
    if version != SUPPORTED_IMPORT_VERSION:
        raise AppError(
            "IMPORT_UNSUPPORTED_VERSION",
            f"不支持的 schema_version: {version!r}, 当前支持 {SUPPORTED_IMPORT_VERSION}",
            422,
        )
    profiles = data.get("profiles")
    if not isinstance(profiles, list):
        raise AppError("IMPORT_INVALID_SHAPE", "profiles 必须是数组", 422)
    if len(profiles) == 0:
        raise AppError("IMPORT_EMPTY", "导入文件里没有供应商", 422)
    if len(profiles) > MAX_IMPORT_ITEMS:
        raise AppError("IMPORT_TOO_MANY_ITEMS", f"一次最多导入 {MAX_IMPORT_ITEMS} 条", 422)
    return list(profiles)


def _analyze(
    parsed: list[Any],
    existing: Iterable[Profile],
) -> tuple[list[ProfileImportItem], dict[int, ProfileCreate]]:
    existing_list = list(existing)
    existing_keys = {
        _key(profile.name, profile.protocol, profile.base_url): profile for profile in existing_list
    }
    existing_names = {profile.name.casefold(): profile for profile in existing_list}
    seen: dict[_DedupeKey, int] = {}
    seen_names: dict[str, int] = {}
    items: list[ProfileImportItem] = []
    candidates: dict[int, ProfileCreate] = {}

    for index, raw in enumerate(parsed):
        if not isinstance(raw, dict):
            items.append(
                ProfileImportItem(index=index, status="invalid", reasons=["条目必须是 JSON 对象"])
            )
            continue
        name_value = raw.get("name")
        display_name = name_value if isinstance(name_value, str) else None
        try:
            candidate = ProfileCreate.model_validate(raw)
        except ValidationError as exc:
            items.append(
                ProfileImportItem(
                    index=index,
                    name=display_name,
                    status="invalid",
                    reasons=[_format_error(error) for error in exc.errors()],
                )
            )
            continue

        key = _key(candidate.name, candidate.protocol, candidate.base_url)
        candidates[index] = candidate
        if key in seen:
            items.append(
                ProfileImportItem(
                    index=index,
                    name=candidate.name,
                    status="duplicate",
                    reasons=[f"与第 {seen[key] + 1} 条重复"],
                )
            )
            continue
        seen[key] = index

        existing_profile = existing_keys.get(key)
        if existing_profile is not None:
            items.append(
                ProfileImportItem(
                    index=index,
                    name=candidate.name,
                    status="duplicate",
                    reasons=["已存在同名、同协议、同地址的供应商"],
                    conflict_profile_id=existing_profile.id,
                )
            )
            continue

        folded_name = candidate.name.casefold()
        if folded_name in existing_names:
            items.append(
                ProfileImportItem(
                    index=index,
                    name=candidate.name,
                    status="invalid",
                    reasons=["名称已被另一个供应商占用"],
                )
            )
            continue
        if folded_name in seen_names:
            items.append(
                ProfileImportItem(
                    index=index,
                    name=candidate.name,
                    status="invalid",
                    reasons=[f"名称与第 {seen_names[folded_name] + 1} 条冲突"],
                )
            )
            continue
        seen_names[folded_name] = index
        items.append(ProfileImportItem(index=index, name=candidate.name, status="new"))

    return items, candidates


def _plan(
    items: list[ProfileImportItem],
    candidates: dict[int, ProfileCreate],
    existing: list[Profile],
    policy: ImportPolicy,
) -> tuple[list[tuple[_DedupeKey, ProfileCreate]], list[tuple[str, ProfileCreate]]]:
    creates: dict[_DedupeKey, ProfileCreate] = {}
    overwrites: dict[str, ProfileCreate] = {}
    for item in items:
        candidate = candidates.get(item.index)
        if candidate is None:
            continue
        key = _key(candidate.name, candidate.protocol, candidate.base_url)
        if item.status == "new":
            creates[key] = candidate
        elif item.status == "duplicate" and policy == "overwrite":
            if item.conflict_profile_id is None:
                creates[key] = candidate
            else:
                overwrites[item.conflict_profile_id] = candidate
    return list(creates.items()), list(overwrites.items())


def _totals(items: list[ProfileImportItem]) -> ProfileImportTotals:
    return ProfileImportTotals(
        new=sum(1 for item in items if item.status == "new"),
        duplicate=sum(1 for item in items if item.status == "duplicate"),
        invalid=sum(1 for item in items if item.status == "invalid"),
    )


def _key(name: str, protocol: str, base_url: str) -> _DedupeKey:
    return (name.casefold(), protocol, base_url)


def _find(profile_id: str, profiles: Iterable[Profile]) -> Profile:
    for profile in profiles:
        if profile.id == profile_id:
            return profile
    raise AppError("PROFILE_NOT_FOUND", f"档案不存在: {profile_id}", 404)


def _format_error(error: ErrorDetails) -> str:
    location = ".".join(str(part) for part in error.get("loc", ()) if part != "body") or "字段"
    message = str(error.get("msg", "校验失败"))
    return f"{location}: {message}"
