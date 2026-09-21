from copy import deepcopy
from datetime import UTC, datetime, timedelta
from math import asin, cos, radians, sin, sqrt
from typing import Any, Protocol
from uuid import uuid4

from pymongo import ASCENDING, DESCENDING, MongoClient, ReturnDocument

from app.config import Settings
from app.domain.market import BidCreate, CQCResultCreate, FleetCreate, LotCreate


def now_utc() -> datetime:
    return datetime.now(UTC)


def distance_km(first: dict[str, Any], second: dict[str, Any]) -> float:
    lon1, lat1 = first["coordinates"]
    lon2, lat2 = second["coordinates"]
    lat1, lat2 = radians(lat1), radians(lat2)
    delta_lat = lat2 - lat1
    delta_lon = radians(lon2 - lon1)
    a = sin(delta_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
    return 6371 * 2 * asin(sqrt(a))


def move_towards(
    current: dict[str, Any], target: dict[str, Any], max_km: float = 20
) -> tuple[dict[str, Any], bool]:
    """Move a GeoJSON point by at most max_km, returning the new point and arrival."""
    distance = distance_km(current, target)
    if distance <= max_km or distance == 0:
        return target, True
    ratio = max_km / distance
    current_lon, current_lat = current["coordinates"]
    target_lon, target_lat = target["coordinates"]
    return {
        "type": "Point",
        "coordinates": [
            current_lon + (target_lon - current_lon) * ratio,
            current_lat + (target_lat - current_lat) * ratio,
        ],
    }, False


def insert_order_stops(route: dict[str, Any], order: dict[str, Any]) -> None:
    """Insert a new pickup/dropoff pair before the first open dropoff."""
    insert_at = next(
        (
            index for index, stop in enumerate(route["stops"])
            if stop["status"] != "COMPLETED" and stop["type"] == "DROPOFF"
        ),
        len(route["stops"]),
    )
    new_stops = [
        {
            "sequence": 0, "type": "PICKUP", "orderId": order["orderId"],
            "location": order["origin"], "status": "PENDING",
        },
        {
            "sequence": 0, "type": "DROPOFF", "orderId": order["orderId"],
            "location": order["destination"], "status": "PENDING",
        },
    ]
    route["stops"][insert_at:insert_at] = new_stops
    for sequence, stop in enumerate(route["stops"], start=1):
        stop["sequence"] = sequence
    route["version"] += 1


def recalculate_route_distance(route: dict[str, Any], current: dict[str, Any]) -> None:
    points = [current] + [
        stop["location"] for stop in route["stops"] if stop["status"] != "COMPLETED"
    ]
    route["distanceKm"] = round(
        sum(
            distance_km(first, second)
            for first, second in zip(points, points[1:], strict=False)
        ),
        1,
    )
    route["estimatedMinutes"] = max(1, round(route["distanceKm"] * 2))


def build_replacement_route(
    fleet_id: str,
    stops: list[dict[str, Any]],
    current: dict[str, Any],
    timestamp: datetime,
) -> dict[str, Any]:
    route = {
        "routeId": f"route-{uuid4().hex[:10]}",
        "fleetId": fleet_id,
        "version": 1,
        "status": "ACTIVE",
        "stops": deepcopy(stops),
        "distanceKm": 0.0,
        "estimatedMinutes": 1,
        "createdAt": timestamp,
        "updatedAt": timestamp,
    }
    for sequence, stop in enumerate(route["stops"], start=1):
        stop["sequence"] = sequence
    recalculate_route_distance(route, current)
    return route


def seed_demo_data(store: Any) -> None:
    """Create a repeatable presentation state without external integrations."""
    origin = {"type": "Point", "coordinates": [127.017, 36.806]}
    destination = {"type": "Point", "coordinates": [127.028, 37.498]}
    first_cqc = store.save_cqc_result(
        CQCResultCreate(
            cqcId="CQC-demo-market-001", farmId="farm-asan", variety="fuji",
            qualityGrade="SPECIAL", confidence=0.96, quantityKg=500, origin=origin,
        )
    )
    first_lot = store.create_lot(
        LotCreate(cqcId=first_cqc["cqcId"], reservePriceWon=1_200_000), first_cqc
    )
    store.open_lot(first_lot["lotId"])
    second_cqc = store.save_cqc_result(
        CQCResultCreate(
            cqcId="CQC-demo-route-001", farmId="farm-chungju", variety="hongro",
            qualityGrade="PREMIUM", confidence=0.93, quantityKg=500, origin=origin,
        )
    )
    second_lot = store.create_lot(
        LotCreate(cqcId=second_cqc["cqcId"], reservePriceWon=900_000), second_cqc
    )
    store.open_lot(second_lot["lotId"])
    bid = store.place_bid(
        second_lot["lotId"],
        BidCreate(buyerId="buyer-seoul-mart", priceWon=980_000, destination=destination),
    )
    awarded_lot = store.close_lot(second_lot["lotId"])
    order = store.create_order(awarded_lot, bid)
    store.create_fleet(
        FleetCreate(name="CQC-01", capacityKg=2_000, location=origin)
    )
    store.create_fleet(
        FleetCreate(
            name="CQC-02", capacityKg=4_000,
            location={"type": "Point", "coordinates": [129.0756, 35.1796]},
        )
    )
    store.create_fleet(
        FleetCreate(
            name="CQC-03", capacityKg=2_000,
            location={"type": "Point", "coordinates": [127.3845, 36.3504]},
        )
    )
    store.dispatch_order(order["orderId"])


class Store(Protocol):
    storage_name: str

    def save_cqc_result(self, payload: CQCResultCreate) -> dict[str, Any]: ...

    def get_cqc_result(self, cqc_id: str) -> dict[str, Any] | None: ...

    def create_lot(self, payload: LotCreate, cqc: dict[str, Any]) -> dict[str, Any]: ...

    def list_lots(self, status: str | None = None) -> list[dict[str, Any]]: ...

    def open_lot(self, lot_id: str) -> dict[str, Any] | None: ...

    def get_lot(self, lot_id: str) -> dict[str, Any] | None: ...

    def place_bid(self, lot_id: str, payload: BidCreate) -> dict[str, Any]: ...

    def list_bids(self, lot_id: str) -> list[dict[str, Any]]: ...

    def close_lot(self, lot_id: str) -> dict[str, Any] | None: ...

    def create_order(self, lot: dict[str, Any], bid: dict[str, Any]) -> dict[str, Any]: ...

    def get_order(self, order_id: str) -> dict[str, Any] | None: ...

    def create_fleet(self, payload: FleetCreate) -> dict[str, Any]: ...

    def list_fleets(self) -> list[dict[str, Any]]: ...

    def get_fleet(self, fleet_id: str) -> dict[str, Any] | None: ...

    def list_orders(self) -> list[dict[str, Any]]: ...

    def dispatch_order(self, order_id: str) -> dict[str, Any]: ...

    def get_route(self, route_id: str) -> dict[str, Any] | None: ...

    def list_routes(self) -> list[dict[str, Any]]: ...

    def simulate_fleet_step(self, fleet_id: str) -> dict[str, Any]: ...

    def load_order(self, order_id: str) -> dict[str, Any]: ...

    def unload_order(self, order_id: str) -> dict[str, Any]: ...

    def breakdown_fleet(self, fleet_id: str) -> dict[str, Any]: ...

    def reset_demo(self) -> None: ...


class MemoryStore:
    storage_name = "memory"

    def __init__(self) -> None:
        self.cqc_results: dict[str, dict[str, Any]] = {}
        self.lots: dict[str, dict[str, Any]] = {}
        self.bids: dict[str, list[dict[str, Any]]] = {}
        self.orders: dict[str, dict[str, Any]] = {}
        self.fleets: dict[str, dict[str, Any]] = {}
        self.routes: dict[str, dict[str, Any]] = {}

    def save_cqc_result(self, payload: CQCResultCreate) -> dict[str, Any]:
        existing = self.cqc_results.get(payload.cqcId)
        document = payload.model_dump(mode="json")
        document["createdAt"] = existing["createdAt"] if existing else now_utc()
        self.cqc_results[payload.cqcId] = document
        return document

    def get_cqc_result(self, cqc_id: str) -> dict[str, Any] | None:
        return self.cqc_results.get(cqc_id)

    def create_lot(self, payload: LotCreate, cqc: dict[str, Any]) -> dict[str, Any]:
        timestamp = now_utc()
        document = {
            "lotId": f"lot-{uuid4().hex[:10]}",
            "cqcId": payload.cqcId,
            "sellerId": cqc["farmId"],
            "crop": cqc["crop"],
            "variety": cqc["variety"],
            "qualityGrade": cqc["qualityGrade"],
            "quantityKg": cqc["quantityKg"],
            "origin": cqc["origin"],
            "reservePriceWon": payload.reservePriceWon,
            "suggestedPriceWon": payload.suggestedPriceWon,
            "auctionStatus": "DRAFT",
            "closesAt": payload.closesAt or timestamp + timedelta(minutes=10),
            "createdAt": timestamp,
            "updatedAt": timestamp,
        }
        self.lots[document["lotId"]] = document
        return document

    def list_lots(self, status: str | None = None) -> list[dict[str, Any]]:
        documents = list(self.lots.values())
        if status:
            documents = [lot for lot in documents if lot["auctionStatus"] == status]
        return sorted(documents, key=lambda lot: lot["createdAt"], reverse=True)

    def open_lot(self, lot_id: str) -> dict[str, Any] | None:
        document = self.lots.get(lot_id)
        if document is None or document["auctionStatus"] != "DRAFT":
            return None
        document["auctionStatus"] = "OPEN"
        document["updatedAt"] = now_utc()
        return document

    def get_lot(self, lot_id: str) -> dict[str, Any] | None:
        return self.lots.get(lot_id)

    def place_bid(self, lot_id: str, payload: BidCreate) -> dict[str, Any]:
        lot = self.lots.get(lot_id)
        if lot is None or lot["auctionStatus"] != "OPEN":
            raise ValueError("auction_not_open")
        bids = self.bids.setdefault(lot_id, [])
        highest = max((bid["priceWon"] for bid in bids), default=0)
        if payload.priceWon < lot["reservePriceWon"]:
            raise ValueError("below_reserve")
        if payload.priceWon <= highest:
            raise ValueError("not_highest")
        document = {
            "bidId": f"bid-{uuid4().hex[:10]}",
            "lotId": lot_id,
            **payload.model_dump(),
            "accepted": True,
            "placedAt": now_utc(),
        }
        bids.append(document)
        return document

    def list_bids(self, lot_id: str) -> list[dict[str, Any]]:
        return sorted(
            self.bids.get(lot_id, []),
            key=lambda bid: (bid["priceWon"], bid["placedAt"]),
            reverse=True,
        )

    def close_lot(self, lot_id: str) -> dict[str, Any] | None:
        lot = self.lots.get(lot_id)
        if lot is None or lot["auctionStatus"] != "OPEN":
            return None
        highest = self.list_bids(lot_id)
        lot["auctionStatus"] = "AWARDED" if highest else "CLOSED_UNSOLD"
        lot["updatedAt"] = now_utc()
        return lot

    def create_order(self, lot: dict[str, Any], bid: dict[str, Any]) -> dict[str, Any]:
        existing = next(
            (order for order in self.orders.values() if order["lotId"] == lot["lotId"]),
            None,
        )
        if existing:
            return existing
        timestamp = now_utc()
        order = {
            "orderId": f"order-{uuid4().hex[:10]}",
            "lotId": lot["lotId"],
            "sellerId": lot["sellerId"],
            "buyerId": bid["buyerId"],
            "quantityKg": lot["quantityKg"],
            "priceWon": bid["priceWon"],
            "origin": lot["origin"],
            "destination": bid["destination"],
            "status": "MATCHED",
            "fleetId": None,
            "routeId": None,
            "createdAt": timestamp,
            "updatedAt": timestamp,
        }
        self.orders[order["orderId"]] = order
        return order

    def get_order(self, order_id: str) -> dict[str, Any] | None:
        return self.orders.get(order_id)

    def list_orders(self) -> list[dict[str, Any]]:
        return sorted(self.orders.values(), key=lambda order: order["updatedAt"], reverse=True)

    def create_fleet(self, payload: FleetCreate) -> dict[str, Any]:
        timestamp = now_utc()
        fleet = {
            "fleetId": f"fleet-{uuid4().hex[:10]}",
            **payload.model_dump(),
            "currentLoadKg": 0,
            "status": "IDLE",
            "lastPositionAt": timestamp,
        }
        self.fleets[fleet["fleetId"]] = fleet
        return fleet

    def list_fleets(self) -> list[dict[str, Any]]:
        return list(self.fleets.values())

    def get_fleet(self, fleet_id: str) -> dict[str, Any] | None:
        return self.fleets.get(fleet_id)

    def dispatch_order(self, order_id: str) -> dict[str, Any]:
        order = self.orders.get(order_id)
        if order is None:
            raise ValueError("order_not_found")
        if order["status"] != "MATCHED":
            raise ValueError("already_dispatched")
        candidates = [
            fleet
            for fleet in self.fleets.values()
            if fleet["status"] == "IDLE"
            and fleet["capacityKg"] - fleet["currentLoadKg"] >= order["quantityKg"]
        ]
        if not candidates:
            active_candidates = []
            for candidate in self.fleets.values():
                active_route = next(
                    (
                        route for route in self.routes.values()
                        if route["fleetId"] == candidate["fleetId"]
                        and route["status"] == "ACTIVE"
                    ),
                    None,
                )
                if (
                    active_route is not None
                    and candidate["status"] in {
                        "TO_PICKUP", "WAITING_LOAD", "IN_TRANSIT", "WAITING_UNLOAD",
                    }
                    and candidate["capacityKg"] - candidate["currentLoadKg"]
                    >= order["quantityKg"]
                ):
                    active_candidates.append((candidate, active_route))
            if not active_candidates:
                raise ValueError("no_fleet")
            fleet, route = min(
                active_candidates,
                key=lambda item: distance_km(item[0]["location"], order["origin"])
                + distance_km(order["origin"], order["destination"]),
            )
            timestamp = now_utc()
            insert_order_stops(route, order)
            recalculate_route_distance(route, fleet["location"])
            route["updatedAt"] = timestamp
            fleet["currentLoadKg"] += order["quantityKg"]
            fleet["lastPositionAt"] = timestamp
            order["status"] = "ASSIGNED"
            order["fleetId"] = fleet["fleetId"]
            order["routeId"] = route["routeId"]
            order["updatedAt"] = timestamp
            return {"order": order, "fleet": fleet, "route": route}
        fleet = min(candidates, key=lambda item: distance_km(item["location"], order["origin"]))
        timestamp = now_utc()
        distance = distance_km(order["origin"], order["destination"])
        route = {
            "routeId": f"route-{uuid4().hex[:10]}",
            "fleetId": fleet["fleetId"],
            "version": 1,
            "status": "ACTIVE",
            "stops": [
                {
                    "sequence": 1, "type": "PICKUP", "orderId": order_id,
                    "location": order["origin"], "status": "PENDING",
                },
                {
                    "sequence": 2, "type": "DROPOFF", "orderId": order_id,
                    "location": order["destination"], "status": "PENDING",
                },
            ],
            "distanceKm": round(distance, 1),
            "estimatedMinutes": max(1, round(distance * 2)),
            "createdAt": timestamp,
            "updatedAt": timestamp,
        }
        fleet["currentLoadKg"] += order["quantityKg"]
        fleet["status"] = "TO_PICKUP"
        fleet["lastPositionAt"] = timestamp
        order["status"] = "ASSIGNED"
        order["fleetId"] = fleet["fleetId"]
        order["routeId"] = route["routeId"]
        order["updatedAt"] = timestamp
        self.routes[route["routeId"]] = route
        return {"order": order, "fleet": fleet, "route": route}

    def get_route(self, route_id: str) -> dict[str, Any] | None:
        return self.routes.get(route_id)

    def list_routes(self) -> list[dict[str, Any]]:
        return sorted(self.routes.values(), key=lambda route: route["updatedAt"], reverse=True)

    def simulate_fleet_step(self, fleet_id: str) -> dict[str, Any]:
        fleet = self.get_fleet(fleet_id)
        if fleet is None:
            raise ValueError("fleet_not_found")
        route = next(
            (item for item in self.routes.values()
             if item["fleetId"] == fleet_id and item["status"] == "ACTIVE"),
            None,
        )
        if route is None:
            raise ValueError("no_route")
        stop = next((item for item in route["stops"] if item["status"] != "COMPLETED"), None)
        if stop is None:
            raise ValueError("no_route")
        position, arrived = move_towards(fleet["location"], stop["location"])
        timestamp = now_utc()
        fleet["location"] = position
        fleet["lastPositionAt"] = timestamp
        order = self.orders[stop["orderId"]]
        if arrived:
            stop["status"] = "ARRIVED"
            fleet["status"] = "WAITING_LOAD" if stop["type"] == "PICKUP" else "WAITING_UNLOAD"
            order["status"] = "PICKUP_ARRIVED" if stop["type"] == "PICKUP" else "DELIVERY_ARRIVED"
            order["updatedAt"] = timestamp
        else:
            fleet["status"] = "TO_PICKUP" if stop["type"] == "PICKUP" else "IN_TRANSIT"
        route["updatedAt"] = timestamp
        return {"fleet": fleet, "route": route, "arrived": arrived}

    def load_order(self, order_id: str) -> dict[str, Any]:
        order = self.get_order(order_id)
        if order is None:
            raise ValueError("order_not_found")
        if order["status"] not in {"ASSIGNED", "PICKUP_ARRIVED"}:
            raise ValueError("invalid_state")
        fleet = self.get_fleet(order["fleetId"])
        route = self.get_route(order["routeId"])
        if fleet is None or route is None:
            raise ValueError("invalid_state")
        pickup = next(
            (stop for stop in route["stops"]
             if stop["orderId"] == order_id and stop["type"] == "PICKUP"),
            None,
        )
        if pickup is None or pickup["status"] != "ARRIVED":
            raise ValueError("not_arrived")
        timestamp = now_utc()
        pickup["status"] = "COMPLETED"
        order["status"] = "LOADED"
        order["updatedAt"] = timestamp
        fleet["status"] = "IN_TRANSIT"
        fleet["lastPositionAt"] = timestamp
        route["updatedAt"] = timestamp
        return {"order": order, "fleet": fleet, "route": route}

    def unload_order(self, order_id: str) -> dict[str, Any]:
        order = self.get_order(order_id)
        if order is None:
            raise ValueError("order_not_found")
        if order["status"] not in {"LOADED", "DELIVERY_ARRIVED"}:
            raise ValueError("invalid_state")
        fleet = self.get_fleet(order["fleetId"])
        route = self.get_route(order["routeId"])
        if fleet is None or route is None:
            raise ValueError("invalid_state")
        dropoff = next(
            (stop for stop in route["stops"]
             if stop["orderId"] == order_id and stop["type"] == "DROPOFF"),
            None,
        )
        if dropoff is None or dropoff["status"] != "ARRIVED":
            raise ValueError("not_arrived")
        timestamp = now_utc()
        dropoff["status"] = "COMPLETED"
        remaining = next(
            (stop for stop in route["stops"] if stop["status"] != "COMPLETED"),
            None,
        )
        route["status"] = "ACTIVE" if remaining else "COMPLETED"
        route["updatedAt"] = timestamp
        order["status"] = "DELIVERED"
        order["updatedAt"] = timestamp
        fleet["currentLoadKg"] = max(0, fleet["currentLoadKg"] - order["quantityKg"])
        fleet["status"] = (
            "TO_PICKUP" if remaining and remaining["type"] == "PICKUP"
            else "IN_TRANSIT" if remaining
            else "IDLE"
        )
        fleet["lastPositionAt"] = timestamp
        return {"order": order, "fleet": fleet, "route": route}

    def breakdown_fleet(self, fleet_id: str) -> dict[str, Any]:
        fleet = self.get_fleet(fleet_id)
        if fleet is None:
            raise ValueError("fleet_not_found")
        if fleet["status"] == "OUT_OF_SERVICE":
            raise ValueError("already_broken")
        timestamp = now_utc()
        fleet["status"] = "OUT_OF_SERVICE"
        fleet["currentLoadKg"] = 0
        fleet["lastPositionAt"] = timestamp
        route = next(
            (item for item in self.routes.values()
             if item["fleetId"] == fleet_id and item["status"] == "ACTIVE"),
            None,
        )
        if route is None:
            return {
                "brokenFleet": fleet, "previousRoute": None,
                "replacementFleet": None, "replacementRoute": None, "orders": [],
            }
        route["status"] = "CANCELLED"
        route["updatedAt"] = timestamp
        remaining_stops = [
            stop for stop in route["stops"] if stop["status"] != "COMPLETED"
        ]
        order_ids = list(dict.fromkeys(stop["orderId"] for stop in remaining_stops))
        orders = [self.orders[order_id] for order_id in order_ids if order_id in self.orders]
        required_load = sum(order["quantityKg"] for order in orders)
        candidates = [
            candidate for candidate in self.fleets.values()
            if candidate["status"] == "IDLE"
            and candidate["capacityKg"] - candidate["currentLoadKg"] >= required_load
        ]
        if not candidates or not remaining_stops:
            return {
                "brokenFleet": fleet, "previousRoute": route,
                "replacementFleet": None, "replacementRoute": None, "orders": orders,
            }
        replacement = min(
            candidates,
            key=lambda candidate: distance_km(
                candidate["location"], remaining_stops[0]["location"]
            ),
        )
        replacement_route = build_replacement_route(
            replacement["fleetId"], remaining_stops, replacement["location"], timestamp
        )
        replacement["currentLoadKg"] += required_load
        first_stop = replacement_route["stops"][0]
        replacement["status"] = (
            "WAITING_LOAD" if first_stop["status"] == "ARRIVED"
            and first_stop["type"] == "PICKUP"
            else "WAITING_UNLOAD" if first_stop["status"] == "ARRIVED"
            else "TO_PICKUP" if first_stop["type"] == "PICKUP"
            else "IN_TRANSIT"
        )
        replacement["lastPositionAt"] = timestamp
        self.routes[replacement_route["routeId"]] = replacement_route
        for order in orders:
            order["fleetId"] = replacement["fleetId"]
            order["routeId"] = replacement_route["routeId"]
            if order["status"] not in {"LOADED", "DELIVERY_ARRIVED"}:
                order["status"] = "ASSIGNED"
            order["updatedAt"] = timestamp
        return {
            "brokenFleet": fleet, "previousRoute": route,
            "replacementFleet": replacement, "replacementRoute": replacement_route,
            "orders": orders,
        }

    def reset_demo(self) -> None:
        self.cqc_results.clear()
        self.lots.clear()
        self.bids.clear()
        self.orders.clear()
        self.fleets.clear()
        self.routes.clear()
        seed_demo_data(self)


class MongoStore:
    storage_name = "mongodb"

    def __init__(self, settings: Settings) -> None:
        self.client = MongoClient(settings.mongodb_url, serverSelectionTimeoutMS=5_000)
        self.client.admin.command("ping")
        self.db = self.client[settings.mongodb_database]
        self.db.cqc_results.create_index("cqcId", unique=True)
        self.db.lots.create_index("lotId", unique=True)
        self.db.lots.create_index([("auctionStatus", ASCENDING), ("createdAt", DESCENDING)])
        self.db.lots.create_index([("origin", "2dsphere")])
        self.db.bids.create_index(
            [("lotId", ASCENDING), ("priceWon", DESCENDING), ("placedAt", ASCENDING)]
        )
        self.db.orders.create_index("orderId", unique=True)
        self.db.orders.create_index("lotId", unique=True)
        self.db.fleets.create_index("fleetId", unique=True)
        self.db.fleets.create_index([("location", "2dsphere")])
        self.db.routes.create_index("routeId", unique=True)

    def save_cqc_result(self, payload: CQCResultCreate) -> dict[str, Any]:
        existing = self.db.cqc_results.find_one({"cqcId": payload.cqcId})
        document = payload.model_dump()
        document["createdAt"] = existing["createdAt"] if existing else now_utc()
        self.db.cqc_results.replace_one({"cqcId": payload.cqcId}, document, upsert=True)
        return document

    def get_cqc_result(self, cqc_id: str) -> dict[str, Any] | None:
        return self.db.cqc_results.find_one({"cqcId": cqc_id}, {"_id": 0})

    def create_lot(self, payload: LotCreate, cqc: dict[str, Any]) -> dict[str, Any]:
        timestamp = now_utc()
        document = {
            "lotId": f"lot-{uuid4().hex[:10]}",
            "cqcId": payload.cqcId,
            "sellerId": cqc["farmId"],
            "crop": cqc["crop"],
            "variety": cqc["variety"],
            "qualityGrade": cqc["qualityGrade"],
            "quantityKg": cqc["quantityKg"],
            "origin": cqc["origin"],
            "reservePriceWon": payload.reservePriceWon,
            "suggestedPriceWon": payload.suggestedPriceWon,
            "auctionStatus": "DRAFT",
            "closesAt": payload.closesAt or timestamp + timedelta(minutes=10),
            "createdAt": timestamp,
            "updatedAt": timestamp,
        }
        self.db.lots.insert_one(document)
        return {key: value for key, value in document.items() if key != "_id"}

    def list_lots(self, status: str | None = None) -> list[dict[str, Any]]:
        query = {"auctionStatus": status} if status else {}
        return list(self.db.lots.find(query, {"_id": 0}).sort("createdAt", DESCENDING))

    def open_lot(self, lot_id: str) -> dict[str, Any] | None:
        return self.db.lots.find_one_and_update(
            {"lotId": lot_id, "auctionStatus": "DRAFT"},
            {"$set": {"auctionStatus": "OPEN", "updatedAt": now_utc()}},
            projection={"_id": 0},
            return_document=ReturnDocument.AFTER,
        )

    def get_lot(self, lot_id: str) -> dict[str, Any] | None:
        return self.db.lots.find_one({"lotId": lot_id}, {"_id": 0})

    def place_bid(self, lot_id: str, payload: BidCreate) -> dict[str, Any]:
        lot = self.get_lot(lot_id)
        if lot is None or lot["auctionStatus"] != "OPEN":
            raise ValueError("auction_not_open")
        highest = self.db.bids.find_one(
            {"lotId": lot_id}, sort=[("priceWon", DESCENDING), ("placedAt", ASCENDING)]
        )
        highest_price = highest["priceWon"] if highest else 0
        if payload.priceWon < lot["reservePriceWon"]:
            raise ValueError("below_reserve")
        if payload.priceWon <= highest_price:
            raise ValueError("not_highest")
        document = {
            "bidId": f"bid-{uuid4().hex[:10]}",
            "lotId": lot_id,
            **payload.model_dump(),
            "accepted": True,
            "placedAt": now_utc(),
        }
        self.db.bids.insert_one(document)
        return {key: value for key, value in document.items() if key != "_id"}

    def list_bids(self, lot_id: str) -> list[dict[str, Any]]:
        return list(
            self.db.bids.find({"lotId": lot_id}, {"_id": 0}).sort(
                [("priceWon", DESCENDING), ("placedAt", ASCENDING)]
            )
        )

    def close_lot(self, lot_id: str) -> dict[str, Any] | None:
        highest = self.db.bids.find_one(
            {"lotId": lot_id}, sort=[("priceWon", DESCENDING), ("placedAt", ASCENDING)]
        )
        status = "AWARDED" if highest else "CLOSED_UNSOLD"
        return self.db.lots.find_one_and_update(
            {"lotId": lot_id, "auctionStatus": "OPEN"},
            {"$set": {"auctionStatus": status, "updatedAt": now_utc()}},
            projection={"_id": 0},
            return_document=ReturnDocument.AFTER,
        )

    def create_order(self, lot: dict[str, Any], bid: dict[str, Any]) -> dict[str, Any]:
        existing = self.db.orders.find_one({"lotId": lot["lotId"]}, {"_id": 0})
        if existing:
            return existing
        timestamp = now_utc()
        order = {
            "orderId": f"order-{uuid4().hex[:10]}",
            "lotId": lot["lotId"],
            "sellerId": lot["sellerId"],
            "buyerId": bid["buyerId"],
            "quantityKg": lot["quantityKg"],
            "priceWon": bid["priceWon"],
            "origin": lot["origin"],
            "destination": bid["destination"],
            "status": "MATCHED",
            "fleetId": None,
            "routeId": None,
            "createdAt": timestamp,
            "updatedAt": timestamp,
        }
        self.db.orders.insert_one(order)
        return {key: value for key, value in order.items() if key != "_id"}

    def get_order(self, order_id: str) -> dict[str, Any] | None:
        return self.db.orders.find_one({"orderId": order_id}, {"_id": 0})

    def list_orders(self) -> list[dict[str, Any]]:
        return list(self.db.orders.find({}, {"_id": 0}).sort("updatedAt", DESCENDING))

    def create_fleet(self, payload: FleetCreate) -> dict[str, Any]:
        timestamp = now_utc()
        fleet = {
            "fleetId": f"fleet-{uuid4().hex[:10]}",
            **payload.model_dump(),
            "currentLoadKg": 0,
            "status": "IDLE",
            "lastPositionAt": timestamp,
        }
        self.db.fleets.insert_one(fleet)
        return {key: value for key, value in fleet.items() if key != "_id"}

    def list_fleets(self) -> list[dict[str, Any]]:
        return list(self.db.fleets.find({}, {"_id": 0}).sort("fleetId", ASCENDING))

    def get_fleet(self, fleet_id: str) -> dict[str, Any] | None:
        return self.db.fleets.find_one({"fleetId": fleet_id}, {"_id": 0})

    def dispatch_order(self, order_id: str) -> dict[str, Any]:
        order = self.get_order(order_id)
        if order is None:
            raise ValueError("order_not_found")
        if order["status"] != "MATCHED":
            raise ValueError("already_dispatched")
        candidates = [
            fleet
            for fleet in self.list_fleets()
            if fleet["status"] == "IDLE"
            and fleet["capacityKg"] - fleet["currentLoadKg"] >= order["quantityKg"]
        ]
        if not candidates:
            active_candidates = []
            for candidate in self.list_fleets():
                active_route = self.db.routes.find_one(
                    {"fleetId": candidate["fleetId"], "status": "ACTIVE"}, {"_id": 0}
                )
                if (
                    active_route is not None
                    and candidate["status"] in {
                        "TO_PICKUP", "WAITING_LOAD", "IN_TRANSIT", "WAITING_UNLOAD",
                    }
                    and candidate["capacityKg"] - candidate["currentLoadKg"]
                    >= order["quantityKg"]
                ):
                    active_candidates.append((candidate, active_route))
            if not active_candidates:
                raise ValueError("no_fleet")
            fleet, route = min(
                active_candidates,
                key=lambda item: distance_km(item[0]["location"], order["origin"])
                + distance_km(order["origin"], order["destination"]),
            )
            timestamp = now_utc()
            insert_order_stops(route, order)
            recalculate_route_distance(route, fleet["location"])
            route["updatedAt"] = timestamp
            fleet["currentLoadKg"] += order["quantityKg"]
            fleet["lastPositionAt"] = timestamp
            order["status"] = "ASSIGNED"
            order["fleetId"] = fleet["fleetId"]
            order["routeId"] = route["routeId"]
            order["updatedAt"] = timestamp
            self.db.routes.replace_one({"routeId": route["routeId"]}, route)
            self.db.fleets.replace_one({"fleetId": fleet["fleetId"]}, fleet)
            self.db.orders.replace_one({"orderId": order_id}, order)
            return {"order": order, "fleet": fleet, "route": route}
        fleet = min(candidates, key=lambda item: distance_km(item["location"], order["origin"]))
        timestamp = now_utc()
        distance = distance_km(order["origin"], order["destination"])
        route = {
            "routeId": f"route-{uuid4().hex[:10]}",
            "fleetId": fleet["fleetId"],
            "version": 1,
            "status": "ACTIVE",
            "stops": [
                {
                    "sequence": 1, "type": "PICKUP", "orderId": order_id,
                    "location": order["origin"], "status": "PENDING",
                },
                {
                    "sequence": 2, "type": "DROPOFF", "orderId": order_id,
                    "location": order["destination"], "status": "PENDING",
                },
            ],
            "distanceKm": round(distance, 1),
            "estimatedMinutes": max(1, round(distance * 2)),
            "createdAt": timestamp,
            "updatedAt": timestamp,
        }
        self.db.routes.insert_one(route)
        fleet_filter = {
            "fleetId": fleet["fleetId"],
            "status": "IDLE",
            "$expr": {
                "$gte": [
                    {"$subtract": ["$capacityKg", "$currentLoadKg"]},
                    order["quantityKg"],
                ]
            },
        }
        fleet_update = {
            "$inc": {"currentLoadKg": order["quantityKg"]},
            "$set": {"status": "TO_PICKUP", "lastPositionAt": timestamp},
        }
        updated_fleet = self.db.fleets.find_one_and_update(
            fleet_filter,
            fleet_update,
            projection={"_id": 0},
            return_document=ReturnDocument.AFTER,
        )
        if updated_fleet is None:
            self.db.routes.delete_one({"routeId": route["routeId"]})
            raise ValueError("no_fleet")
        updated_order = self.db.orders.find_one_and_update(
            {"orderId": order_id, "status": "MATCHED"},
            {
                "$set": {
                    "status": "ASSIGNED", "fleetId": fleet["fleetId"],
                    "routeId": route["routeId"], "updatedAt": timestamp,
                }
            },
            projection={"_id": 0},
            return_document=ReturnDocument.AFTER,
        )
        if updated_order is None:
            raise ValueError("already_dispatched")
        return {
            "order": updated_order,
            "fleet": updated_fleet,
            "route": {key: value for key, value in route.items() if key != "_id"},
        }

    def get_route(self, route_id: str) -> dict[str, Any] | None:
        return self.db.routes.find_one({"routeId": route_id}, {"_id": 0})

    def list_routes(self) -> list[dict[str, Any]]:
        return list(self.db.routes.find({}, {"_id": 0}).sort("updatedAt", DESCENDING))

    def simulate_fleet_step(self, fleet_id: str) -> dict[str, Any]:
        fleet = self.get_fleet(fleet_id)
        if fleet is None:
            raise ValueError("fleet_not_found")
        route = self.db.routes.find_one(
            {"fleetId": fleet_id, "status": "ACTIVE"}, {"_id": 0}
        )
        if route is None:
            raise ValueError("no_route")
        stop = next((item for item in route["stops"] if item["status"] != "COMPLETED"), None)
        if stop is None:
            raise ValueError("no_route")
        position, arrived = move_towards(fleet["location"], stop["location"])
        timestamp = now_utc()
        fleet["location"] = position
        fleet["lastPositionAt"] = timestamp
        order = self.get_order(stop["orderId"])
        if order is None:
            raise ValueError("order_not_found")
        if arrived:
            stop["status"] = "ARRIVED"
            fleet["status"] = "WAITING_LOAD" if stop["type"] == "PICKUP" else "WAITING_UNLOAD"
            order["status"] = "PICKUP_ARRIVED" if stop["type"] == "PICKUP" else "DELIVERY_ARRIVED"
            order["updatedAt"] = timestamp
        else:
            fleet["status"] = "TO_PICKUP" if stop["type"] == "PICKUP" else "IN_TRANSIT"
        route["updatedAt"] = timestamp
        self.db.fleets.replace_one({"fleetId": fleet_id}, fleet)
        self.db.orders.replace_one({"orderId": order["orderId"]}, order)
        self.db.routes.replace_one({"routeId": route["routeId"]}, route)
        return {"fleet": fleet, "route": route, "arrived": arrived}

    def load_order(self, order_id: str) -> dict[str, Any]:
        order = self.get_order(order_id)
        if order is None:
            raise ValueError("order_not_found")
        if order["status"] not in {"ASSIGNED", "PICKUP_ARRIVED"}:
            raise ValueError("invalid_state")
        fleet = self.get_fleet(order["fleetId"])
        route = self.get_route(order["routeId"])
        if fleet is None or route is None:
            raise ValueError("invalid_state")
        pickup = next(
            (stop for stop in route["stops"]
             if stop["orderId"] == order_id and stop["type"] == "PICKUP"),
            None,
        )
        if pickup is None or pickup["status"] != "ARRIVED":
            raise ValueError("not_arrived")
        timestamp = now_utc()
        pickup["status"] = "COMPLETED"
        order["status"] = "LOADED"
        order["updatedAt"] = timestamp
        fleet["status"] = "IN_TRANSIT"
        fleet["lastPositionAt"] = timestamp
        route["updatedAt"] = timestamp
        self.db.fleets.replace_one({"fleetId": fleet["fleetId"]}, fleet)
        self.db.orders.replace_one({"orderId": order_id}, order)
        self.db.routes.replace_one({"routeId": route["routeId"]}, route)
        return {"order": order, "fleet": fleet, "route": route}

    def breakdown_fleet(self, fleet_id: str) -> dict[str, Any]:
        fleet = self.get_fleet(fleet_id)
        if fleet is None:
            raise ValueError("fleet_not_found")
        if fleet["status"] == "OUT_OF_SERVICE":
            raise ValueError("already_broken")
        timestamp = now_utc()
        fleet["status"] = "OUT_OF_SERVICE"
        fleet["currentLoadKg"] = 0
        fleet["lastPositionAt"] = timestamp
        route = self.db.routes.find_one(
            {"fleetId": fleet_id, "status": "ACTIVE"}, {"_id": 0}
        )
        if route is None:
            self.db.fleets.replace_one({"fleetId": fleet_id}, fleet)
            return {
                "brokenFleet": fleet, "previousRoute": None,
                "replacementFleet": None, "replacementRoute": None, "orders": [],
            }
        route["status"] = "CANCELLED"
        route["updatedAt"] = timestamp
        remaining_stops = [
            stop for stop in route["stops"] if stop["status"] != "COMPLETED"
        ]
        order_ids = list(dict.fromkeys(stop["orderId"] for stop in remaining_stops))
        orders = [
            order for order_id in order_ids
            if (order := self.get_order(order_id)) is not None
        ]
        required_load = sum(order["quantityKg"] for order in orders)
        candidates = [
            candidate for candidate in self.list_fleets()
            if candidate["status"] == "IDLE"
            and candidate["capacityKg"] - candidate["currentLoadKg"] >= required_load
        ]
        if not candidates or not remaining_stops:
            self.db.fleets.replace_one({"fleetId": fleet_id}, fleet)
            self.db.routes.replace_one({"routeId": route["routeId"]}, route)
            return {
                "brokenFleet": fleet, "previousRoute": route,
                "replacementFleet": None, "replacementRoute": None, "orders": orders,
            }
        replacement = min(
            candidates,
            key=lambda candidate: distance_km(
                candidate["location"], remaining_stops[0]["location"]
            ),
        )
        replacement_route = build_replacement_route(
            replacement["fleetId"], remaining_stops, replacement["location"], timestamp
        )
        replacement["currentLoadKg"] += required_load
        first_stop = replacement_route["stops"][0]
        replacement["status"] = (
            "WAITING_LOAD" if first_stop["status"] == "ARRIVED"
            and first_stop["type"] == "PICKUP"
            else "WAITING_UNLOAD" if first_stop["status"] == "ARRIVED"
            else "TO_PICKUP" if first_stop["type"] == "PICKUP"
            else "IN_TRANSIT"
        )
        replacement["lastPositionAt"] = timestamp
        self.db.fleets.replace_one({"fleetId": fleet_id}, fleet)
        self.db.routes.replace_one({"routeId": route["routeId"]}, route)
        self.db.fleets.replace_one({"fleetId": replacement["fleetId"]}, replacement)
        self.db.routes.insert_one(replacement_route)
        for order in orders:
            order["fleetId"] = replacement["fleetId"]
            order["routeId"] = replacement_route["routeId"]
            if order["status"] not in {"LOADED", "DELIVERY_ARRIVED"}:
                order["status"] = "ASSIGNED"
            order["updatedAt"] = timestamp
            self.db.orders.replace_one({"orderId": order["orderId"]}, order)
        return {
            "brokenFleet": fleet, "previousRoute": route,
            "replacementFleet": replacement, "replacementRoute": replacement_route,
            "orders": orders,
        }

    def unload_order(self, order_id: str) -> dict[str, Any]:
        order = self.get_order(order_id)
        if order is None:
            raise ValueError("order_not_found")
        if order["status"] not in {"LOADED", "DELIVERY_ARRIVED"}:
            raise ValueError("invalid_state")
        fleet = self.get_fleet(order["fleetId"])
        route = self.get_route(order["routeId"])
        if fleet is None or route is None:
            raise ValueError("invalid_state")
        dropoff = next(
            (stop for stop in route["stops"]
             if stop["orderId"] == order_id and stop["type"] == "DROPOFF"),
            None,
        )
        if dropoff is None or dropoff["status"] != "ARRIVED":
            raise ValueError("not_arrived")
        timestamp = now_utc()
        dropoff["status"] = "COMPLETED"
        remaining = next(
            (stop for stop in route["stops"] if stop["status"] != "COMPLETED"),
            None,
        )
        route["status"] = "ACTIVE" if remaining else "COMPLETED"
        route["updatedAt"] = timestamp
        order["status"] = "DELIVERED"
        order["updatedAt"] = timestamp
        fleet["currentLoadKg"] = max(0, fleet["currentLoadKg"] - order["quantityKg"])
        fleet["status"] = (
            "TO_PICKUP" if remaining and remaining["type"] == "PICKUP"
            else "IN_TRANSIT" if remaining
            else "IDLE"
        )
        fleet["lastPositionAt"] = timestamp
        self.db.fleets.replace_one({"fleetId": fleet["fleetId"]}, fleet)
        self.db.orders.replace_one({"orderId": order_id}, order)
        self.db.routes.replace_one({"routeId": route["routeId"]}, route)
        return {"order": order, "fleet": fleet, "route": route}

    def reset_demo(self) -> None:
        for collection in (
            "cqc_results", "lots", "bids", "orders", "fleets", "routes",
        ):
            self.db[collection].delete_many({})
        seed_demo_data(self)


def create_store(settings: Settings) -> Store:
    if settings.store_mode.lower() == "mongo":
        return MongoStore(settings)
    return MemoryStore()
