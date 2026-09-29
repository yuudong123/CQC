"""Virtual Control 호출 이력 Repository."""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..core.datetime import to_utc_naive
from ..db.models import ControlAttempt
from .records import ControlAttemptRecord


class ControlAttemptRepository:
    """한 검사에 속한 제어 시도를 호출 순서대로 저장한다."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add_all(
        self,
        inspection_id: str,
        attempts: list[ControlAttemptRecord],
    ) -> None:
        """검사 FK와 attempt_no를 유지해 제어 시도를 추가한다."""

        self._session.add_all(
            [
                ControlAttempt(
                    command_id=attempt.command_id,
                    inspection_id=inspection_id,
                    attempt_no=attempt.attempt_no,
                    requested_bin_code=attempt.requested_bin_code,
                    command_type=attempt.command_type,
                    control_status=attempt.control_status,
                    requested_at=to_utc_naive(attempt.requested_at),
                    responded_at=(
                        to_utc_naive(attempt.responded_at)
                        if attempt.responded_at is not None
                        else None
                    ),
                    response_time_ms=attempt.response_time_ms,
                    failure_reason=attempt.failure_reason,
                )
                for attempt in attempts
            ]
        )
