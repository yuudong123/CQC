import pytest
from pytest import MonkeyPatch

from src.api.core.config import Settings


def test_settings_reads_backend_environment_variables(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("APP_NAME", "Configured CQC Backend")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("APP_HOST", "127.0.0.1")
    monkeypatch.setenv("APP_PORT", "8100")
    monkeypatch.setenv(
        "DATABASE_URL",
        "mysql+pymysql://backend:password@127.0.0.1:3306/cqc_test",
    )
    monkeypatch.setenv("CULTIVAR_CONFIDENCE_THRESHOLD", "0.61")
    monkeypatch.setenv("QUALITY_CONFIDENCE_THRESHOLD", "0.62")
    monkeypatch.setenv("DB_CONNECT_TIMEOUT_SECONDS", "3")
    monkeypatch.setenv("INSPECTION_HISTORY_LIMIT", "100")
    monkeypatch.setenv("INSPECTION_HISTORY_DELETE_BATCH", "10")
    monkeypatch.setenv("INFERENCE_BUSINESS_DEADLINE_MS", "750")
    monkeypatch.setenv("INFERENCE_HARD_TIMEOUT_MS", "2500")
    monkeypatch.setenv("INFERENCE_CONNECT_TIMEOUT_MS", "220")
    monkeypatch.setenv("MAX_LATE_TASKS", "3")
    monkeypatch.setenv("VIRTUAL_CONTROL_HISTORY_LIMIT", "17")
    monkeypatch.setenv("LATE_RESULT_HISTORY_LIMIT", "23")

    settings = Settings()

    assert settings.app_name == "Configured CQC Backend"
    assert settings.app_env == "test"
    assert settings.app_host == "127.0.0.1"
    assert settings.app_port == 8100
    assert settings.database_url == (
        "mysql+pymysql://backend:password@127.0.0.1:3306/cqc_test"
    )
    assert settings.db_connect_timeout_seconds == 3
    assert settings.inspection_history_limit == 100
    assert settings.inspection_history_delete_batch == 10
    assert settings.cultivar_confidence_threshold == 0.61
    assert settings.quality_confidence_threshold == 0.62
    assert settings.inference_business_deadline_ms == 750
    assert settings.inference_hard_timeout_ms == 2500
    assert settings.inference_connect_timeout_ms == 220
    assert settings.max_late_tasks == 3
    assert settings.virtual_control_history_limit == 17
    assert settings.late_result_history_limit == 23


def test_policy_settings_use_confirmed_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.cultivar_confidence_threshold == 0.50
    assert settings.quality_confidence_threshold == 0.60
    assert settings.db_connect_timeout_seconds == 1
    assert settings.inspection_history_limit == 86_400
    assert settings.inspection_history_delete_batch == 8_640
    assert settings.inference_business_deadline_ms == 500
    assert settings.inference_hard_timeout_ms == 2000
    assert settings.inference_connect_timeout_ms == 200
    assert settings.max_late_tasks == 4
    assert settings.virtual_control_history_limit == 200
    assert settings.late_result_history_limit == 200
    assert settings.live_preview_grace_seconds == 3
    assert settings.live_preview_max_dimension == 240
    assert settings.live_preview_jpeg_quality == 90


def test_history_delete_batch_must_be_below_limit() -> None:
    with pytest.raises(ValueError, match="INSPECTION_HISTORY_DELETE_BATCH"):
        Settings(
            _env_file=None,
            inspection_history_limit=5,
            inspection_history_delete_batch=5,
        )


def test_connect_timeout_must_be_below_500ms_deadline() -> None:
    with pytest.raises(ValueError, match="inference_connect_timeout_ms"):
        Settings(_env_file=None, inference_connect_timeout_ms=500)


@pytest.mark.parametrize(
    "name", ["virtual_control_history_limit", "late_result_history_limit"]
)
@pytest.mark.parametrize("limit", [0, -1])
def test_diagnostic_history_limits_must_be_positive(name, limit):
    with pytest.raises(ValueError, match=name):
        Settings(_env_file=None, **{name: limit})


def test_app_injects_independent_diagnostic_history_limits():
    from src.api.main import create_app

    app = create_app(
        Settings(
            _env_file=None,
            database_url=None,
            inference_client_mode="mock",
            simulator_internal_url=None,
            virtual_control_history_limit=17,
            late_result_history_limit=23,
        )
    )
    service = app.state.inspection_service
    assert service._virtual_control._history_limit == 17
    assert service._late_result_manager._history_limit == 23
