"""Request-local line deadlines, transport budgets and late-result isolation."""

from __future__ import annotations

import asyncio
from io import BytesIO

import httpx
import pytest
from fastapi import UploadFile
from fastapi.testclient import TestClient

from src.api.clients.inference import HttpInferenceClient, MockInferenceClient
from src.api.control.virtual_control import MockVirtualControl
from src.api.core.config import Settings
from src.api.main import create_app
from src.api.schemas.inference import InferenceRequest
from src.api.schemas.inspections import InspectionImageMetadata
from src.api.services.inspections import InspectionService
from src.api.services.late_results import LateResultManager

from .fakes import FakeBinMappingRepository, RecordingPersistence


def _request(identifier: str) -> InferenceRequest:
    return InferenceRequest(
        inspection_id=identifier,
        images=[b"image"],
        metadata=[
            InspectionImageMetadata(
                view_index=0,
                angle_direction="top",
                verticality_angle=0,
                horizontality_angle=0,
            )
        ],
    )


def _service(client, manager, persistence=None, deadline=500):
    return InspectionService(
        client,
        MockVirtualControl(),
        cultivar_confidence_threshold=0.5,
        quality_confidence_threshold=0.6,
        inference_business_deadline_ms=deadline,
        late_result_manager=manager,
        bin_mapping_repository=FakeBinMappingRepository(),
        persistence=persistence or RecordingPersistence(),
    )


@pytest.mark.parametrize("interval", [1000, 2000, 3000])
def test_interval_deadline_and_transport_hard_budget(
    interval: int, monkeypatch
) -> None:
    async def run():
        observed = []

        async def respond(request):
            observed.append(request.extensions["timeout"])
            await asyncio.sleep(interval / 1000 + 0.05)
            response = await MockInferenceClient().predict(_request("line"))
            return httpx.Response(200, json=response.model_dump(mode="json"))

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            manager = LateResultManager(hard_timeout_ms=10, max_tasks=4)
            hard_budgets = []
            original_track = manager.track

            def track(**kwargs):
                hard_budgets.append(kwargs["hard_timeout_ms"])
                return original_track(**kwargs)

            monkeypatch.setattr(manager, "track", track)
            service = _service(
                HttpInferenceClient("http://inference/v1/predict", client=http), manager
            )
            started = asyncio.get_running_loop().time()
            response, decision, _ = await service._infer(
                _request("line"),
                persist_late_result=False,
                simulator_interval_ms=interval,
            )
            elapsed = asyncio.get_running_loop().time() - started
            assert response is None
            assert decision.reason.value == "INFERENCE_DEADLINE_EXCEEDED"
            assert interval / 1000 - 0.03 <= elapsed < interval / 1000 + 0.5
            assert observed == [
                {
                    "connect": 0.2,
                    "read": (interval + 1000) / 1000,
                    "write": (interval + 1000) / 1000,
                    "pool": (interval + 1000) / 1000,
                }
            ]
            await manager.wait_until_idle()
            # The tiny fallback hard budget must not cancel a request-local late task.
            assert len(manager.results) == 1
            assert manager.hard_timeout_inspection_ids == []
            assert hard_budgets == [interval + 1000]
            assert http.timeout.read == 5.0

    asyncio.run(run())


def test_one_second_late_request_does_not_block_next_inspection() -> None:
    async def run():
        release = asyncio.Event()

        class Client(MockInferenceClient):
            async def predict(self, request):
                if request.inspection_id == "a":
                    await release.wait()
                return await super().predict(request)

        persistence = RecordingPersistence()
        manager = LateResultManager(hard_timeout_ms=2000, max_tasks=4)
        service = _service(Client(), manager, persistence)

        async def inspect(identifier):
            upload = UploadFile(file=BytesIO(b"image"), filename="view.png")
            try:
                return await service.inspect(
                    inspection_id=identifier,
                    images=[upload],
                    metadata=_request(identifier).metadata,
                    virtual_brix=14,
                    simulator_interval_ms=1000,
                )
            finally:
                await upload.close()

        try:
            a = await inspect("a")
            frozen = a.model_dump()
            assert a.decision_reason.value == "INFERENCE_DEADLINE_EXCEEDED"
            assert manager.active_count == 1
            b = await asyncio.wait_for(inspect("b"), timeout=0.5)
            assert b.decision_reason.value == "NORMAL"
            assert manager.active_count == 1
            attempts = len(service._virtual_control.requests)
            release.set()
            await manager.wait_until_idle()
            assert a.model_dump() == frozen
            assert len(service._virtual_control.requests) == attempts
            assert len(persistence.late_results) == 1
            assert persistence.late_results[0][0] == "a"
            assert persistence.final_values[0]["predicted_grade"] is None
        finally:
            await service.shutdown()

    asyncio.run(run())


def test_concurrent_intervals_do_not_share_deadlines_or_transport_timeouts() -> None:
    async def run():
        budgets = {}

        async def respond(request):
            identifier = (
                request.content.decode()
                .split('name="inspection_id"')[1]
                .split("\r\n\r\n")[1]
                .split("\r\n")[0]
            )
            budgets[identifier] = request.extensions["timeout"]
            await asyncio.sleep(1.1)
            response = await MockInferenceClient().predict(_request(identifier))
            return httpx.Response(200, json=response.model_dump(mode="json"))

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            manager = LateResultManager(hard_timeout_ms=2000, max_tasks=4)
            service = _service(
                HttpInferenceClient("http://inference/v1/predict", client=http), manager
            )
            results = await asyncio.gather(
                *(
                    service._infer(
                        _request(str(interval)),
                        persist_late_result=False,
                        simulator_interval_ms=interval,
                    )
                    for interval in (1000, 2000, 3000)
                )
            )
            assert [decision.reason.value for _, decision, _ in results] == [
                "INFERENCE_DEADLINE_EXCEEDED",
                "NORMAL",
                "NORMAL",
            ]
            assert {key: value["read"] for key, value in budgets.items()} == {
                "1000": 2.0,
                "2000": 3.0,
                "3000": 4.0,
            }
            await manager.wait_until_idle()

    asyncio.run(run())


@pytest.mark.parametrize(
    "error,reason",
    [
        (httpx.ConnectError, "INFERENCE_CONNECTION_ERROR"),
        (httpx.ConnectTimeout, "INFERENCE_CONNECTION_ERROR"),
        (httpx.ReadTimeout, "INFERENCE_DEADLINE_EXCEEDED"),
    ],
)
def test_dynamic_deadline_keeps_connection_and_response_error_classification(
    error, reason
):
    class Client(MockInferenceClient):
        async def predict(self, request):
            raise error("test")

    async def run():
        manager = LateResultManager(hard_timeout_ms=2000, max_tasks=4)
        _, decision, _ = await _service(Client(), manager)._infer(
            _request("failure"),
            persist_late_result=False,
            simulator_interval_ms=3000,
        )
        assert decision.reason.value == reason
        assert decision.exclude_from_normal_stats

    asyncio.run(run())


def test_missing_interval_keeps_configured_fallback() -> None:
    async def run():
        manager = LateResultManager(hard_timeout_ms=200, max_tasks=4)
        service = _service(
            MockInferenceClient(response_delay_ms=30), manager, deadline=5
        )
        _, decision, _ = await service._infer(
            _request("fallback"), persist_late_result=False
        )
        assert decision.reason.value == "INFERENCE_DEADLINE_EXCEEDED"
        await manager.wait_until_idle()
        assert len(manager.results) == 1

    asyncio.run(run())


@pytest.mark.parametrize(
    "interval,token,status",
    [
        ("1000", "secret", 200),
        ("2000", "secret", 200),
        ("3000", "secret", 200),
        (None, "secret", 200),
        (None, None, 200),
        ("500", "secret", 422),
        ("4000", "secret", 422),
        ("2e3", "secret", 422),
        ("", "secret", 422),
        ("1000", None, 403),
        ("1000", "wrong", 403),
    ],
)
def test_internal_interval_header_validation(interval, token, status, monkeypatch):
    manager = LateResultManager(hard_timeout_ms=2000, max_tasks=4)
    service = _service(MockInferenceClient(), manager)
    received = []
    original_inspect = service.inspect

    async def inspect(**kwargs):
        received.append(kwargs.get("simulator_interval_ms"))
        return await original_inspect(**kwargs)

    monkeypatch.setattr(service, "inspect", inspect)
    app = create_app(
        Settings(_env_file=None, simulator_fault_token="secret"),
        inspection_service=service,
    )
    headers = {}
    if interval is not None:
        headers["X-CQC-Simulator-Interval-Ms"] = interval
    if token is not None:
        headers.update(
            {"X-CQC-Simulator-Token": token, "X-CQC-Simulator-Bundle-ID": "bundle"}
        )
    with TestClient(app) as client:
        response = client.post(
            "/v1/inspections",
            headers=headers,
            data={
                "inspection_id": "header",
                "metadata": '[{"view_index":0,"angle_direction":"top","verticality_angle":0,"horizontality_angle":0}]',
                "virtual_brix": "14",
            },
            files=[("images", ("view.png", b"image", "image/png"))],
        )
        assert response.status_code == status
        assert received == (
            [int(interval) if interval is not None else None] if status == 200 else []
        )


@pytest.mark.parametrize("interval", [1000, 2000, 3000])
def test_timeout_fault_injection_is_independent_of_line_deadline(interval):
    async def run():
        manager = LateResultManager(hard_timeout_ms=2000, max_tasks=4)
        service = _service(MockInferenceClient(), manager)
        upload = UploadFile(file=BytesIO(b"image"), filename="view.png")
        try:
            result = await service.inspect(
                inspection_id="fault",
                images=[upload],
                metadata=_request("fault").metadata,
                virtual_brix=14,
                simulator_interval_ms=interval,
                simulator_faults=("INFERENCE_TIMEOUT",),
            )
            assert result.decision_reason.value == "INFERENCE_DEADLINE_EXCEEDED"
            assert manager.active_count == 0
        finally:
            await upload.close()
            await service.shutdown()

    asyncio.run(run())


def test_late_manager_cancels_each_task_at_its_own_total_hard_timeout():
    async def run():
        manager = LateResultManager(hard_timeout_ms=1, max_tasks=4)
        cancelled = []

        async def hang(identifier):
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.append(identifier)

        loop = asyncio.get_running_loop()
        tasks = [asyncio.create_task(hang(identifier)) for identifier in ("a", "b")]
        await asyncio.sleep(0)
        for identifier, task, hard in zip(("a", "b"), tasks, (30, 100), strict=True):
            manager.track(
                inspection_id=identifier,
                inference_task=task,
                started_at=loop.time(),
                hard_timeout_ms=hard,
            )
        await asyncio.sleep(0.06)
        assert cancelled == ["a"]
        assert not tasks[1].done()
        await manager.wait_until_idle()
        assert cancelled == ["a", "b"]
        assert all(task.cancelled() for task in tasks)

    asyncio.run(run())
