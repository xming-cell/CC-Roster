"""保真编辑助手的逐字节契约。

每个用例都用固定 fixture 断言渲染后的完整文本, 而不是只断言解析结果;
这样才能证明缩进、空格、换行、注释与未知字段没有被整份重排。
"""

import pytest
from pydantic import ValidationError

from app.core.errors import AppError
from app.core.format_edits import (
    DocumentFormat,
    FieldEdit,
    render_document,
    verify_rendered,
)

JSON_FIXTURE = (
    "{\n"
    '  "model": "claude-sonnet-4",\n'
    '  "nested": {\n'
    '    "enabled": true,\n'
    '    "untouched": ["a", "b"]\n'
    "  },\n"
    '  "unicode": "中文 ✓",\n'
    '  "unknown": {"keep": [1, 2, 3]}\n'
    "}\n"
)

TOML_FIXTURE = (
    "# 顶部注释\n"
    'model = "old"  # 行内注释\n'
    "\n"
    "[provider]\n"
    'base_url = "https://example.com"\n'
    "unknown = 42\n"
)

KV_FIXTURE = '# 顶部注释\nAPI_KEY = "old"   # 行内注释\n\nTIMEOUT=30\nNAME = old\n'


def edit(path: list[str], action: str, value: object = None) -> FieldEdit:
    return FieldEdit.model_validate({"path": path, "action": action, "value": value})


def test_json_set_only_replaces_target_value() -> None:
    rendered = render_document(JSON_FIXTURE, [edit(["nested", "enabled"], "set", False)], "json")

    assert rendered == JSON_FIXTURE.replace('"enabled": true', '"enabled": false')
    verify_rendered(JSON_FIXTURE, rendered, [edit(["nested", "enabled"], "set", False)], "json")


def test_json_set_creates_missing_parent_objects() -> None:
    rendered = render_document(JSON_FIXTURE, [edit(["new", "deep", "value"], "set", 7)], "json")

    assert '"new": {"deep": {"value": 7}}' in rendered
    verify_rendered(
        JSON_FIXTURE,
        rendered,
        [edit(["new", "deep", "value"], "set", 7)],
        "json",
    )


def test_json_inserts_before_closing_brace_with_existing_indent() -> None:
    rendered = render_document(JSON_FIXTURE, [edit(["nested", "new_key"], "set", "x")], "json")

    assert '    "untouched": ["a", "b"],\n    "new_key": "x"\n  }' in rendered


def test_json_remove_first_middle_and_last_member() -> None:
    first = render_document(JSON_FIXTURE, [edit(["model"], "remove")], "json")
    last = render_document(JSON_FIXTURE, [edit(["unknown"], "remove")], "json")

    assert '"model"' not in first
    assert first.startswith('{\n  "nested"')
    assert '"unknown"' not in last
    assert last.endswith('"unicode": "中文 ✓"\n}\n')
    verify_rendered(JSON_FIXTURE, first, [edit(["model"], "remove")], "json")
    verify_rendered(JSON_FIXTURE, last, [edit(["unknown"], "remove")], "json")


def test_json_remove_nested_member_keeps_parent_and_siblings() -> None:
    rendered = render_document(JSON_FIXTURE, [edit(["nested", "enabled"], "remove")], "json")

    assert rendered == JSON_FIXTURE.replace('    "enabled": true,\n', "")
    verify_rendered(
        JSON_FIXTURE,
        rendered,
        [edit(["nested", "enabled"], "remove")],
        "json",
    )


def test_json_remove_missing_key_is_idempotent() -> None:
    rendered = render_document(JSON_FIXTURE, [edit(["absent"], "remove")], "json")

    assert rendered == JSON_FIXTURE


def test_json_duplicate_target_key_is_unsafe() -> None:
    duplicate = '{"a": 1, "a": 2}'

    with pytest.raises(AppError) as excinfo:
        render_document(duplicate, [edit(["a"], "set", 3)], "json")

    assert excinfo.value.code == "UNSAFE_WRITE"


@pytest.mark.parametrize(
    "original",
    ["{", "[]", '"scalar"', "null"],
)
def test_json_invalid_or_non_object_is_unsafe(original: str) -> None:
    with pytest.raises(AppError) as excinfo:
        render_document(original, [edit(["a"], "set", 1)], "json")

    assert excinfo.value.code == "UNSAFE_WRITE"


def test_json_empty_file_generates_minimal_structure_only_for_set() -> None:
    rendered = render_document("", [edit(["a", "b"], "set", 2)], "json")

    assert rendered == '{"a": {"b": 2}}'
    verify_rendered("", rendered, [edit(["a", "b"], "set", 2)], "json")
    assert render_document("", [edit(["a"], "remove")], "json") == ""


def test_json_preserves_bom_and_crlf() -> None:
    original = '﻿{\r\n  "a": 1\r\n}\r\n'

    rendered = render_document(original, [edit(["b"], "set", 2)], "json")

    assert rendered == '﻿{\r\n  "a": 1,\r\n  "b": 2\r\n}\r\n'


def test_json_unicode_and_escapes_survive() -> None:
    original = '{\n  "text": "中文 \\"quoted\\" \\\\ backslash",\n  "emoji": "✓"\n}\n'

    rendered = render_document(original, [edit(["emoji"], "set", "🚀")], "json")

    assert rendered == ('{\n  "text": "中文 \\"quoted\\" \\\\ backslash",\n  "emoji": "🚀"\n}\n')


def test_toml_set_preserves_comments_order_and_unknown_keys() -> None:
    rendered = render_document(TOML_FIXTURE, [edit(["model"], "set", "new")], "toml")

    assert rendered == TOML_FIXTURE.replace('"old"', '"new"')
    verify_rendered(TOML_FIXTURE, rendered, [edit(["model"], "set", "new")], "toml")


def test_toml_adds_nested_key_and_preserves_existing_tables() -> None:
    rendered = render_document(
        TOML_FIXTURE,
        [edit(["provider", "api_key"], "set", "sk-test")],
        "toml",
    )

    assert rendered.startswith(TOML_FIXTURE)
    assert 'api_key = "sk-test"' in rendered
    verify_rendered(
        TOML_FIXTURE,
        rendered,
        [edit(["provider", "api_key"], "set", "sk-test")],
        "toml",
    )


def test_toml_remove_and_missing_remove() -> None:
    removed = render_document(TOML_FIXTURE, [edit(["provider", "unknown"], "remove")], "toml")

    assert "unknown = 42" not in removed
    assert "# 顶部注释" in removed
    assert (
        render_document(TOML_FIXTURE, [edit(["provider", "missing"], "remove")], "toml")
        == TOML_FIXTURE
    )
    verify_rendered(
        TOML_FIXTURE,
        removed,
        [edit(["provider", "unknown"], "remove")],
        "toml",
    )


def test_toml_empty_file_and_crlf() -> None:
    rendered = render_document("", [edit(["table", "key"], "set", 2)], "toml")
    crlf = render_document("x = 1\r\n", [edit(["y"], "set", 2)], "toml")

    assert rendered == "[table]\nkey = 2\n"
    assert crlf == "x = 1\r\ny = 2\r\n"
    verify_rendered("", rendered, [edit(["table", "key"], "set", 2)], "toml")


def test_toml_invalid_is_unsafe() -> None:
    with pytest.raises(AppError) as excinfo:
        render_document("a = [", [edit(["a"], "set", 1)], "toml")

    assert excinfo.value.code == "UNSAFE_WRITE"


def test_key_value_preserves_comments_quotes_and_spacing() -> None:
    rendered = render_document(KV_FIXTURE, [edit(["API_KEY"], "set", "new")], "key_value")

    assert rendered == KV_FIXTURE.replace('"old"', '"new"')
    verify_rendered(KV_FIXTURE, rendered, [edit(["API_KEY"], "set", "new")], "key_value")


def test_key_value_appends_missing_key_and_keeps_comment_lines() -> None:
    rendered = render_document(KV_FIXTURE, [edit(["NEW_KEY"], "set", "x#y")], "key_value")

    assert rendered == KV_FIXTURE + 'NEW_KEY="x#y"\n'
    assert render_document("A=1", [edit(["B"], "set", 2)], "key_value") == "A=1\nB=2\n"
    verify_rendered(KV_FIXTURE, rendered, [edit(["NEW_KEY"], "set", "x#y")], "key_value")


def test_key_value_remove_and_missing_remove() -> None:
    rendered = render_document(KV_FIXTURE, [edit(["TIMEOUT"], "remove")], "key_value")

    assert "TIMEOUT" not in rendered
    assert rendered.count("#") == 2
    assert render_document(KV_FIXTURE, [edit(["MISSING"], "remove")], "key_value") == KV_FIXTURE


def test_key_value_duplicate_or_invalid_line_is_unsafe() -> None:
    with pytest.raises(AppError) as duplicate:
        render_document("A=1\nA=2\n", [edit(["A"], "set", 3)], "key_value")
    with pytest.raises(AppError) as invalid:
        render_document("BROKEN LINE\n", [edit(["A"], "set", 1)], "key_value")

    assert duplicate.value.code == "UNSAFE_WRITE"
    assert invalid.value.code == "UNSAFE_WRITE"


@pytest.mark.parametrize("value", ["line1\nline2", "line1\rline2"])
def test_key_value_rejects_multiline_values(value: str) -> None:
    with pytest.raises(AppError) as excinfo:
        render_document(KV_FIXTURE, [edit(["NEW_KEY"], "set", value)], "key_value")

    assert excinfo.value.code == "UNSAFE_WRITE"


def test_key_value_preserves_crlf_and_bom() -> None:
    original = "﻿# c\r\nA=1\r\n"

    rendered = render_document(original, [edit(["A"], "set", 2)], "key_value")

    assert rendered == "﻿# c\r\nA=2\r\n"


def test_non_utf8_bytes_are_unsafe_for_every_format() -> None:
    formats: tuple[DocumentFormat, ...] = ("json", "toml", "key_value")
    for format_name in formats:
        with pytest.raises(AppError) as excinfo:
            render_document(b"\xff\xfe\x00", [edit(["a"], "set", 1)], format_name)
        assert excinfo.value.code == "UNSAFE_WRITE"


def test_rendering_is_deterministic() -> None:
    first = render_document(JSON_FIXTURE, [edit(["model"], "set", "x")], "json")
    second = render_document(JSON_FIXTURE, [edit(["model"], "set", "x")], "json")

    assert first == second == JSON_FIXTURE.replace("claude-sonnet-4", "x")


@pytest.mark.parametrize(
    ("rendered", "code"),
    [
        (JSON_FIXTURE, "WRITE_VERIFY_FAILED"),
        ('{"model": "wrong"}', "WRITE_VERIFY_FAILED"),
    ],
)
def test_verify_rendered_rejects_wrong_value(rendered: str, code: str) -> None:
    with pytest.raises(AppError) as excinfo:
        verify_rendered(
            JSON_FIXTURE,
            rendered,
            [edit(["model"], "set", "claude-opus-4")],
            "json",
        )

    assert excinfo.value.code == code


def test_verify_rendered_rejects_remove_still_present() -> None:
    with pytest.raises(AppError) as excinfo:
        verify_rendered(
            JSON_FIXTURE,
            JSON_FIXTURE,
            [edit(["model"], "remove")],
            "json",
        )

    assert excinfo.value.code == "WRITE_VERIFY_FAILED"


def test_field_edit_rejects_invalid_path_and_value() -> None:
    with pytest.raises(ValidationError):
        FieldEdit(path=[], action="set", value=1)
    with pytest.raises(ValidationError):
        FieldEdit(path=["a", ""], action="set", value=1)
    with pytest.raises(ValidationError):
        FieldEdit.model_validate({"path": ["a"], "action": "set", "value": 1.5})
    with pytest.raises(ValidationError):
        FieldEdit.model_validate({"path": ["a"], "action": "replace", "value": 1})
