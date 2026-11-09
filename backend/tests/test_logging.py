import logging
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.logging import _HANDLER_MARKER, LOG_FILE_NAME, configure_logging
from app.main import create_app

SECRET = "sk-live-abcdefghijklmnop"
REDACTED = "sk-l****mnop"


@pytest.fixture()
def clean_logging() -> Iterator[None]:
    root = logging.getLogger()
    saved_level = root.level
    yield
    for handler in list(root.handlers):
        if getattr(handler, _HANDLER_MARKER, False):
            root.removeHandler(handler)
            handler.close()
    root.setLevel(saved_level)


def test_configure_logging_writes_stdout_and_file_without_secret(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    clean_logging: None,
) -> None:
    configure_logging(tmp_path)

    logging.getLogger("app.test").info("token=%s", SECRET)

    captured = capsys.readouterr()
    assert SECRET not in captured.out
    assert REDACTED in captured.out
    assert "INFO" in captured.out
    assert "app.test" in captured.out

    log_text = (tmp_path / "logs" / LOG_FILE_NAME).read_text(encoding="utf-8")
    assert SECRET not in log_text
    assert REDACTED in log_text
    assert "token=" in log_text


def test_configure_logging_is_idempotent(tmp_path: Path, clean_logging: None) -> None:
    configure_logging(tmp_path)
    configure_logging(tmp_path)

    logging.getLogger("app.test").info("configured once")

    log_text = (tmp_path / "logs" / LOG_FILE_NAME).read_text(encoding="utf-8")
    assert log_text.count("configured once") == 1


def test_unhandled_error_log_and_response_hide_secret(
    tmp_path: Path,
    clean_logging: None,
) -> None:
    configure_logging(tmp_path)
    app = create_app()

    @app.get("/test/boom")
    async def boom() -> None:
        raise RuntimeError(f"boom {SECRET}")

    client = TestClient(app, raise_server_exceptions=False)

    resp = client.get("/test/boom")

    assert resp.status_code == 500
    assert SECRET not in resp.text
    log_text = (tmp_path / "logs" / LOG_FILE_NAME).read_text(encoding="utf-8")
    assert SECRET not in log_text
    assert REDACTED in log_text
    assert "RuntimeError" in log_text
