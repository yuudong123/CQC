from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def create_order(cqc_id: str, quantity_kg: int = 500) -> dict:
    client.post(
        "/api/v1/cqc-results",
        json={
            "cqcId": cqc_id,
            "farmId": "farm-delivery",
            "variety": "fuji",
            "qualityGrade": "PREMIUM",
            "confidence": 0.95,
            "quantityKg": quantity_kg,
            "origin": {"type": "Point", "coordinates": [127.017, 36.806]},
        },
    )
    lot = client.post(
        "/api/v1/lots",
        json={"cqcId": cqc_id, "reservePriceWon": 800_000},
    ).json()
    client.post(f"/api/v1/lots/{lot['lotId']}/open")
    client.post(
        f"/api/v1/lots/{lot['lotId']}/bids",
        json={
            "buyerId": f"buyer-{cqc_id}",
            "priceWon": 850_000,
            "destination": {"type": "Point", "coordinates": [127.028, 37.498]},
        },
    )
    return client.post(f"/api/v1/lots/{lot['lotId']}/close").json()["order"]


def test_delivery_requires_arrival_and_completes_route() -> None:
    order = create_order("CQC-test-delivery-001")
    fleet = client.post(
        "/api/v1/fleets",
        json={
            "name": "Delivery Test Fleet",
            "capacityKg": 2_000,
            "location": {"type": "Point", "coordinates": [127.017, 36.806]},
        },
    ).json()
    dispatch = client.post(f"/api/v1/orders/{order['orderId']}/dispatch")
    assert dispatch.status_code == 200

    arrived = client.post(f"/api/v1/fleets/{fleet['fleetId']}/simulate-step")
    assert arrived.status_code == 200
    assert arrived.json()["arrived"] is True
    assert arrived.json()["fleet"]["status"] == "WAITING_LOAD"
    assert arrived.json()["route"]["stops"][0]["status"] == "ARRIVED"

    loaded = client.post(f"/api/v1/orders/{order['orderId']}/load-complete")
    assert loaded.status_code == 200
    assert loaded.json()["order"]["status"] == "LOADED"

    delivery_arrived = None
    for _ in range(10):
        delivery_arrived = client.post(
            f"/api/v1/fleets/{fleet['fleetId']}/simulate-step"
        )
        if delivery_arrived.json()["arrived"]:
            break
    assert delivery_arrived is not None
    assert delivery_arrived.status_code == 200
    assert delivery_arrived.json()["fleet"]["status"] == "WAITING_UNLOAD"

    unloaded = client.post(f"/api/v1/orders/{order['orderId']}/unload-complete")
    assert unloaded.status_code == 200
    result = unloaded.json()
    assert result["order"]["status"] == "DELIVERED"
    assert result["fleet"]["status"] == "IDLE"
    assert result["fleet"]["currentLoadKg"] == 0
    assert result["route"]["status"] == "COMPLETED"


def test_load_before_pickup_arrival_is_rejected() -> None:
    order = create_order("CQC-test-delivery-002")
    client.post(
        "/api/v1/fleets",
        json={
            "name": "Far Delivery Test Fleet",
            "capacityKg": 2_000,
            "location": {"type": "Point", "coordinates": [129.0756, 35.1796]},
        },
    ).json()
    assert client.post(f"/api/v1/orders/{order['orderId']}/dispatch").status_code == 200
    rejected = client.post(f"/api/v1/orders/{order['orderId']}/load-complete")
    assert rejected.status_code == 409
    assert "도착" in rejected.json()["detail"]


def test_new_order_is_inserted_into_active_route() -> None:
    client.post("/api/v1/control/seed-reset")
    first_order = create_order("CQC-test-dynamic-001")
    fleet = client.post(
        "/api/v1/fleets",
        json={
            "name": "Dynamic Route Fleet",
            "capacityKg": 7_000,
            "location": {"type": "Point", "coordinates": [127.017, 36.806]},
        },
    ).json()
    first_dispatch = client.post(f"/api/v1/orders/{first_order['orderId']}/dispatch")
    assert first_dispatch.status_code == 200
    assert client.post(f"/api/v1/fleets/{fleet['fleetId']}/simulate-step").json()["arrived"]
    assert client.post(f"/api/v1/orders/{first_order['orderId']}/load-complete").status_code == 200

    second_order = create_order("CQC-test-dynamic-002", quantity_kg=6_000)
    second_dispatch = client.post(f"/api/v1/orders/{second_order['orderId']}/dispatch")
    assert second_dispatch.status_code == 200
    result = second_dispatch.json()
    assert result["fleet"]["fleetId"] == fleet["fleetId"]
    assert result["fleet"]["currentLoadKg"] == 6_500
    assert result["route"]["version"] == 2
    assert [stop["type"] for stop in result["route"]["stops"]] == [
        "PICKUP", "PICKUP", "DROPOFF", "DROPOFF"
    ]

    assert client.post(f"/api/v1/fleets/{fleet['fleetId']}/simulate-step").json()["arrived"]
    assert client.post(f"/api/v1/orders/{second_order['orderId']}/load-complete").status_code == 200
    for _ in range(10):
        if client.post(f"/api/v1/fleets/{fleet['fleetId']}/simulate-step").json()["arrived"]:
            break
    second_unload = client.post(f"/api/v1/orders/{second_order['orderId']}/unload-complete")
    assert second_unload.status_code == 200
    assert second_unload.json()["route"]["status"] == "ACTIVE"
    assert second_unload.json()["fleet"]["currentLoadKg"] == 500
    for _ in range(10):
        if client.post(f"/api/v1/fleets/{fleet['fleetId']}/simulate-step").json()["arrived"]:
            break
    first_unload = client.post(f"/api/v1/orders/{first_order['orderId']}/unload-complete")
    assert first_unload.status_code == 200
    assert first_unload.json()["route"]["status"] == "COMPLETED"
    assert first_unload.json()["fleet"]["status"] == "IDLE"


def test_breakdown_assigns_remaining_route_to_replacement_fleet() -> None:
    order = create_order("CQC-test-breakdown-001", quantity_kg=3_000)
    broken = client.post(
        "/api/v1/fleets",
        json={
            "name": "Broken Fleet",
            "capacityKg": 4_000,
            "location": {"type": "Point", "coordinates": [127.017, 36.806]},
        },
    ).json()
    client.post(
        "/api/v1/fleets",
        json={
            "name": "Replacement Fleet",
            "capacityKg": 4_000,
            "location": {"type": "Point", "coordinates": [127.02, 36.81]},
        },
    )
    assert client.post(f"/api/v1/orders/{order['orderId']}/dispatch").status_code == 200

    breakdown = client.post(f"/api/v1/fleets/{broken['fleetId']}/breakdown")
    assert breakdown.status_code == 200
    result = breakdown.json()
    assert result["brokenFleet"]["status"] == "OUT_OF_SERVICE"
    assert result["brokenFleet"]["currentLoadKg"] == 0
    assert result["previousRoute"]["status"] == "CANCELLED"
    assert result["replacementFleet"]["fleetId"] != broken["fleetId"]
    assert result["replacementRoute"]["status"] == "ACTIVE"
    assert result["orders"][0]["fleetId"] == result["replacementFleet"]["fleetId"]

    replacement_id = result["replacementFleet"]["fleetId"]
    assert client.post(f"/api/v1/fleets/{replacement_id}/simulate-step").json()["arrived"]
    assert client.post(f"/api/v1/orders/{order['orderId']}/load-complete").status_code == 200
    for _ in range(10):
        if client.post(f"/api/v1/fleets/{replacement_id}/simulate-step").json()["arrived"]:
            break
    unloaded = client.post(f"/api/v1/orders/{order['orderId']}/unload-complete")
    assert unloaded.status_code == 200
    assert unloaded.json()["order"]["status"] == "DELIVERED"
    assert unloaded.json()["fleet"]["status"] == "IDLE"
