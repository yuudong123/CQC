"""Backend 공개 제어 API가 독립 Simulator 상태를 전달하는 계약."""

from __future__ import annotations

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from threading import Barrier

import httpx
import pytest
from fastapi.testclient import TestClient

from src.api.clients.inference import HttpInferenceClient
from src.api.clients.simulator import SimulatorRevisionConflict, SimulatorUnavailable
from src.api.core.config import Settings
from src.api.main import create_app
from src.api.services.quality_operations import QualityOperationsService
from src.simulator.schemas import SimulatorSettingsUpdate, SimulatorStatus
from src.simulator.state import (
    RevisionMismatchError,
    SimulatorStateService,
)


def _base_snapshot() -> dict[str, object]:
    component = {"status": "unknown", "lastSeenAt": None, "detail": "test"}
    return {
        "contractVersion": "1",
        "source": "backend",
        "capturedAt": 0,
        "revision": 0,
        "capabilities": {
            "control": False,
            "faults": False,
            "review": True,
            "deleteImages": False,
            "concurrency": [],
            "intervals": [],
        },
        "components": {
            name: dict(component)
            for name in ("Simulator", "Inference", "Backend", "MySQL")
        },
        "retention": {"images": 0},
        "periodTotals": {key: 0 for key in ("1", "5", "10", "30")},
        "state": {
            "throughput": 0,
            "running": False,
            "faults": [],
            "jobs": [],
            "history": [],
            "images": [],
            "points": [],
            "errors": [],
            "today": {
                "date": "2026-09-30",
                "total": 0,
                "normal": 0,
                "review": 0,
                "excluded": 0,
                "grades": {},
                "varieties": {},
                "bins": {},
                "reinspection": 0,
                "inferenceTotalMs": 0,
                "inferenceCount": 0,
                "suspicions": {
                    "CULTIVAR_SUSPECT": 0,
                    "QUALITY_SUSPECT": 0,
                    "OTHER": 0,
                },
            },
            "lastSaved": None,
            "dbDown": False,
        },
    }


class _SnapshotOperations(QualityOperationsService):
    def __init__(self) -> None:
        pass

    def snapshot(self, captured_at: datetime) -> dict[str, object]:
        del captured_at
        return deepcopy(_base_snapshot())


class _FakeSimulatorClient:
    def __init__(self) -> None:
        self.state = SimulatorStateService()
        self.unavailable = False
        self.updates: list[SimulatorSettingsUpdate] = []

    async def get_status(self) -> SimulatorStatus:
        if self.unavailable:
            raise SimulatorUnavailable("disconnected")
        current = self.state.get_state()
        return SimulatorStatus(
            revision=current.revision,
            running=current.running,
            concurrency=current.concurrency,
            intervalMs=current.interval_ms,
            faults=list(current.faults),
            scope=current.scope,
            status="healthy" if current.running else "stopped",
            lastSeenAt=None,
        )

    async def update(self, update: SimulatorSettingsUpdate) -> SimulatorStatus:
        if self.unavailable:
            raise SimulatorUnavailable("disconnected")
        self.updates.append(update)
        try:
            self.state.update_state(update)
        except RevisionMismatchError as exc:
            raise SimulatorRevisionConflict from exc
        return await self.get_status()


@pytest.fixture
def client() -> TestClient:
    app = create_app(Settings())
    app.state.simulator_client = _FakeSimulatorClient()
    app.state.quality_operations_service = _SnapshotOperations()
    with TestClient(app) as test_client:
        yield test_client


def test_partial_update_and_revision_conflict_are_forwarded(client: TestClient) -> None:
    initial = client.get("/v1/quality/snapshot")
    assert initial.status_code == 200
    assert initial.json()["revision"] == 0
    assert initial.json()["capabilities"]["control"] is True
    assert initial.json()["state"]["intervalMs"] == 2000
    assert initial.json()["capabilities"]["intervals"] == [1000, 2000, 3000]
    assert initial.json()["components"]["Simulator"]["status"] == "stopped"
    changed = client.put(
        "/v1/quality/simulator",
        json={"expectedRevision": 0, "concurrency": 4},
    )
    assert changed.status_code == 200
    assert changed.json()["revision"] == 1
    assert changed.json()["state"]["concurrency"] == 4
    assert client.app.state.simulator_client.updates[0].concurrency == 4
    stale = client.put(
        "/v1/quality/simulator",
        json={"expectedRevision": 0, "running": True},
    )
    assert stale.status_code == 409
    assert stale.json() == {"code": "REVISION_CONFLICT"}
    assert client.get("/v1/quality/snapshot").json()["revision"] == 1


@pytest.mark.parametrize("interval_ms", [1000, 2000, 3000])
def test_interval_update_reaches_simulator_and_snapshot(
    client: TestClient, interval_ms: int
) -> None:
    response = client.put(
        "/v1/quality/simulator",
        json={"expectedRevision": 0, "intervalMs": interval_ms, "faults": ["DB_ERROR"]},
    )
    assert response.status_code == 200
    assert response.json()["revision"] == 1
    assert response.json()["state"]["intervalMs"] == interval_ms
    assert response.json()["state"]["faults"] == ["DB_ERROR"]
    assert response.json()["capabilities"]["intervals"] == [1000, 2000, 3000]
    assert client.app.state.simulator_client.updates[0].interval_ms == interval_ms
    stale = client.put(
        "/v1/quality/simulator",
        json={"expectedRevision": 0, "intervalMs": 1000},
    )
    assert stale.status_code == 409
    assert (
        client.get("/v1/quality/snapshot").json()["state"]["intervalMs"] == interval_ms
    )


@pytest.mark.parametrize("interval_ms", [500, 4000, True, 2000.0, None])
def test_public_interval_rejects_values_outside_choices(
    client: TestClient, interval_ms: object
) -> None:
    response = client.put(
        "/v1/quality/simulator",
        json={"expectedRevision": 0, "intervalMs": interval_ms},
    )
    assert response.status_code == 422
    assert response.json() == {"code": "INVALID_SETTINGS"}
    assert client.app.state.simulator_client.updates == []


@pytest.mark.parametrize("concurrency", [1, 2, 4])
def test_agreed_concurrency_values_are_accepted(
    client: TestClient, concurrency: int
) -> None:
    response = client.put(
        "/v1/quality/simulator",
        json={"expectedRevision": 0, "concurrency": concurrency},
    )
    assert response.status_code == 200
    assert response.json()["state"]["concurrency"] == concurrency


@pytest.mark.parametrize("concurrency", [3, 5, 8, 64, True])
def test_other_concurrency_values_are_rejected(
    client: TestClient, concurrency: object
) -> None:
    response = client.put(
        "/v1/quality/simulator",
        json={"expectedRevision": 0, "concurrency": concurrency},
    )
    assert response.status_code == 422
    assert response.json() == {"code": "INVALID_SETTINGS"}
    assert client.app.state.simulator_client.updates == []


def test_fault_scope_and_next_claim_are_owned_by_simulator(client: TestClient) -> None:
    configured = client.put(
        "/v1/quality/simulator",
        json={
            "expectedRevision": 0,
            "running": True,
            "faults": ["INFERENCE_TIMEOUT"],
            "scope": "NEXT",
        },
    )
    assert configured.status_code == 200
    assert configured.json()["state"]["running"] is True
    assert configured.json()["components"]["Simulator"]["status"] == "healthy"
    state = client.app.state.simulator_client.state
    assert state.claim_faults_for_inspection() == ("INFERENCE_TIMEOUT",)
    assert state.claim_faults_for_inspection() == ()
    snapshot = client.get("/v1/quality/snapshot").json()
    assert snapshot["revision"] == 2
    assert snapshot["state"]["faults"] == []
    assert snapshot["state"]["scope"] == "NEXT"


def test_concurrent_controls_have_one_revision_winner(client: TestClient) -> None:
    barrier = Barrier(2)

    def update(running: bool) -> int:
        barrier.wait()
        return client.put(
            "/v1/quality/simulator",
            json={"expectedRevision": 0, "running": running},
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(update, (True, False)))
    assert sorted(statuses) == [200, 409]


def test_unavailable_simulator_keeps_snapshot_available(client: TestClient) -> None:
    client.app.state.simulator_client.unavailable = True
    snapshot = client.get("/v1/quality/snapshot")
    assert snapshot.status_code == 200
    assert snapshot.json()["components"]["Simulator"]["status"] == "unknown"
    assert snapshot.json()["capabilities"]["control"] is False
    assert snapshot.json()["capabilities"]["intervals"] == []
    response = client.put(
        "/v1/quality/simulator", json={"expectedRevision": 0, "running": True}
    )
    assert response.status_code == 503
    assert response.json() == {"code": "SIMULATOR_UNAVAILABLE"}


@pytest.mark.parametrize(
    ("health_response", "expected_status"),
    [
        (
            httpx.Response(200, json={"status": "ready", "model_loaded": True}),
            "healthy",
        ),
        (httpx.Response(503), "error"),
        (None, "error"),
    ],
)
def test_snapshot_reflects_inference_health_without_failing(
    client: TestClient, health_response: httpx.Response | None, expected_status: str
) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        if health_response is None:
            raise httpx.ConnectError("refused", request=request)
        return health_response

    transport = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    client.app.state.inference_client = HttpInferenceClient(
        "http://inference:8001/v1/predict", client=transport
    )
    try:
        response = client.get("/v1/quality/snapshot")
        assert response.status_code == 200
        component = response.json()["components"]["Inference"]
        assert component["status"] == expected_status
        assert (component["lastSeenAt"] is not None) is (expected_status == "healthy")
    finally:
        asyncio.run(transport.aclose())


def test_backend_without_internal_url_has_no_runner_or_state() -> None:
    app = create_app(Settings())
    assert app.state.simulator_client is None
    assert not hasattr(app.state, "simulator_runner")
    assert not hasattr(app.state, "simulator_state_service")
    app.state.quality_operations_service = _SnapshotOperations()
    with TestClient(app) as client:
        snapshot = client.get("/v1/quality/snapshot")
        assert snapshot.status_code == 200
        assert snapshot.json()["components"]["Simulator"]["status"] == "unknown"
        assert (
            client.put(
                "/v1/quality/simulator", json={"expectedRevision": 0, "running": True}
            ).status_code
            == 503
        )


def test_shared_openapi_keeps_public_simulator_contract() -> None:
    contract = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "docs/contracts/quality-operations.openapi.json"
        ).read_text(encoding="utf-8")
    )
    actual = create_app(Settings()).openapi()
    settings = contract["components"]["schemas"]["Settings"]
    assert settings["properties"]["concurrency"]["enum"] == [1, 2, 4]
    assert settings["properties"]["intervalMs"]["enum"] == [1000, 2000, 3000]
    snapshot_schema = contract["components"]["schemas"]["Snapshot"]
    assert snapshot_schema["properties"]["capabilities"]["properties"]["intervals"][
        "items"
    ]["enum"] == [1000, 2000, 3000]
    assert (
        snapshot_schema["properties"]["state"]["properties"]["intervalMs"]["minimum"]
        == 1
    )
    assert actual["components"]["schemas"]["SimulatorSettingsUpdate"]["properties"][
        "intervalMs"
    ]["enum"] == [1000, 2000, 3000]
    assert set(actual["paths"]["/v1/quality/simulator"]["put"]["responses"]) == set(
        contract["paths"]["/simulator"]["put"]["responses"]
    )
