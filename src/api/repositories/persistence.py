"""검사 한 건의 저장 트랜잭션을 조정한다."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session, sessionmaker

from ..core.datetime import to_utc_naive
from .control_attempts import ControlAttemptRepository
from .inspection_errors import InspectionErrorRepository
from .inspections import InspectionRepository
from .records import ControlAttemptRecord, InspectionErrorRecord


class InspectionPersistence:
    """초기 INSERT와 최종 결과 저장을 분리된 commit 단위로 실행한다."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def create_pending(self, values: dict[str, object]) -> None:
        """검사 시작 행을 별도 트랜잭션으로 commit한다."""

        db_values = dict(values)
        for field_name in ("created_at", "updated_at"):
            db_values[field_name] = to_utc_naive(_datetime_value(db_values, field_name))
        with self._session_factory() as session, session.begin():
            InspectionRepository(session).create_pending(db_values)

    def finalize(
        self,
        *,
        inspection_id: str,
        inspection_values: dict[str, object],
        control_attempts: list[ControlAttemptRecord],
        errors: list[InspectionErrorRecord],
    ) -> None:
        """최종 검사·제어·오류 값을 하나의 트랜잭션으로 commit한다."""

        db_values = dict(inspection_values)
        for field_name in ("completed_at", "updated_at"):
            value = db_values.get(field_name)
            if value is not None:
                db_values[field_name] = to_utc_naive(
                    _datetime_value(db_values, field_name)
                )

        with self._session_factory() as session, session.begin():
            InspectionRepository(session).update_final(inspection_id, db_values)
            ControlAttemptRepository(session).add_all(
                inspection_id,
                control_attempts,
            )
            InspectionErrorRepository(session).add_all(inspection_id, errors)

    def mark_failed(
        self,
        *,
        inspection_id: str,
        updated_at: datetime,
        error: InspectionErrorRecord,
    ) -> None:
        """최종 저장 실패를 기존 검사 행에 한 번만 best-effort 기록한다."""

        with self._session_factory() as session, session.begin():
            InspectionRepository(session).update_final(
                inspection_id,
                {
                    "persistence_status": "FAILED",
                    "error_code": error.error_code,
                    "updated_at": to_utc_naive(updated_at),
                },
            )
            InspectionErrorRepository(session).add_all(inspection_id, [error])

    def save_late_result(
        self,
        *,
        inspection_id: str,
        received_at: datetime,
        payload: dict[str, object],
    ) -> None:
        """원래 요청과 분리된 session에서 늦은 응답 진단만 commit한다."""

        with self._session_factory() as session, session.begin():
            InspectionRepository(session).update_late_result(
                inspection_id, to_utc_naive(received_at), payload
            )


def _datetime_value(values: dict[str, object], field_name: str) -> datetime:
    value = values[field_name]
    if not isinstance(value, datetime):
        raise TypeError(f"{field_name}에는 datetime이 필요합니다")
    return value
