"""Virtual Control 요청과 정상 bin 거부 대체 정책."""

from __future__ import annotations

from ..control.virtual_control import MockVirtualControl
from ..schemas.control import (
    ControlExecutionResult,
    VirtualControlRequest,
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

    first_response = await virtual_control.send(
        VirtualControlRequest(
            inspection_id=inspection_id,
            target_bin_code=target_bin_code,
        )
    )
    attempts = [first_response]

    normal_bin_rejected = (
        target_bin_code != reinspection_bin_code
        and first_response.control_status is ControlStatus.REJECTED
    )
    if normal_bin_rejected:
        attempts.append(
            await virtual_control.send(
                VirtualControlRequest(
                    inspection_id=inspection_id,
                    target_bin_code=reinspection_bin_code,
                )
            )
        )

    return ControlExecutionResult(attempts=attempts)
