from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_alembic_has_single_initial_head() -> None:
    scripts = ScriptDirectory.from_config(Config("alembic.ini"))

    assert scripts.get_heads() == ["20260922_01"]
    assert scripts.get_revision("20260922_01").down_revision is None


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
