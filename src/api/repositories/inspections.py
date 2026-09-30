"""검사 행 생성과 최종 상태 갱신 Repository."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session, sessionmaker

from ..db.models import Inspection


class InspectionRepository:
    """한 트랜잭션 안에서 검사 행을 생성하거나 갱신한다."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create_pending(self, values: dict[str, object]) -> None:
        """처리 시작 상태의 검사 행을 추가한다."""

        self._session.add(Inspection(**values))

    def update_final(self, inspection_id: str, values: dict[str, object]) -> None:
        """이미 생성된 검사 행에 최종 결과를 반영한다."""

        inspection = self._session.get(Inspection, inspection_id)
        if inspection is None:
            raise LookupError(f"검사 행을 찾을 수 없습니다: {inspection_id}")
        for field_name, value in values.items():
            setattr(inspection, field_name, value)


class InspectionReviewRepository:
    """검사 결과를 유지하면서 검수 metadata만 갱신한다."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def set_misclassification(self, inspection_id: str, value: str) -> bool:
        """검사 ID가 없으면 False, 있으면 검수 상태를 저장한다."""

        with self._session_factory() as session, session.begin():
            inspection = session.get(Inspection, inspection_id)
            if inspection is None:
                return False
            changed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            inspection.suspected_error_type = None if value == "NONE" else value
            inspection.is_reviewed = value != "NONE"
            inspection.reviewed_at = changed_at if value != "NONE" else None
            inspection.updated_at = changed_at
        return True
