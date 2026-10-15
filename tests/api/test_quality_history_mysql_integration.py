"""실제 cqc_test에서 snapshot pagination과 KST 경계를 검증한다."""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from src.api.core.config import Settings
from src.api.db.models import Inspection
from src.api.db.session import create_db_engine, create_session_factory
from src.api.repositories.quality_history import (
    HistoryFilters,
    QualityHistoryRepository,
)


def test_mysql_history_snapshot_filters_pagination_and_cleanup() -> None:
    database_url = os.getenv("CQC_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("CQC_TEST_DATABASE_URL이 없어 MySQL integration test를 건너뜁니다")
    engine = create_db_engine(Settings(database_url=database_url))
    session_factory = create_session_factory(engine)
    repository = QualityHistoryRepository(session_factory)
    prefix = f"history-{uuid4().hex[:12]}"
    identifiers: list[str] = []
    midnight_kst_as_utc = datetime(2026, 9, 28, 15, 0, 0)  # noqa: DTZ001 - DB UTC naive

    def add_row(index: int, completed_at: datetime, **overrides: object) -> Inspection:
        inspection_id = f"{prefix}-{index:03d}"
        identifiers.append(inspection_id)
        values = {
            "inspection_id": inspection_id,
            "created_at": completed_at,
            "completed_at": completed_at,
            "updated_at": completed_at,
            "crop_type": "apple",
            "predicted_cultivar": "fuji",
            "predicted_grade": "L",
            "cultivar_confidence": Decimal("0.9"),
            "quality_confidence": Decimal("0.8"),
            "applied_cultivar_threshold": Decimal("0.5"),
            "applied_quality_threshold": Decimal("0.5"),
            "virtual_brix": Decimal("12.0"),
            "review_required": False,
            "target_bin_code": "TEST_HISTORY_BIN",
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
        rows = [add_row(index, midnight_kst_as_utc) for index in range(51)]
        rows.append(add_row(51, midnight_kst_as_utc - timedelta(milliseconds=1)))
        rows.append(add_row(52, midnight_kst_as_utc + timedelta(milliseconds=1)))
        rows.append(
            add_row(
                53,
                midnight_kst_as_utc,
                predicted_cultivar="yanggwang",
                predicted_grade="M",
                target_bin_code="TEST_HISTORY_ERROR",
                control_status="FAILED",
                error_code="CONTROL_FAILED",
                suspected_error_type="OTHER",
                review_required=True,
            )
        )
        rows.append(
            add_row(
                54,
                midnight_kst_as_utc,
                predicted_cultivar=None,
                predicted_grade=None,
                target_bin_code="TEST_HISTORY_TIMEOUT",
                error_code="INFERENCE_DEADLINE_EXCEEDED",
                deadline_exceeded=True,
                exclude_from_normal_stats=True,
            )
        )
        with session_factory() as session, session.begin():
            session.add_all(rows)

        filters = HistoryFilters(
            from_date=date(2026, 9, 29),
            to_date=date(2026, 9, 29),
            variety="부사",
            grade="특",
            bin_code="TEST_HISTORY_BIN",
            processing_status="COMPLETED",
            error_code="NONE",
            misclassification="NONE",
        )
        first = repository.list_page(
            filters, snapshot_at=midnight_kst_as_utc, page=1, page_size=50
        )
        second = repository.list_page(
            filters, snapshot_at=midnight_kst_as_utc, page=2, page_size=50
        )
        assert first.total == second.total == 51
        assert len(first.items) == 50
        assert len(second.items) == 1
        assert first.items[0].inspection_id == f"{prefix}-050"
        assert second.items[0].inspection_id == f"{prefix}-000"
        assert f"{prefix}-052" not in {
            row.inspection_id for row in first.items + second.items
        }
        before_midnight = repository.list_page(
            HistoryFilters(to_date=date(2026, 9, 28), bin_code="TEST_HISTORY_BIN"),
            snapshot_at=midnight_kst_as_utc,
            page=1,
            page_size=50,
        )
        assert before_midnight.total == 1
        assert before_midnight.items[0].inspection_id == f"{prefix}-051"
        failed = repository.list_page(
            HistoryFilters(
                from_date=date(2026, 9, 29),
                to_date=date(2026, 9, 29),
                variety="양광",
                grade="상",
                bin_code="TEST_HISTORY_ERROR",
                processing_status="COMPLETED",
                error_code="CONTROL_FAILED",
                misclassification="OTHER",
            ),
            snapshot_at=midnight_kst_as_utc,
            page=1,
            page_size=100,
        )
        assert failed.total == 1
        assert failed.items[0].inspection_id == f"{prefix}-053"
        timeout = repository.list_page(
            HistoryFilters(
                processing_status="TIMEOUT",
                error_code="INFERENCE_TIMEOUT",
                bin_code="TEST_HISTORY_TIMEOUT",
            ),
            snapshot_at=midnight_kst_as_utc,
            page=1,
            page_size=200,
        )
        assert timeout.total == 1
        assert timeout.items[0].inspection_id == f"{prefix}-054"
    finally:
        with session_factory() as session, session.begin():
            session.execute(
                delete(Inspection).where(Inspection.inspection_id.in_(identifiers))
            )
        with session_factory() as session:
            assert not session.scalars(
                select(Inspection.inspection_id).where(
                    Inspection.inspection_id.in_(identifiers)
                )
            ).first()
        engine.dispose()
