from __future__ import annotations

import asyncio
from io import BytesIO

import pytest
from fastapi import UploadFile

from src.api.clients.inference import MockInferenceClient
from src.api.control.virtual_control import MockVirtualControl
from src.api.schemas.inference import InferenceRequest, InferenceResponse
from src.api.schemas.inspection_results import ControlStatus
from src.api.schemas.inspections import InspectionImageMetadata
from src.api.services.inspections import (
    InferenceResponseMismatchError,
    InspectionService,
)
from src.api.services.late_results import LateResultManager


class RecordingInferenceClient(MockInferenceClient):
    def __init__(self) -> None:
        self.request: InferenceRequest | None = None

    async def predict(self, request: InferenceRequest) -> InferenceResponse:
        self.request = request
        return await super().predict(request)


class MismatchedResponseClient(MockInferenceClient):
    def __init__(
        self, *, inspection_id: bool = False, frame_count: bool = False
    ) -> None:
        self._mismatch_inspection_id = inspection_id
        self._mismatch_frame_count = frame_count

    async def predict(self, request: InferenceRequest) -> InferenceResponse:
        response = await super().predict(request)
        if self._mismatch_inspection_id:
            response = response.model_copy(update={"inspection_id": "different-id"})
        if self._mismatch_frame_count:
            response = response.model_copy(update={"used_frame_count": 12})
        return response


def _images(count: int) -> list[UploadFile]:
    return [
        UploadFile(
            file=BytesIO(f"image-{index}".encode()),
            filename=f"view-{index}.png",
        )
        for index in range(count)
    ]


def _metadata(count: int) -> list[InspectionImageMetadata]:
    return [
        InspectionImageMetadata(
            view_index=index,
            angle_direction="top" if index % 2 == 0 else "bottom",
            verticality_angle=index,
            horizontality_angle=index * 10,
        )
        for index in range(count)
    ]


def _late_result_manager(
    *,
    hard_timeout_ms: int = 2000,
    max_tasks: int = 4,
) -> LateResultManager:
    return LateResultManager(
        hard_timeout_ms=hard_timeout_ms,
        max_tasks=max_tasks,
    )


@pytest.mark.parametrize("image_count", [1, 12])
def test_service_preserves_request_and_returns_mock_result(image_count: int) -> None:
    async def run() -> tuple[
        InferenceResponse,
        RecordingInferenceClient,
        list[UploadFile],
        list[InspectionImageMetadata],
    ]:
        client = RecordingInferenceClient()
        service = InspectionService(
            client,
            MockVirtualControl(),
            cultivar_confidence_threshold=0.50,
            quality_confidence_threshold=0.50,
            inference_business_deadline_ms=500,
            late_result_manager=_late_result_manager(),
        )
        images = _images(image_count)
        metadata = _metadata(image_count)
        response = await service.inspect(
            inspection_id="inspection-service",
            images=images,
            metadata=metadata,
        )
        return response, client, images, metadata

    response, client, images, metadata = asyncio.run(run())

    assert response.inspection_id == "inspection-service"
    assert response.used_frame_count == image_count
    assert response.predicted_cultivar == "fuji"
    assert response.predicted_grade == "L"
    assert response.inspection_status == "COMPLETED"
    assert response.review_required is False
    assert response.exclude_from_normal_stats is False
    assert response.decision_reason == "NORMAL"
    assert response.target_bin_code == "TEST_NORMAL_BIN_1"
    assert response.control_status == "SUCCEEDED"
    assert client.request is not None
    assert client.request.images == [
        f"image-{index}".encode() for index in range(image_count)
    ]
    assert [item.model_dump() for item in client.request.metadata] == [
        item.model_dump() for item in metadata
    ]

    async def read_again() -> list[bytes]:
        return [await image.read() for image in images]

    assert asyncio.run(read_again()) == client.request.images


@pytest.mark.parametrize(
    ("client", "message"),
    [
        (
            MismatchedResponseClient(inspection_id=True),
            "inspection_id",
        ),
        (
            MismatchedResponseClient(frame_count=True),
            "used_frame_count",
        ),
    ],
)
def test_service_rejects_mismatched_inference_response(
    client: MockInferenceClient,
    message: str,
) -> None:
    service = InspectionService(
        client,
        MockVirtualControl(),
        cultivar_confidence_threshold=0.50,
        quality_confidence_threshold=0.50,
        inference_business_deadline_ms=500,
        late_result_manager=_late_result_manager(),
    )

    with pytest.raises(InferenceResponseMismatchError, match=message):
        asyncio.run(
            service.inspect(
                inspection_id="inspection-service",
                images=_images(1),
                metadata=_metadata(1),
            )
        )


def test_service_falls_back_once_after_normal_bin_rejection() -> None:
    control = MockVirtualControl([ControlStatus.REJECTED, ControlStatus.SUCCEEDED])
    service = InspectionService(
        MockInferenceClient(),
        control,
        cultivar_confidence_threshold=0.50,
        quality_confidence_threshold=0.50,
        inference_business_deadline_ms=500,
        late_result_manager=_late_result_manager(),
    )

    response = asyncio.run(
        service.inspect(
            inspection_id="inspection-control-fallback",
            images=_images(1),
            metadata=_metadata(1),
        )
    )

    assert response.target_bin_code == "TEST_REINSPECTION_BIN"
    assert response.control_status is ControlStatus.SUCCEEDED
    assert [request.target_bin_code for request in control.requests] == [
        "TEST_NORMAL_BIN_1",
        "TEST_REINSPECTION_BIN",
    ]


def test_service_accepts_delayed_response_well_before_deadline() -> None:
    service = InspectionService(
        MockInferenceClient(response_delay_ms=1),
        MockVirtualControl(),
        cultivar_confidence_threshold=0.50,
        quality_confidence_threshold=0.50,
        inference_business_deadline_ms=100,
        late_result_manager=_late_result_manager(),
    )

    response = asyncio.run(
        service.inspect(
            inspection_id="inspection-before-deadline",
            images=_images(1),
            metadata=_metadata(1),
        )
    )

    assert response.inspection_status == "COMPLETED"
    assert response.decision_reason == "NORMAL"
    assert response.exclude_from_normal_stats is False


def test_service_does_not_retry_failed_direct_reinspection() -> None:
    control = MockVirtualControl([ControlStatus.FAILED])
    service = InspectionService(
        MockInferenceClient(response_delay_ms=1),
        control,
        cultivar_confidence_threshold=0.95,
        quality_confidence_threshold=0.50,
        inference_business_deadline_ms=100,
        late_result_manager=_late_result_manager(),
    )

    response = asyncio.run(
        service.inspect(
            inspection_id="inspection-direct-reinspection",
            images=_images(1),
            metadata=_metadata(1),
        )
    )

    assert response.inspection_status == "REINSPECTION_REQUIRED"
    assert response.review_required is True
    assert response.exclude_from_normal_stats is False
    assert response.decision_reason == "LOW_CULTIVAR_CONFIDENCE"
    assert response.target_bin_code == "TEST_REINSPECTION_BIN"
    assert response.control_status is ControlStatus.FAILED
    assert len(control.requests) == 1


@pytest.mark.parametrize(
    "control_outcome",
    [
        ControlStatus.SUCCEEDED,
        ControlStatus.REJECTED,
        ControlStatus.NO_RESPONSE,
        ControlStatus.FAILED,
    ],
)
def test_service_timeout_uses_reinspection_bin_without_retry(
    control_outcome: ControlStatus,
) -> None:
    control = MockVirtualControl([control_outcome])
    service = InspectionService(
        MockInferenceClient(response_delay_ms=50),
        control,
        cultivar_confidence_threshold=0.50,
        quality_confidence_threshold=0.50,
        inference_business_deadline_ms=1,
        late_result_manager=_late_result_manager(),
    )

    response = asyncio.run(
        service.inspect(
            inspection_id="inspection-timeout",
            images=_images(1),
            metadata=_metadata(1),
        )
    )

    assert response.inspection_id == "inspection-timeout"
    assert response.inspection_status == "REINSPECTION_REQUIRED"
    assert response.review_required is True
    assert response.exclude_from_normal_stats is True
    assert response.decision_reason == "INFERENCE_DEADLINE_EXCEEDED"
    assert response.predicted_cultivar is None
    assert response.predicted_grade is None
    assert response.used_frame_count is None
    assert response.target_bin_code == "TEST_REINSPECTION_BIN"
    assert response.control_status is control_outcome
    assert len(control.requests) == 1
