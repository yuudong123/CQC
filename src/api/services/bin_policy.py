"""BE-04 제어 흐름 검증용 임시 bin 결정 정책."""

from __future__ import annotations

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
