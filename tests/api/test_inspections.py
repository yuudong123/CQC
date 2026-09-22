from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from httpx import Response

from src.api.clients.inference import MockInferenceClient
from src.api.control.virtual_control import MockVirtualControl
from src.api.core.config import Settings
from src.api.main import create_app
from src.api.schemas.inference import InferenceRequest, InferenceResponse
from src.api.services.inspections import InspectionService


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


def _metadata(
    view_indexes: list[int],
    *,
    angle_direction: str = "top",
) -> str:
    return json.dumps(
        [
            {
                "view_index": view_index,
                "angle_direction": angle_direction,
                "verticality_angle": view_index * 10 - 20,
                "horizontality_angle": view_index * 15 - 30,
            }
            for view_index in view_indexes
        ]
    )


def _images(
    count: int,
    *,
    content_type: str = "image/png",
    content: bytes = b"image-bytes",
) -> list[tuple[str, tuple[str, bytes, str]]]:
    return [
        ("images", (f"view-{index}.png", content, content_type))
        for index in range(count)
    ]


def _post(
    client: TestClient,
    *,
    files: list[tuple[str, tuple[str, bytes, str]]],
    metadata: str,
    inspection_id: str = "inspection-001",
) -> Response:
    return client.post(
        "/v1/inspections",
        data={"inspection_id": inspection_id, "metadata": metadata},
        files=files,
    )


def test_inspection_accepts_valid_multipart_contract() -> None:
    with TestClient(create_app(Settings())) as client:
        response = _post(client, files=_images(2), metadata=_metadata([0, 1]))

    assert response.status_code == 200
    assert response.json() == {
        "inspection_id": "inspection-001",
        "crop_type": "apple",
        "predicted_cultivar": "fuji",
        "cultivar_confidence": 0.9,
        "cultivar_probabilities": {"fuji": 0.9, "yanggwang": 0.1},
        "predicted_grade": "L",
        "quality_confidence": 0.8,
        "quality_probabilities": {"L": 0.8, "M": 0.1, "S": 0.1},
        "inference_time_ms": 12.5,
        "model_name": "mock-separate",
        "model_version": "mock-cqc-separate12-v1",
        "preprocessing_version": "mock-v1",
        "used_frame_count": 2,
        "inspection_status": "COMPLETED",
        "review_required": False,
        "target_bin_code": "TEST_NORMAL_BIN_1",
        "control_status": "SUCCEEDED",
    }


def test_inspection_accepts_jpeg_content_type() -> None:
    with TestClient(create_app(Settings())) as client:
        response = _post(
            client,
            files=_images(1, content_type="image/jpeg"),
            metadata=_metadata([0]),
        )

    assert response.status_code == 200


def test_inspection_accepts_twelve_images() -> None:
    with TestClient(create_app(Settings())) as client:
        response = _post(
            client,
            files=_images(12),
            metadata=_metadata(list(range(12))),
        )

    assert response.status_code == 200
    assert response.json()["used_frame_count"] == 12


def test_inspection_uses_thresholds_from_settings() -> None:
    settings = Settings(
        cultivar_confidence_threshold=0.95,
        quality_confidence_threshold=0.50,
    )
    with TestClient(create_app(settings)) as client:
        response = _post(client, files=_images(1), metadata=_metadata([0]))

    assert response.status_code == 200
    assert response.json()["inspection_status"] == "REINSPECTION_REQUIRED"
    assert response.json()["review_required"] is True
    assert response.json()["target_bin_code"] == "TEST_REINSPECTION_BIN"
    assert response.json()["control_status"] == "SUCCEEDED"


@pytest.mark.parametrize(
    "inference_client",
    [
        MismatchedResponseClient(inspection_id=True),
        MismatchedResponseClient(frame_count=True),
    ],
)
def test_inspection_returns_internal_error_for_mismatched_inference_response(
    inference_client: MockInferenceClient,
) -> None:
    service = InspectionService(
        inference_client,
        MockVirtualControl(),
        cultivar_confidence_threshold=0.50,
        quality_confidence_threshold=0.50,
    )
    with TestClient(create_app(Settings(), inspection_service=service)) as client:
        response = _post(client, files=_images(1), metadata=_metadata([0]))

    assert response.status_code == 500
    assert response.json() == {"detail": "Inference 응답 정합성 검증에 실패했습니다"}


def test_inspection_requires_at_least_one_image() -> None:
    with TestClient(create_app(Settings())) as client:
        response = client.post(
            "/v1/inspections",
            data={"inspection_id": "inspection-001", "metadata": "[]"},
        )

    assert response.status_code == 422


def test_inspection_rejects_more_than_twelve_images() -> None:
    with TestClient(create_app(Settings())) as client:
        response = _post(client, files=_images(13), metadata=_metadata(list(range(13))))

    assert response.status_code == 413


def test_inspection_rejects_mismatched_image_and_metadata_counts() -> None:
    with TestClient(create_app(Settings())) as client:
        response = _post(client, files=_images(2), metadata=_metadata([0]))

    assert response.status_code == 422


def test_inspection_rejects_duplicate_view_indexes() -> None:
    with TestClient(create_app(Settings())) as client:
        response = _post(client, files=_images(2), metadata=_metadata([0, 0]))

    assert response.status_code == 422


def test_inspection_rejects_view_indexes_out_of_order() -> None:
    with TestClient(create_app(Settings())) as client:
        response = _post(client, files=_images(2), metadata=_metadata([1, 0]))

    assert response.status_code == 422


def test_inspection_rejects_unknown_angle_direction() -> None:
    with TestClient(create_app(Settings())) as client:
        response = _post(
            client,
            files=_images(1),
            metadata=_metadata([0], angle_direction="side"),
        )

    assert response.status_code == 422


def test_inspection_rejects_invalid_metadata_json() -> None:
    with TestClient(create_app(Settings())) as client:
        response = _post(client, files=_images(1), metadata="not-json")

    assert response.status_code == 422


def test_inspection_rejects_unsupported_image_content_type() -> None:
    with TestClient(create_app(Settings())) as client:
        response = _post(
            client,
            files=_images(1, content_type="text/plain"),
            metadata=_metadata([0]),
        )

    assert response.status_code == 415


def test_inspection_rejects_request_over_configured_size_limit() -> None:
    settings = Settings(inference_max_request_bytes=256)
    with TestClient(create_app(settings)) as client:
        response = _post(
            client,
            files=_images(1, content=b"x" * 512),
            metadata=_metadata([0]),
        )

    assert response.status_code == 413
