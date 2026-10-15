from fastapi import APIRouter, HTTPException, Request

from app.domain.market import BreakdownRead, DeliveryActionRead, FleetStepRead
from app.store import Store

router = APIRouter(tags=["delivery"])


def get_store(request: Request) -> Store:
    return request.app.state.store


def raise_delivery_error(error: ValueError) -> None:
    messages = {
        "fleet_not_found": (404, "차량을 찾을 수 없습니다."),
        "order_not_found": (404, "주문을 찾을 수 없습니다."),
        "no_route": (409, "진행 중인 노선이 없습니다."),
        "not_arrived": (409, "해당 목적지에 아직 도착하지 않았습니다."),
        "invalid_state": (409, "현재 상태에서는 처리할 수 없습니다."),
    }
    code, message = messages[str(error)]
    raise HTTPException(status_code=code, detail=message) from error


@router.post("/fleets/{fleet_id}/simulate-step", response_model=FleetStepRead)
def simulate_fleet_step(fleet_id: str, request: Request) -> FleetStepRead:
    try:
        result = get_store(request).simulate_fleet_step(fleet_id)
    except ValueError as error:
        raise_delivery_error(error)
    return FleetStepRead.model_validate(result)


@router.post("/orders/{order_id}/load-complete", response_model=DeliveryActionRead)
def load_complete(order_id: str, request: Request) -> DeliveryActionRead:
    try:
        result = get_store(request).load_order(order_id)
    except ValueError as error:
        raise_delivery_error(error)
    return DeliveryActionRead.model_validate(result)


@router.post("/orders/{order_id}/unload-complete", response_model=DeliveryActionRead)
def unload_complete(order_id: str, request: Request) -> DeliveryActionRead:
    try:
        result = get_store(request).unload_order(order_id)
    except ValueError as error:
        raise_delivery_error(error)
    return DeliveryActionRead.model_validate(result)


@router.post("/fleets/{fleet_id}/breakdown", response_model=BreakdownRead)
def breakdown_fleet(fleet_id: str, request: Request) -> BreakdownRead:
    try:
        result = get_store(request).breakdown_fleet(fleet_id)
    except ValueError as error:
        messages = {
            "fleet_not_found": (404, "차량을 찾을 수 없습니다."),
            "already_broken": (409, "이미 고장 처리된 차량입니다."),
        }
        code, message = messages[str(error)]
        raise HTTPException(status_code=code, detail=message) from error
    return BreakdownRead.model_validate(result)
