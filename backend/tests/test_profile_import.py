"""本地导入供应商: 版本、逐条校验、去重策略与全或无。"""

import json
from pathlib import Path

from profile_fixtures import create_profile, make_profile_harness

SECRET = "sk-" + "i" * 32


def content(items: list[object], version: object = 1) -> str:
    return json.dumps({"schema_version": version, "profiles": items}, ensure_ascii=False)


def item(
    name: str,
    *,
    protocol: str = "anthropic",
    base_url: str = "https://api.anthropic.com",
    models: list[object] | None = None,
    secret: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": name,
        "protocol": protocol,
        "base_url": base_url,
        "models": models if models is not None else [],
    }
    if secret is not None:
        payload["secret"] = secret
    return payload


def preview(harness, body: dict[str, object]):
    return harness.client.post("/api/profiles/import/preview", json=body)


def do_import(harness, body: dict[str, object]):
    return harness.client.post("/api/profiles/import", json=body)


def test_preview_marks_new_items_without_writing(tmp_path: Path) -> None:
    harness = make_profile_harness(tmp_path)

    response = preview(harness, {"content": content([item("甲"), item("乙")])})

    assert response.status_code == 200, response.text
    body = response.json()
    assert [entry["status"] for entry in body["items"]] == ["new", "new"]
    assert body["totals"] == {"new": 2, "duplicate": 0, "invalid": 0}
    assert body["can_import"] is True
    assert harness.client.get("/api/profiles").json()["profiles"] == []


def test_duplicate_of_existing_profile_is_skipped(tmp_path: Path) -> None:
    harness = make_profile_harness(tmp_path)
    created = create_profile(harness, name="已存在")

    body = {"content": content([item("已存在")])}
    preview_response = preview(harness, body)
    assert preview_response.status_code == 200
    entry = preview_response.json()["items"][0]
    assert entry["status"] == "duplicate"
    assert entry["conflict_profile_id"] == created["id"]

    result = do_import(harness, body)
    assert result.status_code == 201, result.text
    assert result.json() == {"imported": 0, "overwritten": 0, "skipped": 1, "profile_ids": []}


def test_overwrite_policy_updates_models_and_keeps_secret(tmp_path: Path) -> None:
    harness = make_profile_harness(tmp_path)
    created = create_profile(harness, name="覆盖我", secret=SECRET)

    body = {
        "content": content([item("覆盖我", models=[{"id": "model-x", "display_name": None}])]),
        "policy": "overwrite",
    }
    result = do_import(harness, body)

    assert result.status_code == 201, result.text
    assert result.json()["overwritten"] == 1
    profile = harness.client.get(f"/api/profiles/{created['id']}").json()
    assert [model["id"] for model in profile["models"]] == ["model-x"]
    assert profile["has_secret"] is True


def test_invalid_item_blocks_whole_batch(tmp_path: Path) -> None:
    harness = make_profile_harness(tmp_path)

    body = {"content": content([item("合法的"), item("坏协议", protocol="grpc")])}
    preview_response = preview(harness, body)
    assert preview_response.status_code == 200
    assert preview_response.json()["can_import"] is False
    assert preview_response.json()["totals"]["invalid"] == 1

    result = do_import(harness, body)
    assert result.status_code == 422
    assert result.json()["code"] == "IMPORT_HAS_INVALID_ITEMS"
    assert harness.client.get("/api/profiles").json()["profiles"] == []


def test_in_file_duplicate_is_reported_and_last_wins_on_overwrite(tmp_path: Path) -> None:
    harness = make_profile_harness(tmp_path)
    body = {
        "content": content(
            [
                item("重复", models=[{"id": "first", "display_name": None}]),
                item("重复", models=[{"id": "last", "display_name": None}]),
            ]
        ),
        "policy": "overwrite",
    }

    preview_response = preview(harness, body)
    assert [entry["status"] for entry in preview_response.json()["items"]] == ["new", "duplicate"]

    result = do_import(harness, body)
    assert result.status_code == 201, result.text
    assert result.json()["imported"] == 1
    listing = harness.client.get("/api/profiles").json()["profiles"]
    assert len(listing) == 1
    assert [model["id"] for model in listing[0]["models"]] == ["last"]


def test_name_conflict_with_different_address_is_invalid(tmp_path: Path) -> None:
    harness = make_profile_harness(tmp_path)
    create_profile(harness, name="同名", base_url="https://a.example.com")

    body = {"content": content([item("同名", base_url="https://b.example.com")])}
    preview_response = preview(harness, body)

    entry = preview_response.json()["items"][0]
    assert entry["status"] == "invalid"
    assert "名称已被另一个供应商占用" in entry["reasons"][0]


def test_bad_json_and_unknown_version_are_rejected(tmp_path: Path) -> None:
    harness = make_profile_harness(tmp_path)

    bad_json = preview(harness, {"content": "{not json"})
    assert bad_json.status_code == 422
    assert bad_json.json()["code"] == "IMPORT_INVALID_JSON"

    unknown = preview(harness, {"content": content([item("甲")], version=99)})
    assert unknown.status_code == 422
    assert unknown.json()["code"] == "IMPORT_UNSUPPORTED_VERSION"


def test_import_writes_audit_and_never_leaks_secret(tmp_path: Path) -> None:
    harness = make_profile_harness(tmp_path)

    result = do_import(harness, {"content": content([item("带密钥", secret=SECRET)])})
    assert result.status_code == 201, result.text

    created_id = result.json()["profile_ids"][0]
    profile = harness.client.get(f"/api/profiles/{created_id}").json()
    assert profile["has_secret"] is True
    assert SECRET not in json.dumps(profile, ensure_ascii=False)

    audit = harness.client.get("/api/audit").json()["entries"]
    assert audit[0]["action"] == "profile_import"
    assert SECRET not in json.dumps(audit, ensure_ascii=False)
