"""Issue #53: 처리 중 검사 카드와 메모리 미리보기의 생명주기."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest

from src.api.clients.inference import MockInferenceClient
from src.api.control.virtual_control import MockVirtualControl
from src.api.core.config import Settings
from src.api.main import create_app
from src.api.repositories import BinMappingConfigurationError
from src.api.schemas.inference import InferenceRequest, InferenceResponse
from src.api.services.inspections import InspectionService
from src.api.services.late_results import LateResultManager
from src.api.services.live_inspections import LiveInspectionStore
from src.api.services.quality_operations import QualityOperationsService

from .fakes import FakeBinMappingRepository


class _BlockingInference(MockInferenceClient):
    def __init__(self) -> None:
        self.started: dict[str, asyncio.Event] = {}
        self.release: dict[str, asyncio.Event] = {}

    async def predict(self, request: InferenceRequest) -> InferenceResponse:
        self.started.setdefault(request.inspection_id, asyncio.Event()).set()
        await self.release.setdefault(request.inspection_id, asyncio.Event()).wait()
        return await super().predict(request)


class _History:
    def list_page(self, *args: object, **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(items=[])

    def recent_errors(self, *args: object, **kwargs: object) -> list:
        return []


class _Statistics:
    def today(self, *args: object, **kwargs: object) -> tuple[str, dict]:
        return "2026-10-02", {
            "total": 0,
            "normal": 0,
            "excluded": 0,
            "grades": {},
            "varieties": {},
            "bins": {},
            "suspicions": {},
            "reinspection": 0,
            "inferenceTotalMs": 0,
            "inferenceCount": 0,
        }

    def review_count(self, *args: object, **kwargs: object) -> int:
        return 0

    def last_saved(self, *args: object, **kwargs: object) -> None:
        return None

    def period_totals(self, *args: object, **kwargs: object) -> dict[str, int]:
        return {key: 0 for key in ("1", "5", "10", "30")}

    def points(self, *args: object, **kwargs: object) -> list:
        return []


def _app(*, deadline_ms: int = 1000, mapping_repo=None):
    settings = Settings(inference_business_deadline_ms=deadline_ms)
    store = LiveInspectionStore(limit=64, max_age_seconds=60)
    inference = _BlockingInference()
    service = InspectionService(
        inference,
        MockVirtualControl(),
        cultivar_confidence_threshold=settings.cultivar_confidence_threshold,
        quality_confidence_threshold=settings.quality_confidence_threshold,
        inference_business_deadline_ms=deadline_ms,
        late_result_manager=LateResultManager(hard_timeout_ms=2000, max_tasks=4),
        bin_mapping_repository=mapping_repo or FakeBinMappingRepository(),
        live_inspections=store,
    )
    app = create_app(settings, inspection_service=service)
    app.state.live_inspections = store
    app.state.quality_operations_service = QualityOperationsService(
        _History(), _Statistics(), live_inspections=store
    )
    return app, service, inference, store


def _post(client: httpx.AsyncClient, inspection_id: str, content: bytes | list[bytes]):
    contents = content if isinstance(content, list) else [content]
    return client.post(
        "/v1/inspections",
        data={
            "inspection_id": inspection_id,
            "virtual_brix": "14.0",
            "metadata": json.dumps(
                [
                    {
                        "view_index": index,
                        "angle_direction": "top",
                        "verticality_angle": 0,
                        "horizontality_angle": 0,
                    }
                    for index in range(len(contents))
                ]
            ),
        },
        files=[("images", (f"apple-{index}.png", frame, "image/png")) for index, frame in enumerate(contents)],
    )


def test_job_and_preview_exist_only_while_inspection_runs() -> None:
    asyncio.run(_job_and_preview_exist_only_while_inspection_runs())


async def _job_and_preview_exist_only_while_inspection_runs() -> None:
    app, service, inference, _ = _app()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://backend"
    ) as client:
        frames = [f"apple-{index}".encode() for index in range(12)]
        pending = asyncio.create_task(_post(client, "inspection-a", frames))
        await asyncio.wait_for(
            inference.started.setdefault("inspection-a", asyncio.Event()).wait(), 2
        )
        snapshot = (await client.get("/v1/quality/snapshot")).json()
        jobs = snapshot["state"]["jobs"]
        assert len(jobs) == 1
        assert jobs[0]["id"] == "inspection-a"
        assert jobs[0]["previewUrl"].startswith("/api/quality/previews/live_")
        assert [frame["index"] for frame in jobs[0]["previews"]] == list(range(12))
        assert len({frame["previewUrl"] for frame in jobs[0]["previews"]}) == 12
        preview_path = jobs[0]["previewUrl"].replace("/api/quality", "/v1/quality")
        image = await client.get(preview_path)
        assert image.status_code == 200
        assert image.content == frames[0]
        assert image.headers["content-type"] == "image/png"
        assert image.headers["cache-control"] == "no-store"
        frame_paths = [frame["previewUrl"].replace("/api/quality", "/v1/quality") for frame in jobs[0]["previews"]]
        for index, path in enumerate(frame_paths):
            response = await client.get(path)
            assert response.status_code == 200
            assert response.content == frames[index]

        inference.release["inspection-a"].set()
        assert (await pending).status_code == 200
        assert (await client.get("/v1/quality/snapshot")).json()["state"]["jobs"] == []
        expired = await client.get(preview_path)
        assert expired.status_code == 410
        assert expired.json() == {"code": "IMAGE_EXPIRED"}
        assert expired.headers["cache-control"] == "no-store"
        for path in frame_paths:
            assert (await client.get(path)).status_code == 410
    await service.shutdown()


def test_parallel_inspections_keep_previews_separate() -> None:
    asyncio.run(_parallel_inspections_keep_previews_separate())


async def _parallel_inspections_keep_previews_separate() -> None:
    app, service, inference, _ = _app()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://backend"
    ) as client:
        frames_a = [f"a-{index}".encode() for index in range(12)]
        frames_b = [f"b-{index}".encode() for index in range(3)]
        pending_a = asyncio.create_task(_post(client, "inspection-a", frames_a))
        pending_b = asyncio.create_task(_post(client, "inspection-b", frames_b))
        for inspection_id in ("inspection-a", "inspection-b"):
            await asyncio.wait_for(
                inference.started.setdefault(inspection_id, asyncio.Event()).wait(), 2
            )
        jobs = (await client.get("/v1/quality/snapshot")).json()["state"]["jobs"]
        assert {job["id"] for job in jobs} == {"inspection-a", "inspection-b"}
        paths = {
            job["id"]: job["previewUrl"].replace("/api/quality", "/v1/quality")
            for job in jobs
        }
        assert (await client.get(paths["inspection-a"])).content == frames_a[0]
        assert (await client.get(paths["inspection-b"])).content == frames_b[0]
        for job in jobs:
            expected = frames_a if job["id"] == "inspection-a" else frames_b
            assert len(job["previews"]) == len(expected)
            for frame in job["previews"]:
                path = frame["previewUrl"].replace("/api/quality", "/v1/quality")
                assert (await client.get(path)).content == expected[frame["index"]]

        inference.release["inspection-a"].set()
        assert (await pending_a).status_code == 200
        assert [
            job["id"]
            for job in (await client.get("/v1/quality/snapshot")).json()["state"][
                "jobs"
            ]
        ] == ["inspection-b"]
        assert (await client.get(paths["inspection-a"])).status_code == 410
        assert (await client.get(paths["inspection-b"])).status_code == 200
        for frame in next(job for job in jobs if job["id"] == "inspection-a")["previews"]:
            path = frame["previewUrl"].replace("/api/quality", "/v1/quality")
            assert (await client.get(path)).status_code == 410
        inference.release["inspection-b"].set()
        assert (await pending_b).status_code == 200
    await service.shutdown()


def test_timeout_removes_live_image_without_changing_reinspection() -> None:
    asyncio.run(_timeout_removes_live_image_without_changing_reinspection())


async def _timeout_removes_live_image_without_changing_reinspection() -> None:
    app, service, inference, store = _app(deadline_ms=25)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://backend"
    ) as client:
        pending = asyncio.create_task(_post(client, "inspection-timeout", [b"apple"] * 12))
        await asyncio.wait_for(
            inference.started.setdefault("inspection-timeout", asyncio.Event()).wait(),
            2,
        )
        jobs = (await client.get("/v1/quality/snapshot")).json()["state"]["jobs"]
        assert len(jobs) == 1
        path = jobs[0]["previewUrl"].replace("/api/quality", "/v1/quality")
        frame_paths = [frame["previewUrl"].replace("/api/quality", "/v1/quality") for frame in jobs[0]["previews"]]
        response = await pending
        assert response.status_code == 200
        assert response.json()["decision_reason"] == "INFERENCE_DEADLINE_EXCEEDED"
        assert store.jobs() == []
        assert (await client.get(path)).status_code == 410
        for frame in frame_paths:
            assert (await client.get(frame)).status_code == 410
    await service.shutdown()


def test_live_store_has_bounded_entries_and_expiry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.api.services import live_inspections

    clock = [10.0]
    monkeypatch.setattr(live_inspections, "monotonic", lambda: clock[0])
    store = LiveInspectionStore(limit=1, max_age_seconds=5)
    assert store.publish(
        "a" * 32,
        inspection_id="a",
        images=[(b"a", "image/png")],
        started_ms=1,
    )
    assert not store.publish(
        "b" * 32,
        inspection_id="b",
        images=[(b"b", "image/png")],
        started_ms=1,
    )
    clock[0] = 15.0
    assert store.jobs() == []
    assert store.read("a" * 32) is None
    assert store.publish(
        "b" * 32,
        inspection_id="b",
        images=[(b"b", "image/png")],
        started_ms=1,
    )
    assert store.read("../b") is None
    assert store.read("b" * 32 + "_12") is None
    assert store.read("b" * 32 + "_00/../../secret") is None
    assert store.read("b" * 32 + "_01") is None
    assert store.read("b" * 32 + "_00") == (b"b", "image/png")
    assert not store.publish("c" * 32, inspection_id="c", images=[(b"c", "image/png")] * 13, started_ms=1)


def test_error_path_removes_live_image() -> None:
    asyncio.run(_error_path_removes_live_image())


async def _error_path_removes_live_image() -> None:
    class BrokenMapping(FakeBinMappingRepository):
        def load_snapshot(self):
            raise BinMappingConfigurationError("broken mapping")

    app, service, inference, store = _app(mapping_repo=BrokenMapping())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://backend",
    ) as client:
        pending = asyncio.create_task(_post(client, "inspection-failed", [b"apple"] * 12))
        await asyncio.wait_for(
            inference.started.setdefault("inspection-failed", asyncio.Event()).wait(), 2
        )
        jobs = (await client.get("/v1/quality/snapshot")).json()["state"]["jobs"]
        assert len(jobs) == 1
        path = jobs[0]["previewUrl"].replace("/api/quality", "/v1/quality")
        frame_paths = [frame["previewUrl"].replace("/api/quality", "/v1/quality") for frame in jobs[0]["previews"]]
        inference.release["inspection-failed"].set()
        assert (await pending).status_code == 500
        assert store.jobs() == []
        assert (await client.get(path)).status_code == 410
        for frame in frame_paths:
            assert (await client.get(frame)).status_code == 410
    await service.shutdown()
