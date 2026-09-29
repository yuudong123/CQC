"""Public per-image fault inventory contract."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class QualityFaultImage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    inspectionId: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    imageIndex: int = Field(ge=0, le=11)
    createdAt: float = Field(ge=0)
    errorCode: Literal[
        "INFERENCE_TIMEOUT",
        "INFERENCE_ERROR",
        "INFERENCE_CONNECTION_ERROR",
        "INFERENCE_HTTP_ERROR",
        "INFERENCE_INVALID_RESPONSE",
    ]
    previewUrl: str = Field(pattern=r"^/api/quality/previews/[A-Za-z0-9_-]+$")


class QualityFaultImages(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[QualityFaultImage] = Field(max_length=100)


FaultImageId = Annotated[
    str, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
]


class QualityImageDelete(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ids: list[FaultImageId] = Field(max_length=100)


class QualityImageDeleteAck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deletedIds: list[FaultImageId] = Field(max_length=100)
