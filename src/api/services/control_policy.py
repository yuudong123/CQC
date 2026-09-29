"""Virtual Control 요청과 정상 bin 거부 대체 정책."""

from __future__ import annotations

from time import perf_counter
from uuid import uuid4

from ..control.virtual_control import MockVirtualControl
from ..core.datetime import utc_now
from ..schemas.control import (
    ControlAttemptTrace,
    ControlExecutionResult,
    VirtualControlRequest,
    VirtualControlResponse,
)
from ..schemas.inspection_results import ControlStatus


async def execute_virtual_control(
    virtual_control: MockVirtualControl,
    *,
    inspection_id: str,
    target_bin_code: str,
    reinspection_bin_code: str,
) -> ControlExecutionResult:
    """목적 bin을 요청하고 정상 bin 거부 시 재검사 bin을 한 번 요청한다."""

    first_response, first_trace = await _send_with_trace(
        virtual_control,
        inspection_id=inspection_id,
        target_bin_code=target_bin_code,
    )
    attempts = [first_response]
    traces = [first_trace]

    normal_bin_rejected = (
        target_bin_code != reinspection_bin_code
        and first_response.control_status is ControlStatus.REJECTED
    )
    if normal_bin_rejected:
        fallback_response, fallback_trace = await _send_with_trace(
            virtual_control,
            inspection_id=inspection_id,
            target_bin_code=reinspection_bin_code,
        )
        attempts.append(fallback_response)
        traces.append(fallback_trace)

    return ControlExecutionResult(attempts=attempts, traces=traces)


async def _send_with_trace(
    virtual_control: MockVirtualControl,
    *,
    inspection_id: str,
    target_bin_code: str,
) -> tuple[VirtualControlResponse, ControlAttemptTrace]:
    """제어 계약을 바꾸지 않고 Backend 호출 ID와 경과 시간을 측정한다."""

    requested_at = utc_now()
    started_at = perf_counter()
    response = await virtual_control.send(
        VirtualControlRequest(
            inspection_id=inspection_id,
            target_bin_code=target_bin_code,
        )
    )
    responded_at = utc_now()
    return response, ControlAttemptTrace(
        command_id=str(uuid4()),
        requested_at=requested_at,
        responded_at=responded_at,
        response_time_ms=(perf_counter() - started_at) * 1000,
    )
