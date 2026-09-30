"""Frontend 관제 계약의 Simulator 설정 변경 API."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from src.simulator.schemas import SimulatorSettingsUpdate

from ..clients.simulator import SimulatorRevisionConflict, SimulatorUnavailable
from ..schemas.quality_history import QualityError
from ..schemas.quality_operations import QualitySnapshot
from .quality_history import _error_response
from .quality_operations import _execute


class _SimulatorErrorRoute(APIRoute):
    """제어 요청의 입력 오류를 공유 Error body로 반환한다."""

    def get_route_handler(self):
        handler = super().get_route_handler()

        async def wrapped(request: Request) -> Response:
            try:
                return await handler(request)
            except RequestValidationError:
                return _error_response(422, "INVALID_SETTINGS")

        return wrapped


router = APIRouter(
    prefix="/v1/quality", tags=["quality"], route_class=_SimulatorErrorRoute
)


@router.put(
    "/simulator",
    response_model=QualitySnapshot,
    response_model_exclude_unset=True,
    responses={code: {"model": QualityError} for code in (404, 409, 410, 422, 503)},
)
async def update_simulator(
    update: SimulatorSettingsUpdate, request: Request, response: Response
) -> dict[str, object] | JSONResponse:
    """공개 제어 요청을 독립 Simulator에 전달하고 snapshot으로 응답한다."""

    response.headers["Cache-Control"] = "no-store"
    captured_at = datetime.now(timezone.utc).replace(tzinfo=None)
    snapshot = await _execute(request, "snapshot", captured_at)
    if isinstance(snapshot, JSONResponse):
        return snapshot

    client = request.app.state.simulator_client
    if client is None:
        return _error_response(503, "SIMULATOR_UNAVAILABLE")
    try:
        state = await client.update(update)
    except SimulatorRevisionConflict:
        return _error_response(409, "REVISION_CONFLICT")
    except SimulatorUnavailable:
        return _error_response(503, "SIMULATOR_UNAVAILABLE")

    operations = request.app.state.quality_operations_service
    return operations.with_simulator_state(snapshot, state)
