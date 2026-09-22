"""가상 제어 시도 이력 ORM 모델."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base

if TYPE_CHECKING:
    from .inspection import Inspection


class ControlAttempt(Base):
    """검사별 정상 bin 및 대체 재검사 bin 제어 시도를 기록한다."""

    __tablename__ = "control_attempts"
    __table_args__ = (
        UniqueConstraint(
            "inspection_id",
            "attempt_no",
            name="uq_control_attempts_inspection_attempt",
        ),
        Index(
            "ix_control_attempts_inspection_requested_at",
            "inspection_id",
            "requested_at",
        ),
        Index(
            "ix_control_attempts_status_requested_at",
            "control_status",
            "requested_at",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    command_id: Mapped[str] = mapped_column(String(64), unique=True)
    inspection_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("inspections.inspection_id", ondelete="CASCADE"),
    )
    attempt_no: Mapped[int] = mapped_column()
    requested_bin_code: Mapped[str] = mapped_column(String(64))
    command_type: Mapped[str] = mapped_column(String(32))
    control_status: Mapped[str] = mapped_column(String(32))
    requested_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3))
    responded_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=3))
    response_time_ms: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    failure_reason: Mapped[str | None] = mapped_column(String(255))

    inspection: Mapped[Inspection] = relationship(back_populates="control_attempts")
