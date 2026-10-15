"""처리 중 검사에만 유효한 메모리 이미지 미리보기."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from ..schemas.quality_history import QualityError
from ..services.live_inspections import LiveInspectionStore
from .quality_history import _error_response

router = APIRouter(prefix="/v1/quality", tags=["quality"])


@router.get(
    "/previews/live_{id}",
    # 공유 OpenAPI의 /previews/{id} 계약을 구현하는 내부 분기다.
    include_in_schema=False,
    response_class=Response,
    responses={
        200: {"content": {"image/jpeg": {}, "image/png": {}}},
        410: {"model": QualityError},
    },
)
async def live_preview(request: Request, id: str) -> Response:
    """활성 요청의 이미지만 반환하고 완료 후에는 410으로 응답한다."""

    storage: LiveInspectionStore = request.app.state.live_inspections
    image = storage.read(id)
    if image is None:
        return _error_response(410, "IMAGE_EXPIRED")
    content, content_type = image
    return Response(
        content, media_type=content_type, headers={"Cache-Control": "no-store"}
    )
