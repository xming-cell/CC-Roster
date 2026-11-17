"""028: 一工具多供应商绑定的模型、API、切换与删除保护。

覆盖 ADR-010 的关键语义: 同工具多条绑定、`(tool_id, profile_id)` 唯一、最多一条 active、
精确解绑、切换保留全部绑定、删除保护包含已卸载工具, 以及旧单绑定文件兼容。
"""

import hashlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path

import pytest
from profile_fixtures import (
    NOW,
    bind_profile,
    create_profile,
    make_binding,
    make_profile,
    make_profile_harness,
)
from pydantic import ValidationError
from switch_fixtures import (
    add_profile,
    apply_payload,
    make_switch_harness,
    preview_json,
    write_claude_settings,
)
from tool_fixtures import claude_adapter, seed_claude

from app.core.errors import AppError
from app.repositories.profiles import ProfileRepository
from app.schemas.profile import ModelEntry, Profile, ProfileStore, ToolBinding

UNKNOWN_PROFILE_ID = "00000000-0000-4000-8000-000000000000"


def claude_content() -> bytes:
    return json.dumps(
        {
            "model": "claude-sonnet-4",
            "env": {
                "ANTHROPIC_BASE_URL": "https://old.example.com",
                "ANTHROPIC_API_KEY": "sk-old-api-key",
            },
        }
    ).encode()


def mark_active(harness: object, tool_id: str, profile_id: str) -> None:
    def change(store: ProfileStore) -> None:
        store.bindings = [
            binding.model_copy(
                update={
                    "active": binding.tool_id == tool_id and binding.profile_id == profile_id,
                }
            )
            if binding.tool_id == tool_id
            else binding
            for binding in store.bindings
        ]

    harness.repository.mutate(change)


def file_fingerprint(path: Path) -> tuple[str, int]:
    return hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mtime_ns


# ---------------------------------------------------------------------------
# T1 数据完整性
# ---------------------------------------------------------------------------


def test_store_allows_multiple_profiles_for_one_tool() -> None:
    alpha = make_profile("甲")
    beta = make_profile("乙")
    store = ProfileStore(
        profiles=[alpha, beta],
        bindings=[make_binding(alpha.id), make_binding(beta.id)],
    )

    assert [(binding.tool_id, binding.profile_id) for binding in store.bindings] == [
        ("claude-code", alpha.id),
        ("claude-code", beta.id),
    ]


def test_store_rejects_duplicate_tool_profile_pair() -> None:
    profile = make_profile()

    with pytest.raises(ValidationError):
        ProfileStore(
            profiles=[profile],
            bindings=[
                make_binding(profile.id),
                make_binding(profile.id),
            ],
        )


def test_store_allows_zero_active_and_rejects_two_active_for_one_tool() -> None:
    alpha = make_profile("甲")
    beta = make_profile("乙")
    gamma = make_profile("丙")

    zero = ProfileStore(
        profiles=[alpha, beta, gamma],
        bindings=[
            make_binding(alpha.id),
            make_binding(beta.id),
            make_binding(gamma.id, "codex-cli", active=True),
        ],
    )
    assert sum(binding.active for binding in zero.bindings) == 1

    with pytest.raises(ValidationError):
        ProfileStore(
            profiles=[alpha, beta],
            bindings=[
                make_binding(alpha.id, active=True),
                make_binding(beta.id, active=True),
            ],
        )


def test_repository_reads_legacy_single_binding_file_without_rewriting(tmp_path: Path) -> None:
    profile = make_profile("旧版档案")
    binding = make_binding(profile.id, "claude-code", bound_at=NOW)
    raw = {
        "schema_version": 1,
        "profiles": [profile.model_dump(mode="json")],
        "bindings": [binding.model_dump(mode="json")],
    }
    path = tmp_path / "profiles.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    before = file_fingerprint(path)

    repository = ProfileRepository(tmp_path)

    assert repository.list_profiles() == [profile]
    assert repository.list_bindings() == [binding]
    assert repository.get_binding("claude-code", profile.id) == binding
    assert file_fingerprint(path) == before


def test_repository_rejects_double_active_file_without_repairing_it(tmp_path: Path) -> None:
    alpha = make_profile("甲")
    beta = make_profile("乙")
    raw = {
        "schema_version": 1,
        "profiles": [alpha.model_dump(mode="json"), beta.model_dump(mode="json")],
        "bindings": [
            make_binding(alpha.id, active=True).model_dump(mode="json"),
            make_binding(beta.id, active=True).model_dump(mode="json"),
        ],
    }
    path = tmp_path / "profiles.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    before = file_fingerprint(path)

    repository = ProfileRepository(tmp_path)

    with pytest.raises(AppError) as excinfo:
        repository.load()

    assert excinfo.value.code == "PROFILE_STORE_UNREADABLE"
    assert file_fingerprint(path) == before


def test_repository_mutate_reports_readable_error_for_double_active(tmp_path: Path) -> None:
    alpha = make_profile("甲")
    beta = make_profile("乙")
    repository = ProfileRepository(tmp_path)
    repository.mutate(
        lambda store: (
            store.profiles.extend([alpha, beta]),
            store.bindings.extend([make_binding(alpha.id), make_binding(beta.id)]),
        )
    )

    def make_both_active(store: ProfileStore) -> None:
        store.bindings = [binding.model_copy(update={"active": True}) for binding in store.bindings]

    with pytest.raises(AppError) as excinfo:
        repository.mutate(make_both_active)

    assert excinfo.value.code == "PROFILE_STORE_INVALID"
    assert all(binding.active is False for binding in repository.list_bindings())


# ---------------------------------------------------------------------------
# T2 / T3 绑定与精确解绑 API
# ---------------------------------------------------------------------------


def test_binding_two_profiles_keeps_both_and_new_binding_stays_inactive(
    tmp_path: Path,
) -> None:
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

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["active"] is False
    assert second.json()["active"] is False
    assert [binding.profile_id for binding in harness.repository.list_bindings()] == [
        alpha["id"],
        beta["id"],
    ]


def test_repeated_binding_is_idempotent_while_other_binding_remains(tmp_path: Path) -> None:
    claude_dir = tmp_path / "claude"
    seed_claude(claude_dir)
    harness = make_profile_harness(tmp_path, claude_adapter(claude_dir))
    alpha = create_profile(harness, name="Alpha")
    beta = create_profile(harness, name="Beta")
    harness.client.put("/api/tools/claude-code/profile", json={"profile_id": alpha["id"]})
    first = harness.client.put(
        "/api/tools/claude-code/profile",
        json={"profile_id": beta["id"]},
    )
    second = harness.client.put(
        "/api/tools/claude-code/profile",
        json={"profile_id": beta["id"]},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == first.json()
    assert [binding.profile_id for binding in harness.repository.list_bindings()] == [
        alpha["id"],
        beta["id"],
    ]


def test_concurrent_binds_keep_both_bindings(tmp_path: Path) -> None:
    claude_dir = tmp_path / "claude"
    seed_claude(claude_dir)
    harness = make_profile_harness(tmp_path, claude_adapter(claude_dir))
    alpha = create_profile(harness, name="Alpha")
    beta = create_profile(harness, name="Beta")
    barrier = threading.Barrier(2)

    def bind(profile: dict[str, object]) -> object:
        barrier.wait()
        return harness.client.put(
            "/api/tools/claude-code/profile",
            json={"profile_id": profile["id"]},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(bind, [alpha, beta]))

    assert [response.status_code for response in responses] == [200, 200]
    assert {binding.profile_id for binding in harness.repository.list_bindings()} == {
        alpha["id"],
        beta["id"],
    }


def test_exact_unbind_removes_only_target_binding(tmp_path: Path) -> None:
    claude_dir = tmp_path / "claude"
    seed_claude(claude_dir)
    harness = make_profile_harness(tmp_path, claude_adapter(claude_dir))
    alpha = create_profile(harness, name="Alpha")
    beta = create_profile(harness, name="Beta")
    for profile in (alpha, beta):
        harness.client.put(
            "/api/tools/claude-code/profile",
            json={"profile_id": profile["id"]},
        )

    removed = harness.client.delete(f"/api/tools/claude-code/profiles/{beta['id']}")
    repeated = harness.client.delete(f"/api/tools/claude-code/profiles/{beta['id']}")

    assert removed.status_code == 200
    assert removed.json() == {"tool_id": "claude-code", "removed": True}
    assert repeated.status_code == 200
    assert repeated.json() == {"tool_id": "claude-code", "removed": False}
    assert [binding.profile_id for binding in harness.repository.list_bindings()] == [alpha["id"]]


def test_legacy_delete_requires_profile_id_and_keeps_other_bindings(tmp_path: Path) -> None:
    claude_dir = tmp_path / "claude"
    seed_claude(claude_dir)
    harness = make_profile_harness(tmp_path, claude_adapter(claude_dir))
    alpha = create_profile(harness, name="Alpha")
    beta = create_profile(harness, name="Beta")
    for profile in (alpha, beta):
        harness.client.put(
            "/api/tools/claude-code/profile",
            json={"profile_id": profile["id"]},
        )

    refused = harness.client.delete("/api/tools/claude-code/profile")
    removed = harness.client.delete(f"/api/tools/claude-code/profile?profile_id={alpha['id']}")

    assert refused.status_code == 422
    assert refused.json()["code"] == "VALIDATION_ERROR"
    assert removed.status_code == 200
    assert removed.json() == {"tool_id": "claude-code", "removed": True}
    assert [binding.profile_id for binding in harness.repository.list_bindings()] == [beta["id"]]


def test_unbinding_active_binding_does_not_promote_other_binding(tmp_path: Path) -> None:
    claude_dir = tmp_path / "claude"
    seed_claude(claude_dir)
    harness = make_profile_harness(tmp_path, claude_adapter(claude_dir))
    alpha = create_profile(harness, name="Alpha")
    beta = create_profile(harness, name="Beta")
    for profile in (alpha, beta):
        harness.client.put(
            "/api/tools/claude-code/profile",
            json={"profile_id": profile["id"]},
        )
    mark_active(harness, "claude-code", alpha["id"])

    removed = harness.client.delete(f"/api/tools/claude-code/profiles/{alpha['id']}")

    assert removed.status_code == 200
    remaining = harness.repository.list_bindings()
    assert [binding.profile_id for binding in remaining] == [beta["id"]]
    assert remaining[0].active is False


def test_unbinding_unknown_profile_returns_404_without_touching_bindings(
    tmp_path: Path,
) -> None:
    claude_dir = tmp_path / "claude"
    seed_claude(claude_dir)
    harness = make_profile_harness(tmp_path, claude_adapter(claude_dir))
    profile = create_profile(harness)
    harness.client.put("/api/tools/claude-code/profile", json={"profile_id": profile["id"]})

    response = harness.client.delete(f"/api/tools/claude-code/profiles/{UNKNOWN_PROFILE_ID}")

    assert response.status_code == 404
    assert response.json()["code"] == "PROFILE_NOT_FOUND"
    assert [binding.profile_id for binding in harness.repository.list_bindings()] == [profile["id"]]


# ---------------------------------------------------------------------------
# T4 切换与应用
# ---------------------------------------------------------------------------


def test_switch_a_b_a_keeps_both_bindings_and_one_active(tmp_path: Path) -> None:
    harness = make_switch_harness(tmp_path)
    alpha = add_profile(harness, name="Alpha")
    beta = add_profile(harness, name="Beta")
    write_claude_settings(harness, claude_content())

    first_a = preview_json(harness, alpha.id)
    applied_a = harness.client.post("/api/switch/apply", json=apply_payload(first_a))
    assert applied_a.status_code == 200, applied_a.text
    body_a = applied_a.json()

    applied_b = harness.client.post(
        "/api/switch/apply",
        json=apply_payload(preview_json(harness, beta.id)),
    )
    assert applied_b.status_code == 200, applied_b.text
    body_b = applied_b.json()

    after_b = {
        binding.profile_id: binding for binding in harness.profiles.list_bindings("claude-code")
    }
    assert set(after_b) == {alpha.id, beta.id}
    assert (
        after_b[alpha.id].bound_at.isoformat().replace("+00:00", "Z")
        == body_a["binding"]["bound_at"]
    )
    assert after_b[alpha.id].active is False
    assert after_b[beta.id].active is True
    assert after_b[alpha.id].snapshot_id == body_a["snapshot_id"]
    assert after_b[alpha.id].applied_at is not None
    assert after_b[alpha.id].applied_at.isoformat().replace("+00:00", "Z") == body_a["applied_at"]

    applied_a_again = harness.client.post(
        "/api/switch/apply",
        json=apply_payload(preview_json(harness, alpha.id)),
    )
    assert applied_a_again.status_code == 200, applied_a_again.text
    body_a_again = applied_a_again.json()

    final = {
        binding.profile_id: binding for binding in harness.profiles.list_bindings("claude-code")
    }
    assert set(final) == {alpha.id, beta.id}
    assert sum(binding.active for binding in final.values()) == 1
    assert final[alpha.id].active is True
    assert final[beta.id].active is False
    assert final[alpha.id].bound_at == after_b[alpha.id].bound_at
    assert final[alpha.id].snapshot_id == body_a_again["snapshot_id"]
    assert final[beta.id].snapshot_id == body_b["snapshot_id"]
    assert final[beta.id].applied_at is not None
    assert final[beta.id].applied_at.isoformat().replace("+00:00", "Z") == body_b["applied_at"]


def test_failed_switch_keeps_previous_active_binding_and_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = make_switch_harness(tmp_path)
    alpha = add_profile(harness, name="Alpha")
    beta = add_profile(harness, name="Beta")
    settings = write_claude_settings(harness, claude_content())
    original = settings.read_bytes()
    harness.profiles.mutate(
        lambda store: store.bindings.append(
            ToolBinding(
                tool_id="claude-code",
                profile_id=alpha.id,
                bound_at=NOW,
                active=True,
                applied_at=NOW,
                snapshot_id="snapshot-alpha",
            )
        )
    )
    preview = preview_json(harness, beta.id)

    def fail_mutate(_change: object) -> object:
        raise AppError("PROFILE_STORE_WRITE_FAILED", "档案库写入失败", 500)

    monkeypatch.setattr(harness.profiles, "mutate", fail_mutate)

    response = harness.client.post("/api/switch/apply", json=apply_payload(preview))

    assert response.status_code == 500
    assert response.json()["code"] == "BINDING_WRITE_FAILED"
    assert settings.read_bytes() == original
    bindings = harness.profiles.list_bindings("claude-code")
    assert [binding.profile_id for binding in bindings] == [alpha.id]
    assert bindings[0].active is True
    assert bindings[0].snapshot_id == "snapshot-alpha"


def test_concurrent_switch_keeps_all_bindings_and_one_active(tmp_path: Path) -> None:
    harness = make_switch_harness(tmp_path)
    alpha = add_profile(harness, name="Alpha")
    beta = add_profile(harness, name="Beta")
    write_claude_settings(harness, claude_content())
    harness.profiles.mutate(
        lambda store: store.bindings.extend(
            [
                ToolBinding(tool_id="claude-code", profile_id=alpha.id, bound_at=NOW),
                ToolBinding(tool_id="claude-code", profile_id=beta.id, bound_at=NOW),
            ]
        )
    )
    payload_a = apply_payload(preview_json(harness, alpha.id))
    payload_b = apply_payload(preview_json(harness, beta.id))
    barrier = threading.Barrier(2)

    def apply_once(payload: dict[str, object]) -> object:
        barrier.wait()
        return harness.client.post("/api/switch/apply", json=payload)

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(apply_once, [payload_a, payload_b]))

    statuses = sorted(response.status_code for response in responses)
    assert statuses == [200, 409]
    failed = next(response for response in responses if response.status_code == 409)
    assert failed.json()["code"] in {"WRITE_CONFLICT", "SWITCH_PREVIEW_STALE"}
    bindings = harness.profiles.list_bindings("claude-code")
    assert {binding.profile_id for binding in bindings} == {alpha.id, beta.id}
    assert sum(binding.active for binding in bindings) == 1


# ---------------------------------------------------------------------------
# T5 删除保护与查询
# ---------------------------------------------------------------------------


def test_delete_protection_covers_uninstalled_tool_and_keeps_other_vendor(
    tmp_path: Path,
) -> None:
    claude_dir = tmp_path / "claude"
    seed_claude(claude_dir)
    harness = make_profile_harness(tmp_path, claude_adapter(claude_dir))
    alpha = create_profile(harness, name="Alpha")
    beta = create_profile(harness, name="Beta")
    harness.client.put("/api/tools/claude-code/profile", json={"profile_id": alpha["id"]})
    bind_profile(harness, str(alpha["id"]), "removed-tool")
    harness.client.put("/api/tools/claude-code/profile", json={"profile_id": beta["id"]})

    detail = harness.client.get(f"/api/profiles/{alpha['id']}")
    refused = harness.client.delete(f"/api/profiles/{alpha['id']}")

    assert detail.status_code == 200
    assert detail.json()["used_by"] == [
        {"tool_id": "claude-code", "display_name": "Claude Code", "installed": True},
        {"tool_id": "removed-tool", "display_name": "removed-tool", "installed": False},
    ]
    assert refused.status_code == 409
    assert refused.json()["code"] == "PROFILE_IN_USE"
    assert "Claude Code" in refused.json()["message"]
    assert "removed-tool" in refused.json()["message"]

    deleted = harness.client.delete(f"/api/profiles/{alpha['id']}?confirm=true")

    assert deleted.status_code == 200
    assert deleted.json()["unbound_tools"] == [
        {"tool_id": "claude-code", "display_name": "Claude Code", "installed": True},
        {"tool_id": "removed-tool", "display_name": "removed-tool", "installed": False},
    ]
    assert harness.repository.get_profile(str(alpha["id"])) is None
    assert [
        (binding.tool_id, binding.profile_id) for binding in harness.repository.list_bindings()
    ] == [("claude-code", beta["id"])]


def test_profile_list_filters_by_tool_without_rewriting_file(tmp_path: Path) -> None:
    harness = make_profile_harness(tmp_path)
    alpha = create_profile(harness, name="Alpha")
    beta = create_profile(harness, name="Beta")
    unbound = create_profile(harness, name="Unbound")
    bind_profile(harness, str(alpha["id"]), "tool-one")
    bind_profile(harness, str(alpha["id"]), "tool-two")
    bind_profile(harness, str(beta["id"]), "tool-two")
    path = tmp_path / "profiles.json"
    before = file_fingerprint(path)

    filtered = harness.client.get("/api/profiles?tool_id=tool-two")
    repeated = harness.client.get("/api/profiles?tool_id=tool-two")
    full = harness.client.get("/api/profiles")

    assert filtered.status_code == 200
    body = filtered.json()
    assert [profile["id"] for profile in body["profiles"]] == [alpha["id"], beta["id"]]
    assert [(binding["tool_id"], binding["profile_id"]) for binding in body["bindings"]] == [
        ("tool-two", alpha["id"]),
        ("tool-two", beta["id"]),
    ]
    assert unbound["id"] not in {profile["id"] for profile in body["profiles"]}
    assert repeated.json() == body
    assert len(full.json()["profiles"]) == 3
    assert len(full.json()["bindings"]) == 3
    assert file_fingerprint(path) == before


@pytest.mark.parametrize("tool_id", ["", "%20%20"])
def test_profile_list_rejects_blank_tool_filter(tmp_path: Path, tool_id: str) -> None:
    harness = make_profile_harness(tmp_path)

    response = harness.client.get(f"/api/profiles?tool_id={tool_id}")

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_profile_list_filter_works_for_uninstalled_tool(tmp_path: Path) -> None:
    harness = make_profile_harness(tmp_path)
    profile = create_profile(harness)
    bind_profile(harness, str(profile["id"]), "removed-tool")

    response = harness.client.get("/api/profiles?tool_id=removed-tool")

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body["profiles"]] == [profile["id"]]
    assert body["profiles"][0]["used_by"] == [
        {"tool_id": "removed-tool", "display_name": "removed-tool", "installed": False}
    ]
    assert body["bindings"] == [
        {
            "tool_id": "removed-tool",
            "profile_id": profile["id"],
            "bound_at": body["bindings"][0]["bound_at"],
            "active": False,
            "applied_at": None,
            "snapshot_id": None,
        }
    ]


# ---------------------------------------------------------------------------
# 旧单绑定数据与切换兼容
# ---------------------------------------------------------------------------


def write_legacy_store(data_dir: Path, profile: Profile, binding: ToolBinding) -> Path:
    raw = {
        "schema_version": 1,
        "profiles": [profile.model_dump(mode="json")],
        "bindings": [binding.model_dump(mode="json")],
    }
    path = data_dir / "profiles.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return path


def test_legacy_single_binding_file_is_readable_via_api_without_rewrite(
    tmp_path: Path,
) -> None:
    profile = make_profile("旧版档案", models=[ModelEntry(id="claude-sonnet-4")])
    binding = make_binding(profile.id, "claude-code", bound_at=NOW)
    path = write_legacy_store(tmp_path, profile, binding)
    before = file_fingerprint(path)
    harness = make_profile_harness(tmp_path)

    listing = harness.client.get("/api/profiles")
    detail = harness.client.get(f"/api/profiles/{profile.id}")

    assert listing.status_code == 200
    assert [item["id"] for item in listing.json()["profiles"]] == [profile.id]
    assert len(listing.json()["bindings"]) == 1
    assert detail.status_code == 200
    assert detail.json()["used_by"] == [
        {"tool_id": "claude-code", "display_name": "claude-code", "installed": False}
    ]
    assert file_fingerprint(path) == before


def test_legacy_single_binding_file_switches_without_migration(tmp_path: Path) -> None:
    profile = make_profile(
        "旧版档案",
        models=[ModelEntry(id="claude-sonnet-4")],
        created_at=NOW,
        updated_at=NOW,
    )
    binding = make_binding(profile.id, "claude-code", bound_at=NOW - timedelta(days=2))
    path = write_legacy_store(tmp_path, profile, binding)
    harness = make_switch_harness(tmp_path)
    write_claude_settings(harness, claude_content())
    before_preview = file_fingerprint(path)

    preview = preview_json(harness, profile.id)
    assert file_fingerprint(path) == before_preview

    response = harness.client.post("/api/switch/apply", json=apply_payload(preview))

    assert response.status_code == 200, response.text
    body = response.json()
    stored = harness.profiles.list_bindings("claude-code")
    assert len(stored) == 1
    assert stored[0].active is True
    assert stored[0].bound_at == binding.bound_at
    assert stored[0].snapshot_id == body["snapshot_id"]
    assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == 1
