"""검사 저장 계층에 전달하는 명시적인 기록 값 객체."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ControlAttemptRecord:
    """Virtual Control 호출 한 번의 저장 값."""

    command_id: str
    attempt_no: int
    requested_bin_code: str
    command_type: str
    control_status: str
    requested_at: datetime
    responded_at: datetime | None
    response_time_ms: float | None
    failure_reason: str | None


@dataclass(frozen=True)
class InspectionErrorRecord:
    """검사 처리 중 발생한 내부 오류 한 건의 저장 값."""

    component: str
    error_code: str
    message: str | None
    diagnostic_data: dict[str, object] | None
    occurred_at: datetime
