"""Read-only fault image inventory and preview endpoints."""

from __future__ import annotations

import asyncio
import logging
from typing import Literal

from fastapi import APIRouter, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from ..schemas.inspection_id import (
    INSPECTION_ID_MAX_LENGTH,
    INSPECTION_ID_MIN_LENGTH,
    INSPECTION_ID_PATTERN,
)
from ..schemas.quality_fault_images import (
    QualityFaultImages,
    QualityImageDelete,
    QualityImageDeleteAck,
)
from ..schemas.quality_history import QualityError
from ..services.fault_image_storage import FaultImageStorage
from .quality_history import _error_response


class _FaultImageRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def wrapped(request: Request) -> Response:
            try:
                return await handler(request)
            except RequestValidationError:
                return _error_response(422, "INVALID_IDS")

        return wrapped


router = APIRouter(prefix="/v1/quality", tags=["quality"], route_class=_FaultImageRoute)
logger = logging.getLogger(__name__)
_ERROR_RESPONSES = {code: {"model": QualityError} for code in (404, 409, 410, 422, 503)}


def _storages(request: Request) -> tuple[FaultImageStorage, ...]:
    return tuple(
        storage
        for name in ("fault_image_storage", "low_confidence_image_storage")
        if (storage := getattr(request.app.state, name, None)) is not None
    )


@router.get(
    "/fault-images", response_model=QualityFaultImages, responses=_ERROR_RESPONSES
)
async def fault_images(
    request: Request,
    response: Response,
    category: Literal["SYSTEM_ERROR", "LOW_CONFIDENCE"] | None = None,
    inspectionId: str | None = Query(
        default=None,
        min_length=INSPECTION_ID_MIN_LENGTH,
        max_length=INSPECTION_ID_MAX_LENGTH,
        pattern=INSPECTION_ID_PATTERN,
    ),
) -> dict | JSONResponse:
    response.headers["Cache-Control"] = "no-store"
    storages = _storages(request)
    if not storages:
        return _error_response(503, "IMAGE_UNAVAILABLE")
    try:
        records = []
        for storage in storages:
            records.extend(await asyncio.to_thread(storage.list_images))
        records.sort(key=lambda item: (item.created_at, item.id), reverse=True)
    except OSError:
        logger.exception("Fault image inventory unavailable")
        return _error_response(503, "IMAGE_UNAVAILABLE")
    return {
        "items": [
            {
                "id": item.id,
                "inspectionId": item.inspection_id,
                "imageIndex": item.image_index,
                "createdAt": int(item.created_at.timestamp() * 1000),
                "errorCode": (
                    "INFERENCE_TIMEOUT"
                    if item.error_code == "INFERENCE_DEADLINE_EXCEEDED"
                    else item.error_code
                ),
                "category": item.category,
                "decisionReason": item.decision_reason,
                "cultivarConfidence": item.cultivar_confidence,
                "qualityConfidence": item.quality_confidence,
                "appliedCultivarThreshold": item.applied_cultivar_threshold,
                "appliedQualityThreshold": item.applied_quality_threshold,
                "previewUrl": f"/api/quality/previews/{item.id}",
            }
            for item in records
            if (category is None or item.category == category)
            and (inspectionId is None or item.inspection_id == inspectionId)
        ]
    }


@router.delete(
    "/fault-images", response_model=QualityImageDeleteAck, responses=_ERROR_RESPONSES
)
async def delete_fault_images(
    request: Request, payload: QualityImageDelete, response: Response
) -> dict | JSONResponse:
    response.headers["Cache-Control"] = "no-store"
    storages = _storages(request)
    if not storages:
        return _error_response(503, "IMAGE_UNAVAILABLE")
    try:
        deleted = []
        for storage in storages:
            deleted.extend(await asyncio.to_thread(storage.delete_images, payload.ids))
        deleted = [
            image_id for image_id in dict.fromkeys(payload.ids) if image_id in deleted
        ]
    except OSError:
        logger.exception("Fault image deletion unavailable")
        return _error_response(503, "IMAGE_UNAVAILABLE")
    return {"deletedIds": deleted}


@router.get(
    "/previews/{id}",
    response_class=Response,
    responses={
        200: {"content": {"image/jpeg": {}, "image/png": {}}},
        410: {"model": QualityError},
        503: {"model": QualityError},
    },
)
async def preview(request: Request, id: str) -> Response:
    storages = _storages(request)
    if not storages:
        return _error_response(503, "IMAGE_UNAVAILABLE")
    try:
        image = None
        for storage in storages:
            image = await asyncio.to_thread(storage.read_image, id)
            if image is not None:
                break
    except OSError:
        logger.exception("Fault image preview unavailable")
        return _error_response(503, "IMAGE_UNAVAILABLE")
    if image is None:
        return _error_response(410, "IMAGE_EXPIRED")
    content, content_type = image
    return Response(
        content, media_type=content_type, headers={"Cache-Control": "no-store"}
    )
