"""Backend와 Simulator가 공유하는 내부 상태 전송 계약."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.json_schema import SkipJsonSchema

FaultType = Literal[
    "INFERENCE_TIMEOUT",
    "INFERENCE_ERROR",
    "DB_ERROR",
    "CONTROL_REJECTED",
    "CONTROL_NO_RESPONSE",
    "CONTROL_FAILED",
]
FaultScope = Literal["ALL", "NEXT"]


def _omit_unset_defaults(schema: dict[str, object]) -> None:
    for field in ("running", "concurrency", "faults", "scope", "intervalMs"):
        property_schema = schema.get("properties", {}).get(field)
        if isinstance(property_schema, dict):
            property_schema.pop("default", None)


class SimulatorSettingsUpdate(BaseModel):
    """공유 Settings 계약과 같은 부분 변경 입력을 검증한다."""

    model_config = ConfigDict(
        extra="forbid", strict=True, json_schema_extra=_omit_unset_defaults
    )

    expected_revision: int = Field(alias="expectedRevision", ge=0)
    running: bool | SkipJsonSchema[None] = None
    concurrency: Literal[1, 2, 4] | SkipJsonSchema[None] = None
    interval_ms: Literal[1000, 2000, 3000] | SkipJsonSchema[None] = Field(
        default=None, alias="intervalMs"
    )
    faults: list[FaultType] | SkipJsonSchema[None] = Field(
        default=None, json_schema_extra={"maxItems": 5, "uniqueItems": True}
    )
    scope: FaultScope | SkipJsonSchema[None] = None

    @field_validator("concurrency", "interval_ms", mode="before")
    @classmethod
    def integer_concurrency(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("concurrency must be an integer")
        return value

    @field_validator("faults")
    @classmethod
    def unique_faults(cls, value: list[FaultType] | None) -> list[FaultType] | None:
        if value is not None and len(value) > 5:
            raise ValueError("faults must contain at most five items")
        if value is not None and len(value) != len(set(value)):
            raise ValueError("faults must be unique")
        return value

    @field_validator("running", "concurrency", "interval_ms", "faults", "scope")
    @classmethod
    def no_explicit_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("settings fields cannot be null")
        return value


class SimulatorStatus(BaseModel):
    """Simulator 내부 API가 Backend에 반환하는 현재 상태."""

    model_config = ConfigDict(extra="forbid")

    revision: int = Field(ge=0)
    running: bool
    concurrency: Literal[1, 2, 4]
    interval_ms: int = Field(alias="intervalMs", ge=1)
    faults: list[FaultType] = Field(max_length=5)
    scope: FaultScope
    status: Literal["healthy", "stopped", "error"]
    lastSeenAt: float | None = Field(ge=0)
