import asyncio

import pytest
from pydantic import ValidationError

from src.api.clients.inference import MockInferenceClient
from src.api.schemas.inference import InferenceRequest, InferenceResponse
from src.api.schemas.inspections import InspectionImageMetadata


def _request(
    image_count: int, *, inspection_id: str = "inspection-001"
) -> InferenceRequest:
    return InferenceRequest(
        inspection_id=inspection_id,
        images=[f"image-{index}".encode() for index in range(image_count)],
        metadata=[
            InspectionImageMetadata(
                view_index=index,
                angle_direction="top" if index % 2 == 0 else "bottom",
                verticality_angle=index,
                horizontality_angle=index * 10,
            )
            for index in range(image_count)
        ],
    )


def _predict(request: InferenceRequest) -> InferenceResponse:
    return asyncio.run(MockInferenceClient().predict(request))


@pytest.mark.parametrize("image_count", [1, 12])
def test_mock_uses_request_identifier_and_actual_image_count(image_count: int) -> None:
    request = _request(image_count, inspection_id=f"inspection-{image_count}")

    response = _predict(request)

    assert response.inspection_id == request.inspection_id
    assert response.used_frame_count == image_count


def test_mock_returns_valid_prediction_contract() -> None:
    response = _predict(_request(2))

    assert response.crop_type == "apple"
    assert response.predicted_cultivar == "fuji"
    assert response.cultivar_confidence == 0.9
    assert response.cultivar_probabilities.model_dump() == {
        "fuji": 0.9,
        "yanggwang": 0.1,
    }
    assert response.predicted_grade == "L"
    assert response.quality_confidence == 0.8
    assert response.quality_probabilities.model_dump() == {
        "L": 0.8,
        "M": 0.1,
        "S": 0.1,
    }
    assert response.inference_time_ms == 12.5
    assert response.model_name == "mock-separate"
    assert response.model_version == "mock-cqc-separate12-v1"
    assert response.preprocessing_version == "mock-v1"


def test_mock_does_not_change_metadata_order_or_values() -> None:
    request = _request(3)
    metadata_before = [item.model_dump() for item in request.metadata]

    _predict(request)

    assert [item.model_dump() for item in request.metadata] == metadata_before
    assert [item.view_index for item in request.metadata] == [0, 1, 2]


def test_mock_result_is_deterministic() -> None:
    request = _request(4)

    first = _predict(request)
    second = _predict(request)

    assert first == second


def test_request_rejects_mismatched_image_and_metadata_counts() -> None:
    with pytest.raises(ValidationError, match="images와 metadata 개수"):
        InferenceRequest(
            inspection_id="inspection-invalid-count",
            images=[b"first", b"second"],
            metadata=[
                InspectionImageMetadata(
                    view_index=0,
                    angle_direction="top",
                    verticality_angle=0,
                    horizontality_angle=0,
                )
            ],
        )


def test_request_rejects_reordered_view_indexes() -> None:
    with pytest.raises(ValidationError, match="view_index"):
        InferenceRequest(
            inspection_id="inspection-reordered",
            images=[b"first", b"second"],
            metadata=[
                InspectionImageMetadata(
                    view_index=1,
                    angle_direction="top",
                    verticality_angle=0,
                    horizontality_angle=0,
                ),
                InspectionImageMetadata(
                    view_index=0,
                    angle_direction="bottom",
                    verticality_angle=1,
                    horizontality_angle=10,
                ),
            ],
        )


def test_request_rejects_more_than_twelve_images() -> None:
    with pytest.raises(ValidationError, match="at most 12"):
        _request(13)


def test_response_rejects_invalid_prediction_confidence_and_frame_count() -> None:
    valid = _predict(_request(1)).model_dump()
    valid["predicted_cultivar"] = "unknown"
    valid["predicted_grade"] = "unknown"
    valid["cultivar_confidence"] = 1.1
    valid["quality_confidence"] = -0.1
    valid["used_frame_count"] = 0

    with pytest.raises(ValidationError) as exc_info:
        InferenceResponse.model_validate(valid)

    error_fields = {error["loc"] for error in exc_info.value.errors()}
    assert ("predicted_cultivar",) in error_fields
    assert ("predicted_grade",) in error_fields
    assert ("cultivar_confidence",) in error_fields
    assert ("quality_confidence",) in error_fields
    assert ("used_frame_count",) in error_fields
