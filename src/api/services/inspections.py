"""검사 요청을 Inference 호출로 연결하는 Service."""

from __future__ import annotations

import asyncio

from fastapi import UploadFile

from ..clients.inference import MockInferenceClient
from ..control.virtual_control import MockVirtualControl
from ..schemas.inference import InferenceRequest
from ..schemas.inspection_results import InspectionResponse
from ..schemas.inspections import InspectionImageMetadata
from .bin_policy import TEMPORARY_REINSPECTION_BIN_CODE, determine_target_bin
from .control_policy import execute_virtual_control
from .inspection_policy import decide_inference_timeout, decide_inspection


class InferenceResponseMismatchError(RuntimeError):
    """Inference 응답이 요청과 대응하지 않을 때 발생하는 내부 오류."""


class InspectionService:
    """이미지 요청을 구성하고 Inference 응답 정합성을 검증한다."""

    def __init__(
        self,
        inference_client: MockInferenceClient,
        virtual_control: MockVirtualControl,
        *,
        cultivar_confidence_threshold: float,
        quality_confidence_threshold: float,
        inference_business_deadline_ms: int,
    ) -> None:
        self._inference_client = inference_client
        self._virtual_control = virtual_control
        self._cultivar_confidence_threshold = cultivar_confidence_threshold
        self._quality_confidence_threshold = quality_confidence_threshold
        self._inference_business_deadline_ms = inference_business_deadline_ms

    async def inspect(
        self,
        *,
        inspection_id: str,
        images: list[UploadFile],
        metadata: list[InspectionImageMetadata],
    ) -> InspectionResponse:
        """Mock Inference 결과를 검증하고 confidence 정책을 적용한다."""

        image_payloads: list[bytes] = []
        for image in images:
            image_payloads.append(await image.read())
            # 후속 처리에서 UploadFile을 다시 사용할 수 있도록 읽기 위치를 복원한다.
            await image.seek(0)

        inference_request = InferenceRequest(
            inspection_id=inspection_id,
            images=image_payloads,
            metadata=metadata,
        )
        try:
            inference_response = await asyncio.wait_for(
                self._inference_client.predict(inference_request),
                timeout=self._inference_business_deadline_ms / 1000,
            )
        except TimeoutError:
            inference_response = None
            decision = decide_inference_timeout(
                cultivar_confidence_threshold=self._cultivar_confidence_threshold,
                quality_confidence_threshold=self._quality_confidence_threshold,
            )
        else:
            if inference_response.inspection_id != inference_request.inspection_id:
                raise InferenceResponseMismatchError(
                    "Inference 응답 inspection_id가 요청과 일치하지 않습니다"
                )
            if inference_response.used_frame_count != len(inference_request.images):
                raise InferenceResponseMismatchError(
                    "Inference 응답 used_frame_count가 요청 이미지 수와 일치하지 않습니다"
                )

            decision = decide_inspection(
                inference_response,
                cultivar_confidence_threshold=self._cultivar_confidence_threshold,
                quality_confidence_threshold=self._quality_confidence_threshold,
            )
        target_bin_code = determine_target_bin(inference_response, decision)
        control_result = await execute_virtual_control(
            self._virtual_control,
            inspection_id=inspection_id,
            target_bin_code=target_bin_code,
            reinspection_bin_code=TEMPORARY_REINSPECTION_BIN_CODE,
        )
        final_control_response = control_result.final_response
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
            target_bin_code=final_control_response.target_bin_code,
            control_status=final_control_response.control_status,
        )
