"""품종·품질 조합과 bin 매핑 ORM 모델."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class BinMapping(Base):
    """현재 적용할 정상 6개 및 재검사 bin 매핑을 관리한다."""

    __tablename__ = "bin_mappings"
    __table_args__ = (
        UniqueConstraint(
            "crop_type",
            "cultivar",
            "quality_grade",
            name="uq_bin_mappings_normal_combination",
        ),
        Index(
            "ix_bin_mappings_active_reinspection",
            "is_active",
            "is_reinspection",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    mapping_key: Mapped[str] = mapped_column(String(64), unique=True)
    crop_type: Mapped[str | None] = mapped_column(String(32))
    cultivar: Mapped[str | None] = mapped_column(String(32))
    quality_grade: Mapped[str | None] = mapped_column(String(32))
    bin_code: Mapped[str] = mapped_column(String(64), unique=True)
    is_reinspection: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=text("0"),
    )
    # TODO: 재검사 매핑 단일성은 실제 bin 계약 확정 후 제약조건을 결정한다.
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=text("1"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3),
        server_default=text("CURRENT_TIMESTAMP(3)"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3),
        server_default=text("CURRENT_TIMESTAMP(3)"),
        onupdate=text("CURRENT_TIMESTAMP(3)"),
    )
