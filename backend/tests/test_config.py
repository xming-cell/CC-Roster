import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_defaults_match_local_security_baseline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "APP_NAME",
        "HOST",
        "CORS_ORIGINS",
        "MAX_REQUEST_BODY_BYTES",
        "CC_ROSTER_SECRET_BACKEND",
    ):
        monkeypatch.delenv(name, raising=False)

    config = Settings(_env_file=None)

    assert config.app_name == "CC-Roster"
    assert config.host == "127.0.0.1"
    assert config.cors_origins == ["http://localhost:5173", "http://127.0.0.1:5173"]
    assert config.max_request_body_bytes == 1024 * 1024
    assert config.secret_backend == "auto"


def test_settings_secret_backend_reads_prefixed_environment_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CC_ROSTER_SECRET_BACKEND", "file")

    assert Settings(_env_file=None).secret_backend == "file"


@pytest.mark.parametrize("value", ["memory", "", "KEYRING"])
def test_settings_secret_backend_rejects_unknown_value(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    monkeypatch.setenv("CC_ROSTER_SECRET_BACKEND", value)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
