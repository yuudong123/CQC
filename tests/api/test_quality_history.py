"""관제 검사 이력 조회의 공개 계약 회귀 테스트."""

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from src.api.core.config import Settings
from src.api.db.models import Inspection, InspectionError
from src.api.main import create_app
from src.api.repositories.quality_history import HistoryFilters, HistoryRows
from src.api.services.quality_history import to_quality_result


def _row(**overrides: object) -> Inspection:
    values = {
        "inspection_id": "history_1",
        "completed_at": datetime(2026, 9, 29, 14, 59, 59, 123000),  # noqa: DTZ001 - DB UTC naive
        "predicted_cultivar": "fuji",
        "predicted_grade": "L",
        "quality_confidence": Decimal("0.800000"),
        "cultivar_confidence": Decimal("0.900000"),
        "exclude_from_normal_stats": False,
        "review_required": False,
        "deadline_exceeded": False,
        "persistence_status": "SUCCEEDED",
        "control_status": "SUCCEEDED",
        "target_bin_code": "DEMO_BIN_02",
        "error_code": None,
        "suspected_error_type": None,
        "virtual_brix": Decimal("14.0"),
        "inference_time_ms": Decimal("120.125"),
        "model_version": "demo-v1",
    }
    values.update(overrides)
    row = Inspection(**values)
    row.control_attempts = []
    row.errors = []
    return row


def test_result_converts_utc_to_kst_without_fabricating_image_index() -> None:
    result = to_quality_result(_row())
    assert (result["date"], result["time"]) == ("2026-09-29", "23:59:59.123")
    assert result["imageIndex"] is None
    assert result["variety"] == "부사"
    assert result["grade"] == "특"
    assert result["confidence"] == 80
    assert result["cultivarConfidence"] == 90
    assert result["virtualBrix"] == 14


def test_result_keeps_control_failure_and_excluded_prediction_distinct() -> None:
    result = to_quality_result(
        _row(
            control_status="FAILED",
            error_code="CONTROL_FAILED",
            review_required=True,
        )
    )
    assert result["control"] == "FAILED"
    assert result["errorCode"] == "CONTROL_FAILED"
    assert result["faults"] == ["CONTROL_FAILED"]
    assert result["status"] == "REVIEW"

    excluded = to_quality_result(
        _row(
            deadline_exceeded=True,
            error_code="INFERENCE_DEADLINE_EXCEEDED",
            predicted_cultivar=None,
            predicted_grade=None,
            exclude_from_normal_stats=True,
        )
    )
    assert excluded["processingStatus"] == "TIMEOUT"
    assert excluded["errorCode"] == "INFERENCE_TIMEOUT"
    assert excluded["status"] == "FAIL"
    assert excluded["variety"] is None
    assert excluded["confidence"] is None
    assert excluded["inferenceMs"] is None

    connection_failure = to_quality_result(
        _row(
            error_code="INFERENCE_CONNECTION_ERROR",
            predicted_cultivar=None,
            predicted_grade=None,
            exclude_from_normal_stats=True,
            target_bin_code="TEST_REINSPECTION_BIN",
        )
    )
    assert connection_failure["processingStatus"] == "ERROR"
    assert connection_failure["errorCode"] == "INFERENCE_ERROR"
    assert connection_failure["status"] == "FAIL"


def test_unattempted_control_is_preserved_without_a_failure_label() -> None:
    result = to_quality_result(
        _row(
            control_status="NOT_REQUESTED",
            error_code="BIN_MAPPING_CONFIGURATION_ERROR",
            target_bin_code=None,
        )
    )
    assert result["control"] == "NOT_REQUESTED"
    assert result["errorCode"] == "DB_ERROR"


def test_control_failure_remains_representative_after_low_confidence() -> None:
    row = _row(
        error_code="LOW_QUALITY_CONFIDENCE",
        control_status="FAILED",
        review_required=True,
    )
    row.errors = [
        InspectionError(
            id=1,
            error_code="CONTROL_FAILED",
            occurred_at=row.completed_at,
        )
    ]
    result = to_quality_result(row)
    assert result["errorCode"] == "CONTROL_FAILED"
    assert result["faults"] == ["CONTROL_FAILED"]


class _HistoryRepository:
    def __init__(self, items: list[Inspection]) -> None:
        self.items = items
        self.calls: list[tuple[HistoryFilters, datetime, int, int]] = []

    def list_page(
        self,
        filters: HistoryFilters,
        *,
        snapshot_at: datetime,
        page: int,
        page_size: int,
    ) -> HistoryRows:
        self.calls.append((filters, snapshot_at, page, page_size))
        return HistoryRows(self.items, len(self.items), ["DEMO_BIN_02"])


def test_api_returns_history_page_and_contract_filters() -> None:
    app = create_app(Settings())
    repository = _HistoryRepository([_row()])
    app.state.quality_history_repository = repository
    with TestClient(app) as client:
        response = client.get(
            "/v1/quality/inspections",
            params={
                "from": "2026-09-29",
                "variety": "부사",
                "page": 2,
                "pageSize": 100,
                "snapshotAt": 1790000000000,
            },
        )
    assert response.status_code == 200, response.json()
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["items"][0]["imageIndex"] is None
    assert body["page"] == 2
    assert body["pageSize"] == 100
    assert body["snapshotAt"] == 1790000000000
    assert repository.calls[0][0].from_date.isoformat() == "2026-09-29"
    assert repository.calls[0][0].variety == "부사"


def test_db_unavailable_is_top_level_error_and_no_store() -> None:
    with TestClient(create_app(Settings())) as client:
        response = client.get("/v1/quality/inspections")
    assert response.status_code == 503
    assert response.json() == {"code": "DB_UNAVAILABLE"}
    assert response.headers["cache-control"] == "no-store"


def test_empty_history_and_page_size_contract() -> None:
    app = create_app(Settings())
    repository = _HistoryRepository([])
    app.state.quality_history_repository = repository
    with TestClient(app) as client:
        for size in (50, 100, 200):
            response = client.get("/v1/quality/inspections", params={"pageSize": size})
            assert response.status_code == 200
            assert response.json()["items"] == []
            assert response.json()["total"] == 0
            assert response.json()["pageSize"] == size
            assert isinstance(response.json()["snapshotAt"], (int, float))
        invalid = client.get("/v1/quality/inspections", params={"pageSize": 51})
        unknown = client.get(
            "/v1/quality/inspections", params={"controlStatus": "FAILED"}
        )
    assert invalid.status_code == 422
    assert invalid.json() == {"code": "INVALID_QUERY"}
    assert unknown.status_code == 422
    assert unknown.json() == {"code": "UNKNOWN_QUERY_FIELD"}


def test_fastapi_openapi_matches_shared_history_contract() -> None:
    shared_path = (
        Path(__file__).resolve().parents[2]
        / "docs/contracts/quality-operations.openapi.json"
    )
    shared = json.loads(shared_path.read_text(encoding="utf-8"))
    actual = create_app(Settings()).openapi()
    shared_get = shared["paths"]["/inspections"]["get"]
    actual_get = actual["paths"]["/v1/quality/inspections"]["get"]
    assert [parameter["name"] for parameter in actual_get["parameters"]] == [
        parameter["name"] for parameter in shared_get["parameters"]
    ]
    assert set(actual_get["responses"]) == set(shared_get["responses"])
    result = actual["components"]["schemas"]["QualityResult"]
    shared_result = shared["components"]["schemas"]["Result"]
    assert set(result["required"]) == set(shared_result["required"])
    assert set(result["properties"]) == set(shared_result["properties"]) - {
        "previewUrl"
    }
    assert {"integer", "null"} == {
        part["type"] for part in result["properties"]["imageIndex"]["anyOf"]
    }
    assert set(shared_result["properties"]["imageIndex"]["type"]) == {"integer", "null"}
    assert (
        result["properties"]["control"]["enum"]
        == shared_result["properties"]["control"]["enum"]
    )
    assert (
        result["properties"]["errorCode"]["enum"]
        == shared_result["properties"]["errorCode"]["enum"]
    )


def test_sql_error_does_not_leak_internal_message() -> None:
    class BrokenRepository:
        def list_page(self, *args: object, **kwargs: object) -> None:
            raise SQLAlchemyError("internal SQL and password")

    app = create_app(Settings())
    app.state.quality_history_repository = BrokenRepository()
    with TestClient(app) as client:
        response = client.get("/v1/quality/inspections")
    assert response.status_code == 503
    assert response.json() == {"code": "DB_UNAVAILABLE"}
    assert b"password" not in response.content
    assert response.headers["cache-control"] == "no-store"


def test_unattempted_control_state_is_returned_by_history_api() -> None:
    app = create_app(Settings())
    app.state.quality_history_repository = _HistoryRepository(
        [
            _row(
                control_status="NOT_REQUESTED",
                error_code="BIN_MAPPING_CONFIGURATION_ERROR",
            )
        ]
    )
    with TestClient(app) as client:
        response = client.get("/v1/quality/inspections")
    assert response.status_code == 200
    assert response.json()["items"][0]["control"] == "NOT_REQUESTED"
    assert response.headers["cache-control"] == "no-store"
