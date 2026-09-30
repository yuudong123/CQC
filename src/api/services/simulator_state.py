"""단일 Backend 프로세스의 Simulator 제어 설정을 보관한다."""

from __future__ import annotations

from dataclasses import dataclass, replace
from threading import Lock
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
    for field in ("running", "concurrency", "faults", "scope"):
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
    faults: list[FaultType] | SkipJsonSchema[None] = Field(
        default=None, json_schema_extra={"maxItems": 5, "uniqueItems": True}
    )
    scope: FaultScope | SkipJsonSchema[None] = None

    @field_validator("concurrency", mode="before")
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

    @field_validator("running", "concurrency", "faults", "scope")
    @classmethod
    def no_explicit_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("settings fields cannot be null")
        return value


@dataclass(frozen=True, slots=True)
class SimulatorRuntimeState:
    """외부에서 변경할 수 없는 현재 Simulator 설정 snapshot."""

    revision: int = 0
    running: bool = False
    concurrency: int = 1
    faults: tuple[FaultType, ...] = ()
    scope: FaultScope = "ALL"


class RevisionMismatchError(ValueError):
    """요청 revision이 현재 Simulator 설정과 다를 때 발생한다."""

    def __init__(self, expected: int, current: int) -> None:
        super().__init__(f"Expected revision {expected}, current revision {current}")
        self.expected = expected
        self.current = current


class SimulatorStateService:
    """짧은 메모리 상태 변경을 원자적으로 적용한다."""

    def __init__(self) -> None:
        self._state = SimulatorRuntimeState()
        self._lock = Lock()

    def get_state(self) -> SimulatorRuntimeState:
        """불변 snapshot을 반환한다."""

        with self._lock:
            return self._state

    def update_state(self, update: SimulatorSettingsUpdate) -> SimulatorRuntimeState:
        """revision을 비교한 뒤 모든 변경을 한 번에 적용한다."""

        changes = update.model_dump(exclude_unset=True, exclude={"expected_revision"})
        if "faults" in changes:
            changes["faults"] = tuple(changes["faults"])
        with self._lock:
            if update.expected_revision != self._state.revision:
                raise RevisionMismatchError(
                    update.expected_revision, self._state.revision
                )
            self._state = replace(
                self._state, **changes, revision=self._state.revision + 1
            )
            return self._state

    def claim_faults_for_inspection(self) -> tuple[FaultType, ...]:
        """새 Simulator 검사 1건에 적용할 장애를 원자적으로 가져온다.

        NEXT는 첫 검사에서만 비우고, FE 참조 구현처럼 scope는 유지한다.
        실제 검사 전송과 장애 주입은 후속 Simulator 실행 단계에서 연결한다.
        """

        with self._lock:
            faults = self._state.faults
            if faults and self._state.scope == "NEXT":
                self._state = replace(
                    self._state, faults=(), revision=self._state.revision + 1
                )
            return faults
