"""019 用量与花费: usage 解析、Decimal 估算、聚合与只读。"""

import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.adapters.claude_code import ClaudeCodeAdapter
from app.adapters.codex_cli import CodexCliAdapter
from app.adapters.registry import ToolRegistry
from app.api.usage import get_usage_service
from app.main import create_app
from app.services.usage_service import UsageService


def write_jsonl(path: Path, rows: list[object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def seed_usage(root: Path) -> None:
    write_jsonl(
        root / "claude" / "projects" / "-work-demo" / "s1.jsonl",
        [
            {
                "type": "assistant",
                "timestamp": "2026-11-12T09:00:00Z",
                "message": {
                    "role": "assistant",
                    "model": "claude-sonnet-4",
                    "usage": {"input_tokens": 1_000_000, "output_tokens": 1_000_000},
                    "content": [{"type": "text", "text": "x"}],
                },
            },
            {
                "type": "assistant",
                "timestamp": "2026-11-12T10:00:00Z",
                "message": {
                    "role": "assistant",
                    "model": "mystery-model",
                    "usage": {"input_tokens": 10, "output_tokens": 20},
                },
            },
            "{broken",
        ],
    )
    write_jsonl(
        root / "codex" / "sessions" / "2026" / "11" / "12" / "rollout-s2.jsonl",
        [
            {
                "type": "turn_context",
                "timestamp": "2026-11-12T11:00:00Z",
                "payload": {"model": "gpt-5-codex"},
            },
            {
                "type": "event_msg",
                "timestamp": "2026-11-12T11:01:00Z",
                "payload": {
                    "type": "token_count",
                    "info": {
                        "last_token_usage": {"input_tokens": 2_000_000, "output_tokens": 1_000_000}
                    },
                },
            },
        ],
    )


def client_for(tmp_path: Path) -> TestClient:
    app = create_app()
    service = UsageService(
        ToolRegistry(
            [
                ClaudeCodeAdapter(tmp_path / "claude", which=lambda _name: None),
                CodexCliAdapter(tmp_path / "codex", which=lambda _name: None),
            ]
        )
    )
    app.dependency_overrides[get_usage_service] = lambda: service
    return TestClient(app)


def tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digest.update(path.read_bytes())
    return digest.hexdigest()


def test_usage_aggregates_tools_tokens_and_decimal_cost(tmp_path: Path) -> None:
    seed_usage(tmp_path)
    before = tree_hash(tmp_path)

    response = client_for(tmp_path).get("/api/usage", params={"days": 30})

    assert response.status_code == 200
    body = response.json()
    assert body["days"] == 30
    assert body["totals"]["calls"] == 3
    assert body["totals"]["input_tokens"] == 3_000_010
    assert body["totals"]["output_tokens"] == 2_000_020
    assert body["totals"]["estimated_cost"] == "30.500000"
    assert body["totals"]["unknown_price_calls"] == 1
    assert body["totals"]["currency"] == "USD"
    assert "不代表供应商账单" in body["pricing_note"]
    assert any(item["code"] == "UNKNOWN_PRICE" for item in body["warnings"])
    assert any(item["code"] == "USAGE_SKIPPED" for item in body["warnings"])

    claude = next(
        item
        for item in body["records"]
        if item["tool_id"] == "claude-code" and item["model"] == "claude-sonnet-4"
    )
    assert claude["estimated_cost"] == "18.000000"
    assert claude["price_known"] is True
    unknown = next(item for item in body["records"] if item["model"] == "mystery-model")
    assert unknown["price_known"] is False
    assert unknown["estimated_cost"] is None
    assert tree_hash(tmp_path) == before


def test_usage_empty_and_days_validation(tmp_path: Path) -> None:
    client = client_for(tmp_path)

    empty = client.get("/api/usage")
    invalid_zero = client.get("/api/usage", params={"days": 0})
    invalid_high = client.get("/api/usage", params={"days": 366})

    assert empty.status_code == 200
    assert empty.json()["records"] == []
    assert empty.json()["totals"]["estimated_cost"] == "0.000000"
    assert invalid_zero.status_code == 422
    assert invalid_high.status_code == 422


def test_usage_ignores_records_outside_period(tmp_path: Path) -> None:
    seed_usage(tmp_path)

    response = client_for(tmp_path).get("/api/usage", params={"days": 1})

    assert response.status_code == 200
    assert response.json()["records"] == []
