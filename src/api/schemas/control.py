"""Virtual Control 요청·응답과 제어 실행 결과 Schema."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .inspection_results import ControlStatus


class VirtualControlRequest(BaseModel):
    """Backend가 Virtual Control에 전달하는 최소 제어 명령."""

    model_config = ConfigDict(extra="forbid")

    inspection_id: str = Field(min_length=1)
    target_bin_code: str = Field(min_length=1)


class VirtualControlResponse(BaseModel):
    """Virtual Control이 제어 명령 처리 후 반환하는 결과."""

    model_config = ConfigDict(extra="forbid")

    inspection_id: str = Field(min_length=1)
    target_bin_code: str = Field(min_length=1)
    control_status: ControlStatus
    reason: str | None = None


class ControlExecutionResult(BaseModel):
    """최초 요청과 선택적 대체 요청을 순서대로 보존한 제어 결과."""

    model_config = ConfigDict(extra="forbid")

    attempts: list[VirtualControlResponse] = Field(min_length=1, max_length=2)

    @property
    def final_response(self) -> VirtualControlResponse:
        """마지막으로 실행한 제어 요청의 응답을 반환한다."""

        return self.attempts[-1]
