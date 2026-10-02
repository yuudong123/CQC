"""BE-05 관제 집계 API의 계약 및 장애 경계 테스트."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from src.api.core.config import Settings
from src.api.main import create_app
from src.api.schemas.quality_operations import QualitySnapshot
from src.api.services.quality_operations import QualityOperationsService


def test_snapshot_limits_errors_without_shortening_history_contract() -> None:
    history = Mock()
    history.recent_rows.return_value = []
    history.recent_errors.return_value = []
    statistics = Mock()
    statistics.today.return_value = (
        "2026-10-02",
        {
            "total": 0,
            "normal": 0,
            "excluded": 0,
            "grades": {},
            "varieties": {},
            "bins": {},
            "suspicions": {},
            "reinspection": 0,
            "inferenceTotalMs": 0,
            "inferenceCount": 0,
        },
    )
    statistics.review_count.return_value = 0
    statistics.last_saved.return_value = None
    statistics.period_totals.return_value = {key: 0 for key in ("1", "5", "10", "30")}
    statistics.points.return_value = []
    captured_at = datetime(2026, 10, 2, tzinfo=timezone.utc).replace(tzinfo=None)

    snapshot = QualityOperationsService(history, statistics).snapshot(captured_at)

    history.recent_rows.assert_called_once_with(captured_at, limit=200)
    history.recent_errors.assert_called_once_with(captured_at, limit=8)
    assert snapshot["state"]["jobs"] == []
    assert snapshot["state"]["recentCompletedJobs"] == []
    QualitySnapshot.model_validate(snapshot)


def test_unconfigured_database_returns_503_for_all_operations() -> None:
    with TestClient(create_app(Settings())) as client:
        for path in (
            "/v1/quality/snapshot",
            "/v1/quality/statistics",
            "/v1/quality/inspections.csv",
            "/v1/quality/statistics.csv",
        ):
            response = client.get(path)
            assert response.status_code == 503
            assert response.json() == {"code": "DB_UNAVAILABLE"}
            assert response.headers["cache-control"] == "no-store"


def test_database_sql_error_is_not_exposed_or_returned_as_empty_csv() -> None:
    class BrokenService:
        def __getattr__(self, name: str):
            def fail(*args: object, **kwargs: object) -> None:
                raise SQLAlchemyError("SQL password and table contents")

            return fail

    app = create_app(Settings())
    app.state.quality_operations_service = BrokenService()
    with TestClient(app) as client:
        for path in (
            "/v1/quality/snapshot",
            "/v1/quality/statistics",
            "/v1/quality/inspections.csv",
            "/v1/quality/statistics.csv",
        ):
            response = client.get(path)
            assert response.status_code == 503
            assert response.json() == {"code": "DB_UNAVAILABLE"}
            assert b"password" not in response.content
            assert response.headers["cache-control"] == "no-store"


def test_openapi_operations_match_shared_contract() -> None:
    path = (
        Path(__file__).resolve().parents[2]
        / "docs/contracts/quality-operations.openapi.json"
    )
    shared = json.loads(path.read_text(encoding="utf-8"))
    actual = create_app(Settings()).openapi()
    for endpoint in ("/snapshot", "/statistics", "/inspections.csv", "/statistics.csv"):
        expected = shared["paths"][endpoint]["get"]
        implemented = actual["paths"]["/v1/quality" + endpoint]["get"]
        assert {item["name"] for item in implemented.get("parameters", [])} == {
            item["name"] for item in expected.get("parameters", [])
        }
        assert set(implemented["responses"]) == set(expected["responses"])
        if endpoint.endswith(".csv"):
            assert set(implemented["responses"]["200"]["content"]) == {"text/csv"}
    state = actual["components"]["schemas"]["QualityState"]
    retention = actual["components"]["schemas"]["QualityRetention"]
    shared_state = shared["components"]["schemas"]["Snapshot"]["properties"]["state"]
    shared_retention = shared["components"]["schemas"]["Snapshot"]["properties"][
        "retention"
    ]
    for field in ("concurrency", "sequence", "tick", "scope"):
        assert field not in state["required"]
        assert field not in shared_state["required"]
        assert "null" not in str(state["properties"][field].get("type", ""))
        assert "null" not in str(shared_state["properties"][field].get("type", ""))
    assert "history" not in retention["required"]
    assert "history" not in shared_retention["required"]
    assert retention["properties"]["history"]["type"] == "integer"
    assert shared_retention["properties"]["history"]["type"] == "integer"
    assert "Current number" in shared_retention["properties"]["images"]["description"]
    assert "recentCompletedJobs" in state["required"]
    assert "recentCompletedJobs" in shared_state["required"]
    assert state["properties"]["recentCompletedJobs"]["maxItems"] == 64
    assert shared_state["properties"]["recentCompletedJobs"]["items"] == {
        "$ref": "#/components/schemas/RecentCompletedJob"
    }
    recent = shared["components"]["schemas"]["RecentCompletedJob"]
    assert set(recent["properties"]) == {
        "id",
        "status",
        "completedAt",
        "previewExpiresAt",
        "previews",
    }
    assert recent["properties"]["status"]["enum"] == ["COMPLETED", "ERROR", "TIMEOUT"]


def test_fault_image_contract_is_per_image_while_snapshot_remains_per_inspection() -> (
    None
):
    path = (
        Path(__file__).resolve().parents[2]
        / "docs/contracts/quality-operations.openapi.json"
    )
    shared = json.loads(path.read_text(encoding="utf-8"))
    schemas = shared["components"]["schemas"]
    assert schemas["FaultImages"]["properties"]["items"]["items"] == {
        "$ref": "#/components/schemas/FaultImage"
    }
    assert set(schemas["FaultImage"]["required"]) == {
        "id",
        "inspectionId",
        "imageIndex",
        "createdAt",
        "errorCode",
        "previewUrl",
    }
    assert schemas["Snapshot"]["properties"]["state"]["properties"]["images"][
        "items"
    ] == {"$ref": "#/components/schemas/Result"}
    assert (
        "individual"
        in schemas["ImageDelete"]["properties"]["ids"]["description"].lower()
    )
    actual = create_app(Settings()).openapi()["paths"]
    assert "/v1/quality/fault-images" in actual
    assert "/v1/quality/previews/{id}" in actual
    delete = actual["/v1/quality/fault-images"]["delete"]
    expected = shared["paths"]["/fault-images"]["delete"]
    assert set(delete["responses"]) == set(expected["responses"])
    assert (
        delete["requestBody"]["content"]["application/json"]["schema"]["$ref"]
        == "#/components/schemas/QualityImageDelete"
    )
    assert "delete-all" in schemas["ImageDelete"]["properties"]["ids"]["description"]
