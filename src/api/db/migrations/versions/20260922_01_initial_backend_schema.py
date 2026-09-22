"""Backend 초기 물리 스키마를 생성한다.

Revision ID: 20260922_01
Revises:
Create Date: 2026-09-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "20260922_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """검사·제어·오류·bin 매핑 테이블을 생성한다."""

    op.create_table(
        "bin_mappings",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("mapping_key", sa.String(length=64), nullable=False),
        sa.Column("crop_type", sa.String(length=32), nullable=True),
        sa.Column("cultivar", sa.String(length=32), nullable=True),
        sa.Column("quality_grade", sa.String(length=32), nullable=True),
        sa.Column("bin_code", sa.String(length=64), nullable=False),
        sa.Column(
            "is_reinspection",
            sa.Boolean(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column("created_at", mysql.DATETIME(fsp=3), nullable=False),
        sa.Column("updated_at", mysql.DATETIME(fsp=3), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bin_mappings")),
        sa.UniqueConstraint("bin_code", name=op.f("uq_bin_mappings_bin_code")),
        sa.UniqueConstraint(
            "crop_type",
            "cultivar",
            "quality_grade",
            name="uq_bin_mappings_normal_combination",
        ),
        sa.UniqueConstraint(
            "mapping_key",
            name=op.f("uq_bin_mappings_mapping_key"),
        ),
    )
    op.create_index(
        "ix_bin_mappings_active_reinspection",
        "bin_mappings",
        ["is_active", "is_reinspection"],
        unique=False,
    )

    op.create_table(
        "inspections",
        sa.Column("inspection_id", sa.String(length=64), nullable=False),
        sa.Column("source_reference", sa.String(length=255), nullable=True),
        sa.Column("created_at", mysql.DATETIME(fsp=3), nullable=False),
        sa.Column("completed_at", mysql.DATETIME(fsp=3), nullable=True),
        sa.Column("updated_at", mysql.DATETIME(fsp=3), nullable=False),
        sa.Column("crop_type", sa.String(length=32), nullable=False),
        sa.Column("predicted_cultivar", sa.String(length=32), nullable=True),
        sa.Column("predicted_grade", sa.String(length=32), nullable=True),
        sa.Column("cultivar_confidence", sa.Numeric(7, 6), nullable=True),
        sa.Column("quality_confidence", sa.Numeric(7, 6), nullable=True),
        sa.Column("applied_cultivar_threshold", sa.Numeric(7, 6), nullable=False),
        sa.Column("applied_quality_threshold", sa.Numeric(7, 6), nullable=False),
        sa.Column("model_name", sa.String(length=128), nullable=True),
        sa.Column("model_version", sa.String(length=128), nullable=True),
        sa.Column("preprocessing_version", sa.String(length=128), nullable=True),
        sa.Column("used_frame_count", sa.Integer(), nullable=True),
        sa.Column("inference_time_ms", sa.Numeric(10, 3), nullable=True),
        sa.Column(
            "review_required",
            sa.Boolean(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("target_bin_code", sa.String(length=64), nullable=True),
        sa.Column("inspection_status", sa.String(length=32), nullable=False),
        sa.Column("control_status", sa.String(length=32), nullable=False),
        sa.Column("persistence_status", sa.String(length=32), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column(
            "deadline_exceeded",
            sa.Boolean(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "exclude_from_normal_stats",
            sa.Boolean(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "is_reviewed",
            sa.Boolean(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("suspected_error_type", sa.String(length=32), nullable=True),
        sa.Column("review_note", sa.String(length=500), nullable=True),
        sa.Column("reviewed_at", mysql.DATETIME(fsp=3), nullable=True),
        sa.Column("late_result_received_at", mysql.DATETIME(fsp=3), nullable=True),
        sa.Column("late_predicted_cultivar", sa.String(length=32), nullable=True),
        sa.Column("late_predicted_grade", sa.String(length=32), nullable=True),
        sa.Column("late_result_payload", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("inspection_id", name=op.f("pk_inspections")),
    )
    op.create_index(
        "ix_inspections_control_status_created_at",
        "inspections",
        ["control_status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_inspections_created_at_id",
        "inspections",
        ["created_at", "inspection_id"],
        unique=False,
    )
    op.create_index(
        "ix_inspections_cultivar_grade_created_at",
        "inspections",
        ["predicted_cultivar", "predicted_grade", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_inspections_error_created_at",
        "inspections",
        ["error_code", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_inspections_model_version_created_at",
        "inspections",
        ["model_version", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_inspections_review_created_at",
        "inspections",
        ["is_reviewed", "suspected_error_type", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_inspections_status_created_at",
        "inspections",
        ["inspection_status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_inspections_target_bin_created_at",
        "inspections",
        ["target_bin_code", "created_at"],
        unique=False,
    )

    op.create_table(
        "control_attempts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("command_id", sa.String(length=64), nullable=False),
        sa.Column("inspection_id", sa.String(length=64), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("requested_bin_code", sa.String(length=64), nullable=False),
        sa.Column("command_type", sa.String(length=32), nullable=False),
        sa.Column("control_status", sa.String(length=32), nullable=False),
        sa.Column("requested_at", mysql.DATETIME(fsp=3), nullable=False),
        sa.Column("responded_at", mysql.DATETIME(fsp=3), nullable=True),
        sa.Column("response_time_ms", sa.Numeric(10, 3), nullable=True),
        sa.Column("failure_reason", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(
            ["inspection_id"],
            ["inspections.inspection_id"],
            name=op.f("fk_control_attempts_inspection_id_inspections"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_control_attempts")),
        sa.UniqueConstraint("command_id", name=op.f("uq_control_attempts_command_id")),
        sa.UniqueConstraint(
            "inspection_id",
            "attempt_no",
            name="uq_control_attempts_inspection_attempt",
        ),
    )
    op.create_index(
        "ix_control_attempts_inspection_requested_at",
        "control_attempts",
        ["inspection_id", "requested_at"],
        unique=False,
    )
    op.create_index(
        "ix_control_attempts_status_requested_at",
        "control_attempts",
        ["control_status", "requested_at"],
        unique=False,
    )

    op.create_table(
        "inspection_errors",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("inspection_id", sa.String(length=64), nullable=False),
        sa.Column("component", sa.String(length=32), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("diagnostic_data", sa.JSON(), nullable=True),
        sa.Column("occurred_at", mysql.DATETIME(fsp=3), nullable=False),
        sa.ForeignKeyConstraint(
            ["inspection_id"],
            ["inspections.inspection_id"],
            name=op.f("fk_inspection_errors_inspection_id_inspections"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_inspection_errors")),
    )
    op.create_index(
        "ix_inspection_errors_code_occurred_at",
        "inspection_errors",
        ["error_code", "occurred_at"],
        unique=False,
    )
    op.create_index(
        "ix_inspection_errors_component_occurred_at",
        "inspection_errors",
        ["component", "occurred_at"],
        unique=False,
    )
    op.create_index(
        "ix_inspection_errors_inspection_occurred_at",
        "inspection_errors",
        ["inspection_id", "occurred_at"],
        unique=False,
    )


def downgrade() -> None:
    """FK 자식 테이블부터 초기 스키마를 제거한다."""

    op.drop_table("inspection_errors")
    op.drop_table("control_attempts")
    op.drop_table("inspections")
    op.drop_table("bin_mappings")
