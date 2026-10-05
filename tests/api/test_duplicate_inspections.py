"""Duplicate inspection IDs stop before downstream side effects."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import datetime, timezone
from threading import Lock
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient
from pymysql.err import IntegrityError as MysqlIntegrityError
from sqlalchemy.exc import IntegrityError

from src.api.clients.inference import MockInferenceClient
from src.api.control.virtual_control import MockVirtualControl
from src.api.core.config import Settings
from src.api.main import create_app
from src.api.repositories import DuplicateInspectionIdError, InspectionPersistence
from src.api.schemas.inference import InferenceRequest, InferenceResponse
from src.api.services.inspections import InspectionService
from src.api.services.late_results import LateResultManager

from .fakes import FakeBinMappingRepository, RecordingPersistence
from .test_inspections import _images, _metadata


def _integrity_error(code: int, message: str) -> IntegrityError:
    return IntegrityError("INSERT inspections", {}, MysqlIntegrityError(code, message))


@pytest.mark.parametrize(
    ("code", "message", "duplicate"),
    [
        (1062, "Duplicate entry 'same-id' for key 'PRIMARY'", True),
        (1062, "Duplicate entry 'same-id' for key 'inspections.PRIMARY'", True),
        (1062, "Duplicate entry 'same-id' for key 'cqc.inspections.PRIMARY'", True),
        (1062, "Duplicate entry 'same-id' for key `inspections.PRIMARY`", True),
        (1062, "Duplicate entry 'same-id' for key 'other_unique'", False),
        (1062, "Duplicate entry 'same-id' for key 'other_table.PRIMARY'", False),
        (1062, "Duplicate entry 'same-id'", False),
        (1048, "Column 'inspection_id' cannot be null", False),
        (1452, "Cannot add child row: foreign key constraint fails", False),
    ],
)
def test_only_initial_inspection_pk_conflicts_are_translated(
    code: int, message: str, duplicate: bool
) -> None:
    session = MagicMock()
    session.__enter__.return_value = session
    failure = _integrity_error(code, message)
    session.flush.side_effect = failure
    persistence = InspectionPersistence(lambda: session)
    now = datetime.now(timezone.utc)
    values = {"inspection_id": "same-id", "created_at": now, "updated_at": now}

    with pytest.raises(
        DuplicateInspectionIdError if duplicate else IntegrityError
    ) as exc:
        persistence.create_pending(values)

    if duplicate:
        assert exc.value.__cause__ is failure
    else:
        assert exc.value is failure
    session.add.assert_called_once()
    session.flush.assert_called_once()
    # The failed transaction exits without advancing retention or updating an old row.
    assert session.begin.return_value.__exit__.call_args.args[0] is type(exc.value)
    assert persistence._history_count is None
    assert session.execute.call_count == 0


class UniquePersistence(RecordingPersistence):
    """Atomically model an INSERT conflict, independently of inference concurrency."""

    def __init__(self) -> None:
        super().__init__()
        self._ids: set[str] = set()
        self._lock = Lock()

    def create_pending(self, values: dict[str, object]) -> None:
        with self._lock:
            if values["inspection_id"] in self._ids:
                raise DuplicateInspectionIdError
            super().create_pending(values)
            self._ids.add(str(values["inspection_id"]))


class CountingInference(MockInferenceClient):
    calls = 0
    next_response = "normal"

    async def predict(self, request: InferenceRequest) -> InferenceResponse:
        self.calls += 1
        if self.next_response == "timeout":
            await asyncio.sleep(0.2)
        response = await super().predict(request)
        if self.next_response == "low":
            return response.model_copy(
                update={"cultivar_confidence": 0.1, "quality_confidence": 0.1}
            )
        return response


def _setup(persistence: RecordingPersistence):
    inference = CountingInference()
    control = MockVirtualControl()
    system_images = MagicMock()
    low_images = MagicMock()
    late = LateResultManager(hard_timeout_ms=300, max_tasks=4)
    service = InspectionService(
        inference,
        control,
        cultivar_confidence_threshold=0.50,
        quality_confidence_threshold=0.60,
        inference_business_deadline_ms=100,
        late_result_manager=late,
        bin_mapping_repository=FakeBinMappingRepository(),
        persistence=persistence,
        fault_image_storage=system_images,
        low_confidence_image_storage=low_images,
    )
    return (
        create_app(Settings(), inspection_service=service),
        inference,
        control,
        system_images,
        low_images,
        late,
    )


def _request() -> dict:
    return {
        "data": {
            "inspection_id": "same-id",
            "metadata": _metadata([0]),
            "virtual_brix": "13.9",
        },
        "files": _images(1),
    }


@pytest.mark.parametrize("next_response", ["normal", "low", "timeout"])
def test_repeated_id_returns_409_without_any_downstream_work(
    next_response: str, caplog: pytest.LogCaptureFixture
) -> None:
    persistence = UniquePersistence()
    app, inference, control, system_images, low_images, late = _setup(persistence)
    with TestClient(app) as client:
        first = client.post("/v1/inspections", **_request())
        assert first.status_code == 200
        assert first.json()["decision_reason"] == "NORMAL"
        assert first.json()["persistence_status"] == "SUCCEEDED"
        original = deepcopy(persistence.final_values)
        inference.next_response = next_response
        caplog.clear()

        duplicate = client.post("/v1/inspections", **_request())

        assert duplicate.status_code == 409
        assert duplicate.json() == {"detail": "inspection_id가 이미 존재합니다"}
        schema = client.get("/openapi.json").json()
        assert "409" in schema["paths"]["/v1/inspections"]["post"]["responses"]
    assert inference.calls == 1
    assert len(control.requests) == 1
    assert len(persistence.pending_values) == 1
    assert persistence.final_values == original
    assert len(persistence.control_attempts) == 1
    assert persistence.errors == []
    assert persistence.failed_ids == []
    system_images.save.assert_not_called()
    low_images.save.assert_not_called()
    assert late.active_count == 0
    assert late.results == []
    assert late.dropped_inspection_ids == []
    assert not any(record.levelno >= 40 for record in caplog.records)


def test_simultaneous_duplicate_requests_process_exactly_one() -> None:
    persistence = UniquePersistence()
    app, inference, control, system_images, low_images, late = _setup(persistence)

    async def run() -> list[httpx.Response]:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await asyncio.gather(
                client.post("/v1/inspections", **_request()),
                client.post("/v1/inspections", **_request()),
            )

    responses = asyncio.run(run())
    assert sorted(response.status_code for response in responses) == [200, 409]
    assert inference.calls == 1
    assert len(control.requests) == 1
    assert len(persistence.pending_values) == len(persistence.final_values) == 1
    assert len(persistence.control_attempts) == 1
    system_images.save.assert_not_called()
    low_images.save.assert_not_called()
    assert late.active_count == 0


def test_general_initial_storage_failure_still_processes_request() -> None:
    persistence = RecordingPersistence(fail_create=True)
    app, inference, control, _, _, _ = _setup(persistence)
    with TestClient(app) as client:
        response = client.post("/v1/inspections", **_request())
    assert response.status_code == 200
    assert response.json()["decision_reason"] == "NORMAL"
    assert response.json()["persistence_status"] == "FAILED"
    assert inference.calls == len(control.requests) == 1


def test_other_integrity_error_still_uses_storage_failure_policy() -> None:
    persistence = RecordingPersistence()
    persistence.create_pending = MagicMock(
        side_effect=_integrity_error(1062, "Duplicate entry 'x' for key 'other_unique'")
    )
    app, inference, control, _, _, _ = _setup(persistence)
    with TestClient(app) as client:
        response = client.post("/v1/inspections", **_request())
    assert response.status_code == 200
    assert response.json()["persistence_status"] == "FAILED"
    assert inference.calls == len(control.requests) == 1
