"""격리 MySQL에서 검사 이력 순환 삭제와 조회 일치를 검증한다."""

from __future__ import annotations

import csv
import os
from datetime import datetime, timedelta, timezone
from io import StringIO
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.engine import make_url

from src.api.core.config import Settings
from src.api.db.models import ControlAttempt, Inspection, InspectionError
from src.api.db.session import create_db_engine, create_session_factory
from src.api.main import create_app
from src.api.repositories.inspections import InspectionRepository
from src.api.repositories.persistence import InspectionPersistence
from src.api.repositories.records import ControlAttemptRecord, InspectionErrorRecord


def test_retention_deletes_oldest_batches_and_read_apis_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = os.getenv("CQC_RETENTION_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("격리 순환 삭제 MySQL URL이 없으면 건너뜁니다")
    parsed_url = make_url(database_url)
    if parsed_url.host not in {"127.0.0.1", "localhost"} or not (
        parsed_url.database or ""
    ).endswith("_retention"):
        pytest.skip("로컬 순환 삭제 전용 MySQL 스키마에서만 실행합니다")

    settings = Settings(_env_file=None, database_url=database_url)
    engine = create_db_engine(settings)
    session_factory = create_session_factory(engine)
    persistence = InspectionPersistence(
        session_factory, history_limit=5, history_delete_batch=2
    )
    prefix = f"retention-{uuid4().hex[:12]}"
    base = datetime.now(timezone.utc) - timedelta(minutes=1)
    ids = {name: f"{prefix}-{name}" for name in "abcdefg"}
    count_calls = 0
    original_count = InspectionRepository.count

    def counted(repository: InspectionRepository) -> int:
        nonlocal count_calls
        count_calls += 1
        return original_count(repository)

    monkeypatch.setattr(InspectionRepository, "count", counted)

    def save(name: str, created_at: datetime) -> None:
        inspection_id = ids[name]
        persistence.create_pending(
            {
                "inspection_id": inspection_id,
                "created_at": created_at,
                "updated_at": created_at,
                "crop_type": "apple",
                "applied_cultivar_threshold": 0.5,
                "applied_quality_threshold": 0.6,
                "inspection_status": "INFERENCING",
                "control_status": "PENDING",
                "persistence_status": "PENDING",
            }
        )
        persistence.finalize(
            inspection_id=inspection_id,
            inspection_values={
                "completed_at": created_at,
                "updated_at": created_at,
                "inspection_status": "COMPLETED",
                "control_status": "SUCCEEDED",
                "persistence_status": "SUCCEEDED",
                "target_bin_code": "DEMO_BIN_01",
                "predicted_cultivar": "fuji",
                "predicted_grade": "L",
                "cultivar_confidence": 0.9,
                "quality_confidence": 0.8,
                "virtual_brix": 11.0,
            },
            control_attempts=(
                [
                    ControlAttemptRecord(
                        command_id=str(uuid4()),
                        attempt_no=1,
                        requested_bin_code="DEMO_BIN_01",
                        command_type="SORT",
                        control_status="SUCCEEDED",
                        requested_at=created_at,
                        responded_at=created_at,
                        response_time_ms=1,
                        failure_reason=None,
                    )
                ]
                if name in "ab"
                else []
            ),
            errors=(
                [
                    InspectionErrorRecord(
                        component="test",
                        error_code="TEST_ERROR",
                        message=None,
                        diagnostic_data=None,
                        occurred_at=created_at,
                    )
                ]
                if name in "ab"
                else []
            ),
        )

    try:
        with session_factory() as session:
            if session.scalar(select(func.count()).select_from(Inspection)) != 0:
                pytest.skip("순환 삭제 전용 MySQL 스키마가 비어 있어야 합니다")

        # a, b, c의 동일 시각은 inspection_id로 안정적으로 순서를 정한다.
        for name in "abcd":
            save(name, base if name in "abc" else base + timedelta(seconds=1))
        with session_factory() as session:
            assert session.scalar(select(func.count()).select_from(Inspection)) == 4

        persistence.save_late_result(
            inspection_id=ids["a"],
            received_at=base,
            payload={"diagnostic": True},
        )
        save("e", base + timedelta(seconds=2))
        with session_factory() as session:
            assert session.scalar(select(func.count()).select_from(Inspection)) == 3
            assert session.get(Inspection, ids["a"]) is None
            assert session.get(Inspection, ids["b"]) is None
            assert session.get(Inspection, ids["c"]) is not None
            assert session.scalar(select(func.count()).select_from(ControlAttempt)) == 0
            assert (
                session.scalar(select(func.count()).select_from(InspectionError)) == 0
            )

        save("f", base + timedelta(seconds=3))
        save("g", base + timedelta(seconds=4))
        with session_factory() as session:
            remaining = set(session.scalars(select(Inspection.inspection_id)))
        assert remaining == {ids[name] for name in "efg"}
        assert count_calls == 3  # 최초 1회와 두 삭제 경계에서만 DB 건수를 읽는다.

        with TestClient(
            create_app(Settings(_env_file=None, database_url=database_url))
        ) as client:
            history = client.get("/v1/quality/inspections")
            statistics = client.get("/v1/quality/statistics")
            inspections_csv = client.get("/v1/quality/inspections.csv")
            day = base.astimezone(timezone(timedelta(hours=9))).date().isoformat()
            statistics_csv = client.get(
                "/v1/quality/statistics.csv", params={"from": day, "to": day}
            )
        assert history.status_code == statistics.status_code == 200
        assert inspections_csv.status_code == statistics_csv.status_code == 200
        assert history.json()["total"] == statistics.json()["total"] == 3
        csv_rows = list(
            csv.reader(StringIO(inspections_csv.content.decode("utf-8-sig")))
        )
        assert {row[0] for row in csv_rows[1:]} == remaining
        statistics_rows = list(
            csv.reader(StringIO(statistics_csv.content.decode("utf-8-sig")))
        )
        assert any(row[3:] == ["total", "total", "3"] for row in statistics_rows)
    finally:
        with session_factory() as session, session.begin():
            session.execute(
                delete(Inspection).where(
                    Inspection.inspection_id.in_(list(ids.values()))
                )
            )
        engine.dispose()
