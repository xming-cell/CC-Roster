"""档案业务服务: CRUD、复制、删除保护与对外视图组装。

档案与密钥分开存储。带密钥的写入遵循「先密钥、后档案」的顺序:
档案保存失败时用 `rollback_secret` 恢复旧值, 不留下无提示的半状态。
本层不依赖 FastAPI, 也不直接读写文件。
"""

import uuid
from collections.abc import Iterable, Sequence

from app.core.clock import utc_now
from app.core.errors import AppError
from app.core.redaction import redact_secret
from app.repositories.profiles import ProfileRepository
from app.repositories.secrets import SecretStore, rollback_secret
from app.schemas.profile import (
    MAX_PROFILE_NAME_LENGTH,
    BindingDeleteResponse,
    BindingView,
    ModelEntry,
    Profile,
    ProfileCopyRequest,
    ProfileCreate,
    ProfileDeleteResponse,
    ProfileListResponse,
    ProfileStore,
    ProfileUpdate,
    ProfileView,
    ProfileWarning,
    SecretRef,
    SecretStoreStatus,
    ToolBinding,
    ToolRef,
)
from app.schemas.tool import ToolView
from app.services.tool_discovery import ToolDiscoveryService


class ProfileService:
    """档案用例边界; 仓储、密钥与工具发现都通过构造参数注入。"""

    def __init__(
        self,
        repository: ProfileRepository,
        secrets: SecretStore,
        tools: ToolDiscoveryService,
    ) -> None:
        self._repository = repository
        self._secrets = secrets
        self._tools = tools

    def list_profiles(self) -> ProfileListResponse:
        store = self._repository.load()
        discovered = self._installed_tools()
        status = self._secrets.status()
        return ProfileListResponse(
            profiles=[
                self._build_view(profile, store.bindings, discovered) for profile in store.profiles
            ],
            bindings=[
                BindingView.model_validate(binding.model_dump()) for binding in store.bindings
            ],
            secret_store=status,
            warnings=_store_warnings(status),
        )

    def get_profile(self, profile_id: str) -> ProfileView:
        store = self._repository.load()
        profile = _find_profile(store.profiles, profile_id)
        return self._build_view(profile, store.bindings, self._installed_tools())

    def create_profile(self, payload: ProfileCreate) -> ProfileView:
        _reject_duplicate_models(payload.models)
        profile_id = str(uuid.uuid4())
        secret_ref = self._write_secret(profile_id, payload.secret)
        now = utc_now()
        profile = Profile(
            id=profile_id,
            name=payload.name,
            protocol=payload.protocol,
            base_url=payload.base_url,
            secret_ref=secret_ref,
            models=payload.models,
            created_at=now,
            updated_at=now,
        )
        try:
            self._repository.mutate(lambda store: self._append_profile(store, profile))
        except Exception:
            _rollback_new_secret(self._secrets, secret_ref)
            raise
        return self._build_view(profile, [], {})

    def update_profile(self, profile_id: str, payload: ProfileUpdate) -> ProfileView:
        if not payload.model_fields_set:
            return self.get_profile(profile_id)
        _reject_explicit_nulls(payload)
        if payload.models is not None:
            _reject_duplicate_models(payload.models)

        current = self._find_or_404(profile_id)
        old_ref = current.secret_ref
        secret_update = "secret" in payload.model_fields_set
        previous_secret: str | None = None
        new_ref = old_ref

        if secret_update:
            if payload.secret is None:
                if old_ref is not None:
                    previous_secret = self._read_secret_quietly(old_ref)
                    self._secrets.delete(old_ref)
                new_ref = None
            else:
                if not payload.secret.strip():
                    raise AppError("VALIDATION_ERROR", "密钥不能为空", 422)
                if old_ref is not None:
                    previous_secret = self._read_secret_quietly(old_ref)
                new_ref = self._secrets.put(profile_id, payload.secret)

        updates: dict[str, object] = {
            "secret_ref": new_ref,
            "updated_at": utc_now(),
        }
        if "name" in payload.model_fields_set:
            updates["name"] = payload.name
        if "protocol" in payload.model_fields_set:
            updates["protocol"] = payload.protocol
        if "base_url" in payload.model_fields_set:
            updates["base_url"] = payload.base_url
        if "models" in payload.model_fields_set:
            updates["models"] = payload.models
        updated = Profile.model_validate(current.model_dump() | updates)

        try:
            self._repository.mutate(lambda store: self._replace_profile(store, updated))
        except Exception:
            if secret_update:
                self._restore_secret(old_ref, new_ref, previous_secret)
            raise

        cleanup_failed = False
        if (
            secret_update
            and old_ref is not None
            and new_ref is not None
            and old_ref.backend != new_ref.backend
        ):
            try:
                self._secrets.delete(old_ref)
            except AppError:
                cleanup_failed = True

        view = self._build_view(
            updated,
            self._repository.list_bindings(),
            self._installed_tools(),
        )
        if cleanup_failed:
            view.warnings.append(
                ProfileWarning(
                    code="SECRET_STORE_ERROR",
                    message="新密钥已保存, 但旧后端的密钥清理失败",
                )
            )
        return view

    def copy_profile(
        self,
        profile_id: str,
        payload: ProfileCopyRequest | None,
    ) -> ProfileView:
        source = self._find_or_404(profile_id)
        source_warnings: list[ProfileWarning] = []
        source_secret: str | None = None
        if source.secret_ref is not None:
            try:
                source_secret = self._secrets.get(source.secret_ref)
            except AppError as exc:
                source_warnings.append(
                    ProfileWarning(code="SECRET_STORE_ERROR", message=exc.message)
                )
            else:
                if source_secret is None:
                    source_warnings.append(
                        ProfileWarning(
                            code="SECRET_MISSING",
                            message="原档案的密钥已丢失, 副本未包含密钥",
                        )
                    )

        copy_id = str(uuid.uuid4())
        new_ref = self._write_secret(copy_id, source_secret)
        requested_name = payload.name if payload is not None else None

        def change(store: ProfileStore) -> Profile:
            current_source = _find_profile(store.profiles, profile_id)
            name = requested_name
            if name is None:
                name = _next_copy_name(current_source.name, store.profiles)
            _ensure_name_available(store.profiles, name)
            now = utc_now()
            copied = Profile(
                id=copy_id,
                name=name,
                protocol=current_source.protocol,
                base_url=current_source.base_url,
                secret_ref=new_ref,
                models=current_source.models,
                created_at=now,
                updated_at=now,
            )
            store.profiles.append(copied)
            return copied

        try:
            copied = self._repository.mutate(change)
        except Exception:
            _rollback_new_secret(self._secrets, new_ref)
            raise

        view = self._build_view(copied, [], {})
        view.warnings.extend(source_warnings)
        return view

    def delete_profile(self, profile_id: str, *, confirm: bool) -> ProfileDeleteResponse:
        discovered = self._installed_tools()

        def change(store: ProfileStore) -> tuple[Profile, list[ToolBinding]]:
            profile = _find_profile(store.profiles, profile_id)
            bindings = [binding for binding in store.bindings if binding.profile_id == profile_id]
            if bindings and not confirm:
                names = "、".join(
                    reference.display_name for reference in _tool_refs(bindings, discovered)
                )
                raise AppError(
                    "PROFILE_IN_USE",
                    f"档案仍被以下工具使用: {names}",
                    409,
                )
            store.bindings = [
                binding for binding in store.bindings if binding.profile_id != profile_id
            ]
            store.profiles = [stored for stored in store.profiles if stored.id != profile_id]
            return profile, bindings

        profile, bindings = self._repository.mutate(change)
        if profile.secret_ref is not None:
            self._secrets.delete(profile.secret_ref)
        return ProfileDeleteResponse(
            deleted=True,
            unbound_tools=_tool_refs(bindings, discovered),
        )

    def bind_tool(self, tool_id: str, profile_id: str) -> BindingView:
        """把已安装工具指向档案; 同一档案重复绑定保持 `bound_at` 不变。"""
        self._tools.get_tool(tool_id)

        def change(store: ProfileStore) -> ToolBinding:
            _find_profile(store.profiles, profile_id)
            existing = next(
                (binding for binding in store.bindings if binding.tool_id == tool_id),
                None,
            )
            if existing is not None and existing.profile_id == profile_id:
                return existing
            binding = ToolBinding(
                tool_id=tool_id,
                profile_id=profile_id,
                bound_at=utc_now(),
            )
            store.bindings = [stored for stored in store.bindings if stored.tool_id != tool_id]
            store.bindings.append(binding)
            return binding

        binding = self._repository.mutate(change)
        return BindingView.model_validate(binding.model_dump())

    def unbind_tool(self, tool_id: str) -> BindingDeleteResponse:
        """解除工具绑定; 不要求工具仍安装, 重复解绑返回 `removed=false`。"""

        def change(store: ProfileStore) -> bool:
            remaining = [binding for binding in store.bindings if binding.tool_id != tool_id]
            removed = len(remaining) != len(store.bindings)
            store.bindings = remaining
            return removed

        return BindingDeleteResponse(
            tool_id=tool_id,
            removed=self._repository.mutate(change),
        )

    def _find_or_404(self, profile_id: str) -> Profile:
        profile = self._repository.get_profile(profile_id)
        if profile is None:
            raise _not_found(profile_id)
        return profile

    def _installed_tools(self) -> dict[str, ToolView]:
        """工具发现失败时降级为空目录, 不能拖垮档案列表。"""
        try:
            return {tool.id: tool for tool in self._tools.list_tools().tools}
        except Exception:  # 工具目录只是 used_by 的展示信息
            return {}

    def _write_secret(self, profile_id: str, secret: str | None) -> SecretRef | None:
        if secret is None:
            return None
        if not secret.strip():
            raise AppError("VALIDATION_ERROR", "密钥不能为空", 422)
        return self._secrets.put(profile_id, secret)

    def _read_secret_quietly(self, ref: SecretRef | None) -> str | None:
        """补偿只需要旧值; 读不到时按「无旧值」处理, 不阻塞用户操作。"""
        if ref is None:
            return None
        try:
            return self._secrets.get(ref)
        except AppError:
            return None

    def _restore_secret(
        self,
        old_ref: SecretRef | None,
        new_ref: SecretRef | None,
        previous_secret: str | None,
    ) -> None:
        """档案保存失败后的补偿: 新写入的删除, 被覆盖 / 清除的尽量写回。"""
        if new_ref is None:
            if old_ref is not None and previous_secret is not None:
                self._secrets.put(old_ref.locator, previous_secret)
            return
        if old_ref is not None and old_ref.backend == new_ref.backend:
            rollback_secret(self._secrets, new_ref, previous_secret)
            return
        rollback_secret(self._secrets, new_ref, None)

    def _build_view(
        self,
        profile: Profile,
        bindings: Iterable[ToolBinding],
        discovered: dict[str, ToolView],
    ) -> ProfileView:
        profile_bindings = [binding for binding in bindings if binding.profile_id == profile.id]
        warnings: list[ProfileWarning] = []
        has_secret = False
        preview: str | None = None
        if profile.secret_ref is not None:
            try:
                secret = self._secrets.get(profile.secret_ref)
            except AppError as exc:
                warnings.append(ProfileWarning(code="SECRET_STORE_ERROR", message=exc.message))
            else:
                if secret is None:
                    warnings.append(
                        ProfileWarning(
                            code="SECRET_MISSING",
                            message="密钥引用存在, 但密钥存储中没有对应条目",
                        )
                    )
                else:
                    has_secret = True
                    preview = redact_secret(secret)

        return ProfileView(
            id=profile.id,
            name=profile.name,
            protocol=profile.protocol,
            base_url=profile.base_url,
            models=profile.models,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
            has_secret=has_secret,
            secret_preview=preview,
            secret_backend=(profile.secret_ref.backend if profile.secret_ref is not None else None),
            used_by=_tool_refs(profile_bindings, discovered),
            warnings=warnings,
        )

    @staticmethod
    def _append_profile(store: ProfileStore, profile: Profile) -> None:
        _ensure_name_available(store.profiles, profile.name)
        store.profiles.append(profile)

    @staticmethod
    def _replace_profile(store: ProfileStore, updated: Profile) -> None:
        _find_profile(store.profiles, updated.id)
        _ensure_name_available(store.profiles, updated.name, exclude_id=updated.id)
        store.profiles = [
            updated if stored.id == updated.id else stored for stored in store.profiles
        ]


def _not_found(profile_id: str) -> AppError:
    return AppError("PROFILE_NOT_FOUND", f"档案不存在: {profile_id}", 404)


def _find_profile(profiles: Iterable[Profile], profile_id: str) -> Profile:
    for profile in profiles:
        if profile.id == profile_id:
            return profile
    raise _not_found(profile_id)


def _ensure_name_available(
    profiles: Iterable[Profile],
    name: str,
    *,
    exclude_id: str | None = None,
) -> None:
    folded = name.casefold()
    for profile in profiles:
        if profile.id == exclude_id:
            continue
        if profile.name.casefold() == folded:
            raise AppError(
                "PROFILE_NAME_CONFLICT",
                f"档案名称已存在: {name}",
                409,
            )


def _reject_duplicate_models(models: Sequence[ModelEntry]) -> None:
    seen: set[str] = set()
    duplicates: list[str] = []
    for model in models:
        if model.id in seen and model.id not in duplicates:
            duplicates.append(model.id)
        seen.add(model.id)
    if duplicates:
        raise AppError(
            "VALIDATION_ERROR",
            f"模型清单存在重复项: {', '.join(duplicates)}",
            422,
        )


def _reject_explicit_nulls(payload: ProfileUpdate) -> None:
    for field in payload.model_fields_set:
        if field == "secret":
            continue
        if getattr(payload, field) is None:
            raise AppError("VALIDATION_ERROR", f"字段 {field} 不能为 null", 422)


def _next_copy_name(base_name: str, profiles: Iterable[Profile]) -> str:
    existing = {profile.name.casefold() for profile in profiles}
    candidate = _with_copy_suffix(base_name, " (副本)")
    if candidate.casefold() not in existing:
        return candidate
    index = 2
    while True:
        candidate = _with_copy_suffix(base_name, f" (副本 {index})")
        if candidate.casefold() not in existing:
            return candidate
        index += 1


def _with_copy_suffix(base_name: str, suffix: str) -> str:
    available = MAX_PROFILE_NAME_LENGTH - len(suffix)
    return f"{base_name[:available].rstrip()}{suffix}"


def _tool_refs(
    bindings: Iterable[ToolBinding],
    discovered: dict[str, ToolView],
) -> list[ToolRef]:
    references: list[ToolRef] = []
    for binding in bindings:
        tool = discovered.get(binding.tool_id)
        references.append(
            ToolRef(
                tool_id=binding.tool_id,
                display_name=tool.display_name if tool is not None else binding.tool_id,
                installed=tool is not None,
            )
        )
    return references


def _store_warnings(status: SecretStoreStatus) -> list[ProfileWarning]:
    if status.backend != "unavailable":
        return []
    return [
        ProfileWarning(
            code="SECRET_STORE_ERROR",
            message=status.message or "密钥存储不可用",
        )
    ]


def _rollback_new_secret(secrets: SecretStore, ref: SecretRef | None) -> None:
    if ref is not None:
        rollback_secret(secrets, ref, None)
