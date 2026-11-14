"""工具 ↔ 档案绑定 API 集成测试。

覆盖 T5 的复用关系与删除保护: 同一档案绑定多个工具、同一工具切换档案、
重复绑定幂等、解绑幂等、未知工具 / 档案的 404、删除占用档案的 409 / 确认删除,
以及绑定 / 解绑前后工具配置文件 hash 不变。
"""

from datetime import datetime
from pathlib import Path

import pytest
from adapter_contract import snapshot_tree
from profile_fixtures import (
    bind_profile,
    create_profile,
    make_profile_harness,
)
from tool_fixtures import claude_adapter, codex_adapter, seed_claude, seed_codex

from app.repositories.secrets import KEYRING_SERVICE_NAME

SECRET = "sk-ant-fixture-1234567890abcdef"
UNKNOWN_PROFILE_ID = "00000000-0000-4000-8000-000000000000"


def seed_both_tools(tmp_path: Path) -> tuple[Path, Path]:
    claude_dir = tmp_path / "claude"
    codex_dir = tmp_path / "codex"
    seed_claude(claude_dir)
    seed_codex(codex_dir)
    return claude_dir, codex_dir


def assert_aware_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    assert parsed.utcoffset() is not None
    return parsed


def test_bind_profile_to_installed_tool_returns_binding_and_used_by(tmp_path: Path) -> None:
    claude_dir = tmp_path / "claude"
    seed_claude(claude_dir)
    harness = make_profile_harness(tmp_path, claude_adapter(claude_dir))
    profile = create_profile(harness)

    resp = harness.client.put(
        "/api/tools/claude-code/profile",
        json={"profile_id": profile["id"]},
    )

    assert resp.status_code == 200
    binding = resp.json()
    assert binding["tool_id"] == "claude-code"
    assert binding["profile_id"] == profile["id"]
    assert binding["active"] is False
    assert binding["applied_at"] is None
    assert binding["snapshot_id"] is None
    assert_aware_iso(binding["bound_at"])

    detail = harness.client.get(f"/api/profiles/{profile['id']}").json()
    assert detail["used_by"] == [
        {"tool_id": "claude-code", "display_name": "Claude Code", "installed": True}
    ]
    listing = harness.client.get("/api/profiles").json()
    assert listing["bindings"] == [binding]


def test_same_profile_can_bind_two_tools(tmp_path: Path) -> None:
    claude_dir, codex_dir = seed_both_tools(tmp_path)
    harness = make_profile_harness(
        tmp_path,
        claude_adapter(claude_dir),
        codex_adapter(codex_dir),
    )
    profile = create_profile(harness)

    for tool_id in ("claude-code", "codex-cli"):
        resp = harness.client.put(
            f"/api/tools/{tool_id}/profile",
            json={"profile_id": profile["id"]},
        )
        assert resp.status_code == 200, resp.text

    detail = harness.client.get(f"/api/profiles/{profile['id']}").json()
    assert detail["used_by"] == [
        {"tool_id": "claude-code", "display_name": "Claude Code", "installed": True},
        {"tool_id": "codex-cli", "display_name": "Codex CLI", "installed": True},
    ]
    assert [binding.tool_id for binding in harness.repository.list_bindings()] == [
        "claude-code",
        "codex-cli",
    ]


def test_rebinding_tool_to_another_profile_replaces_old_binding(tmp_path: Path) -> None:
    claude_dir = tmp_path / "claude"
    seed_claude(claude_dir)
    harness = make_profile_harness(tmp_path, claude_adapter(claude_dir))
    alpha = create_profile(harness, name="Alpha")
    beta = create_profile(harness, name="Beta")

    first = harness.client.put(
        "/api/tools/claude-code/profile",
        json={"profile_id": alpha["id"]},
    )
    second = harness.client.put(
        "/api/tools/claude-code/profile",
        json={"profile_id": beta["id"]},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert assert_aware_iso(second.json()["bound_at"]) >= assert_aware_iso(first.json()["bound_at"])
    assert second.json()["profile_id"] == beta["id"]
    assert harness.repository.list_bindings()[0].profile_id == beta["id"]
    assert harness.client.get(f"/api/profiles/{alpha['id']}").json()["used_by"] == []
    assert harness.client.get(f"/api/profiles/{beta['id']}").json()["used_by"] == [
        {"tool_id": "claude-code", "display_name": "Claude Code", "installed": True}
    ]


def test_binding_same_profile_again_is_idempotent_and_keeps_bound_at(tmp_path: Path) -> None:
    claude_dir = tmp_path / "claude"
    seed_claude(claude_dir)
    harness = make_profile_harness(tmp_path, claude_adapter(claude_dir))
    profile = create_profile(harness)

    first = harness.client.put(
        "/api/tools/claude-code/profile",
        json={"profile_id": profile["id"]},
    )
    second = harness.client.put(
        "/api/tools/claude-code/profile",
        json={"profile_id": profile["id"]},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == first.json()
    bindings = harness.repository.list_bindings()
    assert len(bindings) == 1
    assert assert_aware_iso(bindings[0].bound_at.isoformat()) == assert_aware_iso(
        first.json()["bound_at"]
    )


def test_unbind_removes_binding_and_repeated_unbind_is_idempotent(tmp_path: Path) -> None:
    claude_dir = tmp_path / "claude"
    seed_claude(claude_dir)
    harness = make_profile_harness(tmp_path, claude_adapter(claude_dir))
    profile = create_profile(harness)
    harness.client.put(
        "/api/tools/claude-code/profile",
        json={"profile_id": profile["id"]},
    )

    removed = harness.client.delete("/api/tools/claude-code/profile")
    repeated = harness.client.delete("/api/tools/claude-code/profile")

    assert removed.status_code == 200
    assert removed.json() == {"tool_id": "claude-code", "removed": True}
    assert repeated.status_code == 200
    assert repeated.json() == {"tool_id": "claude-code", "removed": False}
    assert harness.repository.list_bindings() == []
    assert harness.client.get(f"/api/profiles/{profile['id']}").json()["used_by"] == []


def test_unbind_does_not_require_tool_to_still_be_installed(tmp_path: Path) -> None:
    harness = make_profile_harness(tmp_path, claude_adapter(tmp_path / "missing"))
    profile = create_profile(harness)
    bind_profile(harness, str(profile["id"]), "removed-tool")

    removed = harness.client.delete("/api/tools/removed-tool/profile")

    assert removed.status_code == 200
    assert removed.json() == {"tool_id": "removed-tool", "removed": True}
    assert harness.repository.list_bindings() == []


def test_bind_rejects_unknown_or_uninstalled_tool(tmp_path: Path) -> None:
    harness = make_profile_harness(tmp_path, claude_adapter(tmp_path / "missing"))
    profile = create_profile(harness)

    for tool_id in ("unknown-tool", "claude-code"):
        resp = harness.client.put(
            f"/api/tools/{tool_id}/profile",
            json={"profile_id": profile["id"]},
        )
        assert resp.status_code == 404
        assert resp.json()["code"] == "TOOL_NOT_FOUND"

    assert harness.repository.list_bindings() == []


def test_bind_unknown_profile_returns_404_without_creating_store(tmp_path: Path) -> None:
    claude_dir = tmp_path / "claude"
    seed_claude(claude_dir)
    harness = make_profile_harness(tmp_path, claude_adapter(claude_dir))

    resp = harness.client.put(
        "/api/tools/claude-code/profile",
        json={"profile_id": UNKNOWN_PROFILE_ID},
    )

    assert resp.status_code == 404
    assert resp.json()["code"] == "PROFILE_NOT_FOUND"
    assert not (tmp_path / "profiles.json").exists()


@pytest.mark.parametrize(
    "payload",
    [
        {"profile_id": "   "},
        {"profile_id": UNKNOWN_PROFILE_ID, "unknown_field": True},
        {},
    ],
)
def test_bind_rejects_invalid_payload(tmp_path: Path, payload: dict[str, object]) -> None:
    claude_dir = tmp_path / "claude"
    seed_claude(claude_dir)
    harness = make_profile_harness(tmp_path, claude_adapter(claude_dir))

    resp = harness.client.put("/api/tools/claude-code/profile", json=payload)

    assert resp.status_code == 422
    assert resp.json()["code"] == "VALIDATION_ERROR"
    assert harness.repository.list_bindings() == []


def test_delete_in_use_profile_via_bindings_requires_confirmation(tmp_path: Path) -> None:
    claude_dir, codex_dir = seed_both_tools(tmp_path)
    tools_before = (snapshot_tree(claude_dir), snapshot_tree(codex_dir))
    harness = make_profile_harness(
        tmp_path,
        claude_adapter(claude_dir),
        codex_adapter(codex_dir),
    )
    profile = create_profile(harness, secret=SECRET)
    profile_id = str(profile["id"])
    for tool_id in ("claude-code", "codex-cli"):
        harness.client.put(
            f"/api/tools/{tool_id}/profile",
            json={"profile_id": profile_id},
        )

    refused = harness.client.delete(f"/api/profiles/{profile_id}")

    assert refused.status_code == 409
    assert refused.json()["code"] == "PROFILE_IN_USE"
    assert "Claude Code" in refused.json()["message"]
    assert "Codex CLI" in refused.json()["message"]
    assert harness.repository.get_profile(profile_id) is not None
    assert len(harness.repository.list_bindings()) == 2
    assert harness.keyring.values == {(KEYRING_SERVICE_NAME, profile_id): SECRET}

    deleted = harness.client.delete(f"/api/profiles/{profile_id}?confirm=true")

    assert deleted.status_code == 200
    assert deleted.json() == {
        "deleted": True,
        "unbound_tools": [
            {"tool_id": "claude-code", "display_name": "Claude Code", "installed": True},
            {"tool_id": "codex-cli", "display_name": "Codex CLI", "installed": True},
        ],
    }
    assert harness.repository.get_profile(profile_id) is None
    assert harness.repository.list_bindings() == []
    assert harness.keyring.values == {}
    assert (snapshot_tree(claude_dir), snapshot_tree(codex_dir)) == tools_before


def test_bind_and_unbind_do_not_touch_tool_config_files(tmp_path: Path) -> None:
    claude_dir, codex_dir = seed_both_tools(tmp_path)
    tools_before = (snapshot_tree(claude_dir), snapshot_tree(codex_dir))
    harness = make_profile_harness(
        tmp_path,
        claude_adapter(claude_dir),
        codex_adapter(codex_dir),
    )
    profile = create_profile(harness)

    for tool_id in ("claude-code", "codex-cli"):
        assert (
            harness.client.put(
                f"/api/tools/{tool_id}/profile",
                json={"profile_id": profile["id"]},
            ).status_code
            == 200
        )
    for tool_id in ("claude-code", "codex-cli"):
        assert harness.client.delete(f"/api/tools/{tool_id}/profile").status_code == 200

    assert (snapshot_tree(claude_dir), snapshot_tree(codex_dir)) == tools_before
    assert harness.repository.list_bindings() == []
    assert harness.repository.get_profile(str(profile["id"])) is not None
