from __future__ import annotations

import asyncio

import pytest

from src.api.control.virtual_control import MockVirtualControl
from src.api.schemas.control import VirtualControlRequest
from src.api.schemas.inspection_results import ControlStatus
from src.api.services.bin_policy import TEMPORARY_REINSPECTION_BIN_CODE
from src.api.services.control_policy import execute_virtual_control

NORMAL_BIN = "TEST_NORMAL_BIN_1"


@pytest.mark.parametrize("count", [2, 3, 4, 30])
def test_control_history_retains_latest_requests_and_matching_statuses(count):
    outcomes = [
        (ControlStatus.SUCCEEDED, ControlStatus.REJECTED, ControlStatus.FAILED)[i % 3]
        for i in range(count)
    ]
    control = MockVirtualControl(outcomes, history_limit=3)

    async def run():
        for index, outcome in enumerate(outcomes):
            response = await control.send(
                VirtualControlRequest(
                    inspection_id=f"bounded-{index}", target_bin_code=NORMAL_BIN
                )
            )
            assert response.control_status is outcome
            assert len(control.requests) == len(control.status_histories) <= 3
        # Exhaustion must not replay outcomes after the history was trimmed.
        with pytest.raises(RuntimeError, match="추가 호출"):
            await control.send(control.requests[-1])

    asyncio.run(run())
    assert control.call_count == count
    assert [request.inspection_id for request in control.requests] == [
        f"bounded-{i}" for i in range(max(0, count - 3), count)
    ]
    assert [history[-1] for history in control.status_histories] == outcomes[-3:]


@pytest.mark.parametrize("limit", [0, -1])
def test_control_history_limit_must_be_positive(limit):
    with pytest.raises(ValueError, match="보관 상한"):
        MockVirtualControl(history_limit=limit)


def test_fallback_keeps_call_order_when_first_attempt_is_evicted():
    control = MockVirtualControl(
        [ControlStatus.SUCCEEDED, ControlStatus.REJECTED, ControlStatus.SUCCEEDED],
        history_limit=1,
    )

    async def run():
        await control.send(
            VirtualControlRequest(inspection_id="warm-up", target_bin_code=NORMAL_BIN)
        )
        return await execute_virtual_control(
            control,
            inspection_id="fallback-after-trim",
            target_bin_code=NORMAL_BIN,
            reinspection_bin_code=TEMPORARY_REINSPECTION_BIN_CODE,
        )

    result = asyncio.run(run())
    assert [attempt.control_status for attempt in result.attempts] == [
        ControlStatus.REJECTED,
        ControlStatus.SUCCEEDED,
    ]
    assert control.call_count == 3
    assert len(control.requests) == len(control.status_histories) == 1
    assert control.requests[0].target_bin_code == TEMPORARY_REINSPECTION_BIN_CODE


def test_mock_virtual_control_succeeds_by_default() -> None:
    control = MockVirtualControl()
    request = VirtualControlRequest(
        inspection_id="inspection-control",
        target_bin_code=NORMAL_BIN,
    )

    response = asyncio.run(control.send(request))

    assert response.inspection_id == request.inspection_id
    assert response.target_bin_code == NORMAL_BIN
    assert response.control_status is ControlStatus.SUCCEEDED
    assert control.requests == [request]
    assert control.status_histories == [
        (
            ControlStatus.NOT_REQUESTED,
            ControlStatus.PENDING,
            ControlStatus.SUCCEEDED,
        )
    ]


def test_default_mock_supports_repeated_backend_requests() -> None:
    control = MockVirtualControl()
    requests = [
        VirtualControlRequest(
            inspection_id=f"inspection-control-{index}",
            target_bin_code=NORMAL_BIN,
        )
        for index in range(2)
    ]

    responses = [asyncio.run(control.send(request)) for request in requests]

    assert [response.control_status for response in responses] == [
        ControlStatus.SUCCEEDED,
        ControlStatus.SUCCEEDED,
    ]
    assert control.requests == requests


def test_rejected_normal_bin_falls_back_to_reinspection_once() -> None:
    control = MockVirtualControl([ControlStatus.REJECTED, ControlStatus.SUCCEEDED])

    result = asyncio.run(
        execute_virtual_control(
            control,
            inspection_id="inspection-control",
            target_bin_code=NORMAL_BIN,
            reinspection_bin_code=TEMPORARY_REINSPECTION_BIN_CODE,
        )
    )

    assert [attempt.control_status for attempt in result.attempts] == [
        ControlStatus.REJECTED,
        ControlStatus.SUCCEEDED,
    ]
    assert [request.target_bin_code for request in control.requests] == [
        NORMAL_BIN,
        TEMPORARY_REINSPECTION_BIN_CODE,
    ]
    assert result.final_response.target_bin_code == TEMPORARY_REINSPECTION_BIN_CODE
    assert result.final_response.control_status is ControlStatus.SUCCEEDED


def test_rejected_fallback_is_not_retried() -> None:
    control = MockVirtualControl([ControlStatus.REJECTED, ControlStatus.REJECTED])

    result = asyncio.run(
        execute_virtual_control(
            control,
            inspection_id="inspection-control",
            target_bin_code=NORMAL_BIN,
            reinspection_bin_code=TEMPORARY_REINSPECTION_BIN_CODE,
        )
    )

    assert len(control.requests) == 2
    assert result.final_response.control_status is ControlStatus.REJECTED
    assert result.final_response.target_bin_code == TEMPORARY_REINSPECTION_BIN_CODE


@pytest.mark.parametrize(
    "outcome",
    [ControlStatus.NO_RESPONSE, ControlStatus.FAILED],
)
def test_no_response_and_failed_normal_bin_are_not_retried(
    outcome: ControlStatus,
) -> None:
    control = MockVirtualControl([outcome])

    result = asyncio.run(
        execute_virtual_control(
            control,
            inspection_id="inspection-control",
            target_bin_code=NORMAL_BIN,
            reinspection_bin_code=TEMPORARY_REINSPECTION_BIN_CODE,
        )
    )

    assert len(control.requests) == 1
    assert result.final_response.target_bin_code == NORMAL_BIN
    assert result.final_response.control_status is outcome


def test_direct_reinspection_bin_failure_is_not_retried() -> None:
    control = MockVirtualControl([ControlStatus.FAILED])

    result = asyncio.run(
        execute_virtual_control(
            control,
            inspection_id="inspection-control",
            target_bin_code=TEMPORARY_REINSPECTION_BIN_CODE,
            reinspection_bin_code=TEMPORARY_REINSPECTION_BIN_CODE,
        )
    )

    assert len(control.requests) == 1
    assert result.final_response.control_status is ControlStatus.FAILED
