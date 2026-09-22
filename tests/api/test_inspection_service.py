from __future__ import annotations

import asyncio
from io import BytesIO

import pytest
from fastapi import UploadFile

from src.api.clients.inference import MockInferenceClient
from src.api.schemas.inference import InferenceRequest, InferenceResponse
from src.api.schemas.inspections import InspectionImageMetadata
from src.api.services.inspections import (
    InferenceResponseMismatchError,
    InspectionService,
)


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
            cultivar_confidence_threshold=0.50,
            quality_confidence_threshold=0.50,
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
        cultivar_confidence_threshold=0.50,
        quality_confidence_threshold=0.50,
    )

    with pytest.raises(InferenceResponseMismatchError, match=message):
        asyncio.run(
            service.inspect(
                inspection_id="inspection-service",
                images=_images(1),
                metadata=_metadata(1),
            )
        )
