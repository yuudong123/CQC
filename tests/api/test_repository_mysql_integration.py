from __future__ import annotations

import asyncio
import os
from io import BytesIO
from uuid import uuid4

import pytest
from fastapi import UploadFile
from sqlalchemy import delete, select

from src.api.clients.inference import MockInferenceClient
from src.api.control.virtual_control import MockVirtualControl
from src.api.core.config import Settings
from src.api.db.models import ControlAttempt, Inspection
from src.api.db.session import create_db_engine, create_session_factory
from src.api.repositories import BinMappingRepository, InspectionPersistence
from src.api.schemas.inspections import InspectionImageMetadata
from src.api.services.bin_policy import DEMO_NORMAL_BIN_MAPPING
from src.api.services.inspections import InspectionService
from src.api.services.late_results import LateResultManager


def _mysql_settings() -> Settings:
    database_url = os.getenv("CQC_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("CQC_TEST_DATABASE_URL이 없어 MySQL integration test를 건너뜁니다")
    return Settings(database_url=database_url)


def test_mysql_repository_vertical_flow_and_all_seed_mappings() -> None:
    settings = _mysql_settings()
    engine = create_db_engine(settings)
    session_factory = create_session_factory(engine)
    mappings = BinMappingRepository(session_factory)
    persistence = InspectionPersistence(session_factory)
    inspection_id = f"repository-integration-{uuid4()}"

    try:
        actual_mapping = {
            (cultivar, grade, sweetness): mappings.find_normal_bin(
                crop_type="apple",
                cultivar=cultivar,
                quality_grade=grade,
                sweetness_band=sweetness,
            )
            for cultivar in ("fuji", "yanggwang")
            for grade in ("L", "M", "S")
            for sweetness in ("less_sweet", "sweet")
        }
        assert actual_mapping == DEMO_NORMAL_BIN_MAPPING
        assert mappings.find_reinspection_bin() == "TEST_REINSPECTION_BIN"

        service = InspectionService(
            MockInferenceClient(),
            MockVirtualControl(),
            cultivar_confidence_threshold=0.50,
            quality_confidence_threshold=0.50,
            inference_business_deadline_ms=500,
            late_result_manager=LateResultManager(
                hard_timeout_ms=2000,
                max_tasks=4,
            ),
            bin_mapping_repository=mappings,
            persistence=persistence,
        )
        response = asyncio.run(
            service.inspect(
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
                virtual_brix=11.9,
            )
        )

        assert response.target_bin_code == "DEMO_BIN_01"
        assert response.persistence_status == "SUCCEEDED"
        with session_factory() as session:
            inspection = session.get(Inspection, inspection_id)
            attempts = list(
                session.scalars(
                    select(ControlAttempt).where(
                        ControlAttempt.inspection_id == inspection_id
                    )
                )
            )
            assert inspection is not None
            assert inspection.source_reference is None
            assert inspection.virtual_brix is not None
            assert str(inspection.virtual_brix) == "11.9"
            assert inspection.brix_source is None
            assert inspection.brix_is_measured is False
            assert inspection.sweetness_band == "less_sweet"
            assert inspection.target_bin_code == "DEMO_BIN_01"
            assert inspection.persistence_status == "SUCCEEDED"
            assert inspection.created_at.tzinfo is None
            assert len(attempts) == 1
            assert attempts[0].attempt_no == 1
            assert attempts[0].requested_bin_code == "DEMO_BIN_01"
            assert attempts[0].requested_at.tzinfo is None
            assert attempts[0].responded_at is not None
    finally:
        with session_factory() as session, session.begin():
            session.execute(
                delete(Inspection).where(Inspection.inspection_id == inspection_id)
            )
        engine.dispose()
