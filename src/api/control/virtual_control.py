"""실제 장치 통신 없이 제어 결과를 재현하는 Virtual Control Mock."""

from __future__ import annotations

from ..schemas.control import VirtualControlRequest, VirtualControlResponse
from ..schemas.inspection_results import ControlStatus

TERMINAL_CONTROL_STATUSES = {
    ControlStatus.SUCCEEDED,
    ControlStatus.REJECTED,
    ControlStatus.NO_RESPONSE,
    ControlStatus.FAILED,
}


class MockVirtualControl:
    """주입한 결과를 순서대로 반환하는 deterministic 제어 Mock."""

    def __init__(self, outcomes: list[ControlStatus] | None = None) -> None:
        self._use_default_success = outcomes is None
        configured_outcomes = outcomes if outcomes is not None else []
        if any(
            status not in TERMINAL_CONTROL_STATUSES for status in configured_outcomes
        ):
            raise ValueError("Mock Virtual Control에는 종료 상태만 설정할 수 있습니다")

        self._outcomes = configured_outcomes
        self.requests: list[VirtualControlRequest] = []
        self.status_histories: list[tuple[ControlStatus, ...]] = []

    async def send(self, request: VirtualControlRequest) -> VirtualControlResponse:
        """요청 순서에 대응하는 설정 결과를 반환하고 상태 전이를 기록한다."""

        call_index = len(self.requests)
        if self._use_default_success:
            outcome = ControlStatus.SUCCEEDED
        elif call_index >= len(self._outcomes):
            raise RuntimeError("설정하지 않은 Virtual Control 추가 호출이 발생했습니다")
        else:
            outcome = self._outcomes[call_index]
        self.requests.append(request)
        self.status_histories.append(
            (
                ControlStatus.NOT_REQUESTED,
                ControlStatus.PENDING,
                outcome,
            )
        )
        return VirtualControlResponse(
            inspection_id=request.inspection_id,
            target_bin_code=request.target_bin_code,
            control_status=outcome,
        )
