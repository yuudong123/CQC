"""Inference 정상 응답에 적용하는 검사 판정 정책."""

from __future__ import annotations

from ..schemas.inference import InferenceResponse
from ..schemas.inspection_results import (
    InspectionDecision,
    InspectionDecisionReason,
    InspectionStatus,
)


def decide_inspection(
    inference_response: InferenceResponse,
    *,
    cultivar_confidence_threshold: float,
    quality_confidence_threshold: float,
) -> InspectionDecision:
    """품종·품질 confidence를 설정 threshold와 비교해 검사 결과를 판정한다."""

    low_cultivar = (
        inference_response.cultivar_confidence < cultivar_confidence_threshold
    )
    low_quality = inference_response.quality_confidence < quality_confidence_threshold

    if low_cultivar and low_quality:
        reason = InspectionDecisionReason.LOW_BOTH_CONFIDENCE
    elif low_cultivar:
        reason = InspectionDecisionReason.LOW_CULTIVAR_CONFIDENCE
    elif low_quality:
        reason = InspectionDecisionReason.LOW_QUALITY_CONFIDENCE
    else:
        reason = InspectionDecisionReason.NORMAL

    review_required = low_cultivar or low_quality
    return InspectionDecision(
        inspection_status=(
            InspectionStatus.REINSPECTION_REQUIRED
            if review_required
            else InspectionStatus.COMPLETED
        ),
        review_required=review_required,
        # 저신뢰도 유효한 모델 응답이므로 정상 품종·품질 통계에는 포함한다.
        exclude_from_normal_stats=False,
        reason=reason,
        cultivar_confidence_threshold=cultivar_confidence_threshold,
        quality_confidence_threshold=quality_confidence_threshold,
    )


def decide_inference_timeout(
    *,
    cultivar_confidence_threshold: float,
    quality_confidence_threshold: float,
) -> InspectionDecision:
    """Business deadline 안에 응답하지 못한 검사를 재검사 대상으로 판정한다."""

    return InspectionDecision(
        inspection_status=InspectionStatus.REINSPECTION_REQUIRED,
        review_required=True,
        exclude_from_normal_stats=True,
        reason=InspectionDecisionReason.INFERENCE_DEADLINE_EXCEEDED,
        cultivar_confidence_threshold=cultivar_confidence_threshold,
        quality_confidence_threshold=quality_confidence_threshold,
    )
