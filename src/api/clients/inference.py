"""Inference 계약을 사용하는 deterministic Mock Client."""

from __future__ import annotations

import asyncio

from ..schemas.inference import (
    CultivarProbabilities,
    InferenceRequest,
    InferenceResponse,
    QualityProbabilities,
)


class MockInferenceClient:
    """HTTP 호출 없이 고정된 정상 추론 결과를 반환한다."""

    def __init__(self, response_delay_ms: int = 0) -> None:
        if response_delay_ms < 0:
            raise ValueError("Mock Inference 지연 시간은 0 이상이어야 합니다")
        self._response_delay_ms = response_delay_ms

    async def predict(self, request: InferenceRequest) -> InferenceResponse:
        """요청 식별자와 실제 이미지 수를 유지한 Mock 결과를 반환한다."""

        response_delay_ms = getattr(self, "_response_delay_ms", 0)
        if response_delay_ms:
            await asyncio.sleep(response_delay_ms / 1000)

        return InferenceResponse(
            inspection_id=request.inspection_id,
            crop_type="apple",
            predicted_cultivar="fuji",
            cultivar_confidence=0.9,
            cultivar_probabilities=CultivarProbabilities(
                fuji=0.9,
                yanggwang=0.1,
            ),
            predicted_grade="L",
            quality_confidence=0.8,
            quality_probabilities=QualityProbabilities(
                L=0.8,
                M=0.1,
                S=0.1,
            ),
            inference_time_ms=12.5,
            model_name="mock-separate",
            model_version="mock-cqc-separate12-v1",
            preprocessing_version="mock-v1",
            used_frame_count=len(request.images),
        )
