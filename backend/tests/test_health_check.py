"""档案体检 API、协议请求与副作用边界测试。"""

import json
import threading
import urllib.error
from collections.abc import Mapping
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from profile_fixtures import create_profile, make_profile_harness

from app.repositories.secrets import KEYRING_SERVICE_NAME
from app.services.health_check import HealthCheckHttpResponse

SECRET = "sk-ant-health-fixture-1234567890"


class FakeResponse:
    def __init__(self, status: int, body: bytes = b'{"ok":true}') -> None:
        self.status = status
        self.body = body


class FakeTransport:
    def __init__(
        self,
        response: HealthCheckHttpResponse | None = None,
        error: Exception | None = None,
    ) -> None:
        self.response = response or FakeResponse(200)
        self.error = error
        self.calls: list[tuple[str, Mapping[str, str], bytes, int]] = []

    def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        body: bytes,
        timeout: int,
    ) -> HealthCheckHttpResponse:
        self.calls.append((url, headers, body, timeout))
        if self.error is not None:
            raise self.error
        return self.response


def test_health_check_without_models_returns_not_attempted_result(tmp_path: Path) -> None:
    harness = make_profile_harness(tmp_path)
    profile = create_profile(harness)

    response = harness.client.post(
        f"/api/profiles/{profile['id']}/health-check",
        json={},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["profile_id"] == profile["id"]
    assert result["model"] is None
    assert result["status"] == "MODEL_REQUIRED"
    assert result["attempted"] is False
    assert result["duration_ms"] is None
    assert "模型" in result["message"]


def test_anthropic_probe_uses_first_model_and_does_not_expose_secret(
    tmp_path: Path,
) -> None:
    transport = FakeTransport()
    harness = make_profile_harness(tmp_path, health_transport=transport)
    profile = create_profile(
        harness,
        secret=SECRET,
        models=[{"id": "claude-sonnet-4"}, {"id": "claude-opus-4"}],
    )
    before = (tmp_path / "profiles.json").read_bytes()

    response = harness.client.post(
        f"/api/profiles/{profile['id']}/health-check",
        json={},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["model"] == "claude-sonnet-4"
    assert result["status"] == "CONNECTED"
    assert result["attempted"] is True
    assert isinstance(result["duration_ms"], int)
    assert result["duration_ms"] >= 0
    assert "Z" in result["checked_at"] or "+" in result["checked_at"]
    assert len(transport.calls) == 1
    url, headers, body, timeout = transport.calls[0]
    assert url == "https://api.anthropic.com/v1/messages"
    assert headers["x-api-key"] == SECRET
    assert headers["anthropic-version"] == "2023-06-01"
    assert timeout > 0
    assert SECRET not in body.decode()
    assert json.loads(body) == {
        "model": "claude-sonnet-4",
        "max_tokens": 1,
        "messages": [{"role": "user", "content": "Health check"}],
    }
    assert (tmp_path / "profiles.json").read_bytes() == before
    assert harness.keyring.values[(KEYRING_SERVICE_NAME, str(profile["id"]))] == SECRET
    assert SECRET not in response.text


def test_openai_probe_can_run_without_auth_and_validates_model_selection(
    tmp_path: Path,
) -> None:
    transport = FakeTransport()
    harness = make_profile_harness(tmp_path, health_transport=transport)
    profile = create_profile(
        harness,
        protocol="openai",
        base_url="https://provider.example",
        models=[{"id": "gpt-5"}],
    )

    response = harness.client.post(
        f"/api/profiles/{profile['id']}/health-check",
        json={"model": "gpt-5"},
    )

    assert response.status_code == 200
    url, headers, body, _ = transport.calls[0]
    assert url == "https://provider.example/v1/chat/completions"
    assert "Authorization" not in headers
    assert json.loads(body)["stream"] is False

    invalid_model = harness.client.post(
        f"/api/profiles/{profile['id']}/health-check",
        json={"model": "not-listed"},
    )
    assert invalid_model.status_code == 422
    assert invalid_model.json()["code"] == "VALIDATION_ERROR"
    assert len(transport.calls) == 1


@pytest.mark.parametrize(
    ("response", "error", "expected_status"),
    [
        (None, TimeoutError("secret " + SECRET), "TIMEOUT"),
        (None, urllib.error.URLError(TimeoutError("secret " + SECRET)), "TIMEOUT"),
        (None, OSError("secret " + SECRET), "INVALID_ADDRESS"),
        (FakeResponse(401, b'{"error":{"message":"secret in body"}}'), None, "INVALID_CREDENTIALS"),
        (FakeResponse(403), None, "INVALID_CREDENTIALS"),
        (
            FakeResponse(404, b'{"error":{"code":"model_not_found"}}'),
            None,
            "MODEL_NOT_FOUND",
        ),
        (
            FakeResponse(404, b'{"error":{"message":"model: claude-sonnet-4 not found"}}'),
            None,
            "MODEL_NOT_FOUND",
        ),
        (FakeResponse(404, b'{"error":{"code":"route_not_found"}}'), None, "INVALID_ADDRESS"),
        (FakeResponse(429), None, "RATE_LIMITED"),
        (FakeResponse(302, b""), None, "INVALID_ADDRESS"),
        (FakeResponse(503), None, "UNKNOWN"),
        (FakeResponse(200, b"<html>not json</html>"), None, "UNKNOWN"),
    ],
)
def test_health_check_classifies_failures_without_echoing_upstream_data(
    tmp_path: Path,
    response: FakeResponse | None,
    error: Exception | None,
    expected_status: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    transport = FakeTransport(response, error)
    harness = make_profile_harness(tmp_path, health_transport=transport)
    profile = create_profile(
        harness,
        secret=SECRET,
        models=[{"id": "claude-sonnet-4"}],
    )

    result = harness.client.post(
        f"/api/profiles/{profile['id']}/health-check",
        json={},
    )

    assert result.status_code == 200
    assert result.json()["status"] == expected_status
    assert SECRET not in result.text
    assert SECRET not in caplog.text
    assert len(transport.calls) == 1
    assert transport.calls[0][3] > 0


def test_missing_or_unreadable_secret_does_not_start_network_request(tmp_path: Path) -> None:
    transport = FakeTransport()
    harness = make_profile_harness(tmp_path, health_transport=transport)
    profile = create_profile(
        harness,
        secret=SECRET,
        models=[{"id": "claude-sonnet-4"}],
    )
    secret_key = (KEYRING_SERVICE_NAME, str(profile["id"]))
    del harness.keyring.values[secret_key]

    missing = harness.client.post(
        f"/api/profiles/{profile['id']}/health-check",
        json={},
    )
    assert missing.json()["status"] == "SECRET_MISSING"
    assert missing.json()["attempted"] is False
    assert missing.json()["duration_ms"] is None

    harness.keyring.values[secret_key] = SECRET
    harness.keyring.fail_get = True
    unreadable = harness.client.post(
        f"/api/profiles/{profile['id']}/health-check",
        json={},
    )
    assert unreadable.json()["status"] == "SECRET_STORE_ERROR"
    assert unreadable.json()["attempted"] is False
    assert unreadable.json()["duration_ms"] is None
    assert transport.calls == []


def test_unknown_profile_and_repeated_checks_have_expected_side_effects(
    tmp_path: Path,
) -> None:
    transport = FakeTransport()
    harness = make_profile_harness(tmp_path, health_transport=transport)
    profile = create_profile(
        harness,
        models=[{"id": "claude-sonnet-4"}],
    )
    profiles_before = (tmp_path / "profiles.json").read_bytes()
    secrets_before = dict(harness.keyring.values)

    missing = harness.client.post(
        "/api/profiles/00000000-0000-4000-8000-000000000000/health-check",
        json={},
    )
    first = harness.client.post(f"/api/profiles/{profile['id']}/health-check", json={})
    second = harness.client.post(f"/api/profiles/{profile['id']}/health-check", json={})

    assert missing.status_code == 404
    assert missing.json()["code"] == "PROFILE_NOT_FOUND"
    assert first.json()["status"] == second.json()["status"] == "CONNECTED"
    assert len(transport.calls) == 2
    assert (tmp_path / "profiles.json").read_bytes() == profiles_before
    assert harness.keyring.values == secrets_before
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "profiles.json",
        "profiles.lock",
    ]


def test_standard_transport_does_not_follow_redirects() -> None:
    requests: list[str] = []

    class RedirectHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            requests.append(self.path)
            self.send_response(302)
            self.send_header("Location", "/elsewhere")
            self.end_headers()

        def log_message(self, _format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), RedirectHandler)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        from app.services.health_check import UrllibHealthCheckTransport

        response = UrllibHealthCheckTransport().post(
            f"http://127.0.0.1:{server.server_port}/probe",
            headers={},
            body=b"{}",
            timeout=2,
        )
    finally:
        server.shutdown()
        thread.join(timeout=3)
        server.server_close()

    assert response.status == 302
    assert requests == ["/probe"]
