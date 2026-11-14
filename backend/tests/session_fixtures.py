"""会话 fixture: 用真实 Claude / Codex JSONL 形状, 不依赖用户目录。"""

import json
from pathlib import Path


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )
    return path


def seed_claude_session(
    config_dir: Path,
    *,
    session_id: str = "claude-session-1",
    project: str = "alpha",
    title: str = "帮我修一下登录",
    started_at: str = "2026-11-12T09:00:00Z",
) -> Path:
    return _write_jsonl(
        config_dir / "projects" / f"-work-{project}" / f"{session_id}.jsonl",
        [
            {
                "type": "user",
                "message": {"role": "user", "content": title},
                "uuid": "u1",
                "timestamp": started_at,
                "sessionId": session_id,
                "cwd": f"/work/{project}",
            },
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": "我先看看文件。"},
                        {
                            "type": "tool_use",
                            "id": "tool-1",
                            "name": "Bash",
                            "input": {"command": "ls"},
                        },
                    ],
                },
                "uuid": "a1",
                "timestamp": "2026-11-12T09:00:05Z",
            },
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "tool-1",
                            "content": "README.md",
                            "is_error": False,
                        }
                    ],
                },
                "uuid": "u2",
                "timestamp": "2026-11-12T09:00:06Z",
                "cwd": f"/work/{project}",
            },
        ],
    )


def seed_codex_session(
    config_dir: Path,
    *,
    session_id: str = "2026-11-12T10-00-00-abc",
    project: str = "beta",
    title: str = "写一个脚本",
) -> Path:
    return _write_jsonl(
        config_dir / "sessions" / "2026" / "11" / "12" / f"rollout-{session_id}.jsonl",
        [
            {
                "type": "session_meta",
                "timestamp": "2026-11-12T10:00:00Z",
                "payload": {
                    "id": session_id,
                    "timestamp": "2026-11-12T10:00:00Z",
                    "cwd": f"/work/{project}",
                },
            },
            {
                "type": "response_item",
                "timestamp": "2026-11-12T10:00:01Z",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": title}],
                },
            },
            {
                "type": "response_item",
                "timestamp": "2026-11-12T10:00:02Z",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "好的。"}],
                },
            },
            {
                "type": "response_item",
                "timestamp": "2026-11-12T10:00:03Z",
                "payload": {
                    "type": "function_call",
                    "name": "shell",
                    "arguments": '{"cmd":"ls"}',
                    "call_id": "call-1",
                },
            },
            {
                "type": "response_item",
                "timestamp": "2026-11-12T10:00:04Z",
                "payload": {
                    "type": "function_call_output",
                    "call_id": "call-1",
                    "output": "ok",
                },
            },
            {
                "type": "response_item",
                "timestamp": "2026-11-12T10:00:05Z",
                "payload": {"type": "mystery_event"},
            },
        ],
    )
