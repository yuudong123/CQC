"""Backend 검사 상태와 내부 판정 결과 Schema."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from .inference import CultivarProbabilities, Probability, QualityProbabilities

Threshold = Annotated[float, Field(ge=0, le=1)]


class InspectionStatus(str, Enum):
    """검사 처리와 판정 결과 상태."""

    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    REINSPECTION_REQUIRED = "REINSPECTION_REQUIRED"


class ControlStatus(str, Enum):
    """Virtual Control 요청 처리 상태."""

    NOT_REQUESTED = "NOT_REQUESTED"
    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"
    REJECTED = "REJECTED"
    NO_RESPONSE = "NO_RESPONSE"
    FAILED = "FAILED"


class PersistenceStatus(str, Enum):
    """검사 결과 저장 처리 상태."""

    NOT_ATTEMPTED = "NOT_ATTEMPTED"
    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class InspectionDecisionReason(str, Enum):
    """최종 error code와 분리해 사용하는 내부 판정 사유."""

    NORMAL = "NORMAL"
    LOW_CULTIVAR_CONFIDENCE = "LOW_CULTIVAR_CONFIDENCE"
    LOW_QUALITY_CONFIDENCE = "LOW_QUALITY_CONFIDENCE"
    LOW_BOTH_CONFIDENCE = "LOW_BOTH_CONFIDENCE"
    INFERENCE_DEADLINE_EXCEEDED = "INFERENCE_DEADLINE_EXCEEDED"


class InspectionDecision(BaseModel):
    """Inference 정상 응답에 confidence 정책을 적용한 내부 판정 결과."""

    model_config = ConfigDict(extra="forbid")

    inspection_status: InspectionStatus
    review_required: bool
    exclude_from_normal_stats: bool
    reason: InspectionDecisionReason
    cultivar_confidence_threshold: Threshold
    quality_confidence_threshold: Threshold


class InspectionResponse(BaseModel):
    """정상 예측 또는 예측 없는 timeout 판정을 표현하는 Backend 응답."""

    model_config = ConfigDict(extra="forbid")

    inspection_id: str = Field(min_length=1)
    crop_type: Literal["apple"] | None = None
    predicted_cultivar: Literal["fuji", "yanggwang"] | None = None
    cultivar_confidence: Probability | None = None
    cultivar_probabilities: CultivarProbabilities | None = None
    predicted_grade: Literal["L", "M", "S"] | None = None
    quality_confidence: Probability | None = None
    quality_probabilities: QualityProbabilities | None = None
    inference_time_ms: float | None = Field(default=None, ge=0)
    model_name: str | None = Field(default=None, min_length=1)
    model_version: str | None = Field(default=None, min_length=1)
    preprocessing_version: str | None = Field(default=None, min_length=1)
    used_frame_count: int | None = Field(default=None, ge=1, le=12)
    inspection_status: InspectionStatus
    review_required: bool
    exclude_from_normal_stats: bool
    decision_reason: InspectionDecisionReason
    virtual_brix: float | None = Field(default=None, ge=9, le=18, allow_inf_nan=False)
    brix_is_measured: Literal[False] | None = None
    sweetness_band: Literal["less_sweet", "sweet"] | None = None
    target_bin_code: str = Field(min_length=1)
    control_status: ControlStatus
