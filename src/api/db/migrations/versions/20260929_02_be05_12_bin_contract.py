"""BE-05 12-bin 검사 이력과 bin 매핑 계약을 반영한다.

Revision ID: 20260929_02
Revises: 20260922_01
Create Date: 2026-09-29
"""

from collections.abc import Sequence
from datetime import datetime, timedelta, timezone

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "20260929_02"
down_revision: str | None = "20260922_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REINSPECTION_BIN_CODE = "TEST_REINSPECTION_BIN"
# 설정 seed의 생성 기준일만 KST로 고정한다. 검사 업무 시각의 DB 저장 규칙은
# BE-05 Repository 단계에서 별도로 확정한다.
KST = timezone(timedelta(hours=9))
SEED_CREATED_AT = datetime(2026, 9, 29, tzinfo=KST).replace(tzinfo=None)

BIN_MAPPING_SEEDS: tuple[dict[str, object], ...] = (
    {
        "crop_type": "apple",
        "cultivar": "fuji",
        "quality_grade": "L",
        "sweetness_band": "less_sweet",
        "bin_code": "DEMO_BIN_01",
        "is_reinspection": False,
    },
    {
        "crop_type": "apple",
        "cultivar": "fuji",
        "quality_grade": "L",
        "sweetness_band": "sweet",
        "bin_code": "DEMO_BIN_02",
        "is_reinspection": False,
    },
    {
        "crop_type": "apple",
        "cultivar": "fuji",
        "quality_grade": "M",
        "sweetness_band": "less_sweet",
        "bin_code": "DEMO_BIN_03",
        "is_reinspection": False,
    },
    {
        "crop_type": "apple",
        "cultivar": "fuji",
        "quality_grade": "M",
        "sweetness_band": "sweet",
        "bin_code": "DEMO_BIN_04",
        "is_reinspection": False,
    },
    {
        "crop_type": "apple",
        "cultivar": "fuji",
        "quality_grade": "S",
        "sweetness_band": "less_sweet",
        "bin_code": "DEMO_BIN_05",
        "is_reinspection": False,
    },
    {
        "crop_type": "apple",
        "cultivar": "fuji",
        "quality_grade": "S",
        "sweetness_band": "sweet",
        "bin_code": "DEMO_BIN_06",
        "is_reinspection": False,
    },
    {
        "crop_type": "apple",
        "cultivar": "yanggwang",
        "quality_grade": "L",
        "sweetness_band": "less_sweet",
        "bin_code": "DEMO_BIN_07",
        "is_reinspection": False,
    },
    {
        "crop_type": "apple",
        "cultivar": "yanggwang",
        "quality_grade": "L",
        "sweetness_band": "sweet",
        "bin_code": "DEMO_BIN_08",
        "is_reinspection": False,
    },
    {
        "crop_type": "apple",
        "cultivar": "yanggwang",
        "quality_grade": "M",
        "sweetness_band": "less_sweet",
        "bin_code": "DEMO_BIN_09",
        "is_reinspection": False,
    },
    {
        "crop_type": "apple",
        "cultivar": "yanggwang",
        "quality_grade": "M",
        "sweetness_band": "sweet",
        "bin_code": "DEMO_BIN_10",
        "is_reinspection": False,
    },
    {
        "crop_type": "apple",
        "cultivar": "yanggwang",
        "quality_grade": "S",
        "sweetness_band": "less_sweet",
        "bin_code": "DEMO_BIN_11",
        "is_reinspection": False,
    },
    {
        "crop_type": "apple",
        "cultivar": "yanggwang",
        "quality_grade": "S",
        "sweetness_band": "sweet",
        "bin_code": "DEMO_BIN_12",
        "is_reinspection": False,
    },
    {
        "crop_type": None,
        "cultivar": None,
        "quality_grade": None,
        "sweetness_band": None,
        "bin_code": REINSPECTION_BIN_CODE,
        "is_reinspection": True,
    },
)


def _bin_mapping_table() -> sa.Table:
    return sa.table(
        "bin_mappings",
        sa.column("crop_type", sa.String(32)),
        sa.column("cultivar", sa.String(32)),
        sa.column("quality_grade", sa.String(32)),
        sa.column("sweetness_band", sa.String(32)),
        sa.column("bin_code", sa.String(64)),
        sa.column("is_reinspection", sa.Boolean()),
        sa.column("is_active", sa.Boolean()),
        sa.column("created_at", mysql.DATETIME(fsp=3)),
        sa.column("updated_at", mysql.DATETIME(fsp=3)),
    )


def _insert_seed_rows() -> None:
    """같은 bin code의 동일 seed는 건너뛰고 충돌 데이터는 실패시킨다."""

    connection = op.get_bind()
    table = _bin_mapping_table()
    comparable_columns = (
        "crop_type",
        "cultivar",
        "quality_grade",
        "sweetness_band",
        "is_reinspection",
    )

    for seed in BIN_MAPPING_SEEDS:
        existing = (
            connection.execute(
                sa.select(table).where(table.c.bin_code == seed["bin_code"])
            )
            .mappings()
            .one_or_none()
        )
        if existing is not None:
            if any(existing[column] != seed[column] for column in comparable_columns):
                raise RuntimeError(
                    f"기존 bin mapping이 12-bin seed와 충돌합니다: {seed['bin_code']}"
                )
            continue

        connection.execute(
            table.insert().values(
                **seed,
                is_active=True,
                created_at=SEED_CREATED_AT,
                updated_at=SEED_CREATED_AT,
            )
        )


def upgrade() -> None:
    """가상 당도 이력, 12-bin 자연키와 시연 seed를 추가한다."""

    op.add_column(
        "inspections",
        sa.Column("virtual_brix", sa.Numeric(4, 1), nullable=True),
    )
    op.add_column(
        "inspections",
        sa.Column("brix_source", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "inspections",
        sa.Column(
            "brix_is_measured",
            sa.Boolean(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.add_column(
        "inspections",
        sa.Column("sweetness_band", sa.String(length=32), nullable=True),
    )
    op.drop_column("inspections", "late_predicted_grade")
    op.drop_column("inspections", "late_predicted_cultivar")

    op.add_column(
        "bin_mappings",
        sa.Column("sweetness_band", sa.String(length=32), nullable=True),
    )
    op.drop_constraint(
        "uq_bin_mappings_normal_combination",
        "bin_mappings",
        type_="unique",
    )
    op.drop_constraint(
        "uq_bin_mappings_mapping_key",
        "bin_mappings",
        type_="unique",
    )
    op.drop_column("bin_mappings", "mapping_key")
    op.create_unique_constraint(
        "uq_bin_mappings_normal_combination",
        "bin_mappings",
        ["crop_type", "cultivar", "quality_grade", "sweetness_band"],
    )

    _insert_seed_rows()


def downgrade() -> None:
    """이 revision의 seed와 컬럼만 제거하고 기존 6-bin 구조를 복원한다."""

    table = _bin_mapping_table()
    seed_bin_codes = [seed["bin_code"] for seed in BIN_MAPPING_SEEDS]
    op.get_bind().execute(table.delete().where(table.c.bin_code.in_(seed_bin_codes)))

    op.drop_constraint(
        "uq_bin_mappings_normal_combination",
        "bin_mappings",
        type_="unique",
    )
    op.add_column(
        "bin_mappings",
        sa.Column("mapping_key", sa.String(length=64), nullable=True),
    )
    op.execute(sa.text("UPDATE bin_mappings SET mapping_key = bin_code"))
    op.alter_column(
        "bin_mappings",
        "mapping_key",
        existing_type=sa.String(length=64),
        nullable=False,
    )
    op.create_unique_constraint(
        "uq_bin_mappings_mapping_key",
        "bin_mappings",
        ["mapping_key"],
    )
    op.drop_column("bin_mappings", "sweetness_band")
    op.create_unique_constraint(
        "uq_bin_mappings_normal_combination",
        "bin_mappings",
        ["crop_type", "cultivar", "quality_grade"],
    )

    op.add_column(
        "inspections",
        sa.Column("late_predicted_cultivar", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "inspections",
        sa.Column("late_predicted_grade", sa.String(length=32), nullable=True),
    )
    op.drop_column("inspections", "sweetness_band")
    op.drop_column("inspections", "brix_is_measured")
    op.drop_column("inspections", "brix_source")
    op.drop_column("inspections", "virtual_brix")
