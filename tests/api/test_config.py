from pytest import MonkeyPatch

from src.api.core.config import Settings


def test_settings_reads_backend_environment_variables(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("APP_NAME", "Configured CQC Backend")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("APP_HOST", "127.0.0.1")
    monkeypatch.setenv("APP_PORT", "8100")

    settings = Settings()

    assert settings.app_name == "Configured CQC Backend"
    assert settings.app_env == "test"
    assert settings.app_host == "127.0.0.1"
    assert settings.app_port == 8100
