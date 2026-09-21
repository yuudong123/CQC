from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class Point(BaseModel):
    type: Literal["Point"] = "Point"
    coordinates: tuple[float, float] = Field(description="[longitude, latitude]")


class CQCResultCreate(BaseModel):
    cqcId: str = Field(min_length=1, max_length=100)
    farmId: str = Field(min_length=1, max_length=100)
    crop: str = Field(default="apple", min_length=1, max_length=50)
    variety: str = Field(min_length=1, max_length=50)
    qualityGrade: Literal["SPECIAL", "PREMIUM", "STANDARD"]
    confidence: float = Field(ge=0, le=1)
    quantityKg: int = Field(gt=0, le=100_000)
    origin: Point
    rawPayload: dict[str, Any] = Field(default_factory=dict)


class CQCResultRead(CQCResultCreate):
    createdAt: datetime


class LotCreate(BaseModel):
    cqcId: str = Field(min_length=1, max_length=100)
    reservePriceWon: int = Field(gt=0)
    suggestedPriceWon: int | None = Field(default=None, gt=0)
    closesAt: datetime | None = None


class LotRead(BaseModel):
    lotId: str
    cqcId: str
    sellerId: str
    crop: str
    variety: str
    qualityGrade: str
    quantityKg: int
    origin: Point
    reservePriceWon: int
    suggestedPriceWon: int | None
    auctionStatus: Literal["DRAFT", "OPEN", "CLOSED", "AWARDED", "CLOSED_UNSOLD"]
    closesAt: datetime
    createdAt: datetime
    updatedAt: datetime


class BidCreate(BaseModel):
    buyerId: str = Field(min_length=1, max_length=100)
    priceWon: int = Field(gt=0)
    destination: Point


class BidRead(BidCreate):
    bidId: str
    lotId: str
    accepted: bool
    placedAt: datetime


class AuctionCloseRead(BaseModel):
    lot: LotRead
    winningBid: BidRead | None
    order: "OrderRead | None" = None


class OrderRead(BaseModel):
    orderId: str
    lotId: str
    sellerId: str
    buyerId: str
    quantityKg: int
    priceWon: int
    origin: Point
    destination: Point
    status: Literal[
        "MATCHED", "DISPATCHING", "ASSIGNED", "PICKUP_ARRIVED", "LOADED",
        "DELIVERY_ARRIVED", "DELIVERED", "CANCELLED",
    ]
    fleetId: str | None = None
    routeId: str | None = None
    createdAt: datetime
    updatedAt: datetime


class FleetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    capacityKg: int = Field(gt=0, le=100_000)
    location: Point


class FleetRead(FleetCreate):
    fleetId: str
    currentLoadKg: int
    status: Literal[
        "IDLE", "TO_PICKUP", "WAITING_LOAD", "IN_TRANSIT", "WAITING_UNLOAD", "OUT_OF_SERVICE",
    ]
    lastPositionAt: datetime


class StopRead(BaseModel):
    sequence: int
    type: Literal["PICKUP", "DROPOFF"]
    orderId: str
    location: Point
    status: Literal["PENDING", "ARRIVED", "COMPLETED"]


class RouteRead(BaseModel):
    routeId: str
    fleetId: str
    version: int
    status: Literal["PLANNED", "ACTIVE", "COMPLETED", "CANCELLED"]
    stops: list[StopRead]
    distanceKm: float
    estimatedMinutes: int
    createdAt: datetime
    updatedAt: datetime


class DispatchRead(BaseModel):
    order: OrderRead
    fleet: FleetRead
    route: RouteRead


class FleetStepRead(BaseModel):
    fleet: FleetRead
    route: RouteRead
    arrived: bool


class DeliveryActionRead(BaseModel):
    order: OrderRead
    fleet: FleetRead
    route: RouteRead


class BreakdownRead(BaseModel):
    brokenFleet: FleetRead
    previousRoute: RouteRead | None
    replacementFleet: FleetRead | None
    replacementRoute: RouteRead | None
    orders: list[OrderRead]


class ControlStatsRead(BaseModel):
    openAuctions: int
    activeFleets: int
    inTransitOrders: int
    attentionRequired: int


class AlertRead(BaseModel):
    alertId: str
    severity: Literal["INFO", "WARNING", "CRITICAL"]
    title: str
    message: str
    createdAt: datetime


class ControlOverviewRead(BaseModel):
    storage: str
    generatedAt: datetime
    stats: ControlStatsRead
    fleets: list[FleetRead]
    orders: list[OrderRead]
    routes: list[RouteRead]
    alerts: list[AlertRead]
