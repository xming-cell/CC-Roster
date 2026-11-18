"""015 桌面壳: 生命周期、单实例、Origin 边界与静态前端。"""

import time
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.desktop.app import create_desktop_app
from app.desktop.server import DesktopServer
from app.desktop.single_instance import DesktopAlreadyRunning, SingleInstance


def test_server_starts_on_loopback_random_port_and_stops_cleanly() -> None:
    def factory(_port: int) -> FastAPI:
        app = FastAPI()

        @app.get("/api/health")
        def health() -> dict[str, str]:
            return {"status": "ok"}

        return app

    server = DesktopServer(factory)
    url = server.start()
    thread = server._thread
    assert url.startswith("http://127.0.0.1:")
    assert server.port is not None and server.port > 0
    for _ in range(50):
        try:
            response = httpx.get(f"{url}api/health", timeout=1)
            break
        except httpx.HTTPError:
            time.sleep(0.05)
    else:
        raise AssertionError("server did not answer")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    server.stop()
    assert server.running is False
    assert thread is not None and not thread.is_alive()
    server.stop()


def test_server_rejects_non_loopback_host() -> None:
    try:
        DesktopServer(lambda _port: FastAPI(), host="0.0.0.0")
    except ValueError as exc:
        assert "127.0.0.1" in str(exc)
    else:
        raise AssertionError("non-loopback host must be rejected")


def test_single_instance_blocks_second_process(tmp_path: Path) -> None:
    first = SingleInstance(tmp_path)
    first.acquire()
    second = SingleInstance(tmp_path)
    try:
        second.acquire()
    except DesktopAlreadyRunning as exc:
        assert "已经在运行" in str(exc)
    else:
        raise AssertionError("second instance must be blocked")
    finally:
        first.release()

    third = SingleInstance(tmp_path)
    third.acquire()
    third.release()


def test_cross_origin_writes_are_denied_but_reads_and_cli_pass(tmp_path: Path) -> None:
    client = TestClient(create_desktop_app(tmp_path / "missing-dist", port=9000))

    denied = client.post(
        "/api/profiles",
        json={},
        headers={"Origin": "http://evil.example"},
    )
    allowed = client.post(
        "/api/profiles",
        json={},
        headers={"Origin": "http://127.0.0.1:9000"},
    )
    no_origin = client.post("/api/profiles", json={})
    read = client.get("/api/health", headers={"Origin": "http://evil.example"})

    assert denied.status_code == 403
    assert denied.json()["code"] == "ORIGIN_DENIED"
    assert allowed.status_code == 422
    assert no_origin.status_code == 422
    assert read.status_code == 200


def test_missing_frontend_shows_build_instruction(tmp_path: Path) -> None:
    client = TestClient(create_desktop_app(tmp_path / "missing-dist", port=9001))

    response = client.get("/")

    assert response.status_code == 200
    assert "pnpm build" in response.text


def test_built_frontend_is_served_from_root(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<h1>CC-Roster desktop</h1>", encoding="utf-8")
    client = TestClient(create_desktop_app(dist, port=9002))

    response = client.get("/")

    assert response.status_code == 200
    assert "CC-Roster desktop" in response.text
