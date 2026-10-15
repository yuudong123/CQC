"""실제 MySQL 검사 행의 검수 저장과 이력 반영을 검증한다."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from src.api.core.config import Settings
from src.api.db.models import Inspection
from src.api.db.session import create_db_engine, create_session_factory
from src.api.main import create_app


def test_mysql_review_updates_history_without_changing_prediction() -> None:
    database_url = os.getenv("CQC_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("CQC_TEST_DATABASE_URL이 없어 MySQL integration test를 건너뜁니다")
    engine = create_db_engine(Settings(database_url=database_url))
    factory = create_session_factory(engine)
    identifier = f"review-{uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    try:
        with factory() as session, session.begin():
            session.add(
                Inspection(
                    inspection_id=identifier,
                    created_at=now,
                    completed_at=now,
                    updated_at=now,
                    crop_type="apple",
                    predicted_cultivar="fuji",
                    predicted_grade="L",
                    cultivar_confidence=Decimal("0.9"),
                    quality_confidence=Decimal("0.8"),
                    applied_cultivar_threshold=Decimal("0.5"),
                    applied_quality_threshold=Decimal("0.5"),
                    virtual_brix=Decimal("14.0"),
                    review_required=False,
                    target_bin_code="DEMO_BIN_02",
                    inspection_status="COMPLETED",
                    control_status="SUCCEEDED",
                    persistence_status="SUCCEEDED",
                    deadline_exceeded=False,
                    exclude_from_normal_stats=False,
                    is_reviewed=False,
                )
            )
        with TestClient(create_app(Settings(database_url=database_url))) as client:
            marked = client.patch(
                f"/v1/quality/inspections/{identifier}/review",
                json={"misclassification": "CULTIVAR_SUSPECT"},
            )
            assert marked.status_code == 200
            history = client.get(
                "/v1/quality/inspections?misclassification=CULTIVAR_SUSPECT"
            )
            assert history.status_code == 200
            assert any(item["id"] == identifier for item in history.json()["items"])
            cleared = client.patch(
                f"/v1/quality/inspections/{identifier}/review",
                json={"misclassification": "NONE"},
            )
            assert cleared.status_code == 200
        with factory() as session:
            row = session.get(Inspection, identifier)
            assert row is not None
            assert row.suspected_error_type is None
            assert row.is_reviewed is False
            assert row.reviewed_at is None
            assert (
                row.predicted_cultivar,
                row.predicted_grade,
                row.target_bin_code,
            ) == (
                "fuji",
                "L",
                "DEMO_BIN_02",
            )
    finally:
        with factory() as session, session.begin():
            session.execute(
                delete(Inspection).where(Inspection.inspection_id == identifier)
            )
        engine.dispose()
