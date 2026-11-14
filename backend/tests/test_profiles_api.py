"""档案 CRUD API 集成测试。

全部通过 TestClient 走真实路由; 数据目录、密钥后端与工具发现都用临时替身,
不触碰真实系统钥匙串与本机工具配置。覆盖校验、重名、密钥补偿、复制、删除保护
与「CRUD 前后工具配置文件 hash 不变」。
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path

import pytest
from adapter_contract import snapshot_tree
from fastapi.testclient import TestClient
from profile_fixtures import (
    FakeKeyring,
    bind_profile,
    create_profile,
    make_binding,
    make_profile,
    make_profile_harness,
    profile_payload,
    stored_profile,
)
from tool_fixtures import claude_adapter, codex_adapter, seed_claude, seed_codex

from app.adapters.registry import ToolRegistry
from app.api.profiles import get_profile_service
from app.core.redaction import redact_secret
from app.main import create_app
from app.repositories.profiles import ProfileRepository
from app.repositories.secrets import (
    KEYRING_SERVICE_NAME,
    FileSecretStore,
    KeyringSecretStore,
    build_secret_store,
)
from app.schemas.profile import ProfileStore
from app.services.profile_service import ProfileService
from app.services.tool_discovery import ToolDiscoveryService

SECRET = "sk-ant-fixture-1234567890abcdef"
OTHER_SECRET = "sk-ant-fixture-fedcba0987654321"
PROFILES_FILE = "profiles.json"


def assert_aware_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    assert parsed.utcoffset() is not None
    return parsed


def test_create_profile_returns_view_and_persists_store(tmp_path: Path) -> None:
    harness = make_profile_harness(tmp_path)

    resp = harness.client.post(
        "/api/profiles",
        json=profile_payload(
            name="  Anthropic 主力  ",
            base_url="  https://api.anthropic.com/v1  ",
            models=[{"id": "  claude-sonnet-4  ", "display_name": "   "}],
        ),
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Anthropic 主力"
    assert body["base_url"] == "https://api.anthropic.com/v1"
    assert body["protocol"] == "anthropic"
    assert body["models"] == [{"id": "claude-sonnet-4", "display_name": None}]
    assert body["has_secret"] is False
    assert body["secret_preview"] is None
    assert body["secret_backend"] is None
    assert body["used_by"] == []
    assert body["warnings"] == []
    assert "secret_ref" not in body
    assert "locator" not in resp.text
    assert_aware_iso(body["created_at"])
    assert_aware_iso(body["updated_at"])

    detail = harness.client.get(f"/api/profiles/{body['id']}")
    assert detail.status_code == 200
    assert detail.json() == body

    listing = harness.client.get("/api/profiles")
    assert listing.status_code == 200
    listed = listing.json()
    assert set(listed) == {"profiles", "bindings", "secret_store", "warnings"}
    assert listed["profiles"] == [body]
    assert listed["bindings"] == []
    assert listed["secret_store"] == {"backend": "keyring", "fallback": False, "message": None}
    assert listed["warnings"] == []

    raw = json.loads((tmp_path / PROFILES_FILE).read_text(encoding="utf-8"))
    assert raw["schema_version"] == 1
    assert raw["bindings"] == []
    assert raw["profiles"][0]["secret_ref"] is None


def test_create_with_secret_persists_reference_and_masks_preview(tmp_path: Path) -> None:
    harness = make_profile_harness(tmp_path)

    body = create_profile(harness, secret=SECRET)

    assert body["has_secret"] is True
    assert body["secret_preview"] == redact_secret(SECRET)
    assert body["secret_backend"] == "keyring"
    stored = stored_profile(harness, str(body["id"]))
    assert stored["secret_ref"]["backend"] == "keyring"
    assert stored["secret_ref"]["locator"] == body["id"]
    assert SECRET not in json.dumps(stored, ensure_ascii=False)
    assert harness.keyring.values == {(KEYRING_SERVICE_NAME, str(body["id"])): SECRET}


@pytest.mark.parametrize(
    ("overrides", "message_hint"),
    [
        ({"name": "   "}, "档案名称"),
        ({"name": "x" * 81}, "档案名称"),
        ({"protocol": "gemini"}, "protocol"),
        ({"base_url": "api.anthropic.com"}, "base_url"),
        ({"base_url": "ftp://api.anthropic.com"}, "base_url"),
        ({"base_url": "https:///v1"}, "base_url"),
        ({"base_url": "https://user:pass@example.com"}, "base_url"),
        ({"base_url": "https://example.com/v1#fragment"}, "base_url"),
        ({"base_url": "https://example.com/" + "a" * 2048}, "base_url"),
        ({"models": [{"id": "same"}, {"id": "  same  "}]}, "same"),
        ({"unknown_field": "value"}, "unknown_field"),
    ],
)
def test_create_rejects_invalid_payload_without_side_effects(
    tmp_path: Path,
    overrides: dict[str, object],
    message_hint: str,
) -> None:
    harness = make_profile_harness(tmp_path)

    resp = harness.client.post("/api/profiles", json=profile_payload(**overrides))

    assert resp.status_code == 422
    body = resp.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert message_hint in body["message"]
    assert "Traceback" not in resp.text
    assert not (tmp_path / PROFILES_FILE).exists()
    assert harness.keyring.values == {}


def test_create_rejects_case_insensitive_name_conflict_and_rolls_back_secret(
    tmp_path: Path,
) -> None:
    harness = make_profile_harness(tmp_path)
    create_profile(harness, name="Main", base_url="https://api.anthropic.com")

    resp = harness.client.post(
        "/api/profiles",
        json=profile_payload(name="  main  ", secret=SECRET),
    )

    assert resp.status_code == 409
    assert resp.json()["code"] == "PROFILE_NAME_CONFLICT"
    assert "main" in resp.json()["message"]
    assert len(harness.repository.list_profiles()) == 1
    assert harness.keyring.values == {}


def test_list_and_detail_return_used_by_for_installed_and_uninstalled_tools(
    tmp_path: Path,
) -> None:
    claude_dir = tmp_path / "claude"
    seed_claude(claude_dir)
    codex_dir = tmp_path / "codex"
    seed_codex(codex_dir)
    tools_before = (snapshot_tree(claude_dir), snapshot_tree(codex_dir))
    harness = make_profile_harness(tmp_path, claude_adapter(claude_dir), codex_adapter(codex_dir))
    created = create_profile(harness)
    profile_id = str(created["id"])
    bind_profile(harness, profile_id, "claude-code")
    bind_profile(harness, profile_id, "codex-cli")
    bind_profile(harness, profile_id, "removed-tool")

    listing = harness.client.get("/api/profiles")
    detail = harness.client.get(f"/api/profiles/{profile_id}")

    assert listing.status_code == 200
    used_by = detail.json()["used_by"]
    assert used_by == [
        {"tool_id": "claude-code", "display_name": "Claude Code", "installed": True},
        {"tool_id": "codex-cli", "display_name": "Codex CLI", "installed": True},
        {"tool_id": "removed-tool", "display_name": "removed-tool", "installed": False},
    ]
    assert listing.json()["profiles"][0]["used_by"] == used_by
    assert [binding["tool_id"] for binding in listing.json()["bindings"]] == [
        "claude-code",
        "codex-cli",
        "removed-tool",
    ]
    assert (snapshot_tree(claude_dir), snapshot_tree(codex_dir)) == tools_before


def test_secret_missing_degrades_to_warning_without_failing_list(tmp_path: Path) -> None:
    harness = make_profile_harness(tmp_path)
    created = create_profile(harness, secret=SECRET)
    profile_id = str(created["id"])
    del harness.keyring.values[(KEYRING_SERVICE_NAME, profile_id)]

    listing = harness.client.get("/api/profiles")
    detail = harness.client.get(f"/api/profiles/{profile_id}")

    assert listing.status_code == 200
    for view in (listing.json()["profiles"][0], detail.json()):
        assert view["has_secret"] is False
        assert view["secret_preview"] is None
        assert [warning["code"] for warning in view["warnings"]] == ["SECRET_MISSING"]
    assert SECRET not in listing.text


def test_secret_store_read_failure_degrades_to_warning(tmp_path: Path) -> None:
    harness = make_profile_harness(tmp_path)
    created = create_profile(harness, secret=SECRET)
    harness.keyring.fail_get = True

    resp = harness.client.get(f"/api/profiles/{created['id']}")

    assert resp.status_code == 200
    view = resp.json()
    assert view["has_secret"] is False
    assert [warning["code"] for warning in view["warnings"]] == ["SECRET_STORE_ERROR"]
    assert SECRET not in resp.text


def test_patch_updates_fields_and_keeps_secret_when_omitted(tmp_path: Path) -> None:
    harness = make_profile_harness(tmp_path)
    created = create_profile(harness, secret=SECRET, models=[{"id": "claude-sonnet-4"}])
    profile_id = str(created["id"])
    created_at = assert_aware_iso(str(created["created_at"]))

    resp = harness.client.patch(
        f"/api/profiles/{profile_id}",
        json={
            "name": "  新名字  ",
            "base_url": "https://example.com/v1/",
            "models": [{"id": "gpt-5-codex", "display_name": "GPT-5"}],
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "新名字"
    assert body["base_url"] == "https://example.com/v1/"
    assert body["models"] == [{"id": "gpt-5-codex", "display_name": "GPT-5"}]
    assert body["protocol"] == "anthropic"
    assert body["has_secret"] is True
    assert body["secret_preview"] == redact_secret(SECRET)
    assert assert_aware_iso(str(body["updated_at"])) >= created_at
    assert harness.keyring.values == {(KEYRING_SERVICE_NAME, profile_id): SECRET}


def test_patch_replaces_and_clears_secret(tmp_path: Path) -> None:
    harness = make_profile_harness(tmp_path)
    created = create_profile(harness, secret=SECRET)
    profile_id = str(created["id"])

    replaced = harness.client.patch(
        f"/api/profiles/{profile_id}",
        json={"secret": OTHER_SECRET},
    )
    assert replaced.status_code == 200
    assert replaced.json()["secret_preview"] == redact_secret(OTHER_SECRET)
    assert harness.keyring.values == {(KEYRING_SERVICE_NAME, profile_id): OTHER_SECRET}

    cleared = harness.client.patch(f"/api/profiles/{profile_id}", json={"secret": None})
    assert cleared.status_code == 200
    assert cleared.json()["has_secret"] is False
    assert cleared.json()["secret_preview"] is None
    assert cleared.json()["secret_backend"] is None
    assert harness.keyring.values == {}
    assert stored_profile(harness, profile_id)["secret_ref"] is None


def test_patch_rejects_invalid_fields_and_unknown_profile(tmp_path: Path) -> None:
    harness = make_profile_harness(tmp_path)
    created = create_profile(harness, models=[{"id": "same"}])
    profile_id = str(created["id"])

    duplicate = harness.client.patch(
        f"/api/profiles/{profile_id}",
        json={"models": [{"id": "same"}, {"id": " same "}]},
    )
    null_name = harness.client.patch(f"/api/profiles/{profile_id}", json={"name": None})
    blank_secret = harness.client.patch(
        f"/api/profiles/{profile_id}",
        json={"secret": "   "},
    )
    unknown_field = harness.client.patch(
        f"/api/profiles/{profile_id}",
        json={"nope": True},
    )
    unknown_profile = harness.client.patch(
        "/api/profiles/00000000-0000-4000-8000-000000000000",
        json={"name": "另一个"},
    )

    assert duplicate.status_code == 422
    assert duplicate.json()["code"] == "VALIDATION_ERROR"
    assert "same" in duplicate.json()["message"]
    assert null_name.status_code == 422
    assert null_name.json()["code"] == "VALIDATION_ERROR"
    assert blank_secret.status_code == 422
    assert unknown_field.status_code == 422
    assert unknown_profile.status_code == 404
    assert unknown_profile.json()["code"] == "PROFILE_NOT_FOUND"
    assert harness.repository.get_profile(profile_id) is not None


def test_create_accepts_empty_model_list_and_persists_it(tmp_path: Path) -> None:
    harness = make_profile_harness(tmp_path)

    created = create_profile(harness, models=[])

    assert created["models"] == []
    assert created["warnings"] == []
    detail = harness.client.get(f"/api/profiles/{created['id']}")
    assert detail.status_code == 200
    assert detail.json()["models"] == []
    assert stored_profile(harness, str(created["id"]))["models"] == []


def test_patch_replaces_model_list_adding_editing_and_removing_entries(
    tmp_path: Path,
) -> None:
    harness = make_profile_harness(tmp_path)
    created = create_profile(
        harness,
        models=[
            {"id": "claude-sonnet-4", "display_name": "Sonnet"},
            {"id": "claude-haiku-4", "display_name": "Haiku"},
        ],
    )
    profile_id = str(created["id"])
    expected = [
        {"id": "claude-sonnet-4", "display_name": "Sonnet 4"},
        {"id": "claude-opus-4", "display_name": None},
    ]

    resp = harness.client.patch(
        f"/api/profiles/{profile_id}",
        json={
            "models": [
                {"id": "claude-sonnet-4", "display_name": "Sonnet 4"},
                {"id": "claude-opus-4"},
            ]
        },
    )

    assert resp.status_code == 200
    assert resp.json()["models"] == expected
    assert resp.json()["name"] == created["name"]
    assert resp.json()["protocol"] == created["protocol"]
    assert resp.json()["base_url"] == created["base_url"]
    assert harness.client.get(f"/api/profiles/{profile_id}").json()["models"] == expected
    assert stored_profile(harness, profile_id)["models"] == expected


def test_patch_can_clear_model_list(tmp_path: Path) -> None:
    harness = make_profile_harness(tmp_path)
    created = create_profile(harness, models=[{"id": "gpt-5-codex"}])
    profile_id = str(created["id"])

    resp = harness.client.patch(f"/api/profiles/{profile_id}", json={"models": []})

    assert resp.status_code == 200
    assert resp.json()["models"] == []
    assert stored_profile(harness, profile_id)["models"] == []


def test_patch_rejects_duplicate_models_and_keeps_previous_list(tmp_path: Path) -> None:
    harness = make_profile_harness(tmp_path)
    created = create_profile(harness, models=[{"id": "gpt-5-codex"}])
    profile_id = str(created["id"])

    resp = harness.client.patch(
        f"/api/profiles/{profile_id}",
        json={"models": [{"id": "gpt-5-codex"}, {"id": "  gpt-5-codex  "}]},
    )

    assert resp.status_code == 422
    assert resp.json()["code"] == "VALIDATION_ERROR"
    assert "gpt-5-codex" in resp.json()["message"]
    assert stored_profile(harness, profile_id)["models"] == [
        {"id": "gpt-5-codex", "display_name": None}
    ]


def test_duplicate_model_error_lists_each_repeated_id_once(tmp_path: Path) -> None:
    harness = make_profile_harness(tmp_path)

    resp = harness.client.post(
        "/api/profiles",
        json=profile_payload(
            models=[
                {"id": "alpha"},
                {"id": " alpha "},
                {"id": "beta"},
                {"id": "beta"},
                {"id": "beta"},
            ]
        ),
    )

    assert resp.status_code == 422
    assert resp.json()["code"] == "VALIDATION_ERROR"
    message = resp.json()["message"]
    assert message.count("alpha") == 1
    assert message.count("beta") == 1
    assert not (tmp_path / PROFILES_FILE).exists()


@pytest.mark.parametrize("model_id", ["", "   ", "x" * 121])
def test_create_rejects_blank_or_overlong_model_id(
    tmp_path: Path,
    model_id: str,
) -> None:
    harness = make_profile_harness(tmp_path)

    resp = harness.client.post(
        "/api/profiles",
        json=profile_payload(models=[{"id": model_id}]),
    )

    assert resp.status_code == 422
    assert resp.json()["code"] == "VALIDATION_ERROR"
    assert "模型标识" in resp.json()["message"]
    assert not (tmp_path / PROFILES_FILE).exists()


def test_model_id_length_boundary_is_measured_after_trimming(tmp_path: Path) -> None:
    harness = make_profile_harness(tmp_path)
    accepted_id = "m" * 120

    created = create_profile(harness, models=[{"id": f"  {accepted_id}  "}])
    profile_id = str(created["id"])
    rejected = harness.client.patch(
        f"/api/profiles/{profile_id}",
        json={"models": [{"id": "m" * 121}]},
    )

    assert created["models"] == [{"id": accepted_id, "display_name": None}]
    assert rejected.status_code == 422
    assert rejected.json()["code"] == "VALIDATION_ERROR"
    assert stored_profile(harness, profile_id)["models"] == [
        {"id": accepted_id, "display_name": None}
    ]


def test_model_ids_that_differ_only_in_case_are_distinct(tmp_path: Path) -> None:
    harness = make_profile_harness(tmp_path)

    created = create_profile(harness, models=[{"id": "GPT-5"}, {"id": "gpt-5"}])

    assert [model["id"] for model in created["models"]] == ["GPT-5", "gpt-5"]
    stored = stored_profile(harness, str(created["id"]))
    assert [model["id"] for model in stored["models"]] == ["GPT-5", "gpt-5"]


def test_patch_normalizes_blank_display_name_to_null(tmp_path: Path) -> None:
    harness = make_profile_harness(tmp_path)
    created = create_profile(
        harness,
        models=[{"id": "gpt-5", "display_name": "GPT-5"}],
    )
    profile_id = str(created["id"])
    expected = [
        {"id": "gpt-5", "display_name": None},
        {"id": "gpt-5-mini", "display_name": None},
    ]

    resp = harness.client.patch(
        f"/api/profiles/{profile_id}",
        json={
            "models": [
                {"id": "gpt-5", "display_name": "   "},
                {"id": "gpt-5-mini", "display_name": None},
            ]
        },
    )

    assert resp.status_code == 200
    assert resp.json()["models"] == expected
    assert stored_profile(harness, profile_id)["models"] == expected


def test_patch_rolls_back_replaced_secret_when_profile_write_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = make_profile_harness(tmp_path)
    created = create_profile(harness, secret=SECRET)
    profile_id = str(created["id"])
    _fail_profile_writes(monkeypatch)

    resp = harness.client.patch(
        f"/api/profiles/{profile_id}",
        json={"secret": OTHER_SECRET},
    )

    assert resp.status_code == 500
    assert resp.json()["code"] == "PROFILE_STORE_WRITE_FAILED"
    assert harness.keyring.values == {(KEYRING_SERVICE_NAME, profile_id): SECRET}
    assert OTHER_SECRET not in resp.text
    assert SECRET not in resp.text


def test_patch_restores_secret_when_clearing_and_profile_write_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = make_profile_harness(tmp_path)
    created = create_profile(harness, secret=SECRET)
    profile_id = str(created["id"])
    _fail_profile_writes(monkeypatch)

    resp = harness.client.patch(f"/api/profiles/{profile_id}", json={"secret": None})

    assert resp.status_code == 500
    assert harness.keyring.values == {(KEYRING_SERVICE_NAME, profile_id): SECRET}
    profile = harness.repository.get_profile(profile_id)
    assert profile is not None
    assert profile.secret_ref is not None


def test_create_rolls_back_secret_when_profile_write_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = make_profile_harness(tmp_path)
    _fail_profile_writes(monkeypatch)

    resp = harness.client.post("/api/profiles", json=profile_payload(secret=SECRET))

    assert resp.status_code == 500
    assert resp.json()["code"] == "PROFILE_STORE_WRITE_FAILED"
    assert harness.keyring.values == {}
    assert not (tmp_path / PROFILES_FILE).exists()
    assert SECRET not in resp.text


def test_copy_profile_copies_secret_models_and_name_suffix_without_bindings(
    tmp_path: Path,
) -> None:
    harness = make_profile_harness(tmp_path)
    created = create_profile(
        harness,
        name="Anthropic 主力",
        models=[{"id": "claude-sonnet-4", "display_name": "Sonnet"}],
        secret=SECRET,
    )
    source_id = str(created["id"])
    bind_profile(harness, source_id, "claude-code")

    first = harness.client.post(f"/api/profiles/{source_id}/copy")
    second = harness.client.post(f"/api/profiles/{source_id}/copy")
    named = harness.client.post(
        f"/api/profiles/{source_id}/copy",
        json={"name": "自定义副本"},
    )
    conflict = harness.client.post(
        f"/api/profiles/{source_id}/copy",
        json={"name": "anthropic 主力"},
    )

    assert first.status_code == 201
    first_copy = first.json()
    assert first_copy["id"] != source_id
    assert first_copy["name"] == "Anthropic 主力 (副本)"
    assert first_copy["protocol"] == created["protocol"]
    assert first_copy["base_url"] == created["base_url"]
    assert first_copy["models"] == created["models"]
    assert first_copy["has_secret"] is True
    assert first_copy["secret_preview"] == redact_secret(SECRET)
    assert first_copy["used_by"] == []
    assert second.json()["name"] == "Anthropic 主力 (副本 2)"
    assert named.status_code == 201
    assert named.json()["name"] == "自定义副本"
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "PROFILE_NAME_CONFLICT"

    assert harness.keyring.values[(KEYRING_SERVICE_NAME, first_copy["id"])] == SECRET
    assert [binding.tool_id for binding in harness.repository.list_bindings()] == ["claude-code"]


def test_copy_without_secret_and_with_missing_source_secret(tmp_path: Path) -> None:
    harness = make_profile_harness(tmp_path)
    plain = create_profile(harness, name="无密钥")

    plain_copy = harness.client.post(f"/api/profiles/{plain['id']}/copy")
    assert plain_copy.status_code == 201
    assert plain_copy.json()["has_secret"] is False
    assert plain_copy.json()["warnings"] == []

    with_secret = create_profile(harness, name="有密钥", secret=SECRET)
    del harness.keyring.values[(KEYRING_SERVICE_NAME, str(with_secret["id"]))]

    missing_copy = harness.client.post(f"/api/profiles/{with_secret['id']}/copy")

    assert missing_copy.status_code == 201
    body = missing_copy.json()
    assert body["has_secret"] is False
    assert body["secret_backend"] is None
    assert [warning["code"] for warning in body["warnings"]] == ["SECRET_MISSING"]
    assert SECRET not in missing_copy.text


def test_copy_reports_secret_store_failure_without_creating_secret(
    tmp_path: Path,
) -> None:
    harness = make_profile_harness(tmp_path)
    source = create_profile(harness, secret=SECRET)
    harness.keyring.fail_get = True

    resp = harness.client.post(f"/api/profiles/{source['id']}/copy")

    assert resp.status_code == 201
    body = resp.json()
    assert body["has_secret"] is False
    assert [warning["code"] for warning in body["warnings"]] == ["SECRET_STORE_ERROR"]
    assert harness.keyring.values == {(KEYRING_SERVICE_NAME, str(source["id"])): SECRET}


def test_delete_in_use_requires_confirmation_and_cleans_up(tmp_path: Path) -> None:
    claude_dir = tmp_path / "claude"
    seed_claude(claude_dir)
    codex_dir = tmp_path / "codex"
    seed_codex(codex_dir)
    tools_before = (snapshot_tree(claude_dir), snapshot_tree(codex_dir))
    harness = make_profile_harness(tmp_path, claude_adapter(claude_dir), codex_adapter(codex_dir))
    created = create_profile(harness, secret=SECRET)
    profile_id = str(created["id"])
    bind_profile(harness, profile_id, "claude-code")
    bind_profile(harness, profile_id, "codex-cli")

    refused = harness.client.delete(f"/api/profiles/{profile_id}")

    assert refused.status_code == 409
    message = refused.json()["message"]
    assert "Claude Code" in message
    assert "Codex CLI" in message
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
    assert harness.client.get(f"/api/profiles/{profile_id}").status_code == 404


def test_delete_unused_profile_without_confirmation(tmp_path: Path) -> None:
    harness = make_profile_harness(tmp_path)
    created = create_profile(harness)

    resp = harness.client.delete(f"/api/profiles/{created['id']}")

    assert resp.status_code == 200
    assert resp.json() == {"deleted": True, "unbound_tools": []}
    assert harness.client.get("/api/profiles").json()["profiles"] == []


def test_delete_protects_profile_bound_to_uninstalled_tool(tmp_path: Path) -> None:
    harness = make_profile_harness(tmp_path)
    created = create_profile(harness)
    profile_id = str(created["id"])
    bind_profile(harness, profile_id, "removed-tool")

    refused = harness.client.delete(f"/api/profiles/{profile_id}")
    deleted = harness.client.delete(f"/api/profiles/{profile_id}?confirm=true")

    assert refused.status_code == 409
    assert "removed-tool" in refused.json()["message"]
    assert deleted.status_code == 200
    assert deleted.json()["unbound_tools"] == [
        {"tool_id": "removed-tool", "display_name": "removed-tool", "installed": False}
    ]


def test_deleting_unknown_profile_returns_404(tmp_path: Path) -> None:
    harness = make_profile_harness(tmp_path)

    resp = harness.client.delete("/api/profiles/00000000-0000-4000-8000-000000000000")

    assert resp.status_code == 404
    assert resp.json()["code"] == "PROFILE_NOT_FOUND"


@pytest.mark.parametrize("method", ["get", "patch", "copy"])
def test_unknown_profile_returns_404_for_read_and_write_endpoints(
    tmp_path: Path,
    method: str,
) -> None:
    harness = make_profile_harness(tmp_path)
    profile_id = "00000000-0000-4000-8000-000000000000"
    url = f"/api/profiles/{profile_id}/copy" if method == "copy" else f"/api/profiles/{profile_id}"
    if method == "copy":
        response = harness.client.post(url)
    elif method == "patch":
        response = harness.client.patch(url, json={})
    else:
        response = harness.client.get(url)

    assert response.status_code == 404
    assert response.json()["code"] == "PROFILE_NOT_FOUND"


def test_validation_errors_never_echo_the_secret(tmp_path: Path) -> None:
    harness = make_profile_harness(tmp_path)

    resp = harness.client.post(
        "/api/profiles",
        json=profile_payload(base_url="https://user:pass@example.com", secret=SECRET),
    )

    assert resp.status_code == 422
    assert SECRET not in resp.text
    assert harness.keyring.values == {}


def test_reads_are_idempotent_and_do_not_touch_profile_or_tool_files(tmp_path: Path) -> None:
    claude_dir = tmp_path / "claude"
    seed_claude(claude_dir)
    harness = make_profile_harness(tmp_path, claude_adapter(claude_dir))
    created = create_profile(harness, secret=SECRET)
    bind_profile(harness, str(created["id"]), "claude-code")
    profiles_hash = _file_hash(tmp_path / PROFILES_FILE)
    tools_before = snapshot_tree(claude_dir)

    for _ in range(3):
        assert harness.client.get("/api/profiles").status_code == 200
        assert harness.client.get(f"/api/profiles/{created['id']}").status_code == 200

    assert _file_hash(tmp_path / PROFILES_FILE) == profiles_hash
    assert snapshot_tree(claude_dir) == tools_before
    assert harness.keyring.values == {(KEYRING_SERVICE_NAME, str(created["id"])): SECRET}


def test_empty_patch_returns_profile_without_rewriting(tmp_path: Path) -> None:
    harness = make_profile_harness(tmp_path)
    created = create_profile(harness)
    before = _file_hash(tmp_path / PROFILES_FILE)

    resp = harness.client.patch(f"/api/profiles/{created['id']}", json={})

    assert resp.status_code == 200
    assert resp.json() == created
    assert _file_hash(tmp_path / PROFILES_FILE) == before


def test_patch_name_conflict_excludes_self_and_rejects_other_profile(
    tmp_path: Path,
) -> None:
    harness = make_profile_harness(tmp_path)
    alpha = create_profile(harness, name="Alpha")
    beta = create_profile(harness, name="Beta")

    same_name = harness.client.patch(f"/api/profiles/{beta['id']}", json={"name": "beta"})
    conflict = harness.client.patch(f"/api/profiles/{beta['id']}", json={"name": "ALPHA"})

    assert same_name.status_code == 200
    assert same_name.json()["name"] == "beta"
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "PROFILE_NAME_CONFLICT"
    stored_alpha = harness.repository.get_profile(str(alpha["id"]))
    assert stored_alpha is not None
    assert stored_alpha.name == "Alpha"


def test_copy_truncates_generated_name_to_profile_name_limit(tmp_path: Path) -> None:
    harness = make_profile_harness(tmp_path)
    source = create_profile(harness, name="x" * 80)

    resp = harness.client.post(f"/api/profiles/{source['id']}/copy")

    assert resp.status_code == 201
    name = resp.json()["name"]
    assert len(name) <= 80
    assert name.endswith(" (副本)")


def test_file_backend_reports_fallback_and_writes_only_to_secrets_file(
    tmp_path: Path,
) -> None:
    harness = make_profile_harness(tmp_path, mode="file")

    body = create_profile(harness, secret=SECRET)

    assert body["secret_backend"] == "file"
    listing = harness.client.get("/api/profiles").json()
    assert listing["secret_store"]["backend"] == "file"
    assert listing["secret_store"]["fallback"] is True
    assert SECRET not in json.dumps(listing, ensure_ascii=False)
    fallback = json.loads((tmp_path / "secrets.json").read_text(encoding="utf-8"))
    assert fallback["secrets"][str(body["id"])] == SECRET
    assert harness.keyring.values == {}


def test_unavailable_secret_store_is_reported_at_list_level(tmp_path: Path) -> None:
    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory", encoding="utf-8")
    keyring = FakeKeyring()
    secrets = build_secret_store(
        blocked,
        mode="auto",
        keyring_store=KeyringSecretStore(keyring, available=False),
        file_store=FileSecretStore(blocked),
    )
    data_dir = tmp_path / "data"
    repository = ProfileRepository(data_dir)
    profile = make_profile()

    def add(store: ProfileStore) -> None:
        store.profiles.append(profile)

    repository.mutate(add)
    service = ProfileService(
        repository,
        secrets,
        ToolDiscoveryService(ToolRegistry([])),
    )
    app = create_app()
    app.dependency_overrides[get_profile_service] = lambda: service

    resp = TestClient(app).get("/api/profiles")

    assert resp.status_code == 200
    body = resp.json()
    assert body["secret_store"]["backend"] == "unavailable"
    assert [warning["code"] for warning in body["warnings"]] == ["SECRET_STORE_ERROR"]


def test_list_handles_many_profiles_and_bindings(tmp_path: Path) -> None:
    harness = make_profile_harness(tmp_path)

    def seed(store: ProfileStore) -> None:
        for index in range(100):
            profile = make_profile(f"档案 {index}")
            store.profiles.append(profile)
            store.bindings.append(make_binding(profile.id, f"tool-{index}"))

    harness.repository.mutate(seed)

    resp = harness.client.get("/api/profiles")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["profiles"]) == 100
    assert len(body["bindings"]) == 100
    assert all(profile["used_by"][0]["installed"] is False for profile in body["profiles"])


def _fail_profile_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_write(_path: Path, _data: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("app.repositories.profiles.write_json_atomic", fail_write)


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
