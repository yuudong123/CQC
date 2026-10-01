"""BE-05 관제 snapshot과 기간 통계의 공개 응답 계약."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.json_schema import SkipJsonSchema

from .quality_history import Fault, QualityResult


def _omit_unset_defaults(schema: dict[str, object]) -> None:
    for field in ("history", "concurrency", "intervalMs", "sequence", "tick", "scope"):
        property_schema = schema.get("properties", {}).get(field)
        if isinstance(property_schema, dict):
            property_schema.pop("default", None)


class QualitySummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int = Field(ge=0)
    normal: int = Field(ge=0)
    excluded: int = Field(ge=0)
    reinspection: int = Field(ge=0)
    inferenceTotalMs: float = Field(ge=0)
    inferenceCount: int = Field(ge=0)
    varieties: dict[str, float]
    grades: dict[str, float]
    bins: dict[str, float]
    suspicions: dict[str, float]


class QualityPoint(BaseModel):
    at: float = Field(ge=0)
    count: int = Field(ge=0)
    review: int = Field(ge=0)
    excluded: int = Field(ge=0)


class QualityComponent(BaseModel):
    status: Literal["healthy", "stopped", "error", "unknown"]
    lastSeenAt: float | None = Field(ge=0)
    detail: str


class QualityCapabilities(BaseModel):
    control: bool
    faults: bool
    review: bool
    deleteImages: bool
    concurrency: list[Literal[1, 2, 4]] = Field(max_length=3)
    intervals: list[Literal[1000, 2000, 3000]] = Field(max_length=3)


class QualityComponents(BaseModel):
    Simulator: QualityComponent
    Inference: QualityComponent
    Backend: QualityComponent
    MySQL: QualityComponent


class QualityRetention(BaseModel):
    model_config = ConfigDict(json_schema_extra=_omit_unset_defaults)

    history: int | SkipJsonSchema[None] = Field(default=None, ge=0)
    images: int = Field(ge=0)


class QualityPeriodTotals(BaseModel):
    one: int = Field(alias="1", ge=0)
    five: int = Field(alias="5", ge=0)
    ten: int = Field(alias="10", ge=0)
    thirty: int = Field(alias="30", ge=0)


class QualityJob(BaseModel):
    id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    index: int = Field(ge=0)
    started: float = Field(ge=0)
    finish: float = Field(ge=0)
    faults: list[Fault] = Field(max_length=5)
    previewUrl: str | None = None


class QualityToday(QualitySummary):
    date: str
    review: int = Field(ge=0)
    suspicions: dict[Literal["CULTIVAR_SUSPECT", "QUALITY_SUSPECT", "OTHER"], int]


class QualityState(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra=_omit_unset_defaults)

    throughput: float = Field(ge=0)
    running: bool
    concurrency: Literal[1, 2, 4] | SkipJsonSchema[None] = None
    intervalMs: int | SkipJsonSchema[None] = Field(default=None, ge=1)
    sequence: int | SkipJsonSchema[None] = Field(default=None, ge=0)
    tick: int | SkipJsonSchema[None] = Field(default=None, ge=0)
    faults: list[Fault] = Field(max_length=5)
    scope: Literal["ALL", "NEXT"] | SkipJsonSchema[None] = None
    jobs: list[QualityJob] = Field(max_length=64)
    history: list[QualityResult] = Field(max_length=200)
    images: list[QualityResult] = Field(max_length=100)
    points: list[QualityPoint] = Field(max_length=1800)
    errors: list[QualityResult] = Field(max_length=50)
    today: QualityToday
    lastSaved: float | None = Field(ge=0)
    dbDown: bool


class QualitySnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contractVersion: Literal["1"]
    source: Literal["backend"]
    capturedAt: float = Field(ge=0)
    revision: int = Field(ge=0)
    capabilities: QualityCapabilities
    components: QualityComponents
    retention: QualityRetention
    periodTotals: QualityPeriodTotals
    state: QualityState
