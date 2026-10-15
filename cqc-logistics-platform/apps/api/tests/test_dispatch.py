from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_awarded_order_selects_nearest_capacity_fleet() -> None:
    cqc_id = "CQC-test-dispatch-001"
    client.post(
        "/api/v1/cqc-results",
        json={
            "cqcId": cqc_id,
            "farmId": "farm-dispatch",
            "variety": "fuji",
            "qualityGrade": "SPECIAL",
            "confidence": 0.93,
            "quantityKg": 500,
            "origin": {"type": "Point", "coordinates": [127.017, 36.806]},
        },
    )
    lot = client.post(
        "/api/v1/lots",
        json={"cqcId": cqc_id, "reservePriceWon": 800_000},
    ).json()
    client.post(f"/api/v1/lots/{lot['lotId']}/open")
    bid = client.post(
        f"/api/v1/lots/{lot['lotId']}/bids",
        json={
            "buyerId": "buyer-dispatch",
            "priceWon": 850_000,
            "destination": {"type": "Point", "coordinates": [127.028, 37.498]},
        },
    )
    assert bid.status_code == 201
    order = client.post(f"/api/v1/lots/{lot['lotId']}/close").json()["order"]

    too_small = client.post(
        "/api/v1/fleets",
        json={
            "name": "Small", "capacityKg": 100,
            "location": {"type": "Point", "coordinates": [127.017, 36.806]},
        },
    )
    assert too_small.status_code == 201
    far = client.post(
        "/api/v1/fleets",
        json={
            "name": "Far", "capacityKg": 2_000,
            "location": {"type": "Point", "coordinates": [129.0, 35.1]},
        },
    )
    assert far.status_code == 201
    near = client.post(
        "/api/v1/fleets",
        json={
            "name": "Near", "capacityKg": 2_000,
            "location": {"type": "Point", "coordinates": [127.018, 36.807]},
        },
    )
    assert near.status_code == 201

    dispatched = client.post(f"/api/v1/orders/{order['orderId']}/dispatch")
    assert dispatched.status_code == 200
    result = dispatched.json()
    assert result["order"]["status"] == "ASSIGNED"
    assert result["fleet"]["fleetId"] == near.json()["fleetId"]
    assert result["fleet"]["currentLoadKg"] == 500
    assert [stop["type"] for stop in result["route"]["stops"]] == ["PICKUP", "DROPOFF"]

    duplicate = client.post(f"/api/v1/orders/{order['orderId']}/dispatch")
    assert duplicate.status_code == 409
