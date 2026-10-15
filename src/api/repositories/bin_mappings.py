"""Load and validate the active bin mappings as one coherent snapshot."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import cast

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from ..db.models import BinMapping

BinKey = tuple[str, str, str, str]
_EXPECTED_KEYS: frozenset[BinKey] = frozenset(
    ("apple", cultivar, grade, sweetness)
    for cultivar in ("fuji", "yanggwang")
    for grade in ("L", "M", "S")
    for sweetness in ("less_sweet", "sweet")
)


class BinMappingConfigurationError(RuntimeError):
    """The database responded, but its active mapping is invalid."""


class BinMappingUnavailableError(RuntimeError):
    """The active mapping could not be read from the database."""


@dataclass(frozen=True)
class BinMappingSnapshot:
    """One immutable, complete set of active destination bins."""

    normal_bins: Mapping[BinKey, str]
    reinspection_bin: str

    def __post_init__(self) -> None:
        normal_bins = dict(self.normal_bins)
        if normal_bins.keys() != _EXPECTED_KEYS:
            raise BinMappingConfigurationError(
                "활성 정상 bin mapping은 정확히 12개여야 합니다"
            )
        codes = [*normal_bins.values(), self.reinspection_bin]
        if any(not code or not code.strip() for code in codes) or len(set(codes)) != 13:
            raise BinMappingConfigurationError(
                "활성 bin code 13개는 비어 있거나 중복될 수 없습니다"
            )
        object.__setattr__(self, "normal_bins", MappingProxyType(normal_bins))

    @classmethod
    def from_rows(cls, rows: list[BinMapping]) -> BinMappingSnapshot:
        """Reject missing, duplicate, or malformed active rows before publication."""

        normal_bins: dict[BinKey, str] = {}
        reinspection_bins: list[str] = []
        for row in rows:
            fields = (
                row.crop_type,
                row.cultivar,
                row.quality_grade,
                row.sweetness_band,
            )
            if row.is_reinspection:
                if any(field is not None for field in fields):
                    raise BinMappingConfigurationError(
                        "재검사 bin의 배차 키는 NULL이어야 합니다"
                    )
                reinspection_bins.append(row.bin_code)
                continue
            if any(field is None for field in fields):
                raise BinMappingConfigurationError(
                    "정상 bin의 배차 키가 누락되었습니다"
                )
            key = cast(BinKey, fields)
            if key in normal_bins:
                raise BinMappingConfigurationError(
                    "활성 정상 bin mapping이 중복되었습니다"
                )
            normal_bins[key] = row.bin_code
        if len(reinspection_bins) != 1:
            raise BinMappingConfigurationError(
                "활성 재검사 bin mapping은 정확히 1개여야 합니다"
            )
        return cls(normal_bins, reinspection_bins[0])

    def normal_bin(
        self, *, crop_type: str, cultivar: str, quality_grade: str, sweetness_band: str
    ) -> str:
        try:
            return self.normal_bins[
                (crop_type, cultivar, quality_grade, sweetness_band)
            ]
        except KeyError as exc:
            raise BinMappingConfigurationError(
                "정상 배차 키가 활성 mapping에 없습니다"
            ) from exc


class BinMappingRepository:
    """Read all active mappings in a single database statement and session."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def load_snapshot(self) -> BinMappingSnapshot:
        try:
            with self._session_factory() as session:
                rows = list(
                    session.scalars(
                        select(BinMapping).where(BinMapping.is_active.is_(True))
                    ).all()
                )
        except SQLAlchemyError as exc:
            raise BinMappingUnavailableError(
                "활성 bin mapping DB 조회에 실패했습니다"
            ) from exc
        return BinMappingSnapshot.from_rows(rows)
