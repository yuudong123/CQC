"""Read-only fault image inventory and preview endpoints."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from ..schemas.quality_fault_images import QualityFaultImages
from ..schemas.quality_history import QualityError
from ..services.fault_image_storage import FaultImageStorage
from .quality_history import _error_response

router = APIRouter(prefix="/v1/quality", tags=["quality"])
logger = logging.getLogger(__name__)
_ERROR_RESPONSES = {code: {"model": QualityError} for code in (404, 409, 410, 422, 503)}


def _storage(request: Request) -> FaultImageStorage | None:
    return getattr(request.app.state, "fault_image_storage", None)


@router.get(
    "/fault-images", response_model=QualityFaultImages, responses=_ERROR_RESPONSES
)
async def fault_images(request: Request, response: Response) -> dict | JSONResponse:
    response.headers["Cache-Control"] = "no-store"
    storage = _storage(request)
    if storage is None:
        return _error_response(503, "IMAGE_UNAVAILABLE")
    try:
        records = await asyncio.to_thread(storage.list_images)
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
                "previewUrl": f"/api/quality/previews/{item.id}",
            }
            for item in records
        ]
    }


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
    storage = _storage(request)
    if storage is None:
        return _error_response(503, "IMAGE_UNAVAILABLE")
    try:
        image = await asyncio.to_thread(storage.read_image, id)
    except OSError:
        logger.exception("Fault image preview unavailable")
        return _error_response(503, "IMAGE_UNAVAILABLE")
    if image is None:
        return _error_response(410, "IMAGE_EXPIRED")
    content, content_type = image
    return Response(
        content, media_type=content_type, headers={"Cache-Control": "no-store"}
    )
