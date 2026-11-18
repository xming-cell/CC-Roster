"""本地导入供应商: 解析、逐条校验、去重预览与全或无写入。

文件是版本化 JSON / TOML; 校验规则复用 `ProfileCreate`, 不另写一套。
任何非法条目都会让整批导入失败, 不产生部分写入。
"""

from __future__ import annotations

import json
import logging
import os
import tomllib
import uuid
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from pydantic_core import ErrorDetails

from app.adapters.claude_code import resolve_claude_config_dir
from app.adapters.codex_cli import resolve_codex_config_dir
from app.adapters.gemini_cli import resolve_gemini_config_dir
from app.adapters.opencode import resolve_opencode_config_dir
from app.core.clock import utc_now
from app.core.errors import AppError
from app.repositories.audit import AuditRepository
from app.repositories.profiles import ProfileRepository
from app.repositories.secrets import SecretStore
from app.schemas.profile import Profile, ProfileCreate, ProfileStore, SecretRef, ToolBinding
from app.schemas.profile_import import (
    MAX_IMPORT_ITEMS,
    SUPPORTED_IMPORT_VERSION,
    ImportFormat,
    ImportPolicy,
    ImportSource,
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
        parsed, import_format = _parse_content(request.content)
        return self._preview_parsed(
            parsed,
            import_format=import_format,
            source="content",
            tool_id=request.tool_id,
        )

    def preview_codex(self) -> ProfileImportPreview:
        parsed, source_path = self._load_codex_config()
        return self._preview_parsed(
            parsed,
            import_format="toml",
            source="codex_config",
            source_path=str(source_path),
            tool_id="codex-cli",
        )

    def preview_local(self, tool_id: str) -> ProfileImportPreview:
        parsed, source_path, import_format = self._load_local_config(tool_id)
        return self._preview_parsed(
            parsed,
            import_format=import_format,
            source="local_config",
            source_path=str(source_path),
            tool_id=tool_id,
        )

    def _preview_parsed(
        self,
        parsed: list[Any],
        *,
        import_format: ImportFormat,
        source: ImportSource,
        source_path: str | None = None,
        tool_id: str | None = None,
    ) -> ProfileImportPreview:
        store = self._repository.load()
        items, _candidates = _analyze(parsed, store.profiles)
        totals = _totals(items)
        return ProfileImportPreview(
            schema_version=SUPPORTED_IMPORT_VERSION,
            items=items,
            totals=totals,
            can_import=totals.invalid == 0,
            source=source,
            source_path=source_path,
            format=import_format,
            tool_id=tool_id,
        )

    def import_profiles(self, request: ProfileImportRequest) -> ProfileImportResult:
        parsed, _import_format = _parse_content(request.content)
        return self._import_parsed(
            parsed,
            request.policy,
            source_label="导入供应商",
            bind_tool_id=request.tool_id,
        )

    def import_codex(self, policy: ImportPolicy) -> ProfileImportResult:
        parsed, _source_path = self._load_codex_config()
        return self._import_parsed(
            parsed,
            policy,
            source_label="从 Codex 配置导入供应商",
            bind_tool_id="codex-cli",
        )

    def import_local(self, tool_id: str, policy: ImportPolicy) -> ProfileImportResult:
        parsed, _source_path, _import_format = self._load_local_config(tool_id)
        return self._import_parsed(
            parsed,
            policy,
            source_label=f"从 {tool_id} 本机配置导入供应商",
            bind_tool_id=tool_id,
        )

    def _import_parsed(
        self,
        parsed: list[Any],
        policy: ImportPolicy,
        *,
        source_label: str,
        bind_tool_id: str | None = None,
    ) -> ProfileImportResult:
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

        creates, overwrites = _plan(items, candidates, store.profiles, policy)
        now = utc_now()
        created_secret_refs: list[SecretRef] = []
        created_profiles: list[tuple[_DedupeKey, Profile]] = []
        overwritten_profiles: list[tuple[str, Profile, SecretRef | None]] = []
        bindings_to_add: list[ToolBinding] = []

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

            if bind_tool_id is not None:
                bound_pairs = {(binding.tool_id, binding.profile_id) for binding in store.bindings}
                for _key_value, profile in created_profiles:
                    pair = (bind_tool_id, profile.id)
                    if pair not in bound_pairs:
                        bindings_to_add.append(
                            ToolBinding(tool_id=bind_tool_id, profile_id=profile.id, bound_at=now)
                        )
                        bound_pairs.add(pair)
                for existing_id, _profile, _ref in overwritten_profiles:
                    pair = (bind_tool_id, existing_id)
                    if pair not in bound_pairs:
                        bindings_to_add.append(
                            ToolBinding(tool_id=bind_tool_id, profile_id=existing_id, bound_at=now)
                        )
                        bound_pairs.add(pair)

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
                existing_pairs = {
                    (binding.tool_id, binding.profile_id) for binding in current.bindings
                }
                for binding in bindings_to_add:
                    pair = (binding.tool_id, binding.profile_id)
                    if pair not in existing_pairs:
                        current.bindings.append(binding)
                        existing_pairs.add(pair)

            self._repository.mutate(change)
        except Exception:
            for ref in created_secret_refs:
                try:
                    self._secrets.delete(ref)
                except Exception:  # 补偿失败不能掩盖主错误
                    logger.warning("导入失败后清理密钥失败", exc_info=True)
            raise

        skipped = totals.duplicate if policy == "skip" else 0
        self._record_audit(
            imported=len(created_profiles),
            overwritten=len(overwritten_profiles),
            skipped=skipped,
            source_label=source_label,
        )
        return ProfileImportResult(
            imported=len(created_profiles),
            overwritten=len(overwritten_profiles),
            skipped=skipped,
            profile_ids=[profile.id for _key_value, profile in created_profiles]
            + [existing_id for existing_id, _profile, _ref in overwritten_profiles],
        )

    def _load_codex_config(self) -> tuple[list[Any], Path]:
        path = resolve_codex_config_dir(environ=os.environ, home=Path.home()) / "config.toml"
        try:
            content = path.read_text(encoding="utf-8-sig")
        except FileNotFoundError as exc:
            raise AppError("CODEX_CONFIG_NOT_FOUND", f"未找到 Codex 配置文件: {path}", 422) from exc
        except OSError as exc:
            raise AppError(
                "CODEX_CONFIG_UNREADABLE", f"无法读取 Codex 配置文件: {path}", 422
            ) from exc
        return _parse_codex_config(content), path

    def _load_local_config(self, tool_id: str) -> tuple[list[Any], Path, ImportFormat]:
        home = Path.home()
        if tool_id == "codex-cli":
            parsed, path = self._load_codex_config()
            return parsed, path, "toml"
        if tool_id == "claude-code":
            path = resolve_claude_config_dir(environ=os.environ, home=home) / "settings.json"
            return _claude_candidates(_read_json_config(path, "Claude Code")), path, "json"
        if tool_id == "gemini-cli":
            path = resolve_gemini_config_dir(environ=os.environ, home=home) / "settings.json"
            return _gemini_candidates(_read_json_config(path, "Gemini CLI")), path, "json"
        if tool_id == "opencode":
            path = resolve_opencode_config_dir(environ=os.environ, home=home) / "opencode.json"
            return _opencode_candidates(_read_json_config(path, "OpenCode")), path, "json"
        raise AppError("LOCAL_IMPORT_UNSUPPORTED_TOOL", f"不支持从本机配置导入: {tool_id}", 422)

    def _put_secret(self, profile_id: str, candidate: ProfileCreate) -> SecretRef | None:
        if candidate.secret is None:
            return None
        if not candidate.secret.strip():
            raise AppError("VALIDATION_ERROR", "密钥不能为空", 422)
        return self._secrets.put(profile_id, candidate.secret)

    def _record_audit(
        self, *, imported: int, overwritten: int, skipped: int, source_label: str
    ) -> None:
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
                message=f"{source_label}: 新增 {imported}、覆盖 {overwritten}、跳过 {skipped}",
            )
        except Exception:
            logger.warning("供应商导入审计写入失败", exc_info=True)


def _parse_content(content: str) -> tuple[list[Any], ImportFormat]:
    cleaned = content.lstrip("\ufeff")
    if not cleaned.strip():
        raise AppError("IMPORT_EMPTY", "导入文件里没有供应商", 422)
    stripped = cleaned.lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise AppError("IMPORT_INVALID_JSON", "文件不是合法 JSON", 422) from exc
        return _extract_profiles(data), "json"
    return _extract_profiles(_load_toml(cleaned)), "toml"


def _load_toml(content: str) -> dict[str, Any]:
    try:
        data = tomllib.loads(content)
    except tomllib.TOMLDecodeError as exc:
        raise AppError("IMPORT_INVALID_TOML", "文件不是合法 TOML", 422) from exc
    if not isinstance(data, dict):
        raise AppError("IMPORT_INVALID_SHAPE", "导入文件顶层必须是 TOML 表", 422)
    return data


def _extract_profiles(data: Any) -> list[Any]:
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


def _read_json_config(path: Path, label: str) -> dict[str, Any]:
    try:
        content = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError as exc:
        raise AppError("LOCAL_CONFIG_NOT_FOUND", f"未找到 {label} 配置文件: {path}", 422) from exc
    except OSError as exc:
        raise AppError(
            "LOCAL_CONFIG_UNREADABLE", f"无法读取 {label} 配置文件: {path}", 422
        ) from exc
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise AppError("LOCAL_CONFIG_PARSE_ERROR", f"{label} 配置不是合法 JSON", 422) from exc
    if not isinstance(parsed, dict):
        raise AppError("LOCAL_CONFIG_INVALID_SHAPE", f"{label} 配置顶层必须是对象", 422)
    return parsed


def _text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _models(values: Iterable[object]) -> list[dict[str, object]]:
    seen: set[str] = set()
    result: list[dict[str, object]] = []
    for value in values:
        model = _text(value)
        if model is None or model in seen:
            continue
        seen.add(model)
        result.append({"id": model, "display_name": None})
    return result


def _claude_candidates(data: dict[str, Any]) -> list[Any]:
    raw_env = data.get("env")
    env = raw_env if isinstance(raw_env, Mapping) else {}
    base_url = _text(env.get("ANTHROPIC_BASE_URL"))
    secret = _text(env.get("ANTHROPIC_AUTH_TOKEN")) or _text(env.get("ANTHROPIC_API_KEY"))
    models = _models(
        [
            env.get("ANTHROPIC_MODEL"),
            env.get("ANTHROPIC_DEFAULT_OPUS_MODEL"),
            env.get("ANTHROPIC_DEFAULT_SONNET_MODEL"),
            env.get("ANTHROPIC_DEFAULT_HAIKU_MODEL"),
            data.get("model"),
        ]
    )
    if base_url is None and secret is None and not models:
        raise AppError("LOCAL_CONFIG_EMPTY", "Claude Code 配置里没有可导入的供应商字段", 422)
    notes: list[str] = []
    if base_url is None:
        base_url = "https://api.anthropic.com"
        notes.append("base_url 来自 Anthropic 官方默认值")
    if secret is None:
        notes.append("未发现本机密钥, 导入后需在供应商页补充")
    candidate: dict[str, Any] = {
        "name": "Anthropic 本机配置",
        "protocol": "anthropic",
        "base_url": base_url,
        "models": models,
    }
    if secret is not None:
        candidate["secret"] = secret
    if notes:
        candidate["_import_notes"] = notes
    return [candidate]


def _gemini_candidates(data: dict[str, Any]) -> list[Any]:
    base_url = _text(data.get("baseUrl"))
    if base_url is None:
        raise AppError("LOCAL_CONFIG_EMPTY", "Gemini CLI 配置缺少 baseUrl, 无法生成供应商", 422)
    model = _text(data.get("model"))
    return [
        {
            "name": "Gemini 本机配置",
            "protocol": "openai",
            "base_url": base_url,
            "models": _models([model]),
            "_import_notes": ["未读取环境变量中的 API key, 导入后需在供应商页补充"],
        }
    ]


def _opencode_candidates(data: dict[str, Any]) -> list[Any]:
    raw_provider = data.get("provider")
    provider = raw_provider if isinstance(raw_provider, Mapping) else {}
    raw_openai = provider.get("openai")
    openai = raw_openai if isinstance(raw_openai, Mapping) else {}
    raw_options = openai.get("options")
    options = raw_options if isinstance(raw_options, Mapping) else {}
    base_url = _text(options.get("baseURL"))
    if base_url is None:
        raise AppError(
            "LOCAL_CONFIG_EMPTY", "OpenCode 配置缺少 provider.openai.options.baseURL", 422
        )
    model = _text(data.get("model"))
    return [
        {
            "name": "OpenCode 本机配置",
            "protocol": "openai",
            "base_url": base_url,
            "models": _models([model]),
            "_import_notes": ["未读取环境变量中的 API key, 导入后需在供应商页补充"],
        }
    ]


def _parse_codex_config(content: str) -> list[Any]:
    data = _load_toml(content)
    raw_providers = data.get("model_providers")
    if not isinstance(raw_providers, Mapping) or len(raw_providers) == 0:
        raise AppError("CODEX_NO_PROVIDERS", "Codex 配置里没有 model_providers", 422)
    default_model = data.get("model")
    model_entries = (
        [{"id": default_model, "display_name": None}]
        if isinstance(default_model, str) and default_model.strip()
        else []
    )
    used_names: set[str] = set()
    parsed: list[Any] = []
    for provider_id, raw in raw_providers.items():
        provider_key = str(provider_id)
        if not isinstance(raw, Mapping):
            parsed.append(
                {
                    "_import_name": provider_key,
                    "_import_invalid_reason": "provider 配置必须是 TOML 表",
                }
            )
            continue
        raw_name = raw.get("name")
        base_name = raw_name if isinstance(raw_name, str) and raw_name.strip() else provider_key
        name = base_name
        if name.casefold() in used_names:
            name = f"{base_name} ({provider_key})"
        used_names.add(name.casefold())

        wire_api = raw.get("wire_api")
        if wire_api not in {"responses", "chat"}:
            parsed.append(
                {
                    "_import_name": name,
                    "_import_invalid_reason": "wire_api 只接受 responses / chat",
                }
            )
            continue
        base_url = raw.get("base_url")
        if not isinstance(base_url, str) or not base_url.strip():
            parsed.append(
                {
                    "_import_name": name,
                    "_import_invalid_reason": "base_url 不能为空",
                }
            )
            continue

        token = raw.get("experimental_bearer_token")
        secret = token if isinstance(token, str) and token.strip() else None
        notes: list[str] = []
        env_key = raw.get("env_key")
        if secret is None and isinstance(env_key, str) and env_key.strip():
            notes.append("未读取 env_key, 导入后需在供应商页补充密钥")
        candidate: dict[str, Any] = {
            "name": name,
            "protocol": "openai",
            "base_url": base_url,
            "models": model_entries,
        }
        if secret is not None:
            candidate["secret"] = secret
        if notes:
            candidate["_import_notes"] = notes
        parsed.append(candidate)
    return parsed


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
        name_value = raw.get("_import_name", raw.get("name"))
        display_name = name_value if isinstance(name_value, str) else None
        raw_notes = raw.get("_import_notes", [])
        notes = [str(note) for note in raw_notes] if isinstance(raw_notes, list) else []
        raw_secret = raw.get("secret")
        has_secret = isinstance(raw_secret, str) and bool(raw_secret.strip())
        invalid_reason = raw.get("_import_invalid_reason")
        if isinstance(invalid_reason, str) and invalid_reason:
            items.append(
                ProfileImportItem(
                    index=index,
                    name=display_name,
                    status="invalid",
                    reasons=[invalid_reason],
                    notes=notes,
                    has_secret=has_secret,
                )
            )
            continue
        sanitized = {key: value for key, value in raw.items() if not key.startswith("_import_")}
        try:
            candidate = ProfileCreate.model_validate(sanitized)
        except ValidationError as exc:
            items.append(
                ProfileImportItem(
                    index=index,
                    name=display_name,
                    status="invalid",
                    reasons=[_format_error(error) for error in exc.errors()],
                    notes=notes,
                    has_secret=has_secret,
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
                    notes=notes,
                    has_secret=has_secret,
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
                    notes=notes,
                    has_secret=has_secret,
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
                    notes=notes,
                    has_secret=has_secret,
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
                    notes=notes,
                    has_secret=has_secret,
                )
            )
            continue
        seen_names[folded_name] = index
        items.append(
            ProfileImportItem(
                index=index,
                name=candidate.name,
                status="new",
                notes=notes,
                has_secret=has_secret,
            )
        )

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
