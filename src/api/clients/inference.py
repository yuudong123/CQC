"""Inference 계약을 사용하는 deterministic Mock Client."""

from __future__ import annotations

import asyncio
import json

import httpx

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


class HttpInferenceClient:
    """Send the existing multipart contract to the real Inference API."""

    def __init__(self, url: str, *, timeout_ms: int = 2000, client: httpx.AsyncClient | None = None) -> None:
        if not url.startswith(("http://", "https://")):
            raise ValueError("Inference URL must be HTTP or HTTPS")
        self._url = url
        self._client = client or httpx.AsyncClient(timeout=timeout_ms / 1000)
        self._owns_client = client is None

    async def predict(self, request: InferenceRequest) -> InferenceResponse:
        files = []
        for index, content in enumerate(request.images):
            is_png = content.startswith(b"\x89PNG\r\n\x1a\n")
            extension, media_type = ("png", "image/png") if is_png else ("jpg", "image/jpeg")
            files.append(("images", (f"view-{index}.{extension}", content, media_type)))
        response = await self._client.post(
            self._url,
            data={
                "inspection_id": request.inspection_id,
                "metadata": json.dumps([item.model_dump() for item in request.metadata]),
            },
            files=files,
        )
        response.raise_for_status()
        return InferenceResponse.model_validate(response.json())

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()
