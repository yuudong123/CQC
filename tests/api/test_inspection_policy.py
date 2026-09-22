from __future__ import annotations

import pytest

from src.api.schemas.inference import (
    CultivarProbabilities,
    InferenceResponse,
    QualityProbabilities,
)
from src.api.schemas.inspection_results import (
    ControlStatus,
    InspectionDecisionReason,
    InspectionStatus,
    PersistenceStatus,
)
from src.api.services.inspection_policy import (
    decide_inference_timeout,
    decide_inspection,
)


def _inference_response(
    *,
    cultivar_confidence: float,
    quality_confidence: float,
) -> InferenceResponse:
    return InferenceResponse(
        inspection_id="inspection-policy",
        crop_type="apple",
        predicted_cultivar="fuji",
        cultivar_confidence=cultivar_confidence,
        cultivar_probabilities=CultivarProbabilities(
            fuji=cultivar_confidence,
            yanggwang=1 - cultivar_confidence,
        ),
        predicted_grade="L",
        quality_confidence=quality_confidence,
        quality_probabilities=QualityProbabilities(
            L=quality_confidence,
            M=(1 - quality_confidence) / 2,
            S=(1 - quality_confidence) / 2,
        ),
        inference_time_ms=12.5,
        model_name="policy-test",
        model_version="policy-test-v1",
        preprocessing_version="policy-test-v1",
        used_frame_count=1,
    )


@pytest.mark.parametrize(
    (
        "cultivar_confidence",
        "quality_confidence",
        "expected_status",
        "expected_reason",
        "expected_review",
    ),
    [
        (
            0.90,
            0.80,
            InspectionStatus.COMPLETED,
            InspectionDecisionReason.NORMAL,
            False,
        ),
        (
            0.49,
            0.80,
            InspectionStatus.REINSPECTION_REQUIRED,
            InspectionDecisionReason.LOW_CULTIVAR_CONFIDENCE,
            True,
        ),
        (
            0.90,
            0.49,
            InspectionStatus.REINSPECTION_REQUIRED,
            InspectionDecisionReason.LOW_QUALITY_CONFIDENCE,
            True,
        ),
        (
            0.49,
            0.49,
            InspectionStatus.REINSPECTION_REQUIRED,
            InspectionDecisionReason.LOW_BOTH_CONFIDENCE,
            True,
        ),
        (
            0.50,
            0.50,
            InspectionStatus.COMPLETED,
            InspectionDecisionReason.NORMAL,
            False,
        ),
    ],
)
def test_decide_inspection_applies_confidence_policy(
    cultivar_confidence: float,
    quality_confidence: float,
    expected_status: InspectionStatus,
    expected_reason: InspectionDecisionReason,
    expected_review: bool,
) -> None:
    decision = decide_inspection(
        _inference_response(
            cultivar_confidence=cultivar_confidence,
            quality_confidence=quality_confidence,
        ),
        cultivar_confidence_threshold=0.50,
        quality_confidence_threshold=0.50,
    )

    assert decision.inspection_status is expected_status
    assert decision.reason is expected_reason
    assert decision.review_required is expected_review
    assert decision.exclude_from_normal_stats is False
    assert decision.cultivar_confidence_threshold == 0.50
    assert decision.quality_confidence_threshold == 0.50


def test_decide_inspection_uses_configurable_thresholds() -> None:
    response = _inference_response(
        cultivar_confidence=0.90,
        quality_confidence=0.80,
    )

    normal = decide_inspection(
        response,
        cultivar_confidence_threshold=0.50,
        quality_confidence_threshold=0.50,
    )
    low_quality = decide_inspection(
        response,
        cultivar_confidence_threshold=0.50,
        quality_confidence_threshold=0.85,
    )

    assert normal.inspection_status is InspectionStatus.COMPLETED
    assert low_quality.inspection_status is InspectionStatus.REINSPECTION_REQUIRED
    assert low_quality.reason is InspectionDecisionReason.LOW_QUALITY_CONFIDENCE


def test_decide_inference_timeout_is_excluded_from_normal_stats() -> None:
    decision = decide_inference_timeout(
        cultivar_confidence_threshold=0.50,
        quality_confidence_threshold=0.50,
    )

    assert decision.inspection_status is InspectionStatus.REINSPECTION_REQUIRED
    assert decision.review_required is True
    assert decision.exclude_from_normal_stats is True
    assert decision.reason is InspectionDecisionReason.INFERENCE_DEADLINE_EXCEEDED


def test_status_values_remain_varchar_compatible_strings() -> None:
    assert isinstance(InspectionStatus.PROCESSING, str)
    assert InspectionStatus.PROCESSING.value == "PROCESSING"
    assert ControlStatus.NOT_REQUESTED.value == "NOT_REQUESTED"
    assert PersistenceStatus.NOT_ATTEMPTED.value == "NOT_ATTEMPTED"
