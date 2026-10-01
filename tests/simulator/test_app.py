"""독립 Simulator 앱의 내부 HTTP 제어와 Backend 검사 전송."""

from __future__ import annotations

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from time import monotonic, sleep

import httpx
import pytest
from fastapi.testclient import TestClient

from src.simulator.config import SimulatorSettings
from src.simulator.main import create_app

from .test_runner import _dataset


def _settings(root: Path) -> SimulatorSettings:
    return SimulatorSettings(
        simulator_dataset_root=root,
        simulator_position_path=root.parent / "state" / "position.json",
        simulator_backend_url="http://backend:8000",
        simulator_fault_token="test-token",
        simulator_interval_ms=10,
    )


def test_internal_health_control_next_and_graceful_shutdown() -> None:
    with TemporaryDirectory(prefix="cqc-simulator-app-", dir=Path.cwd()) as temporary:
        root = Path(temporary) / "dataset"
        root.mkdir()
        _dataset(root)
        requests: list[httpx.Request] = []
        received = Event()
        allow_response = Event()

        async def respond(request: httpx.Request) -> httpx.Response:
            await asyncio.to_thread(allow_response.wait)
            requests.append(request)
            if len(requests) >= 3:
                received.set()
            return httpx.Response(200, json={"inspection_id": "ok"})

        inspection_client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
        app = create_app(_settings(root), inspection_client=inspection_client)
        with TestClient(app) as client:
            try:
                initial = client.get("/state").json()
                assert initial["revision"] == 0
                assert initial["running"] is True
                assert initial["intervalMs"] == 10
                assert initial["lastSeenAt"] is None
                assert client.get("/health").status_code == 503
            finally:
                allow_response.set()
            assert received.wait(5)
            deadline = monotonic() + 5
            while client.get("/health").status_code != 200 and monotonic() < deadline:
                sleep(0.01)
            health = client.get("/health")
            assert health.status_code == 200
            assert health.json()["status"] == "ok"
            assert health.json()["running"] is True
            assert health.json()["lastSeenAt"] is not None

            configured = client.put(
                "/state",
                json={
                    "expectedRevision": 0,
                    "concurrency": 2,
                    "faults": ["INFERENCE_ERROR"],
                    "scope": "NEXT",
                },
            )
            assert configured.status_code == 200
            assert configured.json()["running"] is True
            deadline = monotonic() + 5
            while monotonic() < deadline:
                if client.get("/state").json()["revision"] == 2:
                    break
                sleep(0.01)
            state = client.get("/state").json()
            assert state["revision"] == 2
            assert state["faults"] == []
            assert state["scope"] == "NEXT"
            assert state["status"] == "healthy"
            stale = client.put("/state", json={"expectedRevision": 1, "running": False})
            assert stale.status_code == 409
            stopped = client.put(
                "/state", json={"expectedRevision": 2, "running": False}
            )
            assert stopped.status_code == 200
            assert stopped.json()["revision"] == 3
            assert stopped.json()["running"] is False
            assert stopped.json()["status"] == "stopped"
            assert app.state.simulator_runner.active is False
            stopped_health = client.get("/health")
            assert stopped_health.status_code == 503
            assert stopped_health.json() == {
                "status": "unhealthy",
                "reason": "SIMULATOR_NOT_PLAYING",
            }
            restarted = client.put(
                "/state", json={"expectedRevision": 3, "running": True}
            )
            assert restarted.status_code == 200
            assert restarted.json()["revision"] == 4
            assert restarted.json()["running"] is True
            assert restarted.json()["intervalMs"] == 10
            deadline = monotonic() + 5
            while client.get("/health").status_code != 200 and monotonic() < deadline:
                sleep(0.01)
            assert client.get("/health").status_code == 200
        assert app.state.simulator_runner.active is False
        assert (
            sum(bool(item.headers["x-cqc-simulator-faults"]) for item in requests) == 1
        )
        assert all(item.url.path == "/v1/inspections" for item in requests)
        assert all(
            item.headers["x-cqc-simulator-token"] == "test-token" for item in requests
        )
        assert _settings(root).simulator_position_path.exists()
        asyncio.run(inspection_client.aclose())


def test_internal_start_without_dataset_does_not_change_revision(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with TemporaryDirectory(prefix="cqc-simulator-app-", dir=Path.cwd()) as temporary:
        root = Path(temporary) / "missing"
        app = create_app(_settings(root))
        with TestClient(app) as client:
            state = client.get("/state").json()
            assert state["revision"] == 0
            assert state["running"] is False
            assert state["status"] == "stopped"
            assert state["lastSeenAt"] is None
            assert app.state.simulator_runner.active is False
            assert client.get("/health").status_code == 503
            response = client.put(
                "/state", json={"expectedRevision": 0, "running": True}
            )
            assert response.status_code == 503
            assert response.json() == {"code": "SIMULATOR_DATASET_UNAVAILABLE"}
        assert (
            "Simulator 자동 시작을 위한 dataset 또는 position 준비 실패" in caplog.text
        )
        assert app.state.simulator_state_service.get_state().revision == 0


@pytest.mark.parametrize("failure_kind", ["http", "connection"])
def test_health_only_tracks_successful_backend_posts(failure_kind: str) -> None:
    with TemporaryDirectory(prefix="cqc-simulator-app-", dir=Path.cwd()) as temporary:
        root = Path(temporary) / "dataset"
        root.mkdir()
        _dataset(root)
        allow_success = Event()
        next_request_started = Event()
        attempts = 0

        async def respond(request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            if attempts <= 2:
                if failure_kind == "connection":
                    raise httpx.ConnectError("Backend 연결 실패", request=request)
                return httpx.Response(500)
            next_request_started.set()
            await asyncio.to_thread(allow_success.wait)
            return httpx.Response(200, json={"inspection_id": "ok"})

        inspection_client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
        app = create_app(_settings(root), inspection_client=inspection_client)
        with TestClient(app) as client:
            try:
                assert next_request_started.wait(5)
                state = client.get("/state").json()
                assert state["running"] is True
                assert state["status"] == "healthy"
                assert state["lastSeenAt"] is None
                assert app.state.simulator_runner.failed is False
                assert client.get("/health").status_code == 503
            finally:
                allow_success.set()
            deadline = monotonic() + 5
            while client.get("/health").status_code != 200 and monotonic() < deadline:
                sleep(0.01)
            assert client.get("/health").status_code == 200
            assert client.get("/state").json()["lastSeenAt"] is not None
        asyncio.run(inspection_client.aclose())
