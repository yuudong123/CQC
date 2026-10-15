"""늦은 Inference 응답의 MySQL 진단 저장과 확정 결과 불변 검증."""

from __future__ import annotations

import asyncio
import os
from datetime import timedelta
from io import BytesIO
from uuid import uuid4

import pytest
from fastapi import UploadFile
from sqlalchemy import delete, inspect

from src.api.clients.inference import MockInferenceClient
from src.api.control.virtual_control import MockVirtualControl
from src.api.core.config import Settings
from src.api.core.datetime import to_utc_naive, utc_now
from src.api.db.models import Inspection
from src.api.db.session import create_db_engine, create_session_factory
from src.api.repositories import BinMappingRepository, InspectionPersistence
from src.api.repositories.quality_history import HistoryFilters
from src.api.repositories.quality_statistics import QualityStatisticsRepository
from src.api.schemas.inference import InferenceRequest, InferenceResponse
from src.api.schemas.inspections import InspectionImageMetadata
from src.api.services.inspections import InspectionService
from src.api.services.late_results import LateResultManager
from src.api.services.quality_history import to_quality_result


def test_mysql_late_result_updates_only_diagnostics() -> None:
    database_url = os.getenv("CQC_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("CQC_TEST_DATABASE_URL이 없어 MySQL integration test를 건너뜁니다")

    engine = create_db_engine(Settings(database_url=database_url))
    factory = create_session_factory(engine)
    inspection_id = f"late-result-{uuid4()}"
    fixed_fields = (
        "inspection_status",
        "predicted_cultivar",
        "predicted_grade",
        "cultivar_confidence",
        "quality_confidence",
        "target_bin_code",
        "control_status",
        "persistence_status",
        "error_code",
        "deadline_exceeded",
        "exclude_from_normal_stats",
        "completed_at",
    )

    try:
        columns = {
            column["name"] for column in inspect(engine).get_columns("inspections")
        }
        assert {"late_result_received_at", "late_result_payload"} <= columns

        async def run() -> tuple[
            dict[str, object], tuple[object, ...], dict[str, object], dict[str, object]
        ]:
            release = asyncio.Event()

            class HeldInferenceClient(MockInferenceClient):
                async def predict(self, request: InferenceRequest) -> InferenceResponse:
                    await release.wait()
                    return await super().predict(request)

            manager = LateResultManager(hard_timeout_ms=2000, max_tasks=4)
            control = MockVirtualControl()
            service = InspectionService(
                HeldInferenceClient(),
                control,
                cultivar_confidence_threshold=0.50,
                quality_confidence_threshold=0.60,
                inference_business_deadline_ms=1,
                late_result_manager=manager,
                bin_mapping_repository=BinMappingRepository(factory),
                persistence=InspectionPersistence(factory),
            )
            response = await service.inspect(
                inspection_id=inspection_id,
                images=[UploadFile(file=BytesIO(b"image"), filename="view-0.png")],
                metadata=[
                    InspectionImageMetadata(
                        view_index=0,
                        angle_direction="top",
                        verticality_angle=0,
                        horizontality_angle=0,
                    )
                ],
                virtual_brix=12.0,
            )
            assert manager.active_count == 1
            assert len(control.requests) == 1
            snapshot_at = to_utc_naive(utc_now() + timedelta(days=1))
            statistics = QualityStatisticsRepository(factory)
            with factory() as session:
                row = session.get(Inspection, inspection_id)
                assert row is not None
                assert row.late_result_received_at is None
                assert row.late_result_payload is None
                original = tuple(getattr(row, field) for field in fixed_fields)
                public_before = to_quality_result(row)
            totals_before = statistics.summary(HistoryFilters(), snapshot_at)

            release.set()
            await manager.wait_until_idle()
            assert len(control.requests) == 1
            assert len(manager.results) == 1
            with factory() as session:
                row = session.get(Inspection, inspection_id)
                assert row is not None
                assert tuple(getattr(row, field) for field in fixed_fields) == original
                assert row.late_result_received_at is not None
                assert row.late_result_received_at.tzinfo is None
                assert row.late_result_payload is not None
                assert row.late_result_payload["inspection_id"] == inspection_id
                assert row.late_result_payload["quality_confidence"] == 0.8
                assert to_quality_result(row) == public_before
            assert statistics.summary(HistoryFilters(), snapshot_at) == totals_before
            return response.model_dump(), original, public_before, totals_before

        response, original, public_result, totals = asyncio.run(run())
        assert response["inspection_status"] == "REINSPECTION_REQUIRED"
        assert response["decision_reason"] == "INFERENCE_DEADLINE_EXCEEDED"
        assert response["target_bin_code"] == "TEST_REINSPECTION_BIN"
        assert original[0] == "REINSPECTION_REQUIRED"
        assert public_result["bin"] == "TEST_REINSPECTION_BIN"
        assert totals["total"] >= 1
    finally:
        with factory() as session, session.begin():
            session.execute(
                delete(Inspection).where(Inspection.inspection_id == inspection_id)
            )
        engine.dispose()
