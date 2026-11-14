"""保真编辑助手: JSON 区间替换、TOML round-trip、`KEY=VALUE` 行编辑。

`render_document` 是纯函数, 不读写盘; 渲染后由 `verify_rendered` 重新解析并断言目标
字段。无法安全定位目标、出现重复键、编码 / 解析失败时统一抛 `UNSAFE_WRITE`, 调用方
必须零写入。规则见 `specs/007-snapshot-kernel/spec.md`。
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, MutableMapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, cast

import tomlkit
from pydantic import BaseModel, ConfigDict, field_validator

from app.core.errors import AppError

DocumentFormat = Literal["json", "toml", "key_value"]
EditAction = Literal["set", "remove"]
EditValue = str | int | bool | None
JsonKind = Literal["object", "array", "scalar"]

_KV_LINE = re.compile(
    r"^(?P<indent>[ \t]*)(?P<key>[A-Za-z0-9_.-]+)(?P<sep>[ \t]*=[ \t]*)(?P<value>.*)$"
)
_KV_KEY = re.compile(r"^[A-Za-z0-9_.-]+$")


class FieldEdit(BaseModel):
    """一个字段编辑; `path` 是点分路径拆成的段列表。"""

    model_config = ConfigDict(extra="forbid")

    path: list[str]
    action: EditAction
    value: EditValue = None

    @field_validator("path")
    @classmethod
    def _validate_path(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("编辑路径不能为空")
        for segment in value:
            if not isinstance(segment, str) or not segment:
                raise ValueError("编辑路径段必须是非空字符串")
        return value


def render_document(
    original: bytes | str,
    edits: Sequence[FieldEdit],
    format: DocumentFormat,
) -> str:
    """按 `edits` 渲染文档, 保留未触及的字节; 输入不合法时抛 `UNSAFE_WRITE`。"""
    text = _decode(original)
    if format == "json":
        return _render_json(text, edits)
    if format == "toml":
        return _render_toml(text, edits)
    if format == "key_value":
        return _render_key_value(text, edits)
    raise _unsafe(f"不支持的文档格式: {format}")


def verify_rendered(
    original: bytes | str,
    rendered: bytes | str,
    edits: Sequence[FieldEdit],
    format: DocumentFormat,
) -> None:
    """重新解析渲染结果, 断言每个 set 字段等于目标、每个 remove 字段不存在。"""
    _decode(original)
    try:
        text = _decode(rendered)
        document = _parse_for_verify(text, format)
    except Exception as exc:
        message = exc.message if isinstance(exc, AppError) else "渲染结果无法重新解析"
        raise AppError("WRITE_VERIFY_FAILED", message, 500) from exc

    for edit in edits:
        found, actual = _lookup(document, edit.path, format)
        if edit.action == "set":
            if not found or not _values_equal(actual, edit.value):
                raise AppError(
                    "WRITE_VERIFY_FAILED",
                    f"渲染后字段值不符合预期: {'.'.join(edit.path)}",
                    500,
                )
        elif found:
            raise AppError(
                "WRITE_VERIFY_FAILED",
                f"渲染后字段仍然存在: {'.'.join(edit.path)}",
                500,
            )


def _decode(original: bytes | str) -> str:
    if isinstance(original, bytes):
        try:
            return original.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise _unsafe("文档不是合法 UTF-8") from exc
    return original


def _unsafe(message: str) -> AppError:
    return AppError("UNSAFE_WRITE", message, 400)


# ---------------------------------------------------------------------------
# JSON: 自写扫描器定位值区间, 只替换目标值, 不整份重排
# ---------------------------------------------------------------------------


@dataclass
class _JsonNode:
    kind: JsonKind
    start: int
    end: int
    members: list[_JsonMember] = field(default_factory=list)
    elements: list[_JsonNode] = field(default_factory=list)


@dataclass
class _JsonMember:
    key: str
    key_start: int
    value: _JsonNode


class _JsonParser:
    """只解析已通过 `json.loads` 的文本, 记录区间并拒绝重复键。"""

    def __init__(self, text: str) -> None:
        self._text = text
        self._pos = 0

    def parse(self) -> _JsonNode:
        self._skip_ws()
        node = self._parse_value()
        self._skip_ws()
        if self._pos != len(self._text):
            raise _unsafe("JSON 尾部存在无法识别的内容")
        if node.kind != "object":
            raise _unsafe("JSON 顶层必须是对象")
        return node

    def _skip_ws(self) -> None:
        text = self._text
        while self._pos < len(text) and text[self._pos] in " \t\r\n":
            self._pos += 1

    def _parse_value(self) -> _JsonNode:
        self._skip_ws()
        if self._pos >= len(self._text):
            raise _unsafe("JSON 意外结束")
        char = self._text[self._pos]
        if char == "{":
            return self._parse_object()
        if char == "[":
            return self._parse_array()
        if char == '"':
            start = self._pos
            self._scan_string()
            return _JsonNode(kind="scalar", start=start, end=self._pos)
        return self._parse_literal()

    def _parse_object(self) -> _JsonNode:
        start = self._pos
        self._pos += 1
        members: list[_JsonMember] = []
        seen: set[str] = set()
        self._skip_ws()
        if self._pos < len(self._text) and self._text[self._pos] == "}":
            self._pos += 1
            return _JsonNode(kind="object", start=start, end=self._pos)
        while True:
            self._skip_ws()
            key_start = self._pos
            key = self._scan_string()
            if key in seen:
                raise _unsafe(f"JSON 目标键重复出现: {key}")
            seen.add(key)
            self._skip_ws()
            if self._pos >= len(self._text) or self._text[self._pos] != ":":
                raise _unsafe("JSON 对象缺少冒号")
            self._pos += 1
            value = self._parse_value()
            members.append(_JsonMember(key=key, key_start=key_start, value=value))
            self._skip_ws()
            if self._pos >= len(self._text):
                raise _unsafe("JSON 对象意外结束")
            char = self._text[self._pos]
            if char == ",":
                self._pos += 1
                continue
            if char == "}":
                self._pos += 1
                return _JsonNode(
                    kind="object",
                    start=start,
                    end=self._pos,
                    members=members,
                )
            raise _unsafe("JSON 对象格式不合法")

    def _parse_array(self) -> _JsonNode:
        start = self._pos
        self._pos += 1
        elements: list[_JsonNode] = []
        self._skip_ws()
        if self._pos < len(self._text) and self._text[self._pos] == "]":
            self._pos += 1
            return _JsonNode(kind="array", start=start, end=self._pos, elements=elements)
        while True:
            elements.append(self._parse_value())
            self._skip_ws()
            if self._pos >= len(self._text):
                raise _unsafe("JSON 数组意外结束")
            char = self._text[self._pos]
            if char == ",":
                self._pos += 1
                continue
            if char == "]":
                self._pos += 1
                return _JsonNode(
                    kind="array",
                    start=start,
                    end=self._pos,
                    elements=elements,
                )
            raise _unsafe("JSON 数组格式不合法")

    def _scan_string(self) -> str:
        text = self._text
        if self._pos >= len(text) or text[self._pos] != '"':
            raise _unsafe("JSON 字符串格式不合法")
        start = self._pos
        self._pos += 1
        while self._pos < len(text):
            char = text[self._pos]
            if char == "\\":
                self._pos += 2
                continue
            if char == '"':
                self._pos += 1
                try:
                    return str(json.loads(text[start : self._pos]))
                except json.JSONDecodeError as exc:
                    raise _unsafe("JSON 字符串格式不合法") from exc
            self._pos += 1
        raise _unsafe("JSON 字符串未闭合")

    def _parse_literal(self) -> _JsonNode:
        start = self._pos
        text = self._text
        while self._pos < len(text) and text[self._pos] not in " \t\r\n,]}":
            self._pos += 1
        if self._pos == start:
            raise _unsafe("JSON 值格式不合法")
        try:
            json.loads(text[start : self._pos])
        except json.JSONDecodeError as exc:
            raise _unsafe("JSON 值格式不合法") from exc
        return _JsonNode(kind="scalar", start=start, end=self._pos)


def _render_json(text: str, edits: Sequence[FieldEdit]) -> str:
    bom = text.startswith("﻿")
    body = text[1:] if bom else text
    if body.strip() == "":
        rendered = _json_from_empty(body, edits)
    else:
        if not edits:
            return text
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError as exc:
            raise _unsafe("JSON 解析失败") from exc
        if not isinstance(parsed, dict):
            raise _unsafe("JSON 顶层必须是对象")
        current = body
        for edit in edits:
            current = _json_apply(current, edit)
        rendered = current
    return ("﻿" if bom else "") + rendered


def _json_from_empty(text: str, edits: Sequence[FieldEdit]) -> str:
    """空文件只在存在明确 set 目标时生成最小合法对象。"""
    set_edits = [edit for edit in edits if edit.action == "set"]
    if not set_edits:
        return text
    current = "{}"
    for edit in set_edits:
        current = _json_apply(current, edit)
    return current


def _json_apply(text: str, edit: FieldEdit) -> str:
    root = _JsonParser(text).parse()
    return _json_edit_object(text, root, edit.path, edit)


def _json_edit_object(
    text: str,
    node: _JsonNode,
    segments: Sequence[str],
    edit: FieldEdit,
) -> str:
    if node.kind != "object":
        raise _unsafe("JSON 中间路径不是对象")
    if not segments:
        raise _unsafe("编辑路径不能为空")

    member = next((item for item in node.members if item.key == segments[0]), None)
    if len(segments) == 1:
        if edit.action == "remove":
            if member is None:
                return text
            index = node.members.index(member)
            return _json_remove_member(text, node, index)
        value_literal = _json_scalar(edit.value)
        if member is None:
            return _json_insert_member(text, node, segments[0], value_literal)
        return text[: member.value.start] + value_literal + text[member.value.end :]

    if edit.action == "remove":
        if member is None:
            return text
        if member.value.kind != "object":
            raise _unsafe("JSON 中间路径不是对象")
        child_edited = _json_edit_object(text, member.value, segments[1:], edit)
        child_end = member.value.end + (len(child_edited) - len(text))
        return (
            text[: member.value.start]
            + child_edited[member.value.start : child_end]
            + text[member.value.end :]
        )

    if member is None:
        nested = _json_nested_object(segments[1:], _json_scalar(edit.value))
        return _json_insert_member(text, node, segments[0], nested)
    if member.value.kind != "object":
        raise _unsafe("JSON 中间路径不是对象")
    child_edited = _json_edit_object(text, member.value, segments[1:], edit)
    child_end = member.value.end + (len(child_edited) - len(text))
    return (
        text[: member.value.start]
        + child_edited[member.value.start : child_end]
        + text[member.value.end :]
    )


def _json_scalar(value: EditValue) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    raise _unsafe("JSON 值类型不受支持")


def _json_nested_object(
    segments: Sequence[str],
    value_literal: str,
) -> str:
    if len(segments) == 1:
        return f"{{{json.dumps(segments[0], ensure_ascii=False)}: {value_literal}}}"
    inner = _json_nested_object(segments[1:], value_literal)
    return f"{{{json.dumps(segments[0], ensure_ascii=False)}: {inner}}}"


def _json_insert_member(
    text: str,
    node: _JsonNode,
    key: str,
    value_literal: str,
) -> str:
    open_brace = node.start
    close_brace = node.end - 1
    member_text = f"{json.dumps(key, ensure_ascii=False)}: {value_literal}"

    if node.members:
        insert_at = node.members[-1].value.end
        if "\n" in text[node.start : node.end]:
            newline = _detect_newline(text)
            indent = _line_indent(text, node.members[0].key_start)
            addition = f",{newline}{indent}{member_text}"
        else:
            addition = f", {member_text}"
        return text[:insert_at] + addition + text[insert_at:]

    interior = text[open_brace + 1 : close_brace]
    if "\n" in interior:
        newline = _detect_newline(text)
        parent_indent = _line_indent(text, node.start)
        indent = parent_indent + "  "
        addition = f"{newline}{indent}{member_text}{newline}{parent_indent}"
    elif interior == "":
        addition = member_text
    else:
        addition = interior + member_text + interior
    return text[: open_brace + 1] + addition + text[close_brace:]


def _json_remove_member(text: str, node: _JsonNode, index: int) -> str:
    members = node.members
    if len(members) == 1:
        return text[: node.start + 1] + text[node.end - 1 :]
    if index == 0:
        start = members[0].key_start
        end = members[1].key_start
        return text[:start] + text[end:]
    start = members[index - 1].value.end
    end = members[index].value.end
    return text[:start] + text[end:]


# ---------------------------------------------------------------------------
# TOML: tomlkit round-trip
# ---------------------------------------------------------------------------


def _render_toml(text: str, edits: Sequence[FieldEdit]) -> str:
    bom = text.startswith("﻿")
    body = text[1:] if bom else text
    try:
        document = tomlkit.parse(body)
    except Exception as exc:
        raise _unsafe("TOML 解析失败") from exc

    changed = False
    for edit in edits:
        if _toml_apply(document, edit):
            changed = True
    if not changed:
        return text

    rendered = tomlkit.dumps(document)
    if "\r\n" in body:
        rendered = _to_crlf(rendered)
    return ("﻿" if bom else "") + rendered


def _toml_apply(document: tomlkit.TOMLDocument, edit: FieldEdit) -> bool:
    parent = cast("MutableMapping[str, Any]", document)
    for segment in edit.path[:-1]:
        if segment not in parent:
            if edit.action == "remove":
                return False
            table = tomlkit.table()
            parent[segment] = table
            parent = cast("MutableMapping[str, Any]", table)
            continue
        child = parent[segment]
        if not isinstance(child, MutableMapping):
            raise _unsafe("TOML 中间路径不是表")
        parent = child
    key = edit.path[-1]
    if edit.action == "remove":
        if key in parent:
            del parent[key]
            return True
        return False

    if edit.value is None:
        raise _unsafe("TOML 不支持 null 值")
    if key in parent and _toml_value_equals(parent[key], edit.value):
        return False
    parent[key] = _toml_value(edit.value)
    return True


def _toml_value(value: EditValue) -> str | int | bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return value
    raise _unsafe("TOML 值类型不受支持")


def _toml_value_equals(current: object, target: EditValue) -> bool:
    if hasattr(current, "unwrap"):
        current = current.unwrap()
    if isinstance(target, bool):
        return isinstance(current, bool) and current == target
    if isinstance(target, int):
        return isinstance(current, int) and not isinstance(current, bool) and current == target
    if isinstance(target, str):
        return isinstance(current, str) and current == target
    return False


# ---------------------------------------------------------------------------
# KEY=VALUE: 逐行编辑
# ---------------------------------------------------------------------------


@dataclass
class _KvLine:
    index: int
    content: str
    ending: str
    key: str | None
    indent: str = ""
    separator: str = ""
    value: str = ""
    trailing: str = ""


def _render_key_value(text: str, edits: Sequence[FieldEdit]) -> str:
    bom = text.startswith("﻿")
    body = text[1:] if bom else text
    lines = _kv_parse(body)

    for edit in edits:
        if len(edit.path) != 1:
            raise _unsafe("KEY=VALUE 只支持单段路径")
        key = edit.path[0]
        matches = [line for line in lines if line.key == key]
        if edit.action == "remove":
            if matches:
                lines = [line for line in lines if line.key != key]
            continue
        if len(matches) > 1:
            raise _unsafe(f"KEY=VALUE 键重复出现: {key}")
        value_text = _kv_format_value(edit.value, matches[0] if matches else None)
        if matches:
            matches[0].value = value_text
        else:
            if not _KV_KEY.fullmatch(key):
                raise _unsafe(f"KEY=VALUE 键名不合法: {key}")
            newline = _detect_newline(body) if body else "\n"
            if lines and not lines[-1].ending:
                lines[-1].ending = newline
            lines.append(
                _KvLine(
                    index=len(lines),
                    content=f"{key}={value_text}",
                    ending=newline,
                    key=key,
                    separator="=",
                    value=value_text,
                )
            )

    rendered = "".join(_kv_render_line(line) for line in lines)
    return ("﻿" if bom else "") + rendered


def _kv_parse(text: str) -> list[_KvLine]:
    lines: list[_KvLine] = []
    seen: set[str] = set()
    for index, raw in enumerate(text.splitlines(keepends=True)):
        content, ending = _split_line_ending(raw)
        parsed = _parse_kv_line(index, content, ending)
        if parsed.key is not None:
            if parsed.key in seen:
                raise _unsafe(f"KEY=VALUE 键重复出现: {parsed.key}")
            seen.add(parsed.key)
        lines.append(parsed)
    return lines


def _parse_kv_line(index: int, content: str, ending: str) -> _KvLine:
    stripped = content.strip()
    if not stripped or stripped.startswith("#"):
        return _KvLine(index=index, content=content, ending=ending, key=None)
    match = _KV_LINE.match(content)
    if match is None:
        raise _unsafe("无法解析 KEY=VALUE 行")
    raw_value = match.group("value")
    value, trailing = _split_inline_comment(raw_value)
    return _KvLine(
        index=index,
        content=content,
        ending=ending,
        key=match.group("key"),
        indent=match.group("indent"),
        separator=match.group("sep"),
        value=value,
        trailing=trailing,
    )


def _split_inline_comment(raw: str) -> tuple[str, str]:
    if raw.startswith(('"', "'")):
        quote = raw[0]
        index = 1
        while index < len(raw):
            if raw[index] == "\\":
                index += 2
                continue
            if raw[index] == quote:
                token = raw[: index + 1]
                rest = raw[index + 1 :]
                if rest.strip() and not rest.lstrip().startswith("#"):
                    raise _unsafe("KEY=VALUE 值后存在无法识别的内容")
                return token, rest
            index += 1
        raise _unsafe("KEY=VALUE 引号未闭合")
    comment_at = _comment_index(raw)
    if comment_at is None:
        return raw.rstrip(), raw[len(raw.rstrip()) :]
    value = raw[:comment_at].rstrip()
    return value, raw[len(value) :]


def _comment_index(raw: str) -> int | None:
    for index, char in enumerate(raw):
        if char == "#" and (index == 0 or raw[index - 1] in " \t"):
            return index
    return None


def _kv_render_line(line: _KvLine) -> str:
    if line.key is None:
        return line.content + line.ending
    return f"{line.indent}{line.key}{line.separator}{line.value}{line.trailing}{line.ending}"


def _kv_format_value(value: EditValue, existing: _KvLine | None) -> str:
    if isinstance(value, str) and ("\n" in value or "\r" in value):
        raise _unsafe("KEY=VALUE 不支持多行值")
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if value is None:
        return ""
    quote = ""
    if existing is not None and existing.value.startswith(('"', "'")):
        quote = existing.value[0]
    if quote:
        escaped = value.replace("\\", "\\\\").replace(quote, f"\\{quote}")
        return f"{quote}{escaped}{quote}"
    if value == "" or value != value.strip() or "#" in value or value.startswith(('"', "'")):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def _split_line_ending(raw: str) -> tuple[str, str]:
    if raw.endswith("\r\n"):
        return raw[:-2], "\r\n"
    if raw.endswith("\n") or raw.endswith("\r"):
        return raw[:-1], raw[-1]
    return raw, ""


# ---------------------------------------------------------------------------
# 验证与通用工具
# ---------------------------------------------------------------------------


def _parse_for_verify(text: str, format: DocumentFormat) -> object:
    bom = "﻿" if text.startswith("﻿") else ""
    body = text[1:] if bom else text
    if format == "json":
        if body.strip() == "":
            return {}
        return json.loads(body)
    if format == "toml":
        return tomlkit.parse(body)
    if format == "key_value":
        parsed: dict[str, str | int | bool | None] = {}
        for line in _kv_parse(body):
            if line.key is not None:
                parsed[line.key] = _kv_parse_value(line.value)
        return parsed
    raise AppError("WRITE_VERIFY_FAILED", f"不支持的文档格式: {format}", 500)


def _kv_parse_value(raw: str) -> str | int | bool | None:
    token = raw.strip()
    if not token:
        return None
    if token.startswith(('"', "'")):
        quote = token[0]
        return token[1:-1].replace(f"\\{quote}", quote).replace("\\\\", "\\")
    if token in {"true", "false"}:
        return token == "true"
    try:
        return int(token)
    except ValueError:
        return token


def _lookup(
    document: object,
    path: Sequence[str],
    format: DocumentFormat,
) -> tuple[bool, object]:
    current: object = document
    for segment in path:
        if format == "key_value":
            if not isinstance(current, Mapping) or segment not in current:
                return False, None
            current = current[segment]
            continue
        if not isinstance(current, Mapping) or segment not in current:
            return False, None
        current = current[segment]
    return True, current


def _values_equal(actual: object, target: EditValue) -> bool:
    if hasattr(actual, "unwrap"):
        actual = actual.unwrap()
    if target is None:
        return actual is None
    if isinstance(target, bool):
        return isinstance(actual, bool) and actual == target
    if isinstance(target, int):
        return isinstance(actual, int) and not isinstance(actual, bool) and actual == target
    return isinstance(actual, str) and actual == target


def _detect_newline(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def _to_crlf(text: str) -> str:
    return re.sub(r"(?<!\r)\n", "\r\n", text)


def _line_indent(text: str, position: int) -> str:
    line_start = text.rfind("\n", 0, position) + 1
    prefix = text[line_start:position]
    return prefix[: len(prefix) - len(prefix.lstrip(" \t"))]
