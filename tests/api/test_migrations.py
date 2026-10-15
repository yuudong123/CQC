from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from src.api.services.bin_policy import (
    DEMO_NORMAL_BIN_MAPPING,
    TEMPORARY_REINSPECTION_BIN_CODE,
)


def test_alembic_has_single_be05_head() -> None:
    scripts = ScriptDirectory.from_config(Config("alembic.ini"))

    assert scripts.get_heads() == ["20260929_02"]
    assert scripts.get_revision("20260922_01").down_revision is None
    assert scripts.get_revision("20260929_02").down_revision == "20260922_01"


def test_initial_revision_contains_only_current_business_tables() -> None:
    scripts = ScriptDirectory.from_config(Config("alembic.ini"))
    revision = scripts.get_revision("20260922_01")
    source = Path(revision.path).read_text(encoding="utf-8")
    expected_tables = {
        "inspections",
        "control_attempts",
        "inspection_errors",
        "bin_mappings",
    }

    assert source.count("op.create_table(") == len(expected_tables)
    for table_name in expected_tables:
        assert f'op.create_table(\n        "{table_name}"' in source

    assert "failure_images" not in source
    assert "storage_key" not in source
    assert "BLOB" not in source
    assert "CURRENT_TIMESTAMP" not in source
    assert "NOW(" not in source


def test_be05_revision_matches_orm_and_seeds_twelve_bins() -> None:
    scripts = ScriptDirectory.from_config(Config("alembic.ini"))
    revision = scripts.get_revision("20260929_02")
    source = Path(revision.path).read_text(encoding="utf-8")
    seeds = revision.module.BIN_MAPPING_SEEDS

    assert 'sa.Column("virtual_brix", sa.Numeric(4, 1), nullable=True)' in source
    assert 'sa.Column("brix_source", sa.String(length=64), nullable=True)' in source
    assert '"brix_is_measured",' in source
    assert 'sa.Column("sweetness_band", sa.String(length=32), nullable=True)' in source
    assert 'op.drop_column("inspections", "late_predicted_cultivar")' in source
    assert 'op.drop_column("inspections", "late_predicted_grade")' in source
    assert 'op.drop_column("bin_mappings", "mapping_key")' in source
    assert '["crop_type", "cultivar", "quality_grade", "sweetness_band"]' in source

    normal_seeds = [seed for seed in seeds if not seed["is_reinspection"]]
    reinspection_seeds = [seed for seed in seeds if seed["is_reinspection"]]
    seeded_mapping = {
        (
            seed["cultivar"],
            seed["quality_grade"],
            seed["sweetness_band"],
        ): seed["bin_code"]
        for seed in normal_seeds
    }

    assert len(normal_seeds) == 12
    assert seeded_mapping == DEMO_NORMAL_BIN_MAPPING
    assert len(reinspection_seeds) == 1
    assert reinspection_seeds[0] == {
        "crop_type": None,
        "cultivar": None,
        "quality_grade": None,
        "sweetness_band": None,
        "bin_code": TEMPORARY_REINSPECTION_BIN_CODE,
        "is_reinspection": True,
    }
    assert len({seed["bin_code"] for seed in seeds}) == 13


def test_be05_downgrade_deletes_only_reserved_seed_codes() -> None:
    scripts = ScriptDirectory.from_config(Config("alembic.ini"))
    revision = scripts.get_revision("20260929_02")
    source = Path(revision.path).read_text(encoding="utf-8")

    assert "table.delete().where(table.c.bin_code.in_(seed_bin_codes))" in source
    assert 'op.drop_table("bin_mappings")' not in source
    assert 'op.drop_table("inspections")' not in source
