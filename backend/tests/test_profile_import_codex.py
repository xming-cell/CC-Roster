"""直接读取 Codex config.toml: provider 候选、wire_api 与密钥边界。"""

from pathlib import Path

from profile_fixtures import make_profile_harness

SECRET = "sk-" + "c" * 32


def write_codex_config(tmp_path: Path, content: str) -> Path:
    config_dir = tmp_path / "codex-home"
    config_dir.mkdir()
    (config_dir / "config.toml").write_text(content, encoding="utf-8")
    return config_dir


def preview(harness):
    return harness.client.post("/api/profiles/import/codex/preview")


def do_import(harness, policy: str = "skip"):
    return harness.client.post("/api/profiles/import/codex", json={"policy": policy})


def test_codex_config_maps_providers_and_keeps_token_out_of_preview(
    tmp_path: Path, monkeypatch
) -> None:
    config_dir = write_codex_config(
        tmp_path,
        f'''model = "gpt-5.1-codex"

[model_providers.custom]
name = "自建兼容"
base_url = "https://api.example.com/v1"
wire_api = "responses"
experimental_bearer_token = "{SECRET}"
''',
    )
    monkeypatch.setenv("CODEX_HOME", str(config_dir))
    harness = make_profile_harness(tmp_path / "app")

    response = preview(harness)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source"] == "codex_config"
    assert body["source_path"].endswith("config.toml")
    assert body["items"][0]["status"] == "new"
    assert body["items"][0]["name"] == "自建兼容"
    assert body["items"][0]["has_secret"] is True
    assert SECRET not in response.text

    result = do_import(harness)
    assert result.status_code == 201, result.text
    profile = harness.client.get("/api/profiles/" + result.json()["profile_ids"][0]).json()
    assert [model["id"] for model in profile["models"]] == ["gpt-5.1-codex"]
    assert profile["has_secret"] is True
    assert SECRET not in harness.client.get("/api/audit").text


def test_codex_env_key_is_not_read_and_is_reported_as_missing_secret(
    tmp_path: Path, monkeypatch
) -> None:
    config_dir = write_codex_config(
        tmp_path,
        """[model_providers.env]
base_url = "https://api.example.com/v1"
wire_api = "chat"
env_key = "CUSTOM_API_KEY"
""",
    )
    monkeypatch.setenv("CODEX_HOME", str(config_dir))
    harness = make_profile_harness(tmp_path / "app")

    response = preview(harness)
    assert response.status_code == 200, response.text
    entry = response.json()["items"][0]
    assert entry["status"] == "new"
    assert entry["has_secret"] is False
    assert any("env_key" in note for note in entry["notes"])


def test_codex_invalid_wire_api_is_invalid_and_blocks_batch(tmp_path: Path, monkeypatch) -> None:
    config_dir = write_codex_config(
        tmp_path,
        """[model_providers.good]
base_url = "https://api.example.com/v1"
wire_api = "responses"

[model_providers.bad]
base_url = "https://bad.example.com/v1"
wire_api = "grpc"
""",
    )
    monkeypatch.setenv("CODEX_HOME", str(config_dir))
    harness = make_profile_harness(tmp_path / "app")

    response = preview(harness)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["totals"] == {"new": 1, "duplicate": 0, "invalid": 1}
    invalid = next(entry for entry in body["items"] if entry["status"] == "invalid")
    assert any("wire_api" in reason for reason in invalid["reasons"])

    result = do_import(harness)
    assert result.status_code == 422
    assert harness.client.get("/api/profiles").json()["profiles"] == []


def test_codex_duplicate_provider_names_get_id_suffix(tmp_path: Path, monkeypatch) -> None:
    config_dir = write_codex_config(
        tmp_path,
        """[model_providers.alpha]
name = "同名"
base_url = "https://alpha.example.com/v1"
wire_api = "responses"

[model_providers.beta]
name = "同名"
base_url = "https://beta.example.com/v1"
wire_api = "chat"
""",
    )
    monkeypatch.setenv("CODEX_HOME", str(config_dir))
    harness = make_profile_harness(tmp_path / "app")

    names = [entry["name"] for entry in preview(harness).json()["items"]]
    assert names == ["同名", "同名 (beta)"]


def test_codex_missing_bad_and_empty_config_have_readable_errors(
    tmp_path: Path, monkeypatch
) -> None:
    harness = make_profile_harness(tmp_path / "app")
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "missing"))
    missing = preview(harness)
    assert missing.status_code == 422
    assert missing.json()["code"] == "CODEX_CONFIG_NOT_FOUND"

    config_dir = write_codex_config(tmp_path, "[model_providers.bad\n")
    monkeypatch.setenv("CODEX_HOME", str(config_dir))
    bad = preview(harness)
    assert bad.status_code == 422
    assert bad.json()["code"] == "IMPORT_INVALID_TOML"

    empty_dir = tmp_path / "empty-codex"
    empty_dir.mkdir()
    (empty_dir / "config.toml").write_text('model = "gpt-5"\n', encoding="utf-8")
    monkeypatch.setenv("CODEX_HOME", str(empty_dir))
    empty = preview(harness)
    assert empty.status_code == 422
    assert empty.json()["code"] == "CODEX_NO_PROVIDERS"
