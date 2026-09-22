"""검사 요청을 Inference 호출로 연결하는 Service."""

from __future__ import annotations

from fastapi import UploadFile

from ..clients.inference import MockInferenceClient
from ..schemas.inference import InferenceRequest, InferenceResponse
from ..schemas.inspections import InspectionImageMetadata


class InferenceResponseMismatchError(RuntimeError):
    """Inference 응답이 요청과 대응하지 않을 때 발생하는 내부 오류."""


class InspectionService:
    """이미지 요청을 구성하고 Inference 응답 정합성을 검증한다."""

    def __init__(self, inference_client: MockInferenceClient) -> None:
        self._inference_client = inference_client

    async def inspect(
        self,
        *,
        inspection_id: str,
        images: list[UploadFile],
        metadata: list[InspectionImageMetadata],
    ) -> InferenceResponse:
        """업로드 이미지를 순서대로 읽어 Mock Inference 결과를 반환한다."""

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
        inference_response = await self._inference_client.predict(inference_request)

        if inference_response.inspection_id != inference_request.inspection_id:
            raise InferenceResponseMismatchError(
                "Inference 응답 inspection_id가 요청과 일치하지 않습니다"
            )
        if inference_response.used_frame_count != len(inference_request.images):
            raise InferenceResponseMismatchError(
                "Inference 응답 used_frame_count가 요청 이미지 수와 일치하지 않습니다"
            )

        return inference_response
