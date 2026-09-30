"""Simulator 제어 API와 관제 snapshot의 공유 상태 계약."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from threading import Barrier

import pytest
from fastapi.testclient import TestClient

from src.api.core.config import Settings
from src.api.main import create_app
from src.api.services.quality_operations import QualityOperationsService
from src.api.services.simulator_state import SimulatorStateService


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
            "review": False,
            "deleteImages": False,
            "concurrency": [],
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
    def __init__(self, state: SimulatorStateService) -> None:
        self._simulator_state = state

    def snapshot(self, captured_at: datetime) -> dict[str, object]:
        del captured_at
        return self.with_simulator_state(deepcopy(_base_snapshot()))


@pytest.fixture
def client() -> TestClient:
    app = create_app(Settings())
    app.state.quality_operations_service = _SnapshotOperations(
        app.state.simulator_state_service
    )
    with TestClient(app) as test_client:
        yield test_client


def test_partial_updates_snapshot_and_revision_conflict(client: TestClient) -> None:
    initial = client.get("/v1/quality/snapshot")
    assert initial.status_code == 200
    assert initial.headers["cache-control"] == "no-store"
    assert initial.json()["state"]["concurrency"] == 1
    assert initial.json()["capabilities"]["control"] is True
    assert initial.json()["capabilities"]["concurrency"] == [1, 2, 4]

    changed = client.put(
        "/v1/quality/simulator",
        json={"expectedRevision": 0, "concurrency": 4},
    )
    assert changed.status_code == 200
    assert changed.headers["cache-control"] == "no-store"
    assert changed.json()["revision"] == 1
    assert changed.json()["state"]["concurrency"] == 4
    assert changed.json()["state"]["running"] is False
    assert changed.json()["state"]["faults"] == []
    assert "sequence" not in changed.json()["state"]
    assert "tick" not in changed.json()["state"]

    stale = client.put(
        "/v1/quality/simulator",
        json={"expectedRevision": 0, "running": True},
    )
    assert stale.status_code == 409
    assert stale.json() == {"code": "REVISION_CONFLICT"}
    assert stale.headers["cache-control"] == "no-store"
    assert client.get("/v1/quality/snapshot").json()["revision"] == 1


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
    assert client.get("/v1/quality/snapshot").json()["revision"] == 0


def test_fault_scope_and_running_are_visible_in_snapshot(client: TestClient) -> None:
    response = client.put(
        "/v1/quality/simulator",
        json={
            "expectedRevision": 0,
            "running": True,
            "faults": ["INFERENCE_TIMEOUT"],
            "scope": "NEXT",
        },
    )
    assert response.status_code == 200
    state = response.json()["state"]
    assert state["running"] is True
    assert state["faults"] == ["INFERENCE_TIMEOUT"]
    assert state["scope"] == "NEXT"
    assert response.json()["components"]["Simulator"]["status"] == "stopped"
    current = client.get("/v1/quality/snapshot").json()
    assert current["revision"] == 1
    assert current["state"]["faults"] == ["INFERENCE_TIMEOUT"]


def test_same_revision_control_requests_have_one_winner(client: TestClient) -> None:
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
    assert client.get("/v1/quality/snapshot").json()["revision"] == 1


@pytest.mark.parametrize(
    "field,value",
    [("faults", ["BOGUS"]), ("scope", "OFF"), ("faults", ["DB_ERROR", "DB_ERROR"])],
)
def test_invalid_fault_settings_are_rejected(
    client: TestClient, field: str, value: object
) -> None:
    response = client.put(
        "/v1/quality/simulator", json={"expectedRevision": 0, field: value}
    )
    assert response.status_code == 422
    assert response.json() == {"code": "INVALID_SETTINGS"}


def test_next_claim_is_atomic_and_increments_visible_revision(
    client: TestClient,
) -> None:
    service = client.app.state.simulator_state_service
    configured = client.put(
        "/v1/quality/simulator",
        json={
            "expectedRevision": 0,
            "faults": ["INFERENCE_TIMEOUT"],
            "scope": "NEXT",
        },
    )
    assert configured.status_code == 200
    barrier = Barrier(2)

    def claim() -> tuple[str, ...]:
        barrier.wait()
        return service.claim_faults_for_inspection()

    with ThreadPoolExecutor(max_workers=2) as pool:
        claimed = list(pool.map(lambda _: claim(), range(2)))
    assert sorted(claimed) == [(), ("INFERENCE_TIMEOUT",)]
    snapshot = client.get("/v1/quality/snapshot").json()
    assert snapshot["revision"] == 2
    assert snapshot["state"]["faults"] == []
    assert snapshot["state"]["scope"] == "NEXT"
    assert service.claim_faults_for_inspection() == ()
    assert service.get_state().revision == 2


def test_all_scope_keeps_faults_and_empty_next_is_allowed(client: TestClient) -> None:
    service = client.app.state.simulator_state_service
    configured = client.put(
        "/v1/quality/simulator",
        json={"expectedRevision": 0, "faults": ["DB_ERROR"], "scope": "ALL"},
    )
    assert configured.status_code == 200
    assert service.claim_faults_for_inspection() == ("DB_ERROR",)
    assert service.claim_faults_for_inspection() == ("DB_ERROR",)
    assert service.get_state().revision == 1
    empty_next = client.put(
        "/v1/quality/simulator",
        json={"expectedRevision": 1, "faults": [], "scope": "NEXT"},
    )
    assert empty_next.status_code == 200
    assert service.claim_faults_for_inspection() == ()
    assert service.get_state().revision == 2


def test_shared_openapi_matches_concurrency_and_simulator_responses() -> None:
    contract = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "docs/contracts/quality-operations.openapi.json"
        ).read_text(encoding="utf-8")
    )
    actual = create_app(Settings()).openapi()
    settings = contract["components"]["schemas"]["Settings"]
    assert settings["properties"]["concurrency"]["enum"] == [1, 2, 4]
    assert set(actual["paths"]["/v1/quality/simulator"]["put"]["responses"]) == set(
        contract["paths"]["/simulator"]["put"]["responses"]
    )
    assert actual["components"]["schemas"]["SimulatorSettingsUpdate"]["properties"][
        "concurrency"
    ]["enum"] == [1, 2, 4]
    assert (
        actual["components"]["schemas"]["SimulatorSettingsUpdate"]["properties"][
            "faults"
        ]["uniqueItems"]
        is True
    )
