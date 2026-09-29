"""Frontend 관제 검사 이력의 공개 응답 계약."""

from __future__ import annotations

from datetime import date
from enum import IntEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PageSize(IntEnum):
    FIFTY = 50
    HUNDRED = 100
    TWO_HUNDRED = 200


Fault = Literal[
    "INFERENCE_TIMEOUT",
    "INFERENCE_ERROR",
    "DB_ERROR",
    "CONTROL_REJECTED",
    "CONTROL_NO_RESPONSE",
    "CONTROL_FAILED",
]
ErrorCode = Literal[
    "NONE",
    "INFERENCE_TIMEOUT",
    "INFERENCE_ERROR",
    "DB_ERROR",
    "CONTROL_REJECTED",
    "CONTROL_NO_RESPONSE",
    "CONTROL_FAILED",
]


class QualityResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    date: date
    time: str
    timestamp: float = Field(ge=0)
    variety: Literal["부사", "양광"] | None
    grade: Literal["특", "상", "보통"] | None
    confidence: float | None = Field(ge=0, le=100)
    cultivarConfidence: float | None = Field(ge=0, le=100)
    status: Literal["PASS", "REVIEW", "FAIL"]
    processingStatus: Literal["COMPLETED", "INFERENCING", "TIMEOUT", "ERROR"]
    errorCode: ErrorCode
    misclassification: Literal["NONE", "CULTIVAR_SUSPECT", "QUALITY_SUSPECT", "OTHER"]
    bin: str
    virtualBrix: float | None = Field(ge=9, le=18)
    brixMeasured: Literal[False]
    imageIndex: int | None = Field(ge=0)
    inferenceMs: float | None = Field(ge=0)
    modelVersion: str | None
    reviewRequired: bool
    excluded: bool
    control: Literal[
        "NOT_REQUESTED", "SUCCEEDED", "FALLBACK", "NO_RESPONSE", "REJECTED", "FAILED"
    ]
    persistence: Literal["SAVED", "FAILED"]
    faults: list[Fault] = Field(max_length=5)


class QualityHistoryPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[QualityResult] = Field(max_length=200)
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    pageSize: PageSize
    snapshotAt: float = Field(ge=0)
    bins: list[str]


class QualityError(BaseModel):
    code: str
