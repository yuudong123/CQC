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
    monkeypatch.setenv("INFERENCE_BUSINESS_DEADLINE_MS", "750")
    monkeypatch.setenv("INFERENCE_HARD_TIMEOUT_MS", "2500")
    monkeypatch.setenv("MAX_LATE_TASKS", "3")

    settings = Settings()

    assert settings.app_name == "Configured CQC Backend"
    assert settings.app_env == "test"
    assert settings.app_host == "127.0.0.1"
    assert settings.app_port == 8100
    assert settings.database_url == (
        "mysql+pymysql://backend:password@127.0.0.1:3306/cqc_test"
    )
    assert settings.cultivar_confidence_threshold == 0.61
    assert settings.quality_confidence_threshold == 0.62
    assert settings.inference_business_deadline_ms == 750
    assert settings.inference_hard_timeout_ms == 2500
    assert settings.max_late_tasks == 3


def test_policy_settings_use_confirmed_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.cultivar_confidence_threshold == 0.50
    assert settings.quality_confidence_threshold == 0.50
    assert settings.inference_business_deadline_ms == 500
    assert settings.inference_hard_timeout_ms == 2000
    assert settings.max_late_tasks == 4
