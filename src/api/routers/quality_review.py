"""Frontend 관제용 검사 오판 의심 검수 API."""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Path, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import SQLAlchemyError

from ..schemas.quality_history import QualityError
from .quality_history import _error_response

logger = logging.getLogger(__name__)

Misclassification = Literal["NONE", "CULTIVAR_SUSPECT", "QUALITY_SUSPECT", "OTHER"]


class Review(BaseModel):
    """공유 OpenAPI의 검수 입력."""

    model_config = ConfigDict(extra="forbid")
    misclassification: Misclassification


class ReviewAck(BaseModel):
    """공유 OpenAPI의 검수 확인 응답."""

    inspectionId: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    misclassification: Misclassification


class _ReviewErrorRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def wrapped(request: Request) -> Response:
            try:
                return await handler(request)
            except RequestValidationError:
                return _error_response(422, "INVALID_REVIEW")

        return wrapped


router = APIRouter(
    prefix="/v1/quality", tags=["quality"], route_class=_ReviewErrorRoute
)


@router.patch(
    "/inspections/{id}/review",
    response_model=ReviewAck,
    responses={code: {"model": QualityError} for code in (404, 409, 410, 422, 503)},
)
async def review_inspection(
    id: Annotated[str, Path(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")],
    review: Review,
    request: Request,
    response: Response,
) -> ReviewAck | JSONResponse:
    """검사 결과를 바꾸지 않고 오판 의심 지정 또는 해제를 저장한다."""

    response.headers["Cache-Control"] = "no-store"
    repository = getattr(request.app.state, "inspection_review_repository", None)
    if repository is None:
        return _error_response(503, "DB_UNAVAILABLE")
    try:
        updated = await asyncio.to_thread(
            repository.set_misclassification, id, review.misclassification
        )
    except SQLAlchemyError:
        logger.exception("검사 검수 DB 저장에 실패했습니다: %s", id)
        return _error_response(503, "DB_UNAVAILABLE")
    if not updated:
        return _error_response(404, "INSPECTION_EXPIRED")
    return ReviewAck(inspectionId=id, misclassification=review.misclassification)
