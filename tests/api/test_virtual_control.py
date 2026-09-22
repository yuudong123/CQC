from __future__ import annotations

import asyncio

import pytest

from src.api.control.virtual_control import MockVirtualControl
from src.api.schemas.control import VirtualControlRequest
from src.api.schemas.inspection_results import ControlStatus
from src.api.services.bin_policy import TEMPORARY_REINSPECTION_BIN_CODE
from src.api.services.control_policy import execute_virtual_control

NORMAL_BIN = "TEST_NORMAL_BIN_1"


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
