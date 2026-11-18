"""托管字段适配器的共享渲染 / 校验实现。

适配器只负责把档案映射成 `ToolPlanFile.edits`; 本模块统一负责:

- `render`: 复用 007 的保真编辑器, 纯函数、同输入同输出;
- `verify`: 先断言每个 set / remove 字段符合预期, 再比较「移除托管路径后的剩余
  结构」, 确保注释 / 键序 / 未知字段没有被破坏;
- 计划期解析助手: 无法保证保真时抛 `UNSAFE_WRITE`, 由适配器转成 blocker。

所有函数都不读写磁盘; 真正落盘只发生在 007 的 `WriteEngine`。
"""

from __future__ import annotations

import json
from collections.abc import Mapping, MutableMapping, Sequence
from typing import Literal

import tomlkit
from tomlkit.exceptions import ParseError

from app.adapters.base import (
    ToolBlocker,
    ToolCapabilities,
    ToolPlanFile,
    WriteBlockerCode,
)
from app.core.errors import AppError
from app.core.format_edits import DocumentFormat, FieldEdit, render_document, verify_rendered
from app.core.redaction import redact_secret
from app.schemas.profile import ProfileProtocol
from app.schemas.snapshot import SnapshotChange

MISSING: object = object()


class ManagedFieldsAdapter:
    """两个工具共用的写能力基线; 子类只需实现 `plan` 与只读契约。"""

    capabilities = ToolCapabilities(
        write=True, sessions=True, launch=True, write_mode="managed_fields"
    )
    supported_protocols: tuple[ProfileProtocol, ...] = ()

    def render(self, plan_file: ToolPlanFile, original_bytes: bytes) -> bytes:
        """按计划渲染; 不读写磁盘, 相同输入必须得到相同输出。"""
        rendered = render_document(original_bytes, plan_file.edits, plan_file.format)
        return rendered.encode("utf-8")

    def verify(
        self,
        plan_file: ToolPlanFile,
        original_bytes: bytes,
        rendered_bytes: bytes,
    ) -> None:
        """校验目标字段与未托管内容; 不满足时抛 `WRITE_VERIFY_FAILED`。"""
        verify_rendered(original_bytes, rendered_bytes, plan_file.edits, plan_file.format)
        if not unknown_content_preserved(
            original_bytes,
            rendered_bytes,
            plan_file.edits,
            plan_file.format,
        ):
            raise AppError(
                "WRITE_VERIFY_FAILED",
                f"渲染破坏了未托管内容: {plan_file.path}",
                500,
            )


class PlanBuilder:
    """收集一个文件的 edits 与展示用 changes, 保证两者一一对应且密钥已脱敏。"""

    def __init__(self, file_path: str) -> None:
        self.file_path = file_path
        self.edits: list[FieldEdit] = []
        self.changes: list[SnapshotChange] = []

    def set(self, path: Sequence[str], value: str | int | bool, before: str | None) -> None:
        self.edits.append(FieldEdit(path=list(path), action="set", value=value))
        self.changes.append(_change(self.file_path, path, "set", before, value))

    def set_secret(self, path: Sequence[str], secret: str, before: str | None) -> None:
        """密钥的 before / after 只展示脱敏值; 编辑本身仍携带真实值供写入。"""
        self.edits.append(FieldEdit(path=list(path), action="set", value=secret))
        self.changes.append(
            _change(
                self.file_path,
                path,
                "set",
                _redacted(before),
                _redacted(secret),
            )
        )

    def remove(self, path: Sequence[str], before: str | None) -> None:
        self.edits.append(FieldEdit(path=list(path), action="remove"))
        self.changes.append(_change(self.file_path, path, "remove", before, None))

    def remove_secret(self, path: Sequence[str], before: str | None) -> None:
        self.edits.append(FieldEdit(path=list(path), action="remove"))
        self.changes.append(_change(self.file_path, path, "remove", _redacted(before), None))

    def build(self, format: DocumentFormat, *, create: bool = True) -> ToolPlanFile:
        return ToolPlanFile(
            path=self.file_path,
            format=format,
            edits=self.edits,
            changes=self.changes,
            create=create,
        )


def display_value(value: object) -> str | None:
    """把配置值转成展示字符串; 只接受字符串, 不做猜测性格式化。"""
    if isinstance(value, str):
        return value
    unwrap = getattr(value, "unwrap", None)
    if callable(unwrap):
        unwrapped = unwrap()
        return unwrapped if isinstance(unwrapped, str) else None
    return None


def parse_json_object(data: bytes | None) -> dict[str, object]:
    """解析 JSON 对象; 缺失 / 空文件视为 `{}`, 失败抛带稳定 code 的 `AppError`。"""
    if data is None or not data.strip():
        return {}
    text = decode_utf8(data)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AppError(
            "PARSE_ERROR",
            f"JSON 第 {exc.lineno} 行第 {exc.colno} 列格式错误",
            400,
        ) from exc
    if not isinstance(parsed, dict):
        raise AppError("UNSAFE_WRITE", "JSON 顶层不是对象", 400)
    return parsed


def parse_toml_table(data: bytes | None) -> Mapping[str, object]:
    """解析 TOML; 缺失 / 空文件视为空表, 解析失败抛 `PARSE_ERROR`。"""
    if data is None or not data.strip():
        return {}
    text = decode_utf8(data)
    try:
        return tomlkit.parse(text)
    except ParseError as exc:
        raise AppError("PARSE_ERROR", "TOML 格式错误", 400) from exc


def decode_utf8(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise AppError("UNSAFE_WRITE", "目标文件不是有效的 UTF-8 文本", 400) from exc


def blocker_for_error(exc: AppError, path: str) -> ToolBlocker:
    """计划期只允许把解析类错误降级成 blocker; 其他异常照常上抛。"""
    code: WriteBlockerCode
    if exc.code == "UNSUPPORTED_VERSION":
        code = "UNSUPPORTED_VERSION"
    elif exc.code == "PARSE_ERROR":
        code = "PARSE_ERROR"
    else:
        code = "UNSAFE_WRITE"
    return ToolBlocker(code=code, message=exc.message, path=path)


def unknown_content_preserved(
    original: bytes,
    rendered: bytes,
    edits: Sequence[FieldEdit],
    format: DocumentFormat,
) -> bool:
    """移除托管路径后比较剩余结构; key_value 按非托管行顺序比较。"""
    if format == "key_value":
        managed = {edit.path[0] for edit in edits if edit.path}
        return _kv_unmanaged_lines(original, managed) == _kv_unmanaged_lines(rendered, managed)

    try:
        before = _parse_for_compare(original, format)
        after = _parse_for_compare(rendered, format)
    except (ValueError, AppError):
        return False

    for edit in edits:
        _remove_leaf(before, edit.path)
        _remove_leaf(after, edit.path)
    for edit in edits:
        _prune_empty(before, edit.path)
        _prune_empty(after, edit.path)
    return _unwrap(before) == _unwrap(after)


def _change(
    file_path: str,
    path: Sequence[str],
    action: Literal["set", "remove"],
    before: str | None,
    after: str | int | bool | None,
) -> SnapshotChange:
    return SnapshotChange(
        path=file_path,
        field=".".join(path),
        action=action,
        before=before,
        after=None if after is None else str(after),
    )


def _redacted(value: str | None) -> str | None:
    return None if value is None else redact_secret(value)


def _parse_for_compare(data: bytes, format: DocumentFormat) -> object:
    if format == "json":
        text = data.decode("utf-8-sig")
        if not text.strip():
            return {}
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError("JSON 顶层不是对象")
        return parsed
    if format == "toml":
        text = data.decode("utf-8-sig")
        if not text.strip():
            return {}
        return tomlkit.parse(text)
    raise ValueError(f"不支持的文档格式: {format}")


def _remove_leaf(document: object, path: Sequence[str]) -> None:
    current: object = document
    for segment in path[:-1]:
        if not isinstance(current, MutableMapping) or segment not in current:
            return
        current = current[segment]
    if isinstance(current, MutableMapping):
        current.pop(path[-1], None)


def _prune_empty(document: object, path: Sequence[str]) -> None:
    """只清理编辑路径上因删除而变空的中间容器, 不碰无关的空对象。"""
    chain: list[tuple[MutableMapping[str, object], str, object]] = []
    current: object = document
    for segment in path[:-1]:
        if not isinstance(current, MutableMapping) or segment not in current:
            return
        child = current[segment]
        chain.append((current, segment, child))
        current = child
    for parent, key, child in reversed(chain):
        if isinstance(child, MutableMapping) and len(child) == 0:
            del parent[key]
        else:
            break


def _kv_unmanaged_lines(data: bytes, managed: set[str]) -> list[str]:
    text = data.decode("utf-8-sig")
    kept: list[str] = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if stripped and not stripped.startswith("#"):
            key = stripped.split("=", 1)[0].strip()
            if key in managed:
                continue
        kept.append(raw)
    return kept


def _unwrap(value: object) -> object:
    unwrap = getattr(value, "unwrap", None)
    if callable(unwrap):
        value = unwrap()
    if isinstance(value, Mapping):
        return {str(key): _unwrap(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_unwrap(item) for item in value]
    return value
