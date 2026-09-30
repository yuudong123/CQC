"""독립 Simulator 앱의 내부 HTTP 제어와 Backend 검사 전송."""

from __future__ import annotations

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from time import sleep

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

        async def respond(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            if len(requests) >= 3:
                received.set()
            return httpx.Response(200, json={"inspection_id": "ok"})

        inspection_client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
        app = create_app(_settings(root), inspection_client=inspection_client)
        with TestClient(app) as client:
            assert client.get("/health").json() == {"status": "ok"}
            assert client.get("/state").json()["revision"] == 0
            assert client.get("/state").json()["running"] is True
            assert received.wait(5)
            started = client.put(
                "/state",
                json={
                    "expectedRevision": 1,
                    "concurrency": 2,
                    "faults": ["INFERENCE_ERROR"],
                    "scope": "NEXT",
                },
            )
            assert started.status_code == 200
            assert started.json()["running"] is True
            for _ in range(500):
                if client.get("/state").json()["revision"] == 2:
                    break
                sleep(0.01)
            state = client.get("/state").json()
            assert state["revision"] == 3
            assert state["faults"] == []
            assert state["scope"] == "NEXT"
            assert state["status"] == "healthy"
            stale = client.put("/state", json={"expectedRevision": 2, "running": False})
            assert stale.status_code == 409
            stopped = client.put(
                "/state", json={"expectedRevision": 3, "running": False}
            )
            assert stopped.status_code == 200
            assert stopped.json()["running"] is False
            assert stopped.json()["status"] == "stopped"
            assert app.state.simulator_runner.active is False
            assert client.get("/health").status_code == 503
            assert client.get("/health").json() == {
                "status": "unhealthy",
                "reason": "SIMULATOR_NOT_PLAYING",
            }
        assert (
            sum(bool(item.headers["x-cqc-simulator-faults"]) for item in requests) == 1
        )
        assert all(item.url.path == "/v1/inspections" for item in requests)
        assert all(
            item.headers["x-cqc-simulator-token"] == "test-token" for item in requests
        )
        assert _settings(root).simulator_position_path.exists()
        asyncio.run(inspection_client.aclose())


def test_internal_start_without_dataset_does_not_change_revision() -> None:
    with TemporaryDirectory(prefix="cqc-simulator-app-", dir=Path.cwd()) as temporary:
        root = Path(temporary) / "missing"
        app = create_app(_settings(root))
        with pytest.raises(FileNotFoundError):
            with TestClient(app):
                pass
        assert app.state.simulator_state_service.get_state().revision == 0
