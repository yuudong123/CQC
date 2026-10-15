"""검사 요청의 HTTP 전송 계약을 검증한다."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from hmac import compare_digest
from typing import Annotated, get_args

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.routing import APIRoute
from pydantic import ValidationError
from starlette.types import Message

from src.simulator.schemas import FaultType

from ..core.config import Settings
from ..repositories import (
    BinMappingConfigurationError,
    BinMappingUnavailableError,
    DuplicateInspectionIdError,
)
from ..schemas.inspection_id import (
    INSPECTION_ID_MAX_LENGTH,
    INSPECTION_ID_MIN_LENGTH,
    INSPECTION_ID_PATTERN,
)
from ..schemas.inspection_results import InspectionResponse
from ..schemas.inspections import InspectionImageMetadata, InspectionMetadata
from ..services.inspections import InspectionService


class _InspectionSizeRoute(APIRoute):
    """Limit the multipart body before parsing without buffering a second copy."""

    def get_route_handler(self) -> Callable[[Request], Awaitable[Response]]:
        handler = super().get_route_handler()

        async def limited(request: Request) -> Response:
            limit = _settings_from(request).inference_max_request_bytes
            content_length = request.headers.get("content-length")
            if content_length is not None:
                try:
                    declared_size = int(content_length)
                except ValueError:
                    declared_size = None
                if declared_size is not None and declared_size > limit:
                    raise HTTPException(
                        status_code=413,
                        detail="multipart 요청이 허용된 최대 크기를 초과했습니다",
                    )

            received = 0

            async def counted_receive() -> Message:
                nonlocal received
                message = await request.receive()
                if message["type"] == "http.request":
                    received += len(message.get("body", b""))
                    if received > limit:
                        # Do not pass the over-limit chunk to the multipart parser.
                        # HTTPException preserves 413 through FastAPI; Starlette's
                        # multipart parser closes partial uploads when this propagates.
                        raise HTTPException(
                            status_code=413,
                            detail="multipart 요청이 허용된 최대 크기를 초과했습니다",
                        )
                return message

            return await handler(Request(request.scope, receive=counted_receive))

        return limited


router = APIRouter(prefix="/v1", tags=["inspections"], route_class=_InspectionSizeRoute)

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
    # _InspectionSizeRoute already limits the complete body before/during parsing.
    # Retain the existing payload validation as a secondary input check.
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


@router.post(
    "/inspections",
    response_model=InspectionResponse,
    responses={
        409: {
            "description": "inspection_id가 이미 존재합니다. 후속 검사는 수행하지 않습니다.",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {"detail": {"type": "string"}},
                        "required": ["detail"],
                    }
                }
            },
        }
    },
)
async def validate_inspection_request(
    request: Request,
    inspection_id: Annotated[
        str,
        Form(
            min_length=INSPECTION_ID_MIN_LENGTH,
            max_length=INSPECTION_ID_MAX_LENGTH,
            pattern=INSPECTION_ID_PATTERN,
        ),
    ],
    images: Annotated[list[UploadFile], File()],
    metadata: Annotated[str, Form(min_length=1)],
    virtual_brix: Annotated[
        float | None, Form(ge=9, le=18, allow_inf_nan=False)
    ] = None,
) -> InspectionResponse:
    """검사 요청을 검증하고 Service의 Mock 추론 결과를 반환한다."""

    try:
        return await _validate_and_inspect(
            request=request,
            inspection_id=inspection_id,
            images=images,
            metadata=metadata,
            virtual_brix=virtual_brix,
        )
    finally:
        # FastAPI form 임시 파일을 유효성 검사 실패 시에도 명시적으로 닫는다.
        for image in images:
            await image.close()


async def _validate_and_inspect(
    *,
    request: Request,
    inspection_id: str,
    images: list[UploadFile],
    metadata: str,
    virtual_brix: float | None,
) -> InspectionResponse:
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

    token = request.headers.get("x-cqc-simulator-token")
    raw_faults = request.headers.get("x-cqc-simulator-faults", "")
    raw_interval = request.headers.get("x-cqc-simulator-interval-ms")
    simulator_interval_ms: int | None = None
    simulator_faults: tuple[FaultType, ...] = ()
    source_reference: str | None = None
    if token is not None or raw_faults or raw_interval is not None:
        expected_token = request.app.state.simulator_fault_token
        if (
            expected_token is None
            or token is None
            or not compare_digest(token, expected_token)
        ):
            raise HTTPException(status_code=403, detail="Simulator 인증에 실패했습니다")
        parsed = tuple(raw_faults.split(",")) if raw_faults else ()
        if (
            len(parsed) > 5
            or len(parsed) != len(set(parsed))
            or any(value not in get_args(FaultType) for value in parsed)
        ):
            raise HTTPException(
                status_code=422, detail="Simulator 장애 설정이 잘못되었습니다"
            )
        simulator_faults = parsed
        if raw_interval is not None:
            if raw_interval not in {"1000", "2000", "3000"}:
                raise HTTPException(
                    status_code=422, detail="Simulator interval이 잘못되었습니다"
                )
            simulator_interval_ms = int(raw_interval)
        source_reference = request.headers.get("x-cqc-simulator-bundle-id")
        if source_reference is None or not 1 <= len(source_reference) <= 255:
            raise HTTPException(
                status_code=422, detail="Simulator 묶음 ID가 잘못되었습니다"
            )

    try:
        options = (
            {"simulator_faults": simulator_faults, "source_reference": source_reference}
            if source_reference is not None
            else {}
        )
        if simulator_interval_ms is not None:
            options["simulator_interval_ms"] = simulator_interval_ms
        return await _service_from(request).inspect(
            inspection_id=inspection_id,
            images=images,
            metadata=metadata_items,
            virtual_brix=virtual_brix,
            **options,
        )
    except DuplicateInspectionIdError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="inspection_id가 이미 존재합니다",
        ) from exc
    except (BinMappingConfigurationError, BinMappingUnavailableError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="활성 bin mapping 설정을 확인할 수 없습니다",
        ) from exc
