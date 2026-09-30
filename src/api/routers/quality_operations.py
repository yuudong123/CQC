"""BE-05 관제 snapshot·기간 통계·CSV 조회 API."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import IntEnum
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from ..clients.simulator import SimulatorUnavailable
from ..repositories.quality_history import HistoryFilters
from ..repositories.quality_statistics import StatisticsContractError
from ..schemas.quality_history import PageSize, QualityError
from ..schemas.quality_operations import QualitySnapshot, QualitySummary
from ..services.quality_history import HistoryContractError
from ..services.quality_operations import QualityOperationsService
from .quality_history import _ContractErrorRoute, _error_response, _unavailable

router = APIRouter(
    prefix="/v1/quality", tags=["quality"], route_class=_ContractErrorRoute
)
logger = logging.getLogger(__name__)
_FILTER_FIELDS = {
    "from",
    "to",
    "variety",
    "grade",
    "bin",
    "processingStatus",
    "errorCode",
    "misclassification",
    "page",
    "pageSize",
    "snapshotAt",
}
_CSV_RESPONSES = {
    200: {"content": {"text/csv": {"schema": {"type": "string"}}}},
    422: {"model": QualityError},
    503: {"model": QualityError},
}


class MinuteWindow(IntEnum):
    ONE = 1
    FIVE = 5
    TEN = 10
    THIRTY = 30


@dataclass(frozen=True)
class _Query:
    filters: HistoryFilters
    snapshot_at: datetime


def _query(
    request: Request,
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
    variety: Literal["ALL", "부사", "양광"] = "ALL",
    grade: Literal["ALL", "특", "상", "보통"] = "ALL",
    bin_code: Annotated[str, Query(alias="bin")] = "ALL",
    processing_status: Annotated[
        Literal["ALL", "COMPLETED", "INFERENCING", "TIMEOUT", "ERROR"],
        Query(alias="processingStatus"),
    ] = "ALL",
    error_code: Annotated[
        Literal[
            "ALL",
            "NONE",
            "INFERENCE_TIMEOUT",
            "INFERENCE_ERROR",
            "DB_ERROR",
            "CONTROL_REJECTED",
            "CONTROL_NO_RESPONSE",
            "CONTROL_FAILED",
        ],
        Query(alias="errorCode"),
    ] = "ALL",
    misclassification: Literal[
        "ALL", "NONE", "CULTIVAR_SUSPECT", "QUALITY_SUSPECT", "OTHER"
    ] = "ALL",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[PageSize, Query(alias="pageSize")] = PageSize.FIFTY,
    snapshot_at: Annotated[float | None, Query(alias="snapshotAt", ge=0)] = None,
) -> _Query:
    allowed = _FILTER_FIELDS | (
        {"minutes"} if request.url.path.endswith("statistics.csv") else set()
    )
    if set(request.query_params) - allowed:
        raise HTTPException(422, detail={"code": "UNKNOWN_QUERY_FIELD"})
    if from_date is not None and to_date is not None and from_date > to_date:
        raise HTTPException(422, detail={"code": "INVALID_DATE_RANGE"})
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    if snapshot_at is not None and snapshot_at > now_ms:
        raise HTTPException(422, detail={"code": "INVALID_SNAPSHOT"})
    fixed_ms = now_ms if snapshot_at is None else int(snapshot_at)
    return _Query(
        filters=HistoryFilters(
            from_date=from_date,
            to_date=to_date,
            variety=variety,
            grade=grade,
            bin_code=bin_code,
            processing_status=processing_status,
            error_code=error_code,
            misclassification=misclassification,
        ),
        snapshot_at=datetime.fromtimestamp(fixed_ms / 1000, timezone.utc).replace(
            tzinfo=None
        ),
    )


async def _execute(request: Request, method: str, *args: object, **kwargs: object):
    service: QualityOperationsService | None = getattr(
        request.app.state, "quality_operations_service", None
    )
    if service is None:
        return _unavailable()
    try:
        return await asyncio.to_thread(getattr(service, method), *args, **kwargs)
    except SQLAlchemyError:
        logger.exception("관제 %s DB 조회 실패", method)
        return _unavailable()
    except OSError:
        logger.exception("관제 %s 이미지 저장소 조회 실패", method)
        return _error_response(503, "IMAGE_UNAVAILABLE")
    except (HistoryContractError, StatisticsContractError):
        logger.exception("관제 %s 계약 변환 실패", method)
        return _error_response(503, "HISTORY_CONTRACT_ERROR")


@router.get(
    "/snapshot",
    response_model=QualitySnapshot,
    response_model_exclude_unset=True,
    responses={code: {"model": QualityError} for code in (404, 409, 410, 422, 503)},
)
async def snapshot(
    request: Request, response: Response
) -> dict[str, object] | JSONResponse:
    response.headers["Cache-Control"] = "no-store"
    captured_at = datetime.now(timezone.utc).replace(tzinfo=None)
    result = await _execute(request, "snapshot", captured_at)
    if isinstance(result, JSONResponse):
        return result
    simulator = getattr(request.app.state, "simulator_client", None)
    state = None
    if simulator is not None:
        try:
            state = await simulator.get_status()
        except SimulatorUnavailable:
            logger.warning("Simulator 상태 조회 실패")
    return request.app.state.quality_operations_service.with_simulator_state(
        result, state
    )


@router.get(
    "/statistics",
    response_model=QualitySummary,
    responses={code: {"model": QualityError} for code in (404, 409, 410, 422, 503)},
)
async def statistics(
    request: Request,
    response: Response,
    query: Annotated[_Query, Depends(_query)],
) -> dict[str, object] | JSONResponse:
    response.headers["Cache-Control"] = "no-store"
    return await _execute(request, "statistics", query.filters, query.snapshot_at)


@router.get("/inspections.csv", response_class=Response, responses=_CSV_RESPONSES)
async def inspections_csv(
    request: Request,
    query: Annotated[_Query, Depends(_query)],
) -> Response:
    value = await _execute(request, "inspections_csv", query.filters, query.snapshot_at)
    return (
        value
        if isinstance(value, JSONResponse)
        else _csv_response(value, "cqc-inspections.csv")
    )


@router.get("/statistics.csv", response_class=Response, responses=_CSV_RESPONSES)
async def statistics_csv(
    request: Request,
    query: Annotated[_Query, Depends(_query)],
    minutes: Annotated[MinuteWindow, Query()] = MinuteWindow.ONE,
) -> Response:
    value = await _execute(
        request, "statistics_csv", query.filters, query.snapshot_at, minutes=minutes
    )
    return (
        value
        if isinstance(value, JSONResponse)
        else _csv_response(value, "cqc-statistics.csv")
    )


def _csv_response(value: str, filename: str) -> Response:
    return Response(
        value,
        media_type="text/csv; charset=utf-8",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
