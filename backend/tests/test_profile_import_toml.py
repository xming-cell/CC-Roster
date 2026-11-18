"""TOML 导入: 与 JSON 共用校验、去重和全或无。"""

from pathlib import Path

from profile_fixtures import make_profile_harness

SECRET = "sk-" + "t" * 32


def toml_doc(*profiles: str, version: int = 1) -> str:
    return "schema_version = " + str(version) + "\n\n" + "\n\n".join(profiles)


def toml_profile(
    name: str,
    *,
    protocol: str = "anthropic",
    base_url: str = "https://api.anthropic.com",
    models: str = "[]",
    secret: str | None = None,
) -> str:
    lines = [
        "[[profiles]]",
        f'name = "{name}"',
        f'protocol = "{protocol}"',
        f'base_url = "{base_url}"',
        f"models = {models}",
    ]
    if secret is not None:
        lines.append(f'secret = "{secret}"')
    return "\n".join(lines)


def preview(harness, content: str):
    return harness.client.post("/api/profiles/import/preview", json={"content": content})


def do_import(harness, content: str, policy: str = "skip"):
    return harness.client.post("/api/profiles/import", json={"content": content, "policy": policy})


def test_toml_preview_and_import_keep_secret_out_of_response(tmp_path: Path) -> None:
    harness = make_profile_harness(tmp_path)
    content = toml_doc(
        toml_profile(
            "TOML 甲",
            protocol="openai",
            base_url="https://api.example.com/v1",
            models='[{ id = "gpt-5", display_name = "GPT-5" }]',
            secret=SECRET,
        )
    )

    response = preview(harness, content)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["format"] == "toml"
    assert body["source"] == "content"
    assert body["items"][0]["status"] == "new"
    assert body["items"][0]["has_secret"] is True
    assert SECRET not in response.text

    result = do_import(harness, content)
    assert result.status_code == 201, result.text
    profile = harness.client.get("/api/profiles/" + result.json()["profile_ids"][0]).json()
    assert profile["has_secret"] is True
    assert SECRET not in harness.client.get("/api/audit").text


def test_toml_bom_crlf_comments_and_missing_secret_are_supported(tmp_path: Path) -> None:
    harness = make_profile_harness(tmp_path)
    content = (
        "\ufeff# comment\r\n"
        "schema_version = 1\r\n\r\n"
        "[[profiles]]\r\n"
        'name = "无密钥"\r\n'
        'protocol = "openai"\r\n'
        'base_url = "https://api.example.com/v1"\r\n'
        "models = []\r\n"
    )

    response = preview(harness, content)
    assert response.status_code == 200, response.text
    entry = response.json()["items"][0]
    assert entry["status"] == "new"
    assert entry["has_secret"] is False


def test_toml_bad_syntax_unknown_version_and_too_many_items(tmp_path: Path) -> None:
    harness = make_profile_harness(tmp_path)

    bad = preview(harness, "schema_version = 1\n[[profiles]\nname = ")
    assert bad.status_code == 422
    assert bad.json()["code"] == "IMPORT_INVALID_TOML"

    unknown = preview(harness, toml_doc(toml_profile("甲"), version=9))
    assert unknown.status_code == 422
    assert unknown.json()["code"] == "IMPORT_UNSUPPORTED_VERSION"

    many = toml_doc(*(toml_profile(f"供应商 {index}") for index in range(501)))
    too_many = preview(harness, many)
    assert too_many.status_code == 422
    assert too_many.json()["code"] == "IMPORT_TOO_MANY_ITEMS"


def test_toml_invalid_item_blocks_whole_batch(tmp_path: Path) -> None:
    harness = make_profile_harness(tmp_path)
    content = toml_doc(
        toml_profile("合法"),
        toml_profile("坏协议", protocol="grpc"),
    )

    preview_response = preview(harness, content)
    assert preview_response.status_code == 200
    assert preview_response.json()["totals"]["invalid"] == 1
    result = do_import(harness, content)
    assert result.status_code == 422
    assert harness.client.get("/api/profiles").json()["profiles"] == []
