"""BE-04 제어 흐름 검증용 임시 bin 결정 정책."""

from __future__ import annotations

import math

from ..schemas.inference import InferenceResponse
from ..schemas.inspection_results import InspectionDecision, InspectionStatus

# 실제 DB seed와 운영 bin code가 확정되기 전까지만 사용하는 테스트용 매핑이다.
TEMPORARY_NORMAL_BIN_MAPPING: dict[tuple[str, str], str] = {
    ("fuji", "L"): "TEST_NORMAL_BIN_1",
    ("fuji", "M"): "TEST_NORMAL_BIN_2",
    ("fuji", "S"): "TEST_NORMAL_BIN_3",
    ("yanggwang", "L"): "TEST_NORMAL_BIN_4",
    ("yanggwang", "M"): "TEST_NORMAL_BIN_5",
    ("yanggwang", "S"): "TEST_NORMAL_BIN_6",
}
TEMPORARY_REINSPECTION_BIN_CODE = "TEST_REINSPECTION_BIN"

# 시연용 12-bin 정책. 기존 6-bin Mock 흐름은 Simulator가 virtual_brix를
# 전달하기 전까지 유지하며, 통합 시 이 함수를 호출하도록 교체한다.
DEMO_SWEETNESS_THRESHOLD_BRIX = 12.0
DEMO_SWEETNESS_LABELS = ("less_sweet", "sweet")
DEMO_NORMAL_BIN_MAPPING: dict[tuple[str, str, str], str] = {
    (cultivar, grade, sweetness): f"DEMO_BIN_{index:02d}"
    for index, (cultivar, grade, sweetness) in enumerate(
        (
            (cultivar, grade, sweetness)
            for cultivar in ("fuji", "yanggwang")
            for grade in ("L", "M", "S")
            for sweetness in DEMO_SWEETNESS_LABELS
        ),
        start=1,
    )
}


def determine_demo_target_bin(
    inference_response: InferenceResponse | None,
    decision: InspectionDecision,
    virtual_brix: float | None,
) -> str:
    """품종×외관×가상 당도 12-bin, 보류/누락은 재검사 bin으로 보낸다."""

    if decision.inspection_status is InspectionStatus.REINSPECTION_REQUIRED:
        return TEMPORARY_REINSPECTION_BIN_CODE
    if inference_response is None:
        raise ValueError("정상 판정에는 Inference 응답이 필요합니다")
    if virtual_brix is None:
        return TEMPORARY_REINSPECTION_BIN_CODE
    if (
        isinstance(virtual_brix, bool)
        or not isinstance(virtual_brix, (int, float))
        or not math.isfinite(virtual_brix)
        or not 9 <= virtual_brix <= 18
    ):
        raise ValueError("시연용 virtual_brix는 9~18의 유한 숫자여야 합니다")
    sweetness = (
        "sweet" if virtual_brix >= DEMO_SWEETNESS_THRESHOLD_BRIX else "less_sweet"
    )
    key = (
        inference_response.predicted_cultivar,
        inference_response.predicted_grade,
        sweetness,
    )
    return DEMO_NORMAL_BIN_MAPPING[key]


def determine_target_bin(
    inference_response: InferenceResponse | None,
    decision: InspectionDecision,
) -> str:
    """판정 상태와 예측 조합으로 현재 요청의 목적 bin을 결정한다."""

    if decision.inspection_status is InspectionStatus.REINSPECTION_REQUIRED:
        return TEMPORARY_REINSPECTION_BIN_CODE

    if inference_response is None:
        raise ValueError("정상 판정에는 Inference 응답이 필요합니다")

    key = (
        inference_response.predicted_cultivar,
        inference_response.predicted_grade,
    )
    try:
        return TEMPORARY_NORMAL_BIN_MAPPING[key]
    except KeyError as exc:
        raise ValueError("정상 판정에 대응하는 임시 bin mapping이 없습니다") from exc
