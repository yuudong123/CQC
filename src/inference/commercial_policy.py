"""Demo-only commercial grading; not a learned model or official grade."""

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
    """Keep external review/defect holds; never invent a missing sugar value.

    severe_defect is an external inspection flag, not a v2 model output.
    Grade names may change without changing the stable L/M/S codes.
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
    brix_score = 100 if virtual_brix >= 14 else 70 if virtual_brix >= 12 else 40 if virtual_brix >= 10 else 0
    score = round(0.6 * APPEARANCE_SCORES[appearance_grade] + 0.4 * brix_score, 1)
    grade = "S"
    if score >= 90 and appearance_grade == "L" and virtual_brix >= 14:
        grade = "L"
    elif score >= 65 and appearance_grade in {"L", "M"} and virtual_brix >= 12:
        grade = "M"
    result.update(score=score, commercial_grade=grade, commercial_grade_label=names[grade])
    return result


def assess_prediction(prediction: Mapping, virtual_brix: float | None, **options) -> dict:
    """Wrap an existing v2 response without replacing its appearance prediction.

    This is a local demo envelope, NOT the /v1/predict HTTP response schema.
    The caller must propagate backend review_required into options.
    """
    return {
        "inference": dict(prediction),
        "commercial_assessment": assess_commercial_grade(prediction["predicted_grade"], virtual_brix, **options),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--appearance-grade", choices=tuple(GRADE_LABELS), required=True)
    parser.add_argument("--virtual-brix", type=float)
    parser.add_argument("--review-required", action="store_true")
    parser.add_argument("--severe-defect", action="store_true")
    args = parser.parse_args()
    print(json.dumps(assess_commercial_grade(**vars(args)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
