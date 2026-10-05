"""Public per-image fault inventory contract."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from .inspection_id import (
    INSPECTION_ID_MAX_LENGTH,
    INSPECTION_ID_MIN_LENGTH,
    INSPECTION_ID_PATTERN,
)


class QualityFaultImage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    inspectionId: str = Field(
        min_length=INSPECTION_ID_MIN_LENGTH,
        max_length=INSPECTION_ID_MAX_LENGTH,
        pattern=INSPECTION_ID_PATTERN,
    )
    imageIndex: int = Field(ge=0, le=11)
    createdAt: float = Field(ge=0)
    category: Literal["SYSTEM_ERROR", "LOW_CONFIDENCE"]
    decisionReason: str
    cultivarConfidence: float | None = Field(ge=0, le=1)
    qualityConfidence: float | None = Field(ge=0, le=1)
    appliedCultivarThreshold: float | None = Field(ge=0, le=1)
    appliedQualityThreshold: float | None = Field(ge=0, le=1)
    errorCode: (
        Literal[
            "INFERENCE_TIMEOUT",
            "INFERENCE_ERROR",
            "INFERENCE_CONNECTION_ERROR",
            "INFERENCE_HTTP_ERROR",
            "INFERENCE_INVALID_RESPONSE",
        ]
        | None
    )
    previewUrl: str = Field(pattern=r"^/api/quality/previews/[A-Za-z0-9_-]+$")


class QualityFaultImages(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[QualityFaultImage] = Field(max_length=300)


FaultImageId = Annotated[
    str, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
]


class QualityImageDelete(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ids: list[FaultImageId] = Field(max_length=300)


class QualityImageDeleteAck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deletedIds: list[FaultImageId] = Field(max_length=300)
