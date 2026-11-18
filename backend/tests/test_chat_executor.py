"""子进程执行层: 真实进程边界、JSON 解析与退出码。"""

import sys
from pathlib import Path

import pytest

from app.core.errors import AppError
from app.services.chat_executor import SubprocessChatExecutor, subprocess_argv


def test_executor_streams_json_lines_from_real_process(tmp_path: Path) -> None:
    script = (
        "import json;"
        "print(json.dumps({'type':'assistant','message':{'content':"
        "[{'type':'text','text':'hello'}]}}));"
        "print(json.dumps({'type':'result'}))"
    )
    executor = SubprocessChatExecutor(platform="win32")

    events = list(
        executor.stream(
            session_id="session-1",
            command=[sys.executable, "-c", script],
            cwd=tmp_path,
            env={},
        )
    )

    assert [event.type for event in events] == ["token"]
    assert events[0].content == "hello"
    assert executor.cancel("session-1") is False


def test_executor_reports_non_zero_exit(tmp_path: Path) -> None:
    executor = SubprocessChatExecutor(platform="win32")

    with pytest.raises(AppError) as caught:
        list(
            executor.stream(
                session_id="session-2",
                command=[sys.executable, "-c", "import sys; sys.exit(3)"],
                cwd=tmp_path,
                env={},
            )
        )

    assert caught.value.code == "CHAT_PROCESS_FAILED"


def test_subprocess_argv_wraps_windows_cmd_shims() -> None:
    assert subprocess_argv(["C:/npm/claude.CMD", "-p", "x"], "nt")[1:3] == ["/d", "/c"]
    assert subprocess_argv(["claude"], "win32") == ["claude"]
    assert subprocess_argv(["claude"], "posix") == ["claude"]
