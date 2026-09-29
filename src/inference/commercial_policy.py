"""외관 등급과 가상 당도를 고정 정책으로 합산하는 시연용 상품등급 계산이다."""

from __future__ import annotations

import argparse
import json
import math
from collections.abc import Mapping

POLICY_VERSION = "demo-commercial-v1"
GRADE_LABELS = {"L": "특", "M": "상", "S": "보통"}
APPEARANCE_SCORES = {"L": 100, "M": 70, "S": 40}


def assess_commercial_grade(
    appearance_grade: str,
    virtual_brix: float | None,
    *,
    review_required: bool = False,
    severe_defect: bool = False,
    labels: Mapping[str, str] | None = None,
) -> dict:
    """검토·결함 보류를 유지하고, 당도가 없으면 등급을 확정하지 않는다.

    severe_defect는 외부 검사 결과이며 v2 모델의 출력이 아니다.
    L/M/S 코드는 유지하고 화면에 표시할 등급 이름만 바꿀 수 있다.
    """
    if appearance_grade not in APPEARANCE_SCORES:
        raise ValueError("appearance_grade must be L, M or S")
    names = GRADE_LABELS if labels is None else labels
    if set(names) != set(GRADE_LABELS) or any(not isinstance(v, str) or not v.strip() for v in names.values()):
        raise ValueError("labels must contain nonempty L/M/S names")
    if virtual_brix is not None:
        if isinstance(virtual_brix, bool) or not isinstance(virtual_brix, (int, float)) or not math.isfinite(virtual_brix) or not 9 <= virtual_brix <= 18:
            raise ValueError("virtual_brix must be finite and within the demo range 9..18")
    reasons = []
    if review_required:
        reasons.append("upstream_review_required")
    if severe_defect:
        reasons.append("external_severe_defect")
    if virtual_brix is None:
        reasons.append("missing_virtual_brix")
    result = {
        "policy_version": POLICY_VERSION,
        "grade_basis": "simulated_commercial_grade_not_official",
        "appearance_grade": appearance_grade,
        "virtual_brix": virtual_brix,
        "brix_is_measured": False,
        "appearance_weight": 0.6,
        "brix_weight": 0.4,
        "commercial_grade": None,
        "commercial_grade_label": None,
        "score": None,
        "review_required": bool(reasons),
        "reasons": reasons,
        "low_brix": virtual_brix is not None and virtual_brix < 10,
    }
    if reasons:
        return result
    # 시연 기획의 고정 기준으로 당도를 구간 점수화하고 외관 60%·당도 40%로 합산한다.
    brix_score = 100 if virtual_brix >= 14 else 70 if virtual_brix >= 12 else 40 if virtual_brix >= 10 else 0
    score = round(0.6 * APPEARANCE_SCORES[appearance_grade] + 0.4 * brix_score, 1)
    grade = "S"
    # 합산 점수 외에도 각 등급에 필요한 최소 외관·당도 조건을 함께 적용한다.
    if score >= 90 and appearance_grade == "L" and virtual_brix >= 14:
        grade = "L"
    elif score >= 65 and appearance_grade in {"L", "M"} and virtual_brix >= 12:
        grade = "M"
    result.update(score=score, commercial_grade=grade, commercial_grade_label=names[grade])
    return result


def assess_prediction(prediction: Mapping, virtual_brix: float | None, **options) -> dict:
    """기존 v2 예측에 시연용 상품등급 평가를 함께 묶는다.

    이 묶음은 로컬 시연용이며 /v1/predict의 HTTP 응답 형식과는 다르다.
    호출 측은 백엔드의 review_required 상태를 options로 전달해야 한다.
    """
    return {
        "inference": dict(prediction),
        "commercial_assessment": assess_commercial_grade(prediction["predicted_grade"], virtual_brix, **options),
    }


def main():
    """실행 인자를 읽고 다음 작업을 수행한다: 외관 등급과 가상 당도를 고정 정책으로 합산하는 시연용 상품등급 계산이다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--appearance-grade", choices=tuple(GRADE_LABELS), required=True)
    parser.add_argument("--virtual-brix", type=float)
    parser.add_argument("--review-required", action="store_true")
    parser.add_argument("--severe-defect", action="store_true")
    args = parser.parse_args()
    print(json.dumps(assess_commercial_grade(**vars(args)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
