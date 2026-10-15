from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_reports_memory_storage() -> None:
    assert client.get("/api/v1/health").json()["storage"] == "memory"
