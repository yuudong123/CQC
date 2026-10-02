"""Issue #53: 처리 중 검사 카드와 메모리 미리보기의 생명주기."""

from __future__ import annotations

import asyncio
import json
from io import BytesIO
from types import SimpleNamespace

import httpx
import pytest
from PIL import Image

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
        self.requests: dict[str, list[bytes]] = {}

    async def predict(self, request: InferenceRequest) -> InferenceResponse:
        self.requests[request.inspection_id] = request.images.copy()
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


def _clock(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    from src.api.services import live_inspections

    clock = [10.0]
    monkeypatch.setattr(live_inspections, "monotonic", lambda: clock[0])
    return clock


def _frame(
    index: int, *, format: str = "PNG", size: tuple[int, int] = (640, 480)
) -> bytes:
    image = Image.new("RGB", size, (20 + index * 13, 45 + index * 7, 90 + index * 5))
    output = BytesIO()
    image.save(output, format=format)
    return output.getvalue()


def _oriented_jpeg() -> bytes:
    image = Image.new("RGB", (480, 240), "red")
    exif = image.getexif()
    exif[274] = 6
    output = BytesIO()
    image.save(output, format="JPEG", exif=exif)
    return output.getvalue()


def _post(
    client: httpx.AsyncClient,
    inspection_id: str,
    content: bytes | list[bytes],
    *,
    media_type: str = "image/png",
):
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
        files=[
            ("images", (f"apple-{index}", frame, media_type))
            for index, frame in enumerate(contents)
        ],
    )


def test_job_and_preview_exist_only_while_inspection_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asyncio.run(_job_and_preview_exist_only_while_inspection_runs(_clock(monkeypatch)))


async def _job_and_preview_exist_only_while_inspection_runs(
    clock: list[float],
) -> None:
    app, service, inference, _ = _app()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://backend"
    ) as client:
        frames = [_frame(index) for index in range(12)]
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
        assert image.headers["content-type"] == "image/jpeg"
        assert image.headers["cache-control"] == "no-store"
        frame_paths = [
            frame["previewUrl"].replace("/api/quality", "/v1/quality")
            for frame in jobs[0]["previews"]
        ]
        for index, path in enumerate(frame_paths):
            response = await client.get(path)
            assert response.status_code == 200
            assert response.headers["content-type"] == "image/jpeg"
            with Image.open(BytesIO(response.content)) as preview:
                assert preview.format == "JPEG"
                assert preview.size == (240, 180)
                expected = (20 + index * 13, 45 + index * 7, 90 + index * 5)
                assert all(
                    abs(actual - target) <= 3
                    for actual, target in zip(preview.getpixel((120, 90)), expected)
                )
            assert len(response.content) < len(frames[index])
        assert inference.requests["inspection-a"] == frames

        inference.release["inspection-a"].set()
        assert (await pending).status_code == 200
        assert (await client.get("/v1/quality/snapshot")).json()["state"]["jobs"] == []
        assert (await client.get(preview_path)).status_code == 200
        for path in frame_paths:
            assert (await client.get(path)).status_code == 200
        clock[0] += 3
        expired = await client.get(preview_path)
        assert expired.status_code == 410
        assert expired.json() == {"code": "IMAGE_EXPIRED"}
        assert expired.headers["cache-control"] == "no-store"
        for path in frame_paths:
            assert (await client.get(path)).status_code == 410
    await service.shutdown()


def test_jpeg_input_respects_exif_orientation_and_keeps_url_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asyncio.run(
        _jpeg_input_respects_exif_orientation_and_keeps_url_contract(
            _clock(monkeypatch)
        )
    )


async def _jpeg_input_respects_exif_orientation_and_keeps_url_contract(
    clock: list[float],
) -> None:
    app, service, inference, _ = _app()
    original = _oriented_jpeg()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://backend"
    ) as client:
        pending = asyncio.create_task(
            _post(client, "inspection-jpeg", original, media_type="image/jpeg")
        )
        await asyncio.wait_for(
            inference.started.setdefault("inspection-jpeg", asyncio.Event()).wait(), 2
        )
        jobs = (await client.get("/v1/quality/snapshot")).json()["state"]["jobs"]
        assert len(jobs) == 1
        assert len(jobs[0]["previews"]) == 1
        assert jobs[0]["previewUrl"].startswith("/api/quality/previews/live_")
        path = jobs[0]["previews"][0]["previewUrl"].replace(
            "/api/quality", "/v1/quality"
        )
        response = await client.get(path)
        assert response.headers["content-type"] == "image/jpeg"
        with Image.open(BytesIO(response.content)) as preview:
            assert preview.size == (120, 240)
            assert preview.getexif().get(274) is None
        assert inference.requests["inspection-jpeg"] == [original]
        inference.release["inspection-jpeg"].set()
        assert (await pending).status_code == 200
        assert (await client.get(path)).status_code == 200
        clock[0] += 3
        assert (await client.get(path)).status_code == 410
    await service.shutdown()


def test_preview_conversion_failure_does_not_stop_inspection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.api.services import inspections

    original = _frame(1)

    def fail_conversion(*args: object, **kwargs: object) -> None:
        raise ValueError("preview conversion failed")

    monkeypatch.setattr(inspections, "build_live_previews", fail_conversion)
    asyncio.run(_preview_conversion_failure_does_not_stop_inspection(original))


async def _preview_conversion_failure_does_not_stop_inspection(original: bytes) -> None:
    app, service, inference, store = _app()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://backend"
    ) as client:
        pending = asyncio.create_task(
            _post(client, "inspection-preview-failure", original)
        )
        await asyncio.wait_for(
            inference.started.setdefault(
                "inspection-preview-failure", asyncio.Event()
            ).wait(),
            2,
        )
        assert store.jobs() == []
        assert inference.requests["inspection-preview-failure"] == [original]
        inference.release["inspection-preview-failure"].set()
        response = await pending
        assert response.status_code == 200
        assert response.json()["inspection_status"] == "COMPLETED"
    await service.shutdown()


def test_parallel_inspections_keep_previews_separate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asyncio.run(_parallel_inspections_keep_previews_separate(_clock(monkeypatch)))


async def _parallel_inspections_keep_previews_separate(clock: list[float]) -> None:
    app, service, inference, _ = _app()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://backend"
    ) as client:
        frames_a = [_frame(index) for index in range(12)]
        frames_b = [_frame(index + 12) for index in range(3)]
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
        assert inference.requests["inspection-a"] == frames_a
        assert inference.requests["inspection-b"] == frames_b
        for job in jobs:
            expected = frames_a if job["id"] == "inspection-a" else frames_b
            assert len(job["previews"]) == len(expected)
            for frame in job["previews"]:
                path = frame["previewUrl"].replace("/api/quality", "/v1/quality")
                response = await client.get(path)
                assert response.status_code == 200
                with Image.open(BytesIO(response.content)) as preview:
                    source_index = frame["index"] + (
                        0 if job["id"] == "inspection-a" else 12
                    )
                    expected_color = (
                        20 + source_index * 13,
                        45 + source_index * 7,
                        90 + source_index * 5,
                    )
                    assert all(
                        abs(actual - target) <= 3
                        for actual, target in zip(
                            preview.getpixel((120, 90)), expected_color
                        )
                    )

        inference.release["inspection-a"].set()
        assert (await pending_a).status_code == 200
        assert [
            job["id"]
            for job in (await client.get("/v1/quality/snapshot")).json()["state"][
                "jobs"
            ]
        ] == ["inspection-b"]
        assert (await client.get(paths["inspection-a"])).status_code == 200
        assert (await client.get(paths["inspection-b"])).status_code == 200
        clock[0] += 1
        inference.release["inspection-b"].set()
        assert (await pending_b).status_code == 200
        assert (await client.get("/v1/quality/snapshot")).json()["state"]["jobs"] == []
        clock[0] += 2
        assert (await client.get(paths["inspection-a"])).status_code == 410
        assert (await client.get(paths["inspection-b"])).status_code == 200
        for frame in next(job for job in jobs if job["id"] == "inspection-a")[
            "previews"
        ]:
            path = frame["previewUrl"].replace("/api/quality", "/v1/quality")
            assert (await client.get(path)).status_code == 410
        clock[0] += 1
        assert (await client.get(paths["inspection-b"])).status_code == 410
    await service.shutdown()


def test_timeout_removes_live_image_without_changing_reinspection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asyncio.run(
        _timeout_removes_live_image_without_changing_reinspection(_clock(monkeypatch))
    )


async def _timeout_removes_live_image_without_changing_reinspection(
    clock: list[float],
) -> None:
    app, service, inference, store = _app(deadline_ms=25)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://backend"
    ) as client:
        pending = asyncio.create_task(
            _post(client, "inspection-timeout", [_frame(index) for index in range(12)])
        )
        await asyncio.wait_for(
            inference.started.setdefault("inspection-timeout", asyncio.Event()).wait(),
            2,
        )
        jobs = (await client.get("/v1/quality/snapshot")).json()["state"]["jobs"]
        assert len(jobs) == 1
        path = jobs[0]["previewUrl"].replace("/api/quality", "/v1/quality")
        frame_paths = [
            frame["previewUrl"].replace("/api/quality", "/v1/quality")
            for frame in jobs[0]["previews"]
        ]
        response = await pending
        assert response.status_code == 200
        assert response.json()["decision_reason"] == "INFERENCE_DEADLINE_EXCEEDED"
        assert store.jobs() == []
        assert (await client.get(path)).status_code == 200
        for frame in frame_paths:
            assert (await client.get(frame)).status_code == 200
        clock[0] += 3
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
    assert not store.publish(
        "c" * 32, inspection_id="c", images=[(b"c", "image/png")] * 13, started_ms=1
    )


def test_completed_previews_expire_after_grace_and_release_capacity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = _clock(monkeypatch)
    store = LiveInspectionStore(limit=1, max_age_seconds=60, grace_seconds=3)
    first, second = "a" * 32, "b" * 32
    assert store.publish(
        first, inspection_id="a", images=[(b"a", "image/jpeg")], started_ms=1
    )
    store.complete(first)
    assert store.jobs() == []
    clock[0] = 11.0
    store.complete(first)  # Repeated completion must not extend the deadline.
    assert store.read(first) == (b"a", "image/jpeg")
    assert not store.publish(
        second, inspection_id="b", images=[(b"b", "image/jpeg")], started_ms=1
    )
    clock[0] = 13.0
    assert store.read(first) is None
    assert store.publish(
        second, inspection_id="b", images=[(b"b", "image/jpeg")], started_ms=1
    )


def test_max_age_caps_grace_period(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = _clock(monkeypatch)
    store = LiveInspectionStore(limit=1, max_age_seconds=60, grace_seconds=3)
    token = "a" * 32
    assert store.publish(
        token, inspection_id="a", images=[(b"a", "image/jpeg")], started_ms=1
    )
    clock[0] = 69.0
    store.complete(token)
    assert store.jobs() == []
    assert store.read(token) == (b"a", "image/jpeg")
    clock[0] = 70.0
    assert store.read(token) is None


def test_error_path_removes_live_image(monkeypatch: pytest.MonkeyPatch) -> None:
    asyncio.run(_error_path_removes_live_image(_clock(monkeypatch)))


async def _error_path_removes_live_image(clock: list[float]) -> None:
    class BrokenMapping(FakeBinMappingRepository):
        def load_snapshot(self):
            raise BinMappingConfigurationError("broken mapping")

    app, service, inference, store = _app(mapping_repo=BrokenMapping())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://backend",
    ) as client:
        pending = asyncio.create_task(
            _post(client, "inspection-failed", [_frame(index) for index in range(12)])
        )
        await asyncio.wait_for(
            inference.started.setdefault("inspection-failed", asyncio.Event()).wait(), 2
        )
        jobs = (await client.get("/v1/quality/snapshot")).json()["state"]["jobs"]
        assert len(jobs) == 1
        path = jobs[0]["previewUrl"].replace("/api/quality", "/v1/quality")
        frame_paths = [
            frame["previewUrl"].replace("/api/quality", "/v1/quality")
            for frame in jobs[0]["previews"]
        ]
        inference.release["inspection-failed"].set()
        assert (await pending).status_code == 500
        assert store.jobs() == []
        assert (await client.get(path)).status_code == 200
        for frame in frame_paths:
            assert (await client.get(frame)).status_code == 200
        clock[0] += 3
        assert (await client.get(path)).status_code == 410
        for frame in frame_paths:
            assert (await client.get(frame)).status_code == 410
    await service.shutdown()
