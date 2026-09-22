"""검사 오류와 진단 정보 ORM 모델."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, BigInteger, ForeignKey, Index, String, Text
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base

if TYPE_CHECKING:
    from .inspection import Inspection


class InspectionError(Base):
    """한 검사에서 발생할 수 있는 복수 오류를 진단 목적으로 기록한다."""

    __tablename__ = "inspection_errors"
    __table_args__ = (
        Index(
            "ix_inspection_errors_inspection_occurred_at",
            "inspection_id",
            "occurred_at",
        ),
        Index(
            "ix_inspection_errors_code_occurred_at",
            "error_code",
            "occurred_at",
        ),
        Index(
            "ix_inspection_errors_component_occurred_at",
            "component",
            "occurred_at",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    inspection_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("inspections.inspection_id", ondelete="CASCADE"),
    )
    component: Mapped[str] = mapped_column(String(32))
    error_code: Mapped[str] = mapped_column(String(64))
    message: Mapped[str | None] = mapped_column(Text)
    diagnostic_data: Mapped[dict[str, object] | None] = mapped_column(JSON)
    occurred_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3))

    inspection: Mapped[Inspection] = relationship(back_populates="errors")
