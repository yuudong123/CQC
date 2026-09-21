from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_cqc_result_to_open_lot_flow() -> None:
    cqc_id = "CQC-test-flow-001"
    cqc_response = client.post(
        "/api/v1/cqc-results",
        json={
            "cqcId": cqc_id,
            "farmId": "farm-asan",
            "crop": "apple",
            "variety": "fuji",
            "qualityGrade": "SPECIAL",
            "confidence": 0.94,
            "quantityKg": 500,
            "origin": {"type": "Point", "coordinates": [127.017, 36.806]},
        },
    )
    assert cqc_response.status_code == 201

    lot_response = client.post(
        "/api/v1/lots",
        json={"cqcId": cqc_id, "reservePriceWon": 1_200_000},
    )
    assert lot_response.status_code == 201
    lot = lot_response.json()
    assert lot["quantityKg"] == 500
    assert lot["auctionStatus"] == "DRAFT"

    opened = client.post(f"/api/v1/lots/{lot['lotId']}/open")
    assert opened.status_code == 200
    assert opened.json()["auctionStatus"] == "OPEN"

    reopened = client.post(f"/api/v1/lots/{lot['lotId']}/open")
    assert reopened.status_code == 409


def test_lot_requires_cqc_result() -> None:
    response = client.post(
        "/api/v1/lots",
        json={"cqcId": "missing-cqc", "reservePriceWon": 100_000},
    )

    assert response.status_code == 404


def test_bidding_and_award_flow() -> None:
    cqc_id = "CQC-test-auction-001"
    client.post(
        "/api/v1/cqc-results",
        json={
            "cqcId": cqc_id,
            "farmId": "farm-asan",
            "variety": "fuji",
            "qualityGrade": "SPECIAL",
            "confidence": 0.91,
            "quantityKg": 300,
            "origin": {"type": "Point", "coordinates": [127.017, 36.806]},
        },
    )
    lot = client.post(
        "/api/v1/lots",
        json={"cqcId": cqc_id, "reservePriceWon": 500_000},
    ).json()
    client.post(f"/api/v1/lots/{lot['lotId']}/open")

    below_reserve = client.post(
        f"/api/v1/lots/{lot['lotId']}/bids",
        json={
            "buyerId": "buyer-1",
            "priceWon": 400_000,
            "destination": {"type": "Point", "coordinates": [127.1, 37.4]},
        },
    )
    assert below_reserve.status_code == 409

    first = client.post(
        f"/api/v1/lots/{lot['lotId']}/bids",
        json={
            "buyerId": "buyer-1",
            "priceWon": 550_000,
            "destination": {"type": "Point", "coordinates": [127.1, 37.4]},
        },
    )
    assert first.status_code == 201

    lower = client.post(
        f"/api/v1/lots/{lot['lotId']}/bids",
        json={
            "buyerId": "buyer-2",
            "priceWon": 550_000,
            "destination": {"type": "Point", "coordinates": [127.2, 37.5]},
        },
    )
    assert lower.status_code == 409

    closed = client.post(f"/api/v1/lots/{lot['lotId']}/close")
    assert closed.status_code == 200
    assert closed.json()["lot"]["auctionStatus"] == "AWARDED"
    assert closed.json()["winningBid"]["buyerId"] == "buyer-1"


def test_bid_is_broadcast_over_websocket() -> None:
    cqc_id = "CQC-test-websocket-001"
    client.post(
        "/api/v1/cqc-results",
        json={
            "cqcId": cqc_id,
            "farmId": "farm-websocket",
            "variety": "yanggwang",
            "qualityGrade": "PREMIUM",
            "confidence": 0.9,
            "quantityKg": 200,
            "origin": {"type": "Point", "coordinates": [127.017, 36.806]},
        },
    )
    lot = client.post(
        "/api/v1/lots",
        json={"cqcId": cqc_id, "reservePriceWon": 250_000},
    ).json()
    client.post(f"/api/v1/lots/{lot['lotId']}/open")

    with TestClient(app) as session:
        with session.websocket_connect(f"/api/v1/ws/auctions/{lot['lotId']}") as socket:
            response = session.post(
                f"/api/v1/lots/{lot['lotId']}/bids",
                json={
                    "buyerId": "buyer-websocket",
                    "priceWon": 300_000,
                    "destination": {"type": "Point", "coordinates": [127.2, 37.5]},
                },
            )
            assert response.status_code == 201
            event = socket.receive_json()

    assert event["type"] == "BID_PLACED"
    assert event["bid"]["priceWon"] == 300_000
