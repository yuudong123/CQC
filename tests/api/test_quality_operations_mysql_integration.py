"""BE-05 집계와 두 CSV를 cqc_test의 실제 저장 행으로 검증한다."""

from __future__ import annotations

import csv
import os
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from io import StringIO
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from src.api.core.config import Settings
from src.api.db.models import Inspection, InspectionError
from src.api.db.session import create_db_engine, create_session_factory
from src.api.main import create_app
from src.api.repositories.quality_history import (
    HistoryFilters,
    QualityHistoryRepository,
)
from src.api.repositories.quality_statistics import QualityStatisticsRepository
from src.api.services.quality_operations import QualityOperationsService


def test_mysql_snapshot_statistics_and_both_csv_formats() -> None:
    database_url = os.getenv("CQC_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("CQC_TEST_DATABASE_URL이 없어 MySQL integration test를 건너뜁니다")
    engine = create_db_engine(Settings(database_url=database_url))
    factory = create_session_factory(engine)
    service = QualityOperationsService(
        QualityHistoryRepository(factory), QualityStatisticsRepository(factory)
    )
    kst = timezone(timedelta(hours=9))
    today = datetime.now(kst).date()
    midnight = datetime.combine(today, time.min, tzinfo=kst).astimezone(timezone.utc)
    boundary = midnight.replace(tzinfo=None)
    prefix = f"operations-{uuid4().hex[:12]}"
    identifiers: list[str] = []

    def row(index: int, when: datetime, **overrides: object) -> Inspection:
        inspection_id = f"{prefix}-{index}"
        identifiers.append(inspection_id)
        values = {
            "inspection_id": inspection_id,
            "created_at": when,
            "completed_at": when,
            "updated_at": when,
            "crop_type": "apple",
            "predicted_cultivar": "fuji",
            "predicted_grade": "L",
            "cultivar_confidence": Decimal("0.9"),
            "quality_confidence": Decimal("0.8"),
            "applied_cultivar_threshold": Decimal("0.5"),
            "applied_quality_threshold": Decimal("0.5"),
            "inference_time_ms": Decimal(100),
            "virtual_brix": Decimal("12.0"),
            "review_required": False,
            "target_bin_code": "DEMO_BIN_01",
            "inspection_status": "COMPLETED",
            "control_status": "SUCCEEDED",
            "persistence_status": "SUCCEEDED",
            "deadline_exceeded": False,
            "exclude_from_normal_stats": False,
            "is_reviewed": False,
        }
        values.update(overrides)
        return Inspection(**values)

    try:
        rows = [
            row(0, boundary),
            row(
                1,
                boundary,
                predicted_grade="M",
                quality_confidence=Decimal("0.3"),
                inference_time_ms=Decimal(200),
                review_required=True,
                target_bin_code="TEST_REINSPECTION_BIN",
                inspection_status="REINSPECTION_REQUIRED",
                error_code="LOW_QUALITY_CONFIDENCE",
            ),
            row(
                2,
                boundary,
                predicted_cultivar=None,
                predicted_grade=None,
                cultivar_confidence=None,
                quality_confidence=None,
                inference_time_ms=Decimal(500),
                review_required=True,
                target_bin_code="TEST_REINSPECTION_BIN",
                inspection_status="REINSPECTION_REQUIRED",
                error_code="INFERENCE_DEADLINE_EXCEEDED",
                deadline_exceeded=True,
                exclude_from_normal_stats=True,
            ),
            row(
                3,
                boundary,
                predicted_cultivar=None,
                predicted_grade=None,
                cultivar_confidence=None,
                quality_confidence=None,
                inference_time_ms=None,
                review_required=True,
                target_bin_code="TEST_REINSPECTION_BIN",
                inspection_status="REINSPECTION_REQUIRED",
                error_code="INFERENCE_ERROR",
                exclude_from_normal_stats=True,
            ),
            row(
                4,
                boundary,
                predicted_cultivar="yanggwang",
                predicted_grade="S",
                inference_time_ms=Decimal(300),
                virtual_brix=Decimal("14.0"),
                target_bin_code="DEMO_BIN_12",
                suspected_error_type="OTHER",
            ),
            row(5, boundary - timedelta(milliseconds=1)),
        ]
        for index, code in ((2, "INFERENCE_DEADLINE_EXCEEDED"), (3, "INFERENCE_ERROR")):
            rows[index].errors = [
                InspectionError(
                    component="inference",
                    error_code=code,
                    occurred_at=boundary,
                )
            ]
        with factory() as session, session.begin():
            session.add_all(rows)

        previous = service.snapshot(boundary - timedelta(milliseconds=1))
        assert (
            previous["state"]["today"]["date"]
            == (today - timedelta(days=1)).isoformat()
        )
        assert previous["state"]["today"]["total"] == 1
        empty = service.snapshot(datetime(1970, 1, 1))  # noqa: DTZ001 - DB UTC naive
        assert empty["state"]["today"]["total"] == 0
        assert empty["state"]["history"] == []

        snapshot = service.snapshot(boundary)
        assert snapshot["source"] == "backend"
        assert snapshot["state"]["today"]["date"] == today.isoformat()
        assert snapshot["state"]["today"]["total"] == 5
        assert snapshot["state"]["today"]["review"] == 1
        assert snapshot["state"]["today"]["excluded"] == 2
        assert snapshot["state"]["today"]["normal"] == 3
        assert snapshot["state"]["today"]["varieties"] == {"부사": 2, "양광": 1}
        assert snapshot["state"]["today"]["grades"] == {"특": 1, "상": 1, "보통": 1}
        assert snapshot["state"]["today"]["reinspection"] == 3
        assert snapshot["state"]["points"][-1]["count"] == 5
        assert len(snapshot["state"]["history"]) == 6
        assert len(snapshot["state"]["errors"]) == 2
        assert "concurrency" not in snapshot["state"]
        assert "history" not in snapshot["retention"]

        filters = HistoryFilters(from_date=today, to_date=today)
        summary = service.statistics(filters, boundary)
        assert summary["total"] == 5
        assert summary["normal"] == 3
        assert summary["excluded"] == 2
        assert summary["reinspection"] == 3
        assert summary["inferenceTotalMs"] == 600
        assert summary["inferenceCount"] == 3
        assert summary["grades"] == {"특": 1, "상": 1, "보통": 1}
        assert summary["suspicions"] == {"OTHER": 1}
        assert (
            service.statistics(
                HistoryFilters(from_date=today, grade="상", variety="부사"), boundary
            )["total"]
            == 1
        )
        assert (
            service.statistics(
                HistoryFilters(to_date=today - timedelta(days=1)), boundary
            )["total"]
            == 1
        )
        empty_summary = service.statistics(
            HistoryFilters(from_date=today + timedelta(days=1)), boundary
        )
        assert empty_summary["total"] == 0
        assert empty_summary["inferenceCount"] == 0
        assert empty_summary["reinspection"] == 0

        with TestClient(create_app(Settings(database_url=database_url))) as client:
            snapshot_response = client.get("/v1/quality/snapshot")
            assert snapshot_response.status_code == 200
            assert snapshot_response.json()["source"] == "backend"
            assert snapshot_response.headers["cache-control"] == "no-store"
            assert "concurrency" not in snapshot_response.json()["state"]
            assert "history" not in snapshot_response.json()["retention"]
            stats_response = client.get(
                "/v1/quality/statistics",
                params={"from": today.isoformat(), "to": today.isoformat()},
            )
            assert stats_response.status_code == 200
            assert stats_response.json()["total"] == 5
            csv_response = client.get(
                "/v1/quality/inspections.csv",
                params={"from": today.isoformat(), "page": 2, "pageSize": 50},
            )
            assert csv_response.status_code == 200
            assert csv_response.content.startswith(b"\xef\xbb\xbf")
            assert "text/csv" in csv_response.headers["content-type"]
            assert csv_response.headers["cache-control"] == "no-store"
            parsed = list(
                csv.reader(StringIO(csv_response.content.decode("utf-8-sig")))
            )
            assert len(parsed) == 6
            assert parsed[0][0:3] == ["inspection_id", "date", "time_kst"]
            assert {record[3] for record in parsed[1:]} == {"", "부사", "양광"}
            assert {record[4] for record in parsed[1:]} == {"", "특", "상", "보통"}
            assert all("image" not in column for column in parsed[0])

            stats_csv = client.get(
                "/v1/quality/statistics.csv",
                params={"from": today.isoformat(), "to": today.isoformat()},
            )
            assert stats_csv.status_code == 200
            assert stats_csv.content.startswith(b"\xef\xbb\xbf")
            assert "text/csv" in stats_csv.headers["content-type"]
            assert stats_csv.headers["cache-control"] == "no-store"
            records = list(csv.reader(StringIO(stats_csv.content.decode("utf-8-sig"))))
            assert records[0] == ["mode", "from_kst", "to_kst", "group", "key", "value"]
            assert [
                "BACKEND",
                today.isoformat(),
                today.isoformat(),
                "total",
                "total",
                "5",
            ] in records
            assert [
                "BACKEND",
                today.isoformat(),
                today.isoformat(),
                "total",
                "reinspection_ratio",
                "0.6",
            ] in records
            minute_csv = client.get("/v1/quality/statistics.csv", params={"minutes": 1})
            assert minute_csv.status_code == 200
            assert minute_csv.content.startswith(b"\xef\xbb\xbf")
            minute_records = list(
                csv.reader(StringIO(minute_csv.content.decode("utf-8-sig")))
            )
            assert minute_records[0] == [
                "mode",
                "date_kst",
                "section",
                "key",
                "value",
                "last_saved_at",
            ]
            empty_csv = client.get(
                "/v1/quality/statistics.csv",
                params={"from": (today + timedelta(days=1)).isoformat()},
            )
            empty_records = list(
                csv.reader(StringIO(empty_csv.content.decode("utf-8-sig")))
            )
            assert [
                "BACKEND",
                (today + timedelta(days=1)).isoformat(),
                "",
                "total",
                "total",
                "0",
            ] in empty_records
    finally:
        with factory() as session, session.begin():
            session.execute(
                delete(Inspection).where(Inspection.inspection_id.in_(identifiers))
            )
        with factory() as session:
            assert (
                session.scalar(
                    select(Inspection.inspection_id).where(
                        Inspection.inspection_id.in_(identifiers)
                    )
                )
                is None
            )
        engine.dispose()
