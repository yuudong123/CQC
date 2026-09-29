"""검사 행 생성과 최종 상태 갱신 Repository."""

from __future__ import annotations

from sqlalchemy.orm import Session

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
