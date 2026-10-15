"""BE-05 관제 집계 API의 계약 및 장애 경계 테스트."""

from __future__ import annotations

import csv
import json
from datetime import date, datetime, timezone
from io import StringIO
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from src.api.core.config import Settings
from src.api.main import create_app
from src.api.repositories.quality_history import HistoryFilters
from src.api.schemas.quality_operations import QualitySnapshot
from src.api.services.quality_operations import QualityOperationsService

from .test_quality_history import _row


@pytest.mark.parametrize(
    ("suspicions", "expected_today", "expected_period"),
    [
        ({}, ["0", "0", "0"], []),
        ({"OTHER": 1}, ["0", "0", "1"], [("OTHER", "1")]),
        (
            {"CULTIVAR_SUSPECT": 2, "QUALITY_SUSPECT": 3, "OTHER": 4},
            ["2", "3", "4"],
            [("CULTIVAR_SUSPECT", "2"), ("QUALITY_SUSPECT", "3"), ("OTHER", "4")],
        ),
    ],
    ids=["zero", "one", "multiple"],
)
@pytest.mark.parametrize("dated", [False, True], ids=["today", "period"])
def test_statistics_csv_suspicion_rows_and_format(
    suspicions: dict[str, int],
    expected_today: list[str],
    expected_period: list[tuple[str, str]],
    dated: bool,
) -> None:
    """오늘 CSV의 0값 보완과 기간 CSV·공통 형식의 호환성을 확인한다."""
    summary = {
        "total": 10,
        "normal": 8,
        "excluded": 2,
        "reinspection": 3,
        "grades": {"특": 8},
        "varieties": {"부사": 8},
        "bins": {"DEMO_BIN_01": 7},
        "suspicions": suspicions.copy(),
        "inferenceTotalMs": 800,
        "inferenceCount": 8,
    }
    statistics = Mock()
    statistics.summary.return_value = summary
    statistics.today.return_value = ("2026-10-12", summary)
    captured_at = datetime(2026, 10, 12, 1, tzinfo=timezone.utc).replace(tzinfo=None)
    statistics.last_saved.return_value = captured_at
    statistics.points.return_value = [{"at": 1_791_767_999_000, "count": 1}]
    service = QualityOperationsService(Mock(), statistics)
    day = date(2026, 10, 12)
    filters = HistoryFilters(from_date=day, to_date=day) if dated else HistoryFilters()

    content = service.statistics_csv(filters, captured_at, minutes=1)
    assert content.encode("utf-8").startswith(b"\xef\xbb\xbf")
    assert content.endswith("\r\n")
    assert "\n" not in content.replace("\r\n", "")
    assert all(
        line.startswith('"')
        and line.endswith('"')
        and all(cell.startswith('"') and cell.endswith('"') for cell in line.split(","))
        for line in content.removeprefix("\ufeff").splitlines()
    )
    rows = list(csv.reader(StringIO(content.removeprefix("\ufeff"))))
    assert all(row[0] == "BACKEND" for row in rows[1:])
    group_index = 3 if dated else 2
    suspicion_rows = [row for row in rows[1:] if row[group_index] == "suspicions"]
    if dated:
        assert rows[0] == ["mode", "from_kst", "to_kst", "group", "key", "value"]
        assert [(row[4], row[5]) for row in suspicion_rows] == expected_period
        statistics.today.assert_not_called()
        statistics.points.assert_not_called()
    else:
        assert rows[0] == [
            "mode",
            "date_kst",
            "section",
            "key",
            "value",
            "last_saved_at",
        ]
        assert [row[3] for row in suspicion_rows] == [
            "CULTIVAR_SUSPECT",
            "QUALITY_SUSPECT",
            "OTHER",
        ]
        assert [row[4] for row in suspicion_rows] == expected_today
        assert all(row[5] == "2026-10-12T10:00:00.000+09:00" for row in rows[1:])
        assert sum(row[2] == "last_1_minutes" for row in rows[1:]) == 1
        statistics.summary.assert_not_called()
    assert any(
        row[group_index : group_index + 3] == ["grades", "특", "8"] for row in rows
    )
    assert any(
        row[group_index : group_index + 3] == ["varieties", "부사", "8"] for row in rows
    )
    assert any(
        row[group_index : group_index + 3] == ["bins", "DEMO_BIN_01", "7"]
        for row in rows
    )
    totals = {
        row[group_index + 1]: row[group_index + 2]
        for row in rows[1:]
        if row[group_index] == ("total" if dated else "today")
    }
    assert totals["reinspection_ratio"] == "0.3"
    assert totals["average_inference_ms"] == "100.0"
    assert summary["suspicions"] == suspicions


def test_snapshot_limits_errors_without_shortening_history_contract() -> None:
    history = Mock()
    history.recent_rows.return_value = [_row(inspection_id="snapshot.2026-10-05")]
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

    service = QualityOperationsService(history, statistics)
    snapshot = service.snapshot(captured_at)

    history.recent_rows.assert_called_once_with(captured_at, limit=200)
    history.recent_errors.assert_called_once_with(captured_at, limit=8)
    assert snapshot["state"]["jobs"] == []
    assert snapshot["state"]["recentCompletedJobs"] == []
    QualitySnapshot.model_validate(snapshot)
    assert snapshot["state"]["history"][0]["id"] == "snapshot.2026-10-05"
    app = create_app(Settings())
    app.state.quality_operations_service = service
    with TestClient(app) as client:
        response = client.get("/v1/quality/snapshot")
    assert response.status_code == 200, response.text
    assert response.json()["state"]["history"][0]["id"] == "snapshot.2026-10-05"


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
        "category",
        "decisionReason",
        "cultivarConfidence",
        "qualityConfidence",
        "appliedCultivarThreshold",
        "appliedQualityThreshold",
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
