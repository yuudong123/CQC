import pytest
from sqlalchemy import ForeignKeyConstraint, UniqueConstraint

from src.api.core.config import Settings
from src.api.db.base import Base
from src.api.db.models import BinMapping, ControlAttempt, Inspection, InspectionError
from src.api.db.session import create_db_engine, create_session_factory


def test_metadata_registers_only_current_db_tables() -> None:
    assert set(Base.metadata.tables) == {
        "inspections",
        "control_attempts",
        "inspection_errors",
        "bin_mappings",
    }
    assert all("image" not in table_name for table_name in Base.metadata.tables)


def test_inspections_columns_have_expected_nullability() -> None:
    table = Inspection.__table__

    assert list(table.primary_key.columns.keys()) == ["inspection_id"]
    assert table.c.created_at.nullable is False
    assert table.c.completed_at.nullable is True
    assert table.c.predicted_cultivar.nullable is True
    assert table.c.cultivar_confidence.nullable is True
    assert table.c.applied_cultivar_threshold.nullable is False
    assert table.c.inspection_status.nullable is False
    assert table.c.late_result_payload.nullable is True


def test_control_attempts_have_fk_and_unique_attempt_constraint() -> None:
    table = ControlAttempt.__table__
    foreign_keys = {
        (constraint.columns.keys()[0], constraint.referred_table.name)
        for constraint in table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    }
    unique_column_sets = {
        tuple(constraint.columns.keys())
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert ("inspection_id", "inspections") in foreign_keys
    assert ("inspection_id", "attempt_no") in unique_column_sets
    assert table.c.command_id.unique is True


def test_inspection_errors_have_fk_and_json_diagnostics() -> None:
    table = InspectionError.__table__

    assert table.c.inspection_id.foreign_keys
    assert table.c.diagnostic_data.nullable is True
    assert table.c.message.nullable is True


def test_bin_mappings_have_required_unique_keys_and_lookup_index() -> None:
    table = BinMapping.__table__
    column_unique_constraints = {
        tuple(constraint.columns.keys())
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    indexes = {tuple(index.columns.keys()) for index in table.indexes}

    assert ("mapping_key",) in column_unique_constraints
    assert ("bin_code",) in column_unique_constraints
    assert ("crop_type", "cultivar", "quality_grade") in column_unique_constraints
    assert ("is_active", "is_reinspection") in indexes


def test_sync_engine_and_session_factory_use_configured_mysql_url() -> None:
    settings = Settings(
        database_url="mysql+pymysql://backend:password@127.0.0.1:3306/cqc_test"
    )

    engine = create_db_engine(settings)
    session_factory = create_session_factory(engine)

    assert engine.url.drivername == "mysql+pymysql"
    assert session_factory.kw["bind"] is engine
    assert session_factory.kw["autoflush"] is False
    assert session_factory.kw["expire_on_commit"] is False
    engine.dispose()


def test_engine_requires_mysql_pymysql_database_url() -> None:
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        create_db_engine(Settings(database_url=None))

    with pytest.raises(ValueError, match=r"mysql\+pymysql"):
        create_db_engine(Settings(database_url="sqlite://"))
