"""검사 행 생성과 최종 상태 갱신 Repository."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, sessionmaker

from ..db.models import Inspection


class InspectionRepository:
    """한 트랜잭션 안에서 검사 행을 생성하거나 갱신한다."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create_pending(self, values: dict[str, object]) -> None:
        """처리 시작 상태의 검사 행을 추가한다."""

        self._session.add(Inspection(**values))

    def count(self) -> int:
        """현재 검사 행 수를 보존 정책의 최초 검사 때 확인한다."""

        return self._session.scalar(select(func.count()).select_from(Inspection)) or 0

    def delete_oldest(self, batch_size: int) -> int:
        """생성 시각과 ID 순서로 오래된 검사와 연관 행을 삭제한다."""

        oldest_ids = list(
            self._session.scalars(
                select(Inspection.inspection_id)
                .order_by(Inspection.created_at, Inspection.inspection_id)
                .limit(batch_size)
            )
        )
        if not oldest_ids:
            return 0
        result = self._session.execute(
            delete(Inspection).where(Inspection.inspection_id.in_(oldest_ids))
        )
        return result.rowcount

    def update_final(self, inspection_id: str, values: dict[str, object]) -> None:
        """이미 생성된 검사 행에 최종 결과를 반영한다."""

        inspection = self._session.get(Inspection, inspection_id)
        if inspection is None:
            raise LookupError(f"검사 행을 찾을 수 없습니다: {inspection_id}")
        for field_name, value in values.items():
            setattr(inspection, field_name, value)

    def update_late_result(
        self, inspection_id: str, received_at: datetime, payload: dict[str, object]
    ) -> None:
        """원래 판정 필드는 유지하고 늦은 Inference 진단 필드만 갱신한다."""

        inspection = self._session.get(Inspection, inspection_id)
        if inspection is None:
            raise LookupError(f"검사 행을 찾을 수 없습니다: {inspection_id}")
        inspection.late_result_received_at = received_at
        inspection.late_result_payload = payload


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
