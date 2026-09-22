from __future__ import annotations

import asyncio
import json
from io import BytesIO

import pytest
from fastapi import UploadFile
from fastapi.testclient import TestClient

from src.api.clients.inference import MockInferenceClient
from src.api.control.virtual_control import MockVirtualControl
from src.api.core.config import Settings
from src.api.main import create_app
from src.api.schemas.inspections import InspectionImageMetadata
from src.api.services.inspections import InspectionService
from src.api.services.late_results import LateResultManager


def _upload_files() -> list[UploadFile]:
    return [UploadFile(file=BytesIO(b"image"), filename="view-0.png")]


def _metadata_items() -> list[InspectionImageMetadata]:
    return [
        InspectionImageMetadata(
            view_index=0,
            angle_direction="top",
            verticality_angle=0,
            horizontality_angle=0,
        )
    ]


def _service(
    manager: LateResultManager,
    *,
    response_delay_ms: int,
    business_deadline_ms: int,
    cultivar_threshold: float = 0.50,
) -> tuple[InspectionService, MockVirtualControl]:
    control = MockVirtualControl()
    return (
        InspectionService(
            MockInferenceClient(response_delay_ms=response_delay_ms),
            control,
            cultivar_confidence_threshold=cultivar_threshold,
            quality_confidence_threshold=0.50,
            inference_business_deadline_ms=business_deadline_ms,
            late_result_manager=manager,
        ),
        control,
    )


@pytest.mark.parametrize("cultivar_threshold", [0.50, 0.95])
def test_response_before_business_deadline_creates_no_late_task(
    cultivar_threshold: float,
) -> None:
    async def run() -> tuple[int, int]:
        manager = LateResultManager(hard_timeout_ms=200, max_tasks=4)
        service, _ = _service(
            manager,
            response_delay_ms=1,
            business_deadline_ms=100,
            cultivar_threshold=cultivar_threshold,
        )
        await service.inspect(
            inspection_id="inspection-in-deadline",
            images=_upload_files(),
            metadata=_metadata_items(),
        )
        return manager.active_count, len(manager.results)

    active_count, result_count = asyncio.run(run())

    assert active_count == 0
    assert result_count == 0


@pytest.mark.parametrize("cultivar_threshold", [0.50, 0.95])
def test_late_result_is_diagnostic_only_and_does_not_change_decision(
    cultivar_threshold: float,
) -> None:
    async def run() -> tuple[
        dict[str, object], dict[str, object], LateResultManager, int
    ]:
        manager = LateResultManager(hard_timeout_ms=200, max_tasks=4)
        service, control = _service(
            manager,
            response_delay_ms=30,
            business_deadline_ms=1,
            cultivar_threshold=cultivar_threshold,
        )
        response = await service.inspect(
            inspection_id="inspection-late-result",
            images=_upload_files(),
            metadata=_metadata_items(),
        )
        before_late_result = response.model_dump()
        assert manager.active_count == 1
        await manager.wait_until_idle()
        return before_late_result, response.model_dump(), manager, len(control.requests)

    before, after, manager, control_request_count = asyncio.run(run())

    assert before == after
    assert after["inspection_status"] == "REINSPECTION_REQUIRED"
    assert after["decision_reason"] == "INFERENCE_DEADLINE_EXCEEDED"
    assert after["target_bin_code"] == "TEST_REINSPECTION_BIN"
    assert after["control_status"] == "SUCCEEDED"
    assert control_request_count == 1
    assert len(manager.results) == 1
    assert manager.results[0].inspection_id == "inspection-late-result"
    assert manager.results[0].is_late is True
    assert manager.results[0].inference_response.cultivar_confidence == 0.9


def test_late_task_is_cancelled_at_hard_timeout() -> None:
    async def run() -> tuple[dict[str, object], LateResultManager]:
        manager = LateResultManager(hard_timeout_ms=10, max_tasks=4)
        service, _ = _service(
            manager,
            response_delay_ms=100,
            business_deadline_ms=1,
        )
        response = await service.inspect(
            inspection_id="inspection-hard-timeout",
            images=_upload_files(),
            metadata=_metadata_items(),
        )
        await manager.wait_until_idle()
        return response.model_dump(), manager

    response, manager = asyncio.run(run())

    assert response["decision_reason"] == "INFERENCE_DEADLINE_EXCEEDED"
    assert response["target_bin_code"] == "TEST_REINSPECTION_BIN"
    assert manager.results == []
    assert manager.hard_timeout_inspection_ids == ["inspection-hard-timeout"]
    assert manager.active_count == 0


def test_late_task_limit_drops_only_additional_diagnostics() -> None:
    async def run() -> tuple[list[dict[str, object]], LateResultManager]:
        manager = LateResultManager(hard_timeout_ms=200, max_tasks=1)
        service, _ = _service(
            manager,
            response_delay_ms=30,
            business_deadline_ms=1,
        )
        responses = []
        for inspection_id in ("inspection-tracked", "inspection-dropped"):
            response = await service.inspect(
                inspection_id=inspection_id,
                images=_upload_files(),
                metadata=_metadata_items(),
            )
            responses.append(response.model_dump())
        await manager.wait_until_idle()
        return responses, manager

    responses, manager = asyncio.run(run())

    assert all(
        response["decision_reason"] == "INFERENCE_DEADLINE_EXCEEDED"
        for response in responses
    )
    assert all(
        response["target_bin_code"] == "TEST_REINSPECTION_BIN" for response in responses
    )
    assert manager.dropped_inspection_ids == ["inspection-dropped"]
    assert [result.inspection_id for result in manager.results] == [
        "inspection-tracked"
    ]


def test_fastapi_shutdown_cleans_up_remaining_late_task() -> None:
    manager = LateResultManager(hard_timeout_ms=1000, max_tasks=4)
    service, _ = _service(
        manager,
        response_delay_ms=500,
        business_deadline_ms=1,
    )
    application = create_app(Settings(), inspection_service=service)
    metadata = json.dumps(
        [
            {
                "view_index": 0,
                "angle_direction": "top",
                "verticality_angle": 0,
                "horizontality_angle": 0,
            }
        ]
    )

    with TestClient(application) as client:
        response = client.post(
            "/v1/inspections",
            data={"inspection_id": "inspection-shutdown", "metadata": metadata},
            files=[("images", ("view-0.png", b"image", "image/png"))],
        )
        assert response.status_code == 200
        assert manager.active_count == 1

    assert manager.active_count == 0
    assert manager.results == []
