"""검사 한 건의 저장 트랜잭션을 조정한다."""

from __future__ import annotations

from datetime import datetime
from threading import Lock

from sqlalchemy.orm import Session, sessionmaker

from ..core.datetime import to_utc_naive
from .control_attempts import ControlAttemptRepository
from .inspection_errors import InspectionErrorRepository
from .inspections import InspectionRepository
from .records import ControlAttemptRecord, InspectionErrorRecord


class InspectionPersistence:
    """초기 INSERT와 최종 결과 저장을 분리된 commit 단위로 실행한다."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        history_limit: int = 86_400,
        history_delete_batch: int = 8_640,
    ) -> None:
        if not 0 < history_delete_batch < history_limit:
            raise ValueError("이력 삭제량은 상한보다 작아야 합니다")
        self._session_factory = session_factory
        self._history_limit = history_limit
        self._history_delete_batch = history_delete_batch
        self._history_count: int | None = None
        self._history_lock = Lock()

    def create_pending(self, values: dict[str, object]) -> None:
        """검사 시작 행을 별도 트랜잭션으로 commit한다."""

        db_values = dict(values)
        for field_name in ("created_at", "updated_at"):
            db_values[field_name] = to_utc_naive(_datetime_value(db_values, field_name))
        # 단일 Backend 프로세스의 동시 INSERT를 직렬화해 cached count를 유지한다.
        with self._history_lock:
            with self._session_factory() as session, session.begin():
                repository = InspectionRepository(session)
                count = (
                    repository.count()
                    if self._history_count is None
                    else self._history_count
                )
                repository.create_pending(db_values)
                session.flush()
                count += 1
                if count >= self._history_limit:
                    # 삭제 경계에서 실제 건수를 다시 확인해 외부 삭제로 인한 오차를 제거한다.
                    count = repository.count()
                    while count >= self._history_limit:
                        deleted = repository.delete_oldest(self._history_delete_batch)
                        if deleted == 0:
                            break
                        count -= deleted
            self._history_count = count

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
