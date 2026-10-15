from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_seed_reset_restores_demo_control_state() -> None:
    reset = client.post("/api/v1/control/seed-reset")
    assert reset.status_code == 200
    body = reset.json()
    assert body["storage"] == "memory"
    assert body["stats"]["openAuctions"] == 1
    assert body["stats"]["activeFleets"] == 1
    assert len(body["fleets"]) == 3
    assert len(body["orders"]) == 1
    assert body["routes"][0]["status"] == "ACTIVE"

    overview = client.get("/api/v1/control/overview")
    assert overview.status_code == 200
    assert overview.json()["stats"] == body["stats"]
