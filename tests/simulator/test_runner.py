"""주입된 시연 자료로 Simulator 재생·위치·동시성을 검증한다."""

from __future__ import annotations

import asyncio
import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic

import httpx
import pytest

from src.simulator.dataset import SimulatorDataset, SimulatorDatasetError
from src.simulator.position import (
    SimulatorPositionError,
    SimulatorPositionStore,
)
from src.simulator.runner import SimulatorRunner
from src.simulator.state import (
    SimulatorSettingsUpdate,
    SimulatorStateService,
)


def _dataset(root: Path) -> None:
    entries = []
    for number in range(2):
        bundle_id = f"demo-{number}"
        directory = root / "groups" / bundle_id
        directory.mkdir(parents=True)
        images = [f"frame_{index:02d}.png" for index in range(12)]
        for name in images:
            (directory / name).write_bytes(b"\x89PNG\r\n\x1a\n" + bundle_id.encode())
        (directory / "request.json").write_text(
            json.dumps(
                {
                    "inspection_id": bundle_id,
                    "images": images,
                    "metadata": [
                        {
                            "view_index": index,
                            "angle_direction": "top",
                            "verticality_angle": 0,
                            "horizontality_angle": index,
                        }
                        for index in range(12)
                    ],
                }
            ),
            encoding="utf-8",
        )
        entries.append(
            {
                "inspection_id": bundle_id,
                "path": f"groups/{bundle_id}",
                "frame_count": 12,
                "default_playback": True,
            }
        )
    (root / "index.json").write_text(json.dumps(entries), encoding="utf-8")
    with (root / "demo-virtual-brix.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, ["demo_bundle_id", "virtual_brix"])
        writer.writeheader()
        writer.writerows(
            [
                {"demo_bundle_id": "demo-0", "virtual_brix": "13.9"},
                {"demo_bundle_id": "demo-1", "virtual_brix": "14.0"},
            ]
        )


def test_dataset_and_position_contract() -> None:
    with TemporaryDirectory(prefix="cqc-simulator-", dir=Path.cwd()) as temporary:
        root = Path(temporary)
        _dataset(root)
        dataset = SimulatorDataset(root, 24 * 1024 * 1024)
        first = dataset.load(0)
        second = dataset.load(1)
        assert len(dataset) == 2
        assert len(first.images) == 12
        assert first.images[0][0] == "frame_00.png"
        assert json.loads(first.metadata_json)[11]["view_index"] == 11
        assert (first.virtual_brix, second.virtual_brix) == ("13.9", "14.0")
        assert dataset.bundle_id(2) == "demo-0"
        store = SimulatorPositionStore(root / "state" / "position.json", dataset)
        assert store.load() == 0
        store.save(3)
        assert store.load() == 3
        assert (
            SimulatorPositionStore(
                store.path, SimulatorDataset(root, 24 * 1024 * 1024)
            ).load()
            == 3
        )
        assert not list((root / "state").glob("tmp*"))
        store.path.write_text("{bad", encoding="utf-8")
        with pytest.raises(SimulatorPositionError):
            store.load()
        (root / "groups" / "demo-0" / "frame_00.png").unlink()
        with pytest.raises(SimulatorDatasetError):
            dataset.load(0)


@pytest.mark.parametrize("concurrency", [1, 2, 4])
def test_runner_schedules_and_bounds_inflight(concurrency: int) -> None:
    async def exercise(root: Path) -> None:
        _dataset(root)
        state = SimulatorStateService()
        state.update_state(
            SimulatorSettingsUpdate(
                expectedRevision=0,
                running=True,
                concurrency=concurrency,
                faults=["INFERENCE_ERROR"],
                scope="NEXT",
            )
        )
        seen: list[tuple[float, str, str]] = []
        in_flight = 0
        peak = 0
        reached = asyncio.Event()

        async def respond(request: httpx.Request) -> httpx.Response:
            nonlocal in_flight, peak
            in_flight += 1
            peak = max(peak, in_flight)
            body = await request.aread()
            marker = "demo-0" if b"demo-0" in body else "demo-1"
            seen.append(
                (
                    monotonic(),
                    request.headers["x-cqc-simulator-faults"],
                    marker,
                )
            )
            if len(seen) >= 20:
                reached.set()
            await asyncio.sleep(0.025)
            in_flight -= 1
            return httpx.Response(200, json={"inspection_id": "ok"})

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            runner = SimulatorRunner(
                dataset_root=root,
                position_path=root / "state" / "position.json",
                backend_url="http://backend",
                state=state,
                max_bytes=24 * 1024 * 1024,
                interval_ms=10,
                fault_token="test-token",
                client=client,
            )
            prepared = runner.prepare()
            runner.start(prepared)
            runner.start(prepared)
            await asyncio.wait_for(reached.wait(), timeout=5)
            await runner.stop()
            assert not runner.active
            assert not runner.failed
            assert 1 <= peak <= concurrency
            if concurrency > 1:
                assert peak > 1
            assert len(seen) >= 20
            assert sum(bool(fault) for _, fault, _ in seen) == 1
            assert state.get_state().revision == 2
            assert state.get_state().faults == ()
            assert all(
                seen[index][0] <= seen[index + 1][0] for index in range(len(seen) - 1)
            )
            store = SimulatorPositionStore(
                root / "state" / "position.json", prepared[0]
            )
            assert store.load() == len(seen)
            assert [marker for _, _, marker in seen[:4]] == [
                "demo-0",
                "demo-1",
                "demo-0",
                "demo-1",
            ]

    with TemporaryDirectory(prefix="cqc-simulator-", dir=Path.cwd()) as temporary:
        asyncio.run(exercise(Path(temporary)))


def test_runner_failure_stops_runtime_state() -> None:
    async def exercise(root: Path) -> None:
        _dataset(root)
        state = SimulatorStateService()
        state.update_state(SimulatorSettingsUpdate(expectedRevision=0, running=True))
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _: httpx.Response(500))
        ) as client:
            runner = SimulatorRunner(
                dataset_root=root,
                position_path=root / "position.json",
                backend_url="http://backend",
                state=state,
                max_bytes=24 * 1024 * 1024,
                interval_ms=1,
                fault_token="test-token",
                client=client,
            )
            runner.start(runner.prepare())
            await asyncio.wait_for(runner._task, timeout=5)
            assert runner.failed
            assert not state.get_state().running
            assert state.get_state().revision == 2
            assert not (root / "position.json").exists()

    with TemporaryDirectory(prefix="cqc-simulator-", dir=Path.cwd()) as temporary:
        asyncio.run(exercise(Path(temporary)))
