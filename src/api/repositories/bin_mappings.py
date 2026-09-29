"""활성 정상·재검사 bin mapping 조회 Repository."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from ..db.models import BinMapping


class BinMappingConfigurationError(RuntimeError):
    """활성 mapping이 없거나 하나로 결정되지 않을 때 발생한다."""


class BinMappingRepository:
    """현재 활성화된 목적 bin을 정확히 하나로 조회한다."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def find_normal_bin(
        self,
        *,
        crop_type: str,
        cultivar: str,
        quality_grade: str,
        sweetness_band: str,
    ) -> str:
        """정상 12-bin 자연키로 활성 목적지를 조회한다."""

        statement = select(BinMapping.bin_code).where(
            BinMapping.crop_type == crop_type,
            BinMapping.cultivar == cultivar,
            BinMapping.quality_grade == quality_grade,
            BinMapping.sweetness_band == sweetness_band,
            BinMapping.is_active.is_(True),
            BinMapping.is_reinspection.is_(False),
        )
        return self._require_single(statement, "정상")

    def find_reinspection_bin(self) -> str:
        """자연키가 NULL인 활성 재검사 목적지를 하나로 검증한다."""

        statement = select(BinMapping.bin_code).where(
            BinMapping.is_active.is_(True),
            BinMapping.is_reinspection.is_(True),
        )
        return self._require_single(statement, "재검사")

    def _require_single(self, statement: object, mapping_type: str) -> str:
        try:
            with self._session_factory() as session:
                bin_codes = list(session.scalars(statement).all())
        except SQLAlchemyError as exc:
            raise BinMappingConfigurationError(
                f"활성 {mapping_type} bin mapping 조회에 실패했습니다"
            ) from exc
        if len(bin_codes) != 1:
            raise BinMappingConfigurationError(
                f"활성 {mapping_type} bin mapping은 정확히 1개여야 합니다: "
                f"count={len(bin_codes)}"
            )
        return bin_codes[0]
