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
    assert table.c.virtual_brix.nullable is True
    assert table.c.virtual_brix.type.precision == 4
    assert table.c.virtual_brix.type.scale == 1
    assert table.c.brix_source.nullable is True
    assert table.c.brix_is_measured.nullable is False
    assert table.c.sweetness_band.nullable is True
    assert table.c.late_result_payload.nullable is True
    assert "late_predicted_cultivar" not in table.c
    assert "late_predicted_grade" not in table.c
    assert table.c.persistence_status.nullable is False


def test_datetime_columns_do_not_fix_a_database_timezone_default() -> None:
    inspection_table = Inspection.__table__
    bin_mapping_table = BinMapping.__table__

    for column_name in ("created_at", "completed_at", "updated_at"):
        assert inspection_table.c[column_name].server_default is None

    for column_name in ("created_at", "updated_at"):
        assert bin_mapping_table.c[column_name].server_default is None


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

    assert ("bin_code",) in column_unique_constraints
    assert (
        "crop_type",
        "cultivar",
        "quality_grade",
        "sweetness_band",
    ) in column_unique_constraints
    assert "mapping_key" not in table.c
    assert table.c.sweetness_band.nullable is True
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


def test_engine_passes_configured_connection_timeout_to_pymysql(monkeypatch) -> None:
    from src.api.db import session as db_session

    captured = {}

    def fake_create_engine(url, **kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(db_session, "create_engine", fake_create_engine)
    db_session.create_db_engine(
        Settings(
            database_url="mysql+pymysql://backend@127.0.0.1:3306/cqc_test",
            db_connect_timeout_seconds=3,
        )
    )

    assert captured["connect_args"] == {"connect_timeout": 3}
    assert captured["pool_pre_ping"] is True


def test_engine_requires_mysql_pymysql_database_url() -> None:
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        create_db_engine(Settings(database_url=None))

    with pytest.raises(ValueError, match=r"mysql\+pymysql"):
        create_db_engine(Settings(database_url="sqlite://"))
