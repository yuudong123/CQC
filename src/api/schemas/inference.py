"""Backend가 사용하는 Inference 요청·응답 계약."""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .inspections import InspectionImageMetadata

Probability = Annotated[float, Field(ge=0, le=1)]


class CultivarProbabilities(BaseModel):
    """Inference가 반환하는 품종별 확률."""

    model_config = ConfigDict(extra="forbid")

    fuji: Probability
    yanggwang: Probability


class QualityProbabilities(BaseModel):
    """Inference가 반환하는 품질 등급별 확률."""

    model_config = ConfigDict(extra="forbid")

    L: Probability
    M: Probability
    S: Probability


class InferenceRequest(BaseModel):
    """Backend 내부에서 Inference Client로 전달하는 요청."""

    model_config = ConfigDict(extra="forbid")

    inspection_id: str = Field(min_length=1)
    images: list[bytes] = Field(min_length=1, max_length=12)
    metadata: list[InspectionImageMetadata] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def validate_image_metadata_alignment(self) -> Self:
        """이미지와 metadata의 개수·순서 대응을 검증하되 재정렬하지 않는다."""

        if len(self.images) != len(self.metadata):
            raise ValueError("images와 metadata 개수는 같아야 합니다")

        view_indexes = [item.view_index for item in self.metadata]
        if view_indexes != list(range(len(self.images))):
            raise ValueError(
                "metadata의 view_index는 이미지 순서에 따라 0부터 연속되어야 합니다"
            )
        return self


class InferenceResponse(BaseModel):
    """Backend가 검증할 Inference 정상 응답."""

    model_config = ConfigDict(extra="forbid")

    inspection_id: str = Field(min_length=1)
    crop_type: Literal["apple"]
    predicted_cultivar: Literal["fuji", "yanggwang"]
    cultivar_confidence: Probability
    cultivar_probabilities: CultivarProbabilities
    predicted_grade: Literal["L", "M", "S"]
    quality_confidence: Probability
    quality_probabilities: QualityProbabilities
    inference_time_ms: float = Field(ge=0)
    model_name: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    preprocessing_version: str = Field(min_length=1)
    used_frame_count: int = Field(ge=1, le=12)
