"""密钥脱敏与序列化: T5 的行为测试。

覆盖列表 / 详情 / 损坏文件 / warning / 日志五条出口, 断言完整序列化文本
不含 fixture 明文 key, 响应里只有 `has_secret` 与 `secret_preview`。
"""

import logging
from collections.abc import Iterator
from pathlib import Path

import pytest
from tool_fixtures import (
    CLAUDE_TOKEN,
    CODEX_KEY,
    claude_adapter,
    codex_adapter,
    make_service,
    seed_claude,
    seed_codex,
)

from app.adapters.base import ToolWarning
from app.core.logging import _HANDLER_MARKER, LOG_FILE_NAME, configure_logging

REDACTED_CLAUDE = "sk-a****cdef"
REDACTED_CODEX = "sk-o****cdef"


@pytest.fixture()
def clean_logging() -> Iterator[None]:
    """与 test_logging 相同: 结束后移除本测试注册的日志 handler。"""
    root = logging.getLogger()
    saved_level = root.level
    yield
    for handler in list(root.handlers):
        if getattr(handler, _HANDLER_MARKER, False):
            root.removeHandler(handler)
            handler.close()
    root.setLevel(saved_level)


def test_list_serialization_contains_only_redacted_secrets(tmp_path: Path) -> None:
    claude_dir = tmp_path / "claude"
    seed_claude(claude_dir)
    codex_dir = tmp_path / "codex"
    seed_codex(codex_dir)

    response = make_service(claude_adapter(claude_dir), codex_adapter(codex_dir)).list_tools()
    payload = response.model_dump_json()

    assert CLAUDE_TOKEN not in payload
    assert CODEX_KEY not in payload
    assert response.tools[0].has_secret is True
    assert response.tools[0].secret_preview == REDACTED_CLAUDE
    assert response.tools[1].has_secret is True
    assert response.tools[1].secret_preview == REDACTED_CODEX
    assert REDACTED_CLAUDE in payload
    assert REDACTED_CODEX in payload


def test_detail_serialization_contains_only_redacted_secret(tmp_path: Path) -> None:
    claude_dir = tmp_path / "claude"
    seed_claude(claude_dir)

    view = make_service(claude_adapter(claude_dir)).get_tool("claude-code")
    payload = view.model_dump_json()

    assert CLAUDE_TOKEN not in payload
    assert view.has_secret is True
    assert view.secret_preview == REDACTED_CLAUDE
    assert REDACTED_CLAUDE in payload


def test_broken_configs_with_inline_secrets_do_not_leak(tmp_path: Path) -> None:
    claude_dir = tmp_path / "claude"
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text(
        '{"env": {"ANTHROPIC_AUTH_TOKEN": "' + CLAUDE_TOKEN + '"}',
        encoding="utf-8",
    )
    codex_dir = tmp_path / "codex"
    codex_dir.mkdir()
    (codex_dir / "config.toml").write_text(
        f'model = "{CODEX_KEY}"\nprovider = "openai\n',
        encoding="utf-8",
    )

    response = make_service(claude_adapter(claude_dir), codex_adapter(codex_dir)).list_tools()
    payload = response.model_dump_json()

    assert CLAUDE_TOKEN not in payload
    assert CODEX_KEY not in payload
    assert [tool.status for tool in response.tools] == ["error", "error"]
    assert [warning.code for warning in response.tools[0].warnings] == ["PARSE_ERROR"]
    assert [warning.code for warning in response.tools[1].warnings] == ["PARSE_ERROR"]
    assert "第 1 行第" in response.tools[0].warnings[0].message
    assert "第 2 行第" in response.tools[1].warnings[0].message


def test_warning_message_is_redacted_at_construction() -> None:
    warning = ToolWarning(code="PARSE_ERROR", message=f"解析失败: token={CLAUDE_TOKEN}")

    payload = warning.model_dump_json()

    assert CLAUDE_TOKEN not in payload
    assert REDACTED_CLAUDE in warning.message


def test_logs_never_contain_plaintext_secrets(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, clean_logging: None
) -> None:
    configure_logging(tmp_path)
    caplog.set_level(logging.DEBUG)
    claude_dir = tmp_path / "claude"
    seed_claude(claude_dir)
    codex_dir = tmp_path / "codex"
    seed_codex(codex_dir)
    service = make_service(claude_adapter(claude_dir), codex_adapter(codex_dir))

    response = service.list_tools()
    detail = service.get_tool("claude-code")
    logger = logging.getLogger("app.test.tools")
    logger.info("list=%s", response.model_dump_json())
    logger.info("detail=%s", detail.model_dump_json())

    # 发现流程本身不把明文写进日志
    assert CLAUDE_TOKEN not in caplog.text
    assert CODEX_KEY not in caplog.text

    # 即使有人把密钥直接交给 logger, 文件输出仍经过统一脱敏
    logger.warning("raw token=%s key=%s", CLAUDE_TOKEN, CODEX_KEY)
    log_text = (tmp_path / "logs" / LOG_FILE_NAME).read_text(encoding="utf-8")

    assert CLAUDE_TOKEN not in log_text
    assert CODEX_KEY not in log_text
    assert REDACTED_CLAUDE in log_text
    assert REDACTED_CODEX in log_text
