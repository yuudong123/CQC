"""검사 이력 ORM 모델."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, Index, Numeric, String, text
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base

if TYPE_CHECKING:
    from .control_attempt import ControlAttempt
    from .inspection_error import InspectionError


class Inspection(Base):
    """검사 결과, 처리 상태, 검수 정보와 지연 결과를 보관한다."""

    __tablename__ = "inspections"
    __table_args__ = (
        Index("ix_inspections_created_at_id", "created_at", "inspection_id"),
        Index(
            "ix_inspections_cultivar_grade_created_at",
            "predicted_cultivar",
            "predicted_grade",
            "created_at",
        ),
        Index(
            "ix_inspections_target_bin_created_at",
            "target_bin_code",
            "created_at",
        ),
        Index(
            "ix_inspections_status_created_at",
            "inspection_status",
            "created_at",
        ),
        Index(
            "ix_inspections_control_status_created_at",
            "control_status",
            "created_at",
        ),
        Index(
            "ix_inspections_error_created_at",
            "error_code",
            "created_at",
        ),
        Index(
            "ix_inspections_review_created_at",
            "is_reviewed",
            "suspected_error_type",
            "created_at",
        ),
        Index(
            "ix_inspections_model_version_created_at",
            "model_version",
            "created_at",
        ),
    )

    inspection_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    # 반복 검사에서도 원래 시연 묶음을 추적할 수 있도록 demo_bundle_id 같은
    # 입력 원본 식별자를 저장한다. Inference에는 이 값을 전달하지 않는다.
    source_reference: Mapped[str | None] = mapped_column(String(255))

    # TODO: DATETIME은 timezone 정보를 보존하지 않으므로 UTC/KST 정책을 확정해야 한다.
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3))
    completed_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=3))
    updated_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3))

    crop_type: Mapped[str] = mapped_column(String(32))
    predicted_cultivar: Mapped[str | None] = mapped_column(String(32))
    predicted_grade: Mapped[str | None] = mapped_column(String(32))
    cultivar_confidence: Mapped[Decimal | None] = mapped_column(Numeric(7, 6))
    quality_confidence: Mapped[Decimal | None] = mapped_column(Numeric(7, 6))
    applied_cultivar_threshold: Mapped[Decimal] = mapped_column(Numeric(7, 6))
    applied_quality_threshold: Mapped[Decimal] = mapped_column(Numeric(7, 6))
    model_name: Mapped[str | None] = mapped_column(String(128))
    model_version: Mapped[str | None] = mapped_column(String(128))
    preprocessing_version: Mapped[str | None] = mapped_column(String(128))
    used_frame_count: Mapped[int | None] = mapped_column()
    inference_time_ms: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    virtual_brix: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    brix_source: Mapped[str | None] = mapped_column(String(64))
    brix_is_measured: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=text("0"),
    )
    sweetness_band: Mapped[str | None] = mapped_column(String(32))

    review_required: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=text("0"),
    )
    target_bin_code: Mapped[str | None] = mapped_column(String(64))
    # TODO: 상태 문자열과 전이가 확정되기 전까지 DB native ENUM을 사용하지 않는다.
    inspection_status: Mapped[str] = mapped_column(String(32))
    control_status: Mapped[str] = mapped_column(String(32))
    # 행 생성 이후 저장 단계의 상태 snapshot이다. 최초 INSERT가 완전히 실패하면
    # 행이 없으므로 FAILED는 application log와 API 상태로만 남길 수 있다.
    persistence_status: Mapped[str] = mapped_column(String(32))
    error_code: Mapped[str | None] = mapped_column(String(64))
    deadline_exceeded: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=text("0"),
    )
    exclude_from_normal_stats: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=text("0"),
    )

    is_reviewed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=text("0"),
    )
    suspected_error_type: Mapped[str | None] = mapped_column(String(32))
    review_note: Mapped[str | None] = mapped_column(String(500))
    reviewed_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=3))

    late_result_received_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=3))
    late_result_payload: Mapped[dict[str, object] | None] = mapped_column(JSON)

    control_attempts: Mapped[list[ControlAttempt]] = relationship(
        back_populates="inspection",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    errors: Mapped[list[InspectionError]] = relationship(
        back_populates="inspection",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
