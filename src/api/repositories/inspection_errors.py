"""검사 처리 오류와 진단 정보 Repository."""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..core.datetime import to_utc_naive
from ..db.models import InspectionError
from .records import InspectionErrorRecord


class InspectionErrorRepository:
    """검사 FK에 연결된 내부 오류를 저장한다."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add_all(
        self,
        inspection_id: str,
        errors: list[InspectionErrorRecord],
    ) -> None:
        """검사 처리 중 모은 오류를 한 트랜잭션에 추가한다."""

        self._session.add_all(
            [
                InspectionError(
                    inspection_id=inspection_id,
                    component=error.component,
                    error_code=error.error_code,
                    message=error.message,
                    diagnostic_data=error.diagnostic_data,
                    occurred_at=to_utc_naive(error.occurred_at),
                )
                for error in errors
            ]
        )
