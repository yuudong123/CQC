"""검사 요청의 HTTP 전송 계약을 검증한다."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status
from pydantic import ValidationError

from ..core.config import Settings
from ..schemas.inference import InferenceResponse
from ..schemas.inspections import InspectionImageMetadata, InspectionMetadata
from ..services.inspections import InferenceResponseMismatchError, InspectionService

router = APIRouter(prefix="/v1", tags=["inspections"])

SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png"}


def _settings_from(request: Request) -> Settings:
    return request.app.state.settings


def _service_from(request: Request) -> InspectionService:
    return request.app.state.inspection_service


def _validate_request_size(
    request: Request,
    *,
    inspection_id: str,
    metadata: str,
    images: list[UploadFile],
    limit: int,
) -> None:
    # FastAPI는 endpoint에 진입하기 전에 form을 파싱한다. 배포 연동 시에는
    # proxy 또는 ASGI 수신 제한으로 파싱 전에도 같은 크기 제한을 적용한다.
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > limit:
                raise HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail="multipart 요청이 허용된 최대 크기를 초과했습니다",
                )
        except ValueError:
            pass

    known_payload_size = len(inspection_id.encode()) + len(metadata.encode())
    known_payload_size += sum(image.size or 0 for image in images)
    if known_payload_size > limit:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="multipart 요청이 허용된 최대 크기를 초과했습니다",
        )


def _parse_metadata(value: str) -> list[InspectionImageMetadata]:
    try:
        return InspectionMetadata.model_validate_json(value).root
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="metadata는 유효한 이미지 metadata JSON 배열이어야 합니다",
        ) from exc


@router.post("/inspections", response_model=InferenceResponse)
async def validate_inspection_request(
    request: Request,
    inspection_id: Annotated[str, Form(min_length=1)],
    images: Annotated[list[UploadFile], File()],
    metadata: Annotated[str, Form(min_length=1)],
) -> InferenceResponse:
    """검사 요청을 검증하고 Service의 Mock 추론 결과를 반환한다."""

    settings = _settings_from(request)

    if not inspection_id.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="inspection_id는 비어 있을 수 없습니다",
        )
    if not 1 <= len(images) <= settings.inference_max_files:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"images는 최대 {settings.inference_max_files}장까지 허용합니다",
        )

    _validate_request_size(
        request,
        inspection_id=inspection_id,
        metadata=metadata,
        images=images,
        limit=settings.inference_max_request_bytes,
    )

    if any(image.content_type not in SUPPORTED_IMAGE_TYPES for image in images):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="images는 PNG 또는 JPEG만 지원합니다",
        )

    metadata_items = _parse_metadata(metadata)
    if len(images) != len(metadata_items):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="images와 metadata 개수는 같아야 합니다",
        )

    view_indexes = [item.view_index for item in metadata_items]
    if len(view_indexes) != len(set(view_indexes)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="view_index는 중복될 수 없습니다",
        )
    if view_indexes != list(range(len(images))):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="view_index는 현재 이미지 순서에 따라 0부터 연속되어야 합니다",
        )

    try:
        return await _service_from(request).inspect(
            inspection_id=inspection_id,
            images=images,
            metadata=metadata_items,
        )
    except InferenceResponseMismatchError as exc:
        # 최종 공통 error code 계약 전까지 정합성 오류를 단순 내부 오류로 응답한다.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Inference 응답 정합성 검증에 실패했습니다",
        ) from exc
