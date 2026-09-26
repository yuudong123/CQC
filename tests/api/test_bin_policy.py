from __future__ import annotations

import pytest

from src.api.schemas.inference import (
    CultivarProbabilities,
    InferenceResponse,
    QualityProbabilities,
)
from src.api.schemas.inspection_results import (
    InspectionDecision,
    InspectionDecisionReason,
    InspectionStatus,
)
from src.api.services.bin_policy import (
    DEMO_NORMAL_BIN_MAPPING,
    DEMO_SWEETNESS_THRESHOLD_BRIX,
    TEMPORARY_REINSPECTION_BIN_CODE,
    determine_demo_target_bin,
    determine_target_bin,
)


def _inference_response(cultivar: str, grade: str) -> InferenceResponse:
    return InferenceResponse(
        inspection_id="inspection-bin",
        crop_type="apple",
        predicted_cultivar=cultivar,
        cultivar_confidence=0.9,
        cultivar_probabilities=CultivarProbabilities(fuji=0.9, yanggwang=0.1),
        predicted_grade=grade,
        quality_confidence=0.8,
        quality_probabilities=QualityProbabilities(L=0.8, M=0.1, S=0.1),
        inference_time_ms=12.5,
        model_name="bin-test",
        model_version="bin-test-v1",
        preprocessing_version="bin-test-v1",
        used_frame_count=1,
    )


def _decision(status: InspectionStatus) -> InspectionDecision:
    review_required = status is InspectionStatus.REINSPECTION_REQUIRED
    return InspectionDecision(
        inspection_status=status,
        review_required=review_required,
        exclude_from_normal_stats=False,
        reason=(
            InspectionDecisionReason.LOW_CULTIVAR_CONFIDENCE
            if review_required
            else InspectionDecisionReason.NORMAL
        ),
        cultivar_confidence_threshold=0.5,
        quality_confidence_threshold=0.5,
    )


@pytest.mark.parametrize(
    ("cultivar", "grade", "expected_bin"),
    [
        ("fuji", "L", "TEST_NORMAL_BIN_1"),
        ("fuji", "M", "TEST_NORMAL_BIN_2"),
        ("fuji", "S", "TEST_NORMAL_BIN_3"),
        ("yanggwang", "L", "TEST_NORMAL_BIN_4"),
        ("yanggwang", "M", "TEST_NORMAL_BIN_5"),
        ("yanggwang", "S", "TEST_NORMAL_BIN_6"),
    ],
)
def test_completed_inspection_uses_temporary_normal_mapping(
    cultivar: str,
    grade: str,
    expected_bin: str,
) -> None:
    target_bin = determine_target_bin(
        _inference_response(cultivar, grade),
        _decision(InspectionStatus.COMPLETED),
    )

    assert target_bin == expected_bin


def test_low_confidence_uses_reinspection_bin_without_normal_mapping() -> None:
    target_bin = determine_target_bin(
        _inference_response("fuji", "L"),
        _decision(InspectionStatus.REINSPECTION_REQUIRED),
    )

    assert target_bin == TEMPORARY_REINSPECTION_BIN_CODE


@pytest.mark.parametrize("cultivar", ["fuji", "yanggwang"])
@pytest.mark.parametrize("grade", ["L", "M", "S"])
def test_demo_bin_has_two_sweetness_destinations(cultivar: str, grade: str) -> None:
    response = _inference_response(cultivar, grade)
    decision = _decision(InspectionStatus.COMPLETED)
    lower = determine_demo_target_bin(response, decision, 11.9)
    upper = determine_demo_target_bin(response, decision, DEMO_SWEETNESS_THRESHOLD_BRIX)
    assert lower != upper
    assert lower == DEMO_NORMAL_BIN_MAPPING[(cultivar, grade, "less_sweet")]
    assert upper == DEMO_NORMAL_BIN_MAPPING[(cultivar, grade, "sweet")]


def test_demo_mapping_has_twelve_distinct_normal_bins() -> None:
    assert len(DEMO_NORMAL_BIN_MAPPING) == 12
    assert len(set(DEMO_NORMAL_BIN_MAPPING.values())) == 12


def test_demo_missing_brix_or_review_uses_reinspection() -> None:
    response = _inference_response("fuji", "L")
    assert (
        determine_demo_target_bin(response, _decision(InspectionStatus.COMPLETED), None)
        == TEMPORARY_REINSPECTION_BIN_CODE
    )
    assert (
        determine_demo_target_bin(
            response, _decision(InspectionStatus.REINSPECTION_REQUIRED), 14.0
        )
        == TEMPORARY_REINSPECTION_BIN_CODE
    )


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), 8.9, 18.1, True])
def test_demo_rejects_invalid_brix(invalid: float) -> None:
    with pytest.raises(ValueError):
        determine_demo_target_bin(
            _inference_response("fuji", "L"),
            _decision(InspectionStatus.COMPLETED),
            invalid,
        )
