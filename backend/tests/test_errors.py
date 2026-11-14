from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.errors import (
    AppError,
    ErrorDetails,
    FileConflict,
    WriteConflict,
)
from app.main import create_app
from app.schemas.snapshot import FileObservation


class Echo(BaseModel):
    limit: int


def build_test_app() -> FastAPI:
    app = create_app()

    @app.get("/test/business-error")
    async def business_error() -> Echo:
        raise AppError("PROFILE_NOT_FOUND", "档案不存在")

    @app.get("/test/conflict-error")
    async def conflict_error() -> Echo:
        raise AppError("PROFILE_CONFLICT", "档案已被占用", status_code=409)

    @app.get("/test/validation")
    async def validation(limit: int) -> Echo:
        return Echo(limit=limit)

    @app.get("/test/unknown-error")
    async def unknown_error() -> Echo:
        raise RuntimeError("boom sk-live-abcdefghijklmnop /home/alice/.config/secret")

    @app.get("/test/secret-error")
    async def secret_error() -> Echo:
        raise AppError("AUTH_FAILED", "密钥 sk-live-abcdefghijklmnop 无效")

    @app.get("/test/details-conflict")
    async def details_conflict() -> Echo:
        missing = str(Path.cwd() / "missing.json")
        created = str(Path.cwd() / "created.json")
        changed = str(Path.cwd() / "changed.json")
        raise WriteConflict(
            [
                FileConflict(
                    path=missing,
                    reason="MISSING",
                    expected=FileObservation(
                        path=missing,
                        exists=True,
                        sha256="a" * 64,
                        size=3,
                        mtime_ns=1,
                    ),
                    actual=FileObservation(path=missing, exists=False),
                ),
                FileConflict(
                    path=created,
                    reason="CREATED",
                    expected=FileObservation(path=created, exists=False),
                    actual=FileObservation(
                        path=created,
                        exists=True,
                        sha256="b" * 64,
                        size=4,
                        mtime_ns=2,
                    ),
                ),
                FileConflict(
                    path=changed,
                    reason="CONTENT_CHANGED",
                    expected=FileObservation(
                        path=changed,
                        exists=True,
                        sha256="c" * 64,
                        size=5,
                        mtime_ns=3,
                    ),
                    actual=FileObservation(
                        path=changed,
                        exists=True,
                        sha256="d" * 64,
                        size=6,
                        mtime_ns=4,
                    ),
                ),
            ]
        )

    @app.get("/test/details-stale")
    async def details_stale() -> Echo:
        raise AppError(
            "SWITCH_PREVIEW_STALE",
            "预览已过期",
            409,
            details=ErrorDetails(stale_paths=[str(Path.cwd() / "settings.json")]),
        )

    return app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(build_test_app(), raise_server_exceptions=False)


def test_business_error_returns_code_and_message(client: TestClient) -> None:
    resp = client.get("/test/business-error")

    assert resp.status_code == 400
    assert resp.json() == {"code": "PROFILE_NOT_FOUND", "message": "档案不存在"}


def test_business_error_keeps_custom_status_code(client: TestClient) -> None:
    resp = client.get("/test/conflict-error")

    assert resp.status_code == 409
    assert resp.json() == {"code": "PROFILE_CONFLICT", "message": "档案已被占用"}


def test_validation_error_uses_stable_code_without_detail(client: TestClient) -> None:
    resp = client.get("/test/validation", params={"limit": "not-a-number"})

    assert resp.status_code == 422
    body = resp.json()
    assert set(body) == {"code", "message"}
    assert body["code"] == "VALIDATION_ERROR"
    assert body["message"]


def test_unknown_route_returns_not_found_without_detail(client: TestClient) -> None:
    resp = client.get("/api/does-not-exist")

    assert resp.status_code == 404
    assert resp.json() == {"code": "NOT_FOUND", "message": "请求的资源不存在"}


def test_method_not_allowed_uses_stable_code(client: TestClient) -> None:
    resp = client.post("/api/health")

    assert resp.status_code == 405
    assert resp.json() == {"code": "METHOD_NOT_ALLOWED", "message": "请求方法不被允许"}
    assert resp.headers["allow"] == "GET"


def test_app_error_message_is_redacted_in_response(client: TestClient) -> None:
    resp = client.get("/test/secret-error")

    assert resp.status_code == 400
    assert "sk-live-abcdefghijklmnop" not in resp.text
    body = resp.json()
    assert body["code"] == "AUTH_FAILED"
    assert "sk-l****mnop" in body["message"]


def test_conflict_error_serializes_all_conflict_reasons(client: TestClient) -> None:
    resp = client.get("/test/details-conflict")

    assert resp.status_code == 409
    body = resp.json()
    assert set(body) == {"code", "message", "details"}
    assert body["code"] == "WRITE_CONFLICT"
    assert set(body["details"]) == {"conflicts"}
    conflicts = body["details"]["conflicts"]
    assert [item["reason"] for item in conflicts] == [
        "MISSING",
        "CREATED",
        "CONTENT_CHANGED",
    ]
    observation_keys = {"path", "exists", "sha256", "size", "mtime_ns"}
    for item in conflicts:
        assert set(item) == {"path", "reason", "expected", "actual"}
        for observation in (item["expected"], item["actual"]):
            assert {"path", "exists", "size"} <= set(observation) <= observation_keys
    missing, created, changed = conflicts
    assert missing["expected"]["exists"] is True
    assert missing["actual"]["exists"] is False
    assert "sha256" not in missing["actual"]
    assert "mtime_ns" not in missing["actual"]
    assert missing["expected"]["sha256"] == "a" * 64
    assert created["expected"]["exists"] is False
    assert created["actual"]["exists"] is True
    assert created["actual"]["sha256"] == "b" * 64
    assert changed["expected"]["sha256"] == "c" * 64
    assert changed["actual"]["sha256"] == "d" * 64
    assert changed["expected"]["mtime_ns"] == 3
    assert changed["actual"]["mtime_ns"] == 4


def test_stale_error_details_contain_only_stale_paths(client: TestClient) -> None:
    resp = client.get("/test/details-stale")

    assert resp.status_code == 409
    body = resp.json()
    assert set(body) == {"code", "message", "details"}
    assert body["code"] == "SWITCH_PREVIEW_STALE"
    assert body["details"] == {"stale_paths": [str(Path.cwd() / "settings.json")]}


def test_unknown_exception_returns_generic_500_without_internals(client: TestClient) -> None:
    resp = client.get("/test/unknown-error")

    assert resp.status_code == 500
    assert resp.json() == {"code": "INTERNAL_ERROR", "message": "服务器内部错误"}
    assert "Traceback" not in resp.text
    assert "boom" not in resp.text
    assert "sk-live-abcdefghijklmnop" not in resp.text
    assert "/home/alice" not in resp.text
