"""Frontend 관제용 완료 검사 이력 목록 API."""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from sqlalchemy.exc import SQLAlchemyError

from ..repositories.quality_history import HistoryFilters, QualityHistoryRepository
from ..schemas.quality_history import PageSize, QualityError, QualityHistoryPage
from ..services.quality_history import HistoryContractError, to_quality_result


class _ContractErrorRoute(APIRoute):
    """이 조회 endpoint의 입력 오류만 공유 Error body로 변환한다."""

    def get_route_handler(self):
        handler = super().get_route_handler()

        async def wrapped(request: Request) -> Response:
            try:
                return await handler(request)
            except RequestValidationError:
                return _error_response(422, "INVALID_QUERY")
            except HTTPException as exc:
                if exc.status_code == 422 and isinstance(exc.detail, dict):
                    return _error_response(422, str(exc.detail["code"]))
                raise

        return wrapped


router = APIRouter(
    prefix="/v1/quality", tags=["quality"], route_class=_ContractErrorRoute
)
logger = logging.getLogger(__name__)
_QUERY_FIELDS = {
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


@router.get(
    "/inspections",
    response_model=QualityHistoryPage,
    responses={code: {"model": QualityError} for code in (404, 409, 410, 422, 503)},
)
async def list_quality_inspections(
    request: Request,
    response: Response,
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
) -> dict[str, object]:
    """완료된 검사만 고정된 snapshot 시각 기준으로 페이지 조회한다."""

    response.headers["Cache-Control"] = "no-store"
    if set(request.query_params) - _QUERY_FIELDS:
        raise HTTPException(422, detail={"code": "UNKNOWN_QUERY_FIELD"})
    if from_date is not None and to_date is not None and from_date > to_date:
        raise HTTPException(422, detail={"code": "INVALID_DATE_RANGE"})
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    if snapshot_at is not None and snapshot_at > now_ms:
        raise HTTPException(422, detail={"code": "INVALID_SNAPSHOT"})
    fixed_ms = now_ms if snapshot_at is None else int(snapshot_at)
    snapshot_utc = datetime.fromtimestamp(fixed_ms / 1000, timezone.utc).replace(
        tzinfo=None
    )
    repository: QualityHistoryRepository | None = getattr(
        request.app.state, "quality_history_repository", None
    )
    if repository is None:
        return _unavailable()
    filters = HistoryFilters(
        from_date=from_date,
        to_date=to_date,
        variety=variety,
        grade=grade,
        bin_code=bin_code,
        processing_status=processing_status,
        error_code=error_code,
        misclassification=misclassification,
    )
    try:
        rows = await asyncio.to_thread(
            repository.list_page,
            filters,
            snapshot_at=snapshot_utc,
            page=page,
            page_size=page_size,
        )
        items = [to_quality_result(item) for item in rows.items]
    except SQLAlchemyError:
        logger.exception("관제 검사 이력 DB 조회에 실패했습니다")
        return _unavailable()
    except HistoryContractError:
        logger.exception("저장된 검사 상태를 관제 계약으로 변환하지 못했습니다")
        return _error_response(503, "HISTORY_CONTRACT_ERROR")
    return {
        "items": items,
        "total": rows.total,
        "page": page,
        "pageSize": page_size,
        "snapshotAt": fixed_ms,
        "bins": rows.bins,
    }


def _unavailable() -> JSONResponse:
    return _error_response(503, "DB_UNAVAILABLE")


def _error_response(status_code: int, code: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"code": code},
        headers={"Cache-Control": "no-store"},
    )
