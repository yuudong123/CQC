from fastapi.testclient import TestClient

from src.api.core.config import Settings
from src.api.main import create_app


def test_health_returns_backend_status() -> None:
    settings = Settings(app_name="CQC Backend Test", app_env="test")

    with TestClient(create_app(settings)) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "CQC Backend Test",
        "environment": "test",
    }


def test_openapi_exposes_current_backend_endpoints() -> None:
    with TestClient(create_app(Settings())) as client:
        paths = client.app.openapi()["paths"]

    assert set(paths) == {"/health", "/v1/inspections"}
