import pytest

from app.core.config import Settings


def test_settings_defaults_match_local_security_baseline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in ("APP_NAME", "HOST", "CORS_ORIGINS", "MAX_REQUEST_BODY_BYTES"):
        monkeypatch.delenv(name, raising=False)

    config = Settings(_env_file=None)

    assert config.app_name == "CC-Roster"
    assert config.host == "127.0.0.1"
    assert config.cors_origins == ["http://localhost:5173", "http://127.0.0.1:5173"]
    assert config.max_request_body_bytes == 1024 * 1024
