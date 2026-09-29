"""저장된 검사 이력을 Frontend 관제 Result 계약으로 변환한다."""

from __future__ import annotations

from datetime import timedelta, timezone

from ..db.models import Inspection

KST = timezone(timedelta(hours=9))
_CULTIVARS = {"fuji": "부사", "yanggwang": "양광"}
_GRADES = {"L": "특", "M": "상", "S": "보통"}
_ERRORS = {
    "INFERENCE_DEADLINE_EXCEEDED": "INFERENCE_TIMEOUT",
    "INFERENCE_CONNECTION_ERROR": "INFERENCE_ERROR",
    "INFERENCE_HTTP_ERROR": "INFERENCE_ERROR",
    "INFERENCE_INVALID_RESPONSE": "INFERENCE_ERROR",
    "INFERENCE_ERROR": "INFERENCE_ERROR",
    "BIN_MAPPING_CONFIGURATION_ERROR": "DB_ERROR",
    "DB_PERSISTENCE_ERROR": "DB_ERROR",
    "CONTROL_REJECTED": "CONTROL_REJECTED",
    "CONTROL_NO_RESPONSE": "CONTROL_NO_RESPONSE",
    "CONTROL_FAILED": "CONTROL_FAILED",
}


class HistoryContractError(ValueError):
    """DB 상태를 공개 Result로 정확히 표현할 수 없다."""


def _error_code(code: str | None) -> str:
    if code is None or code in {
        "LOW_CULTIVAR_CONFIDENCE",
        "LOW_QUALITY_CONFIDENCE",
        "LOW_BOTH_CONFIDENCE",
        "VIRTUAL_BRIX_MISSING",
    }:
        return "NONE"
    try:
        return _ERRORS[code]
    except KeyError as exc:
        raise HistoryContractError("알 수 없는 검사 오류 상태") from exc


def to_quality_result(row: Inspection) -> dict[str, object]:
    """ORM의 내부 코드와 UTC 시각을 공개 관제 계약으로 변환한다."""

    if row.completed_at is None:
        raise HistoryContractError("완료되지 않은 검사")
    completed = row.completed_at.replace(tzinfo=timezone.utc).astimezone(KST)
    excluded = row.exclude_from_normal_stats
    try:
        variety = None if excluded else _CULTIVARS[row.predicted_cultivar]
        grade = None if excluded else _GRADES[row.predicted_grade]
    except KeyError as exc:
        raise HistoryContractError("지원하지 않는 예측 라벨") from exc
    if row.deadline_exceeded:
        processing = "TIMEOUT"
    elif (
        row.error_code
        in {
            "INFERENCE_CONNECTION_ERROR",
            "INFERENCE_HTTP_ERROR",
            "INFERENCE_INVALID_RESPONSE",
            "INFERENCE_ERROR",
            "BIN_MAPPING_CONFIGURATION_ERROR",
        }
        or row.persistence_status == "FAILED"
    ):
        processing = "ERROR"
    else:
        processing = "COMPLETED"
    attempts = sorted(row.control_attempts, key=lambda item: item.attempt_no)
    if row.control_status == "SUCCEEDED":
        control = "FALLBACK" if len(attempts) > 1 else "SUCCEEDED"
    elif row.control_status == "NOT_REQUESTED":
        control = "NOT_REQUESTED"
    elif row.control_status in {"NO_RESPONSE", "REJECTED", "FAILED"}:
        control = row.control_status
    else:
        raise HistoryContractError("관제 계약으로 표현할 수 없는 제어 상태")
    if row.persistence_status not in {"SUCCEEDED", "FAILED"}:
        raise HistoryContractError("지원하지 않는 저장 상태")
    errors = sorted(row.errors, key=lambda item: (item.occurred_at, item.id or 0))
    faults = list(
        dict.fromkeys(
            code
            for error in errors
            if (code := _error_code(error.error_code)) != "NONE"
        )
    )[:5]
    error_code = _error_code(row.error_code)
    if error_code == "NONE" and faults:
        error_code = faults[0]
    if error_code != "NONE" and error_code not in faults:
        faults.insert(0, error_code)
        faults = faults[:5]
    review_required = row.review_required or control in {
        "FALLBACK",
        "NO_RESPONSE",
        "REJECTED",
        "FAILED",
    }
    status = "FAIL" if excluded else "REVIEW" if review_required else "PASS"
    return {
        "id": row.inspection_id,
        "date": completed.date().isoformat(),
        "time": completed.strftime("%H:%M:%S.%f")[:12],
        "timestamp": int(completed.timestamp() * 1000),
        "variety": variety,
        "grade": grade,
        "confidence": None if excluded else float(row.quality_confidence) * 100,
        "cultivarConfidence": None
        if excluded
        else float(row.cultivar_confidence) * 100,
        "status": status,
        "processingStatus": processing,
        "errorCode": error_code,
        "misclassification": row.suspected_error_type or "NONE",
        "bin": row.target_bin_code or "",
        "virtualBrix": float(row.virtual_brix)
        if row.virtual_brix is not None
        else None,
        "brixMeasured": False,
        "imageIndex": None,
        "inferenceMs": None
        if excluded or row.inference_time_ms is None
        else float(row.inference_time_ms),
        "modelVersion": None if excluded else row.model_version,
        "reviewRequired": review_required,
        "excluded": excluded,
        "control": control,
        "persistence": "SAVED" if row.persistence_status == "SUCCEEDED" else "FAILED",
        "faults": faults,
    }
