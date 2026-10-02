"""검사 판정·DB mapping·제어·저장을 조정하는 Service."""

from __future__ import annotations

import asyncio
import logging
import math
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

import httpx
from fastapi import UploadFile
from pydantic import ValidationError

from src.simulator.schemas import FaultType

from ..clients.inference import HttpInferenceClient, MockInferenceClient
from ..control.virtual_control import MockVirtualControl
from ..core.datetime import utc_now
from ..db.session import is_database_unavailable_error
from ..repositories import (
    BinMappingConfigurationError,
    BinMappingRepository,
    BinMappingUnavailableError,
    InspectionPersistence,
)
from ..repositories.records import ControlAttemptRecord, InspectionErrorRecord
from ..schemas.control import ControlExecutionResult
from ..schemas.inference import InferenceRequest, InferenceResponse
from ..schemas.inspection_results import (
    ControlStatus,
    InspectionDecision,
    InspectionDecisionReason,
    InspectionResponse,
    InspectionStatus,
    PersistenceStatus,
)
from ..schemas.inspections import InspectionImageMetadata
from ..schemas.late_results import LateInferenceResult
from .bin_mapping_lkg import LkgBinMapping
from .bin_policy import DEMO_SWEETNESS_THRESHOLD_BRIX
from .control_policy import execute_virtual_control
from .fault_image_storage import FaultImage, FaultImageStorage
from .inspection_policy import (
    decide_inference_timeout,
    decide_inspection,
    decide_reinspection,
)
from .late_results import LateResultManager
from .live_inspections import LiveInspectionStore
from .live_preview_images import build_live_previews

logger = logging.getLogger(__name__)
_FAULT_IMAGE_REASONS = frozenset(
    {
        InspectionDecisionReason.INFERENCE_DEADLINE_EXCEEDED,
        InspectionDecisionReason.INFERENCE_CONNECTION_ERROR,
        InspectionDecisionReason.INFERENCE_HTTP_ERROR,
        InspectionDecisionReason.INFERENCE_INVALID_RESPONSE,
    }
)


class InferenceResponseMismatchError(RuntimeError):
    """Inference 응답이 요청과 대응하지 않을 때 발생하는 내부 오류."""


class InspectionService:
    """Inference부터 DB 기반 배차·제어·기록까지 검사 흐름을 조정한다."""

    def __init__(
        self,
        inference_client: MockInferenceClient | HttpInferenceClient,
        virtual_control: MockVirtualControl,
        *,
        cultivar_confidence_threshold: float,
        quality_confidence_threshold: float,
        inference_business_deadline_ms: int,
        late_result_manager: LateResultManager,
        bin_mapping_repository: BinMappingRepository | None = None,
        persistence: InspectionPersistence | None = None,
        fault_image_storage: FaultImageStorage | None = None,
        live_inspections: LiveInspectionStore | None = None,
        live_preview_max_dimension: int = 240,
        live_preview_jpeg_quality: int = 90,
    ) -> None:
        self._inference_client = inference_client
        self._virtual_control = virtual_control
        self._cultivar_confidence_threshold = cultivar_confidence_threshold
        self._quality_confidence_threshold = quality_confidence_threshold
        self._inference_business_deadline_ms = inference_business_deadline_ms
        self._late_result_manager = late_result_manager
        self._bin_mapping_lkg = (
            LkgBinMapping(bin_mapping_repository)
            if bin_mapping_repository is not None
            else None
        )
        self._persistence = persistence
        self._fault_image_storage = fault_image_storage
        self._live_inspections = live_inspections
        self._live_preview_max_dimension = live_preview_max_dimension
        self._live_preview_jpeg_quality = live_preview_jpeg_quality

    async def shutdown(self) -> None:
        """서버 종료 시 남아 있는 late Inference task를 정리한다."""

        await self._late_result_manager.shutdown()

    async def inspect(
        self,
        *,
        inspection_id: str,
        images: list[UploadFile],
        metadata: list[InspectionImageMetadata],
        virtual_brix: float | None = None,
        simulator_faults: tuple[FaultType, ...] = (),
        injected_inference_reason: InspectionDecisionReason | None = None,
        source_reference: str | None = None,
    ) -> InspectionResponse:
        """검사 요청을 판정·제어하고 가능한 결과를 DB에 기록한다."""

        preview_token = uuid4().hex
        try:
            return await self._inspect(
                inspection_id=inspection_id,
                images=images,
                metadata=metadata,
                virtual_brix=virtual_brix,
                simulator_faults=simulator_faults,
                injected_inference_reason=injected_inference_reason,
                source_reference=source_reference,
                preview_token=preview_token,
            )
        finally:
            if self._live_inspections is not None:
                try:
                    self._live_inspections.complete(preview_token)
                except Exception:
                    logger.exception("처리 중 이미지 정리 실패: %s", inspection_id)

    async def _inspect(
        self,
        *,
        inspection_id: str,
        images: list[UploadFile],
        metadata: list[InspectionImageMetadata],
        virtual_brix: float | None,
        simulator_faults: tuple[FaultType, ...],
        injected_inference_reason: InspectionDecisionReason | None,
        source_reference: str | None,
        preview_token: str,
    ) -> InspectionResponse:
        """기존 검사 흐름을 수행하며 입력을 읽은 뒤 임시 이미지를 게시한다."""

        sweetness_band = _classify_sweetness(virtual_brix)
        created_at = utc_now()
        row_created = False
        db_unavailable = False
        persistence_status = PersistenceStatus.NOT_ATTEMPTED
        if "DB_ERROR" in simulator_faults:
            persistence_status = PersistenceStatus.FAILED
        elif self._persistence is not None:
            try:
                await asyncio.to_thread(
                    self._persistence.create_pending,
                    self._pending_values(
                        inspection_id=inspection_id,
                        source_reference=source_reference,
                        virtual_brix=virtual_brix,
                        sweetness_band=sweetness_band,
                        created_at=created_at,
                    ),
                )
            except Exception as exc:
                # DB 단절 판단은 이 검사에만 적용하고 다음 검사는 다시 접속을 시도한다.
                db_unavailable = is_database_unavailable_error(exc)
                persistence_status = PersistenceStatus.FAILED
                logger.exception("검사 초기 행 저장에 실패했습니다: %s", inspection_id)
            else:
                row_created = True
                persistence_status = PersistenceStatus.PENDING

        image_payloads: list[bytes] = []
        for image in images:
            image_payloads.append(await image.read())
            await image.seek(0)

        if self._live_inspections is not None and image_payloads:
            try:
                previews = await asyncio.to_thread(
                    build_live_previews,
                    image_payloads,
                    max_dimension=self._live_preview_max_dimension,
                    jpeg_quality=self._live_preview_jpeg_quality,
                )
                self._live_inspections.publish(
                    preview_token,
                    inspection_id=inspection_id,
                    images=previews,
                    started_ms=int(created_at.timestamp() * 1000),
                )
            except Exception:
                # 미리보기 장애가 검사 판정·제어·저장 경로에 영향을 주지 않도록 한다.
                logger.exception("처리 중 이미지 게시 실패: %s", inspection_id)

        inference_request = InferenceRequest(
            inspection_id=inspection_id,
            images=image_payloads,
            metadata=metadata,
        )
        injected_reason = injected_inference_reason
        if "INFERENCE_TIMEOUT" in simulator_faults:
            injected_reason = InspectionDecisionReason.INFERENCE_DEADLINE_EXCEEDED
        elif "INFERENCE_ERROR" in simulator_faults:
            injected_reason = InspectionDecisionReason.INFERENCE_HTTP_ERROR
        inference_response, decision, processing_errors = await self._infer(
            inference_request,
            injected_reason=injected_reason,
            persist_late_result=row_created,
        )

        if (
            decision.inspection_status is InspectionStatus.COMPLETED
            and virtual_brix is None
        ):
            decision = decide_reinspection(
                InspectionDecisionReason.VIRTUAL_BRIX_MISSING,
                cultivar_confidence_threshold=self._cultivar_confidence_threshold,
                quality_confidence_threshold=self._quality_confidence_threshold,
                exclude_from_normal_stats=False,
            )

        try:
            (
                target_bin_code,
                reinspection_bin_code,
                mapping_db_available,
            ) = await self._find_target_bins(
                inference_response=inference_response,
                decision=decision,
                sweetness_band=sweetness_band,
                skip_db=db_unavailable,
            )
        except (BinMappingConfigurationError, BinMappingUnavailableError) as exc:
            processing_errors.append(
                _error_record(
                    component="bin_mapping",
                    error_code="BIN_MAPPING_CONFIGURATION_ERROR",
                    message=str(exc),
                )
            )
            if row_created and isinstance(exc, BinMappingConfigurationError):
                persistence_status = await self._persist_without_control(
                    inspection_id=inspection_id,
                    inference_response=inference_response,
                    decision=decision,
                    virtual_brix=virtual_brix,
                    sweetness_band=sweetness_band,
                    errors=processing_errors,
                )
            logger.error(
                "검사 bin mapping을 결정하지 못했습니다: %s (%s)",
                inspection_id,
                persistence_status.value,
            )
            raise

        control_outcome = next(
            (
                status
                for fault, status in (
                    ("CONTROL_REJECTED", ControlStatus.REJECTED),
                    ("CONTROL_NO_RESPONSE", ControlStatus.NO_RESPONSE),
                    ("CONTROL_FAILED", ControlStatus.FAILED),
                )
                if fault in simulator_faults
            ),
            None,
        )
        control = (
            MockVirtualControl([control_outcome, ControlStatus.SUCCEEDED])
            if control_outcome is not None
            else self._virtual_control
        )
        control_result = await execute_virtual_control(
            control,
            inspection_id=inspection_id,
            target_bin_code=target_bin_code,
            reinspection_bin_code=reinspection_bin_code,
        )
        control_attempts = _control_attempt_records(control_result)
        processing_errors.extend(_control_error_records(control_result))
        final_control_response = control_result.final_response

        if row_created and mapping_db_available:
            persistence_status = await self._persist_final(
                inspection_id=inspection_id,
                inference_response=inference_response,
                decision=decision,
                virtual_brix=virtual_brix,
                sweetness_band=sweetness_band,
                target_bin_code=final_control_response.target_bin_code,
                control_status=final_control_response.control_status,
                control_attempts=control_attempts,
                errors=processing_errors,
            )
        elif row_created:
            # Mapping 조회에서 DB 단절이 확인되면 같은 검사의 저장 재시도를 생략한다.
            persistence_status = PersistenceStatus.FAILED

        if decision.reason in _FAULT_IMAGE_REASONS and self._fault_image_storage:
            try:
                await asyncio.to_thread(
                    self._fault_image_storage.save,
                    inspection_id=inspection_id,
                    error_code=decision.reason.value,
                    images=[
                        FaultImage(content, image.content_type or "")
                        for content, image in zip(image_payloads, images, strict=True)
                    ],
                    created_at=utc_now(),
                )
            except Exception:
                logger.exception("Fault image storage failed: %s", inspection_id)

        inference_fields = (
            inference_response.model_dump(exclude={"inspection_id"})
            if inference_response is not None
            else {}
        )
        return InspectionResponse(
            inspection_id=inspection_id,
            **inference_fields,
            inspection_status=decision.inspection_status,
            review_required=decision.review_required,
            exclude_from_normal_stats=decision.exclude_from_normal_stats,
            decision_reason=decision.reason,
            virtual_brix=virtual_brix,
            brix_is_measured=False,
            sweetness_band=sweetness_band,
            target_bin_code=final_control_response.target_bin_code,
            control_status=final_control_response.control_status,
            persistence_status=persistence_status,
        )

    async def _infer(
        self,
        request: InferenceRequest,
        *,
        persist_late_result: bool,
        injected_reason: InspectionDecisionReason | None = None,
    ) -> tuple[
        InferenceResponse | None,
        InspectionDecision,
        list[InspectionErrorRecord],
    ]:
        if injected_reason is not None:
            decision = (
                decide_inference_timeout(
                    cultivar_confidence_threshold=self._cultivar_confidence_threshold,
                    quality_confidence_threshold=self._quality_confidence_threshold,
                )
                if injected_reason
                is InspectionDecisionReason.INFERENCE_DEADLINE_EXCEEDED
                else decide_reinspection(
                    injected_reason,
                    cultivar_confidence_threshold=self._cultivar_confidence_threshold,
                    quality_confidence_threshold=self._quality_confidence_threshold,
                    exclude_from_normal_stats=True,
                )
            )
            return (
                None,
                decision,
                [
                    _error_record(
                        component="inference",
                        error_code=decision.reason.value,
                        message="Simulator 장애 주입",
                    )
                ],
            )
        event_loop = asyncio.get_running_loop()
        inference_started_at = event_loop.time()
        inference_task = asyncio.create_task(self._inference_client.predict(request))
        completed, _ = await asyncio.wait(
            {inference_task},
            timeout=self._inference_business_deadline_ms / 1000,
        )
        if inference_task not in completed:
            frame_count = len(request.images)
            on_result = (
                (
                    lambda result: self._persist_late_result(
                        result, expected_frame_count=frame_count
                    )
                )
                if persist_late_result
                else None
            )
            self._late_result_manager.track(
                inspection_id=request.inspection_id,
                inference_task=inference_task,
                started_at=inference_started_at,
                on_result=on_result,
            )
            decision = decide_inference_timeout(
                cultivar_confidence_threshold=self._cultivar_confidence_threshold,
                quality_confidence_threshold=self._quality_confidence_threshold,
            )
            return (
                None,
                decision,
                [
                    _error_record(
                        component="inference",
                        error_code=decision.reason.value,
                        message="Inference business deadline을 초과했습니다",
                    )
                ],
            )

        try:
            response = inference_task.result()
            _validate_inference_response(request, response)
        except Exception as exc:  # noqa: BLE001 - 외부 Inference 오류 경계다.
            reason = _inference_failure_reason(exc)
            decision = decide_reinspection(
                reason,
                cultivar_confidence_threshold=self._cultivar_confidence_threshold,
                quality_confidence_threshold=self._quality_confidence_threshold,
                exclude_from_normal_stats=True,
            )
            return (
                None,
                decision,
                [
                    _error_record(
                        component="inference",
                        error_code=reason.value,
                        message=_safe_inference_error_message(reason),
                        diagnostic_data={"exception_type": type(exc).__name__},
                    )
                ],
            )

        decision = decide_inspection(
            response,
            cultivar_confidence_threshold=self._cultivar_confidence_threshold,
            quality_confidence_threshold=self._quality_confidence_threshold,
        )
        return response, decision, []

    async def _persist_late_result(
        self, result: LateInferenceResult, *, expected_frame_count: int
    ) -> None:
        """늦은 응답은 확정 판정과 분리해 기존 검사 행에만 기록한다."""

        response = result.inference_response
        if (
            response.inspection_id != result.inspection_id
            or response.used_frame_count != expected_frame_count
        ):
            logger.warning("늦은 Inference 응답 계약 불일치: %s", result.inspection_id)
            return
        if self._persistence is None:
            return
        try:
            await asyncio.to_thread(
                self._persistence.save_late_result,
                inspection_id=result.inspection_id,
                received_at=utc_now(),
                payload=response.model_dump(mode="json"),
            )
        except Exception:
            logger.exception("늦은 Inference 진단 저장 실패: %s", result.inspection_id)

    async def _find_target_bins(
        self,
        *,
        inference_response: InferenceResponse | None,
        decision: InspectionDecision,
        sweetness_band: str | None,
        skip_db: bool,
    ) -> tuple[str, str, bool]:
        lkg = self._bin_mapping_lkg
        if lkg is None:
            raise BinMappingConfigurationError(
                "bin mapping Repository가 설정되지 않았습니다"
            )

        snapshot, db_available = await asyncio.to_thread(
            lkg.resolve_for_inspection, skip_db=skip_db
        )
        reinspection_bin = snapshot.reinspection_bin
        if decision.inspection_status is InspectionStatus.REINSPECTION_REQUIRED:
            return reinspection_bin, reinspection_bin, db_available
        if inference_response is None or sweetness_band is None:
            raise BinMappingConfigurationError("정상 배차에 필요한 판정값이 없습니다")

        normal_bin = snapshot.normal_bin(
            crop_type=inference_response.crop_type,
            cultivar=inference_response.predicted_cultivar,
            quality_grade=inference_response.predicted_grade,
            sweetness_band=sweetness_band,
        )
        return normal_bin, reinspection_bin, db_available

    async def _persist_final(
        self,
        *,
        inspection_id: str,
        inference_response: InferenceResponse | None,
        decision: InspectionDecision,
        virtual_brix: float | None,
        sweetness_band: str | None,
        target_bin_code: str,
        control_status: ControlStatus,
        control_attempts: list[ControlAttemptRecord],
        errors: list[InspectionErrorRecord],
    ) -> PersistenceStatus:
        values = self._final_values(
            inference_response=inference_response,
            decision=decision,
            virtual_brix=virtual_brix,
            sweetness_band=sweetness_band,
            target_bin_code=target_bin_code,
            control_status=control_status,
            persistence_status=PersistenceStatus.SUCCEEDED,
        )
        if values["error_code"] is None and errors:
            values["error_code"] = errors[0].error_code
        try:
            await asyncio.to_thread(
                self._persistence.finalize,  # type: ignore[union-attr]
                inspection_id=inspection_id,
                inspection_values=values,
                control_attempts=control_attempts,
                errors=errors,
            )
        except Exception as exc:  # noqa: BLE001 - DB 장애를 상태로 격리한다.
            await self._mark_persistence_failed(inspection_id, exc)
            return PersistenceStatus.FAILED
        return PersistenceStatus.SUCCEEDED

    async def _persist_without_control(
        self,
        *,
        inspection_id: str,
        inference_response: InferenceResponse | None,
        decision: InspectionDecision,
        virtual_brix: float | None,
        sweetness_band: str | None,
        errors: list[InspectionErrorRecord],
    ) -> PersistenceStatus:
        values = self._final_values(
            inference_response=inference_response,
            decision=decision,
            virtual_brix=virtual_brix,
            sweetness_band=sweetness_band,
            target_bin_code=None,
            control_status=ControlStatus.NOT_REQUESTED,
            persistence_status=PersistenceStatus.SUCCEEDED,
        )
        values["error_code"] = errors[0].error_code
        try:
            await asyncio.to_thread(
                self._persistence.finalize,  # type: ignore[union-attr]
                inspection_id=inspection_id,
                inspection_values=values,
                control_attempts=[],
                errors=errors,
            )
        except Exception as exc:  # noqa: BLE001 - DB 장애를 상태로 격리한다.
            await self._mark_persistence_failed(inspection_id, exc)
            return PersistenceStatus.FAILED
        return PersistenceStatus.SUCCEEDED

    async def _mark_persistence_failed(
        self,
        inspection_id: str,
        cause: Exception,
    ) -> None:
        logger.error(
            "검사 최종 저장에 실패했습니다: %s (%s)",
            inspection_id,
            type(cause).__name__,
            exc_info=cause,
        )
        error = _error_record(
            component="database",
            error_code="DB_PERSISTENCE_ERROR",
            message="검사 결과 저장에 실패했습니다",
            diagnostic_data={"exception_type": type(cause).__name__},
        )
        try:
            await asyncio.to_thread(
                self._persistence.mark_failed,  # type: ignore[union-attr]
                inspection_id=inspection_id,
                updated_at=utc_now(),
                error=error,
            )
        except Exception:
            logger.exception(
                "검사 저장 실패 상태도 기록하지 못했습니다: %s",
                inspection_id,
            )

    def _pending_values(
        self,
        *,
        inspection_id: str,
        source_reference: str | None,
        virtual_brix: float | None,
        sweetness_band: str | None,
        created_at: datetime,
    ) -> dict[str, object]:
        return {
            "inspection_id": inspection_id,
            "source_reference": source_reference,
            "created_at": created_at,
            "completed_at": None,
            "updated_at": created_at,
            "crop_type": "apple",
            "predicted_cultivar": None,
            "predicted_grade": None,
            "cultivar_confidence": None,
            "quality_confidence": None,
            "applied_cultivar_threshold": _decimal(self._cultivar_confidence_threshold),
            "applied_quality_threshold": _decimal(self._quality_confidence_threshold),
            "model_name": None,
            "model_version": None,
            "preprocessing_version": None,
            "used_frame_count": None,
            "inference_time_ms": None,
            "virtual_brix": _decimal(virtual_brix),
            "brix_source": None,
            "brix_is_measured": False,
            "sweetness_band": sweetness_band,
            "review_required": False,
            "target_bin_code": None,
            "inspection_status": InspectionStatus.PROCESSING.value,
            "control_status": ControlStatus.NOT_REQUESTED.value,
            "persistence_status": PersistenceStatus.PENDING.value,
            "error_code": None,
            "deadline_exceeded": False,
            "exclude_from_normal_stats": False,
            "is_reviewed": False,
            "suspected_error_type": None,
            "review_note": None,
            "reviewed_at": None,
            "late_result_received_at": None,
            "late_result_payload": None,
        }

    def _final_values(
        self,
        *,
        inference_response: InferenceResponse | None,
        decision: InspectionDecision,
        virtual_brix: float | None,
        sweetness_band: str | None,
        target_bin_code: str | None,
        control_status: ControlStatus,
        persistence_status: PersistenceStatus,
    ) -> dict[str, object]:
        completed_at = utc_now()
        return {
            "completed_at": completed_at,
            "updated_at": completed_at,
            "predicted_cultivar": (
                inference_response.predicted_cultivar
                if inference_response is not None
                else None
            ),
            "predicted_grade": (
                inference_response.predicted_grade
                if inference_response is not None
                else None
            ),
            "cultivar_confidence": _decimal(
                inference_response.cultivar_confidence
                if inference_response is not None
                else None
            ),
            "quality_confidence": _decimal(
                inference_response.quality_confidence
                if inference_response is not None
                else None
            ),
            "model_name": inference_response.model_name if inference_response else None,
            "model_version": (
                inference_response.model_version if inference_response else None
            ),
            "preprocessing_version": (
                inference_response.preprocessing_version if inference_response else None
            ),
            "used_frame_count": (
                inference_response.used_frame_count if inference_response else None
            ),
            "inference_time_ms": _decimal(
                inference_response.inference_time_ms if inference_response else None
            ),
            "virtual_brix": _decimal(virtual_brix),
            "brix_source": None,
            "brix_is_measured": False,
            "sweetness_band": sweetness_band,
            "review_required": decision.review_required,
            "target_bin_code": target_bin_code,
            "inspection_status": decision.inspection_status.value,
            "control_status": control_status.value,
            "persistence_status": persistence_status.value,
            "error_code": (
                None
                if decision.reason is InspectionDecisionReason.NORMAL
                else decision.reason.value
            ),
            "deadline_exceeded": (
                decision.reason is InspectionDecisionReason.INFERENCE_DEADLINE_EXCEEDED
            ),
            "exclude_from_normal_stats": decision.exclude_from_normal_stats,
        }


def _classify_sweetness(virtual_brix: float | None) -> str | None:
    if virtual_brix is None:
        return None
    if (
        isinstance(virtual_brix, bool)
        or not isinstance(virtual_brix, (int, float))
        or not math.isfinite(virtual_brix)
        or not 9 <= virtual_brix <= 18
    ):
        raise ValueError("시연용 virtual_brix는 9~18의 유한 숫자여야 합니다")
    return "sweet" if virtual_brix >= DEMO_SWEETNESS_THRESHOLD_BRIX else "less_sweet"


def _validate_inference_response(
    request: InferenceRequest,
    response: InferenceResponse,
) -> None:
    if response.inspection_id != request.inspection_id:
        raise InferenceResponseMismatchError(
            "Inference 응답 inspection_id가 요청과 일치하지 않습니다"
        )
    if response.used_frame_count != len(request.images):
        raise InferenceResponseMismatchError(
            "Inference 응답 used_frame_count가 요청 이미지 수와 일치하지 않습니다"
        )


def _inference_failure_reason(exc: Exception) -> InspectionDecisionReason:
    if isinstance(exc, httpx.HTTPStatusError):
        return InspectionDecisionReason.INFERENCE_HTTP_ERROR
    if isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout)):
        return InspectionDecisionReason.INFERENCE_CONNECTION_ERROR
    if isinstance(exc, httpx.TimeoutException):
        return InspectionDecisionReason.INFERENCE_DEADLINE_EXCEEDED
    if isinstance(exc, httpx.RequestError):
        return InspectionDecisionReason.INFERENCE_CONNECTION_ERROR
    if isinstance(exc, (ValidationError, InferenceResponseMismatchError, ValueError)):
        return InspectionDecisionReason.INFERENCE_INVALID_RESPONSE
    return InspectionDecisionReason.INFERENCE_ERROR


def _safe_inference_error_message(reason: InspectionDecisionReason) -> str:
    messages = {
        InspectionDecisionReason.INFERENCE_DEADLINE_EXCEEDED: (
            "Inference 요청 시간이 초과되었습니다"
        ),
        InspectionDecisionReason.INFERENCE_CONNECTION_ERROR: (
            "Inference 서비스 연결에 실패했습니다"
        ),
        InspectionDecisionReason.INFERENCE_HTTP_ERROR: (
            "Inference 서비스가 오류 응답을 반환했습니다"
        ),
        InspectionDecisionReason.INFERENCE_INVALID_RESPONSE: (
            "Inference 응답 검증에 실패했습니다"
        ),
        InspectionDecisionReason.INFERENCE_ERROR: "Inference 처리에 실패했습니다",
    }
    return messages[reason]


def _error_record(
    *,
    component: str,
    error_code: str,
    message: str,
    diagnostic_data: dict[str, object] | None = None,
) -> InspectionErrorRecord:
    return InspectionErrorRecord(
        component=component,
        error_code=error_code,
        message=message,
        diagnostic_data=diagnostic_data,
        occurred_at=utc_now(),
    )


def _control_attempt_records(
    control_result: ControlExecutionResult,
) -> list[ControlAttemptRecord]:
    return [
        ControlAttemptRecord(
            command_id=trace.command_id,
            attempt_no=index,
            requested_bin_code=response.target_bin_code,
            command_type="ROUTE_TO_BIN",
            control_status=response.control_status.value,
            requested_at=trace.requested_at,
            responded_at=trace.responded_at,
            response_time_ms=trace.response_time_ms,
            failure_reason=response.reason,
        )
        for index, (response, trace) in enumerate(
            zip(control_result.attempts, control_result.traces, strict=True),
            start=1,
        )
    ]


def _control_error_records(
    control_result: ControlExecutionResult,
) -> list[InspectionErrorRecord]:
    errors = []
    for response, trace in zip(
        control_result.attempts,
        control_result.traces,
        strict=True,
    ):
        if response.control_status is ControlStatus.SUCCEEDED:
            continue
        errors.append(
            InspectionErrorRecord(
                component="virtual_control",
                error_code=f"CONTROL_{response.control_status.value}",
                message=response.reason or "Virtual Control 요청이 성공하지 않았습니다",
                diagnostic_data={"target_bin_code": response.target_bin_code},
                occurred_at=trace.responded_at or trace.requested_at,
            )
        )
    return errors


def _decimal(value: float | None) -> Decimal | None:
    return Decimal(str(value)) if value is not None else None
