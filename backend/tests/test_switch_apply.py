"""008 T3: 应用、防漂移、外部冲突、绑定失败回滚与脱敏。"""

import hashlib
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path

import pytest
from switch_fixtures import (
    NOW,
    SECRET,
    add_codex_profile,
    add_profile,
    apply_payload,
    make_switch_harness,
    preview_json,
    write_claude_settings,
    write_codex_files,
)

from app.core.errors import AppError
from app.core.locks import FileLock
from app.schemas.profile import Profile, ToolBinding


def claude_content() -> bytes:
    return json.dumps(
        {
            "model": "claude-sonnet-4",
            "env": {
                "ANTHROPIC_BASE_URL": "https://old.example.com",
                "ANTHROPIC_API_KEY": "sk-old-api-key",
                "KEEP_ME": "原样保留",
            },
            "hooks": {"Stop": [{"command": "echo hi"}]},
            "unknown": [1, 2, 3],
        },
        ensure_ascii=False,
    ).encode()


def update_profile(
    harness: object,
    profile: Profile,
    **updates: object,
) -> Profile:
    updated = Profile.model_validate(profile.model_dump() | updates)
    harness.profiles.mutate(
        lambda store: setattr(
            store,
            "profiles",
            [updated if item.id == profile.id else item for item in store.profiles],
        )
    )
    return updated


def post_apply(harness: object, payload: dict[str, object]) -> object:
    return harness.client.post("/api/switch/apply", json=payload)


def test_apply_writes_fields_snapshot_audit_and_binding(tmp_path: Path) -> None:
    harness = make_switch_harness(tmp_path)
    profile = add_profile(harness)
    settings = write_claude_settings(harness, claude_content())
    original = settings.read_bytes()
    previous_bound_at = NOW - timedelta(days=1)
    harness.profiles.mutate(
        lambda store: store.bindings.append(
            ToolBinding(
                tool_id="claude-code",
                profile_id=profile.id,
                bound_at=previous_bound_at,
            )
        )
    )
    preview = preview_json(harness, profile.id)

    response = post_apply(harness, apply_payload(preview))

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["snapshot_id"]
    assert body["audit_id"]
    assert body["restart_required"] is True
    assert "重启" in body["restart_message"]
    assert body["binding"]["active"] is True
    assert body["binding"]["profile_id"] == profile.id
    assert body["binding"]["snapshot_id"] == body["snapshot_id"]
    assert body["binding"]["applied_at"] == body["applied_at"]
    assert body["binding"]["bound_at"] == previous_bound_at.isoformat().replace("+00:00", "Z")
    assert SECRET not in response.text

    written = settings.read_bytes()
    assert written != original
    assert SECRET.encode() in written
    assert '"KEEP_ME": "原样保留"' in written.decode()
    assert '"hooks"' in written.decode()
    assert '"unknown": [1, 2, 3]' in written.decode()
    parsed = json.loads(written)
    assert parsed["model"] == "claude-sonnet-4"
    assert parsed["env"]["ANTHROPIC_BASE_URL"] == profile.base_url
    assert parsed["env"]["ANTHROPIC_API_KEY"] == SECRET

    snapshot = harness.snapshots.get(body["snapshot_id"])
    assert snapshot is not None
    assert snapshot.tool_id == "claude-code"
    assert snapshot.profile_id == profile.id
    assert snapshot.reason == "apply"
    meta_path = tmp_path / "snapshots" / body["snapshot_id"] / "meta.json"
    meta_text = meta_path.read_text(encoding="utf-8")
    assert SECRET not in meta_text
    assert "sk-old-api-key" not in meta_text

    entries = harness.audit.list_recent()
    assert entries[0].result == "success"
    assert entries[0].snapshot_id == body["snapshot_id"]
    assert entries[0].profile_id == profile.id
    dumped = json.dumps(
        [entry.model_dump(mode="json") for entry in entries],
        ensure_ascii=False,
    )
    assert SECRET not in dumped
    for field in entries[0].fields:
        assert SECRET not in field

    binding = harness.profiles.get_binding("claude-code")
    assert binding is not None
    assert binding.active is True
    assert binding.snapshot_id == body["snapshot_id"]


def test_apply_codex_writes_both_files(tmp_path: Path) -> None:
    harness = make_switch_harness(tmp_path)
    profile = add_codex_profile(harness)
    config, auth = write_codex_files(
        harness,
        config=(
            'model = "gpt-old"\n'
            'model_provider = "openai"\n'
            "\n"
            "[model_providers.openai]\n"
            'name = "OpenAI"\n'
            'base_url = "https://old.example.com/v1"\n'
            'wire_api = "chat"\n'
        ),
        auth=json.dumps(
            {
                "OPENAI_API_KEY": "sk-old-openai-key",
                "tokens": {"id_token": "oauth-token"},
            }
        ),
    )
    preview = preview_json(harness, profile.id, tool_id="codex-cli")

    response = post_apply(harness, apply_payload(preview))

    assert response.status_code == 200, response.text
    body = response.json()
    assert {item["path"] for item in body["files"]} == {
        str(config.resolve()),
        str(auth.resolve()),
    }
    rendered_config = config.read_text(encoding="utf-8")
    assert 'model = "gpt-5-codex"' in rendered_config
    assert 'model_provider = "openai"' in rendered_config
    assert 'base_url = "https://relay.example.com/v1"' in rendered_config
    rendered_auth = json.loads(auth.read_text(encoding="utf-8"))
    assert rendered_auth["OPENAI_API_KEY"] == SECRET
    assert rendered_auth["tokens"] == {"id_token": "oauth-token"}
    binding = harness.profiles.get_binding("codex-cli")
    assert binding is not None and binding.active is True


def test_apply_with_stale_digest_writes_nothing(tmp_path: Path) -> None:
    harness = make_switch_harness(tmp_path)
    profile = add_profile(harness)
    settings = write_claude_settings(harness, claude_content())
    original = settings.read_bytes()
    preview = preview_json(harness, profile.id)
    update_profile(
        harness,
        profile,
        name="改过的档案",
        updated_at=NOW + timedelta(seconds=5),
    )

    response = post_apply(harness, apply_payload(preview))

    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "SWITCH_PREVIEW_STALE"
    assert body["details"]["stale_paths"]
    assert settings.read_bytes() == original
    assert not (tmp_path / "snapshots").exists()
    assert not (tmp_path / "db" / "app.sqlite3").exists()


def test_apply_after_profile_deleted_is_stale(tmp_path: Path) -> None:
    harness = make_switch_harness(tmp_path)
    profile = add_profile(harness)
    settings = write_claude_settings(harness, claude_content())
    original = settings.read_bytes()
    preview = preview_json(harness, profile.id)
    harness.profiles.mutate(lambda store: setattr(store, "profiles", []))

    response = post_apply(harness, apply_payload(preview))

    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "SWITCH_PREVIEW_STALE"
    assert body["details"]["stale_paths"] == [
        observation["path"] for observation in preview["observations"]
    ]
    assert settings.read_bytes() == original


def test_apply_after_model_removed_from_profile_is_stale(tmp_path: Path) -> None:
    harness = make_switch_harness(tmp_path)
    profile = add_profile(harness)
    settings = write_claude_settings(harness, claude_content())
    original = settings.read_bytes()
    preview = preview_json(harness, profile.id)
    update_profile(
        harness,
        profile,
        models=[],
        updated_at=NOW + timedelta(seconds=2),
    )

    response = post_apply(harness, apply_payload(preview))

    assert response.status_code == 409
    assert response.json()["code"] == "SWITCH_PREVIEW_STALE"
    assert settings.read_bytes() == original


def test_apply_external_content_change_is_conflict(tmp_path: Path) -> None:
    harness = make_switch_harness(tmp_path)
    profile = add_profile(harness)
    settings = write_claude_settings(harness, claude_content())
    preview = preview_json(harness, profile.id)
    external = b'{"env": {"ANTHROPIC_BASE_URL": "https://external.example.com"}}'
    settings.write_bytes(external)

    response = post_apply(harness, apply_payload(preview))

    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "WRITE_CONFLICT"
    conflicts = body["details"]["conflicts"]
    assert len(conflicts) == 1
    assert conflicts[0]["reason"] == "CONTENT_CHANGED"
    assert conflicts[0]["expected"]["sha256"] == preview["observations"][0]["sha256"]
    assert conflicts[0]["actual"]["sha256"] == hashlib.sha256(external).hexdigest()
    assert settings.read_bytes() == external
    assert not (tmp_path / "snapshots").exists()
    entries = harness.audit.list_recent()
    assert entries[0].result == "conflict"


def test_apply_external_delete_is_missing_conflict(tmp_path: Path) -> None:
    harness = make_switch_harness(tmp_path)
    profile = add_profile(harness)
    settings = write_claude_settings(harness, claude_content())
    preview = preview_json(harness, profile.id)
    settings.unlink()

    response = post_apply(harness, apply_payload(preview))

    assert response.status_code == 409
    conflicts = response.json()["details"]["conflicts"]
    assert conflicts[0]["reason"] == "MISSING"
    assert not settings.exists()


def test_apply_external_create_is_created_conflict(tmp_path: Path) -> None:
    harness = make_switch_harness(tmp_path)
    profile = add_profile(harness)
    preview = preview_json(harness, profile.id)
    settings = write_claude_settings(harness, claude_content())
    external = settings.read_bytes()

    response = post_apply(harness, apply_payload(preview))

    assert response.status_code == 409
    conflicts = response.json()["details"]["conflicts"]
    assert conflicts[0]["reason"] == "CREATED"
    assert settings.read_bytes() == external


def test_apply_mtime_only_change_is_not_a_conflict(tmp_path: Path) -> None:
    harness = make_switch_harness(tmp_path)
    profile = add_profile(harness)
    settings = write_claude_settings(harness, claude_content())
    preview = preview_json(harness, profile.id)
    os.utime(settings, (1_700_000_000, 1_700_000_000))

    response = post_apply(harness, apply_payload(preview))

    assert response.status_code == 200, response.text


def test_apply_blockers_return_switch_blocked_without_writing(tmp_path: Path) -> None:
    harness = make_switch_harness(tmp_path)
    profile = add_profile(harness)
    preview = preview_json(harness, profile.id, tool_id="codex-cli")

    response = post_apply(harness, apply_payload(preview))

    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "SWITCH_BLOCKED"
    assert "details" not in body
    assert not (harness.codex_dir / "config.toml").exists()
    assert not (harness.codex_dir / "auth.json").exists()
    assert not (tmp_path / "snapshots").exists()


def test_apply_binding_failure_rolls_back_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = make_switch_harness(tmp_path)
    profile = add_profile(harness)
    settings = write_claude_settings(harness, claude_content())
    original = settings.read_bytes()
    preview = preview_json(harness, profile.id)

    def fail_mutate(_change: object) -> object:
        raise AppError("PROFILE_STORE_WRITE_FAILED", "档案库写入失败", 500)

    monkeypatch.setattr(harness.profiles, "mutate", fail_mutate)

    response = post_apply(harness, apply_payload(preview))

    assert response.status_code == 500
    assert response.json()["code"] == "BINDING_WRITE_FAILED"
    assert settings.read_bytes() == original
    assert harness.profiles.get_binding("claude-code") is None
    entries = harness.audit.list_recent()
    assert entries[0].result == "failed"
    assert entries[0].snapshot_id is not None


def test_apply_binding_failure_and_rollback_failure_is_reported(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = make_switch_harness(tmp_path)
    profile = add_profile(harness)
    settings = write_claude_settings(harness, claude_content())
    preview = preview_json(harness, profile.id)

    def fail_mutate(_change: object) -> object:
        raise AppError("PROFILE_STORE_WRITE_FAILED", "档案库写入失败", 500)

    def fail_rollback(_snapshot_id: str) -> object:
        raise AppError("ROLLBACK_FAILED", "无法还原目标文件", 500)

    monkeypatch.setattr(harness.profiles, "mutate", fail_mutate)
    monkeypatch.setattr(harness.service._snapshots, "rollback", fail_rollback)

    response = post_apply(harness, apply_payload(preview))

    assert response.status_code == 500
    body = response.json()
    assert body["code"] == "APPLY_ROLLBACK_FAILED"
    assert "快照" in body["message"]
    assert "无法还原" in body["message"]
    assert settings.read_bytes() != claude_content()


def test_profile_edit_during_write_rolls_back_and_is_stale(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = make_switch_harness(tmp_path)
    profile = add_profile(harness)
    settings = write_claude_settings(harness, claude_content())
    original = settings.read_bytes()
    preview = preview_json(harness, profile.id)
    engine = harness.service._write_engine
    original_apply = engine.apply

    def apply_then_edit(plan: object) -> object:
        result = original_apply(plan)
        update_profile(
            harness,
            profile,
            name="写入期间被改",
            updated_at=NOW + timedelta(seconds=3),
        )
        return result

    monkeypatch.setattr(engine, "apply", apply_then_edit)

    response = post_apply(harness, apply_payload(preview))

    assert response.status_code == 409
    assert response.json()["code"] == "SWITCH_PREVIEW_STALE"
    assert settings.read_bytes() == original
    assert harness.profiles.get_binding("claude-code") is None


def test_audit_failure_restores_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = make_switch_harness(tmp_path)
    profile = add_profile(harness)
    settings = write_claude_settings(harness, claude_content())
    original = settings.read_bytes()
    preview = preview_json(harness, profile.id)

    def fail_record(**_kwargs: object) -> object:
        raise AppError("AUDIT_WRITE_FAILED", "审计记录写入失败", 500)

    monkeypatch.setattr(harness.audit, "record", fail_record)

    response = post_apply(harness, apply_payload(preview))

    assert response.status_code == 500
    assert response.json()["code"] == "AUDIT_WRITE_FAILED"
    assert settings.read_bytes() == original


def test_write_lock_timeout_returns_503_and_writes_nothing(tmp_path: Path) -> None:
    harness = make_switch_harness(tmp_path, lock_timeout=0.05)
    profile = add_profile(harness)
    settings = write_claude_settings(harness, claude_content())
    original = settings.read_bytes()
    preview = preview_json(harness, profile.id)

    with FileLock(tmp_path / "locks" / "write.lock", timeout=1.0):
        response = post_apply(harness, apply_payload(preview))

    assert response.status_code == 503
    assert response.json()["code"] == "WRITE_LOCK_TIMEOUT"
    assert settings.read_bytes() == original


def test_concurrent_apply_has_exactly_one_success(tmp_path: Path) -> None:
    harness = make_switch_harness(tmp_path)
    profile = add_profile(harness)
    settings = write_claude_settings(harness, claude_content())
    preview = preview_json(harness, profile.id)
    payload = apply_payload(preview)
    barrier = threading.Barrier(2)

    def apply_once() -> object:
        barrier.wait()
        return harness.client.post("/api/switch/apply", json=payload)

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _index: apply_once(), range(2)))

    statuses = sorted(response.status_code for response in responses)
    assert statuses == [200, 409]
    failed = next(response for response in responses if response.status_code == 409)
    assert failed.json()["code"] == "WRITE_CONFLICT"
    assert json.loads(settings.read_bytes())["env"]["ANTHROPIC_API_KEY"] == SECRET
    binding = harness.profiles.get_binding("claude-code")
    assert binding is not None and binding.active is True


def test_secret_never_reaches_logs(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    harness = make_switch_harness(tmp_path)
    profile = add_profile(harness)
    write_claude_settings(harness, claude_content())
    preview = preview_json(harness, profile.id)

    response = post_apply(harness, apply_payload(preview))

    assert response.status_code == 200
    assert SECRET not in caplog.text
