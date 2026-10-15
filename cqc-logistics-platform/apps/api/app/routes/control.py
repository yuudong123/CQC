from datetime import UTC, datetime

from fastapi import APIRouter, Request, status

from app.domain.market import (
    AlertRead,
    ControlOverviewRead,
    ControlStatsRead,
    FleetRead,
    LotRead,
    OrderRead,
    RouteRead,
)
from app.store import Store

router = APIRouter(prefix="/control", tags=["control"])


def get_store(request: Request) -> Store:
    return request.app.state.store


def build_overview(store: Store) -> ControlOverviewRead:
    generated_at = datetime.now(UTC)
    fleets = [FleetRead.model_validate(fleet) for fleet in store.list_fleets()]
    orders = [OrderRead.model_validate(order) for order in store.list_orders()]
    routes = [RouteRead.model_validate(route) for route in store.list_routes()]
    alerts: list[AlertRead] = []
    for fleet in fleets:
        if fleet.status == "OUT_OF_SERVICE":
            alerts.append(AlertRead(
                alertId=f"fleet-breakdown-{fleet.fleetId}", severity="CRITICAL",
                title="차량 고장 격리", message=f"{fleet.name} 차량이 운행에서 제외됐습니다.",
                createdAt=fleet.lastPositionAt,
            ))
        elif fleet.status in {"WAITING_LOAD", "WAITING_UNLOAD"}:
            action = "상차" if fleet.status == "WAITING_LOAD" else "하차"
            alerts.append(AlertRead(
                alertId=f"fleet-gate-{fleet.fleetId}", severity="WARNING",
                title=f"{action} 확인 필요",
                message=f"{fleet.name} 차량이 {action} 완료를 기다립니다.",
                createdAt=fleet.lastPositionAt,
            ))
    for order in orders:
        if order.status == "MATCHED":
            alerts.append(AlertRead(
                alertId=f"order-dispatch-{order.orderId}", severity="INFO",
                title="배차 필요", message=f"주문 {order.orderId}이 배차를 기다립니다.",
                createdAt=order.updatedAt,
            ))
    open_lots = [LotRead.model_validate(lot) for lot in store.list_lots("OPEN")]
    stats = ControlStatsRead(
        openAuctions=len(open_lots),
        activeFleets=sum(fleet.status not in {"IDLE", "OUT_OF_SERVICE"} for fleet in fleets),
        inTransitOrders=sum(
            order.status not in {"MATCHED", "DELIVERED", "CANCELLED"}
            for order in orders
        ),
        attentionRequired=sum(alert.severity != "INFO" for alert in alerts),
    )
    return ControlOverviewRead(
        storage=store.storage_name,
        generatedAt=generated_at,
        stats=stats,
        fleets=fleets,
        orders=orders,
        routes=routes,
        alerts=alerts,
    )


@router.get("/overview", response_model=ControlOverviewRead)
def get_overview(request: Request) -> ControlOverviewRead:
    return build_overview(get_store(request))


@router.post(
    "/seed-reset",
    response_model=ControlOverviewRead,
    status_code=status.HTTP_200_OK,
)
def reset_demo(request: Request) -> ControlOverviewRead:
    store = get_store(request)
    store.reset_demo()
    return build_overview(store)
