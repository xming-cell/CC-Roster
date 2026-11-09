from collections.abc import Iterator

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.config import settings
from app.main import create_app

LIMIT = settings.max_request_body_bytes


class BodySizeResponse(BaseModel):
    size: int


def build_test_app() -> FastAPI:
    app = create_app()

    @app.post("/test/echo-size")
    async def echo_size(request: Request) -> BodySizeResponse:
        return BodySizeResponse(size=len(await request.body()))

    return app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(build_test_app())


def test_allowed_origin_gets_cors_header(client: TestClient) -> None:
    resp = client.get("/api/health", headers={"Origin": "http://localhost:5173"})

    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_preflight_from_allowed_origin_succeeds(client: TestClient) -> None:
    resp = client.options(
        "/api/health",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"


def test_foreign_origin_gets_no_cors_header(client: TestClient) -> None:
    resp = client.get("/api/health", headers={"Origin": "http://evil.example"})

    assert resp.status_code == 200
    assert "access-control-allow-origin" not in resp.headers


def test_preflight_from_foreign_origin_is_rejected(client: TestClient) -> None:
    resp = client.options(
        "/api/health",
        headers={
            "Origin": "http://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert resp.status_code == 400
    assert "access-control-allow-origin" not in resp.headers


def test_body_at_limit_is_allowed(client: TestClient) -> None:
    resp = client.post("/test/echo-size", content=b"x" * LIMIT)

    assert resp.status_code == 200
    assert resp.json() == {"size": LIMIT}


def test_body_over_limit_returns_payload_too_large(client: TestClient) -> None:
    resp = client.post("/test/echo-size", content=b"x" * (LIMIT + 1))

    assert resp.status_code == 413
    body = resp.json()
    assert set(body) == {"code", "message"}
    assert body["code"] == "PAYLOAD_TOO_LARGE"
    assert body["message"]


def test_streamed_body_over_limit_returns_payload_too_large(client: TestClient) -> None:
    def chunks() -> Iterator[bytes]:
        yield b"x" * (LIMIT // 2)
        yield b"x" * (LIMIT - LIMIT // 2 + 1)

    resp = client.post("/test/echo-size", content=chunks())

    assert resp.status_code == 413
    assert resp.json()["code"] == "PAYLOAD_TOO_LARGE"
