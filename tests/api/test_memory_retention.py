"""Bounded diagnostics, active-task isolation and accelerated local memory checks."""

from __future__ import annotations

import asyncio
import gc
import json
import tracemalloc

import pytest

from src.api.clients.inference import MockInferenceClient
from src.api.control.virtual_control import MockVirtualControl
from src.api.schemas.control import VirtualControlRequest
from src.api.schemas.inference import InferenceRequest
from src.api.schemas.inspections import InspectionImageMetadata
from src.api.services.late_results import LateResultManager


async def _response(identifier):
    return await MockInferenceClient().predict(
        InferenceRequest(
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
    )


async def _collect(manager, identifier, *, on_result=None):
    task = asyncio.create_task(_response(identifier))
    assert manager.track(
        inspection_id=identifier,
        inference_task=task,
        started_at=asyncio.get_running_loop().time(),
        on_result=on_result,
    )
    await asyncio.wait_for(manager.wait_until_idle(), timeout=5)


@pytest.mark.parametrize("count", [2, 3, 4, 30])
def test_late_histories_have_independent_limits_and_keep_latest(count):
    async def run():
        manager = LateResultManager(hard_timeout_ms=5000, max_tasks=1, history_limit=3)
        for index in range(count):
            await _collect(manager, f"result-{index}")
        results = list(manager.results)

        # An already expired deadline exercises real cancellation without sleep.
        for index in range(count):
            task = asyncio.create_task(asyncio.Event().wait())
            assert manager.track(
                inspection_id=f"hard-{index}",
                inference_task=task,
                started_at=asyncio.get_running_loop().time() - 10,
            )
            await asyncio.wait_for(manager.wait_until_idle(), timeout=5)
            assert task.cancelled()
        assert manager.results == results

        started = asyncio.Event()
        release = asyncio.Event()

        async def pending():
            started.set()
            await release.wait()
            return await _response("active")

        active = asyncio.create_task(pending())
        await asyncio.wait_for(started.wait(), timeout=5)
        assert manager.track(
            inspection_id="active",
            inference_task=active,
            started_at=asyncio.get_running_loop().time(),
        )
        for index in range(count):
            dropped = asyncio.create_task(_response(f"drop-{index}"))
            assert not manager.track(
                inspection_id=f"drop-{index}",
                inference_task=dropped,
                started_at=asyncio.get_running_loop().time(),
            )
            await asyncio.gather(dropped, return_exceptions=True)
            assert dropped.cancelled()
            assert manager.active_count == 1 and not active.done()
        expected = range(max(0, count - 3), count)
        assert [item.inspection_id for item in manager.results] == [
            f"result-{i}" for i in expected
        ]
        assert manager.hard_timeout_inspection_ids == [f"hard-{i}" for i in expected]
        assert manager.dropped_inspection_ids == [f"drop-{i}" for i in expected]
        await manager.shutdown()
        assert active.cancelled() and manager.active_count == 0

    asyncio.run(run())


def test_evicted_result_still_finishes_callback_while_other_tasks_complete():
    async def run():
        manager = LateResultManager(hard_timeout_ms=5000, max_tasks=4, history_limit=1)
        entered = asyncio.Event()
        release = asyncio.Event()
        persisted = asyncio.Event()

        async def persist(result):
            entered.set()
            await release.wait()
            assert result.inspection_id == "first"
            persisted.set()

        first = asyncio.create_task(_response("first"))
        manager.track(
            inspection_id="first",
            inference_task=first,
            started_at=asyncio.get_running_loop().time(),
            on_result=persist,
        )
        await asyncio.wait_for(entered.wait(), timeout=5)
        others_done = asyncio.Event()
        callbacks = 0

        async def other_persist(result):
            nonlocal callbacks
            assert result.inspection_id.startswith("other-")
            callbacks += 1
            if callbacks == 2:
                others_done.set()

        for index in range(2):
            manager.track(
                inspection_id=f"other-{index}",
                inference_task=asyncio.create_task(_response(f"other-{index}")),
                started_at=asyncio.get_running_loop().time(),
                on_result=other_persist,
            )
        await asyncio.wait_for(others_done.wait(), timeout=5)
        assert len(manager.results) == 1
        assert manager.results[0].inspection_id.startswith("other-")
        assert manager.active_count >= 1 and not persisted.is_set()
        release.set()
        await asyncio.wait_for(manager.wait_until_idle(), timeout=5)
        assert persisted.is_set() and manager.active_count == 0

    asyncio.run(run())


@pytest.mark.parametrize("limit", [0, -1])
def test_late_history_limit_must_be_positive(limit):
    with pytest.raises(ValueError, match="보관 상한"):
        LateResultManager(hard_timeout_ms=1000, max_tasks=1, history_limit=limit)


@pytest.mark.parametrize("kind", ["control", "late"])
def test_accelerated_diagnostic_memory_plateaus(kind):
    """Measure live allocations after warm-up; no append-only persistence spy."""

    async def run():
        control = MockVirtualControl(history_limit=200)
        manager = LateResultManager(
            hard_timeout_ms=5000, max_tasks=1, history_limit=200
        )
        batch_size, batches = (10000, 6) if kind == "control" else (250, 6)
        samples = []
        tracemalloc.start()
        try:
            for batch in range(batches):
                for index in range(batch_size):
                    identifier = f"memory-{batch * batch_size + index:08d}"
                    if kind == "control":
                        await control.send(
                            VirtualControlRequest(
                                inspection_id=identifier, target_bin_code="DEMO_BIN_01"
                            )
                        )
                    else:
                        await _collect(manager, identifier)
                gc.collect()
                current, peak = tracemalloc.get_traced_memory()
                lengths = (
                    [len(control.requests), len(control.status_histories)]
                    if kind == "control"
                    else [
                        len(manager.results),
                        len(manager.hard_timeout_inspection_ids),
                        len(manager.dropped_inspection_ids),
                    ]
                )
                assert max(lengths) == 200
                assert manager.active_count == 0
                samples.append(
                    {
                        "completed": (batch + 1) * batch_size,
                        "lengths": lengths,
                        "current_bytes": current,
                        "peak_bytes": peak,
                    }
                )
            # Ignore warm-up and allow small allocator/measurement overhead.
            retained = [sample["current_bytes"] for sample in samples[1:]]
            assert max(retained) - min(retained) < 128 * 1024
            print(json.dumps({"kind": kind, "batches": samples}))
        finally:
            tracemalloc.stop()
            await manager.shutdown()

    asyncio.run(run())
