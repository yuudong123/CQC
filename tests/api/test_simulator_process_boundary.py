"""두 FastAPI 앱을 독립 생성해 Backend→Simulator 제어를 확인한다."""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from src.api.clients.simulator import SimulatorClient
from src.api.core.config import Settings
from src.api.main import create_app as create_backend_app
from src.simulator.config import SimulatorSettings
from src.simulator.main import create_app as create_simulator_app

from .test_quality_simulator import _SnapshotOperations


def test_backend_control_reaches_independent_simulator_app() -> None:
    simulator = create_simulator_app(
        SimulatorSettings(
            simulator_dataset_root=Path("."),
            simulator_position_path=Path("unused-position.json"),
            simulator_backend_url="http://backend:8000",
            simulator_fault_token="test-token",
        )
    )
    transport = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=simulator), base_url="http://simulator"
    )
    backend = create_backend_app(Settings())
    backend.state.quality_operations_service = _SnapshotOperations()
    backend.state.simulator_client = SimulatorClient(
        "http://simulator", client=transport
    )
    with TestClient(simulator), TestClient(backend) as client:
        initial = client.get("/v1/quality/snapshot")
        assert initial.status_code == 200
        assert initial.json()["revision"] == 0
        changed = client.put(
            "/v1/quality/simulator",
            json={"expectedRevision": 0, "concurrency": 2, "intervalMs": 3000},
        )
        assert changed.status_code == 200
        assert changed.json()["revision"] == 1
        assert changed.json()["state"]["concurrency"] == 2
        assert changed.json()["state"]["intervalMs"] == 3000
        assert changed.json()["capabilities"]["intervals"] == [1000, 2000, 3000]
        assert simulator.state.simulator_state_service.get_state().interval_ms == 3000
        assert simulator.state.simulator_state_service.get_state().revision == 1
        assert not hasattr(backend.state, "simulator_state_service")
    asyncio.run(transport.aclose())
