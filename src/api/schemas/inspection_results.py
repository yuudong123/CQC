"""Backend 검사 상태와 내부 판정 결과 Schema."""

from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from .inference import InferenceResponse

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


class InspectionDecision(BaseModel):
    """Inference 정상 응답에 confidence 정책을 적용한 내부 판정 결과."""

    model_config = ConfigDict(extra="forbid")

    inspection_status: InspectionStatus
    review_required: bool
    exclude_from_normal_stats: bool
    reason: InspectionDecisionReason
    cultivar_confidence_threshold: Threshold
    quality_confidence_threshold: Threshold


class InspectionResponse(InferenceResponse):
    """Inference 결과에 현재 Backend 판정 상태를 더한 검사 응답."""

    inspection_status: InspectionStatus
    review_required: bool
