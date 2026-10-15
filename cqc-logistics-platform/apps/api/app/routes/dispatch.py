from fastapi import APIRouter, HTTPException, Request, status

from app.domain.market import DispatchRead, FleetCreate, FleetRead, OrderRead, RouteRead
from app.store import Store

router = APIRouter(tags=["dispatch"])


def get_store(request: Request) -> Store:
    return request.app.state.store


@router.post("/fleets", response_model=FleetRead, status_code=status.HTTP_201_CREATED)
def create_fleet(payload: FleetCreate, request: Request) -> FleetRead:
    return FleetRead.model_validate(get_store(request).create_fleet(payload))


@router.get("/fleets", response_model=list[FleetRead])
def list_fleets(request: Request) -> list[FleetRead]:
    return [FleetRead.model_validate(fleet) for fleet in get_store(request).list_fleets()]


@router.get("/orders/{order_id}", response_model=OrderRead)
def get_order(order_id: str, request: Request) -> OrderRead:
    order = get_store(request).get_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")
    return OrderRead.model_validate(order)


@router.post("/orders/{order_id}/dispatch", response_model=DispatchRead)
def dispatch_order(order_id: str, request: Request) -> DispatchRead:
    try:
        result = get_store(request).dispatch_order(order_id)
    except ValueError as error:
        messages = {
            "order_not_found": (404, "주문을 찾을 수 없습니다."),
            "already_dispatched": (409, "이미 배차된 주문입니다."),
            "no_fleet": (409, "조건에 맞는 가용 차량이 없습니다."),
        }
        code, message = messages[str(error)]
        raise HTTPException(status_code=code, detail=message) from error
    return DispatchRead.model_validate(result)


@router.get("/routes/{route_id}", response_model=RouteRead)
def get_route(route_id: str, request: Request) -> RouteRead:
    route = get_store(request).get_route(route_id)
    if route is None:
        raise HTTPException(status_code=404, detail="노선을 찾을 수 없습니다.")
    return RouteRead.model_validate(route)

