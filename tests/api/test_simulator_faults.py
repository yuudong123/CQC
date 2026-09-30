"""Simulator 전용 장애가 검사 정책과 장애 이미지로 이어지는지 검증한다."""

from __future__ import annotations

import asyncio
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

from src.api.clients.inference import MockInferenceClient
from src.api.control.virtual_control import MockVirtualControl
from src.api.schemas.inspection_results import (
    ControlStatus,
    InspectionDecisionReason,
    PersistenceStatus,
)
from src.api.schemas.inspections import InspectionImageMetadata
from src.api.services.fault_image_storage import FaultImageStorage
from src.api.services.inspections import InspectionService
from src.api.services.late_results import LateResultManager

from .fakes import FakeBinMappingRepository, RecordingPersistence

PNG = b"\x89PNG\r\n\x1a\n" + b"sample"


@pytest.mark.parametrize(
    "fault,internal_reason,expected_reason,has_image",
    [
        ("INFERENCE_TIMEOUT", None, "INFERENCE_DEADLINE_EXCEEDED", True),
        ("INFERENCE_ERROR", None, "INFERENCE_HTTP_ERROR", True),
        (
            None,
            InspectionDecisionReason.INFERENCE_CONNECTION_ERROR,
            "INFERENCE_CONNECTION_ERROR",
            True,
        ),
        (
            None,
            InspectionDecisionReason.INFERENCE_INVALID_RESPONSE,
            "INFERENCE_INVALID_RESPONSE",
            True,
        ),
        ("DB_ERROR", None, "NORMAL", False),
        ("CONTROL_REJECTED", None, "NORMAL", False),
        ("CONTROL_NO_RESPONSE", None, "NORMAL", False),
        ("CONTROL_FAILED", None, "NORMAL", False),
    ],
)
def test_fault_injection_is_request_local_and_retains_only_inference_images(
    fault: str | None,
    internal_reason: InspectionDecisionReason | None,
    expected_reason: str,
    has_image: bool,
) -> None:
    with TemporaryDirectory(prefix="cqc-simulator-fault-", dir=Path.cwd()) as temporary:
        storage = FaultImageStorage(Path(temporary), limit=100)
        persistence = RecordingPersistence()
        service = InspectionService(
            MockInferenceClient(),
            MockVirtualControl(),
            cultivar_confidence_threshold=0.5,
            quality_confidence_threshold=0.5,
            inference_business_deadline_ms=500,
            late_result_manager=LateResultManager(hard_timeout_ms=2000, max_tasks=4),
            bin_mapping_repository=FakeBinMappingRepository(),
            persistence=persistence,
            fault_image_storage=storage,
        )

        async def inspect() -> None:
            image = UploadFile(
                file=BytesIO(PNG),
                filename="frame.png",
                headers=Headers({"content-type": "image/png"}),
            )
            try:
                result = await service.inspect(
                    inspection_id="simulator-fault-1",
                    images=[image],
                    metadata=[
                        InspectionImageMetadata(
                            view_index=0,
                            angle_direction="top",
                            verticality_angle=0,
                            horizontality_angle=0,
                        )
                    ],
                    virtual_brix=14.0,
                    simulator_faults=(fault,) if fault else (),
                    injected_inference_reason=internal_reason,
                    source_reference="demo-1",
                )
                assert result.decision_reason.value == expected_reason
                assert result.persistence_status is (
                    PersistenceStatus.FAILED
                    if fault == "DB_ERROR"
                    else PersistenceStatus.SUCCEEDED
                )
                if fault == "CONTROL_NO_RESPONSE":
                    assert result.control_status is ControlStatus.NO_RESPONSE
                if fault == "CONTROL_FAILED":
                    assert result.control_status is ControlStatus.FAILED
                assert len(storage.list_images()) == int(has_image)
                if fault != "DB_ERROR":
                    assert persistence.pending_values[0]["source_reference"] == "demo-1"
            finally:
                await image.close()
                await service.shutdown()

        asyncio.run(inspect())
