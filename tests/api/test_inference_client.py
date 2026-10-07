import asyncio
from dataclasses import asdict

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


@pytest.mark.parametrize(
    ("inference_time_ms", "valid"),
    [
        pytest.param(12.5, True, id="positive"),
        pytest.param(0.0, True, id="zero"),
        pytest.param(float("inf"), False, id="infinity"),
        pytest.param(float("nan"), False, id="nan"),
        pytest.param(float("-inf"), False, id="negative-infinity"),
        pytest.param(-1.0, False, id="negative"),
    ],
)
def test_response_requires_finite_nonnegative_inference_time(
    inference_time_ms: float, valid: bool
) -> None:
    payload = _predict(_request(1)).model_dump()
    payload["inference_time_ms"] = inference_time_ms

    if valid:
        assert InferenceResponse.model_validate(payload).inference_time_ms == (
            inference_time_ms
        )
    else:
        with pytest.raises(ValidationError) as exc_info:
            InferenceResponse.model_validate(payload)
        assert {error["loc"] for error in exc_info.value.errors()} == {
            ("inference_time_ms",)
        }


@pytest.mark.parametrize("task", ["cultivar", "quality"])
@pytest.mark.parametrize(
    ("probabilities", "prediction_index", "confidence", "valid"),
    [
        pytest.param((0.7, 0.3), 0, 0.7, True, id="normal"),
        pytest.param((0.7, 0.299), 0, 0.7, True, id="sum-lower-bound"),
        pytest.param((0.7, 0.301), 0, 0.7, True, id="sum-upper-bound"),
        pytest.param((0.7, 0.298), 0, 0.7, False, id="sum-too-low"),
        pytest.param((0.7, 0.302), 0, 0.7, False, id="sum-too-high"),
        pytest.param((0.7, 0.3), 0, 0.7000005, True, id="confidence-within"),
        pytest.param((0.7, 0.3), 0, 0.700001, True, id="confidence-upper-bound"),
        pytest.param((0.7, 0.3), 0, 0.699999, True, id="confidence-lower-bound"),
        pytest.param((0.7, 0.3), 0, 0.7000011, False, id="confidence-too-high"),
        pytest.param((0.7, 0.3), 0, 0.6999989, False, id="confidence-too-low"),
        pytest.param((0.2, 0.8), 0, 0.8, False, id="prediction-mismatch"),
        pytest.param((0.5, 0.5), 0, 0.5, True, id="tie-first"),
        pytest.param((0.5, 0.5), 1, 0.5, True, id="tie-second"),
        pytest.param(
            (0.4999999, 0.5000001), 0, 0.5000001, False, id="near-tie-is-not-tie"
        ),
    ],
)
def test_response_validates_prediction_consistency_without_changing_values(
    task: str,
    probabilities: tuple[float, float],
    prediction_index: int,
    confidence: float,
    valid: bool,
) -> None:
    payload = _predict(_request(1)).model_dump()
    labels = ("fuji", "yanggwang") if task == "cultivar" else ("L", "M", "S")
    values = probabilities if task == "cultivar" else (*probabilities, 0.0)
    payload[f"{task}_probabilities"] = dict(zip(labels, values, strict=True))
    payload[f"{task}_confidence"] = confidence
    prediction_field = "predicted_cultivar" if task == "cultivar" else "predicted_grade"
    payload[prediction_field] = labels[prediction_index]

    if valid:
        assert InferenceResponse.model_validate(payload).model_dump() == payload
    else:
        with pytest.raises(ValidationError):
            InferenceResponse.model_validate(payload)


@pytest.mark.parametrize("prediction", ["L", "M", "S"])
def test_quality_prediction_accepts_only_exact_maximum_ties(prediction: str) -> None:
    payload = _predict(_request(1)).model_dump()
    payload.update(
        predicted_grade=prediction,
        quality_confidence=0.4,
        quality_probabilities={"L": 0.4, "M": 0.4, "S": 0.2},
    )
    if prediction in ("L", "M"):
        assert InferenceResponse.model_validate(payload).model_dump() == payload
    else:
        with pytest.raises(ValidationError):
            InferenceResponse.model_validate(payload)


def test_predictor_output_satisfies_backend_response_validation() -> None:
    pytest.importorskip("torch")
    pytest.importorskip("torchvision")
    from tests.test_inference_predictor import PredictorTest, _png

    predictor = PredictorTest()._predictor()
    payload = asdict(predictor.predict([_png()]))
    payload["inspection_id"] = "predictor-validation"
    assert InferenceResponse.model_validate(payload).model_dump() == payload
