"""선정된 시연 묶음을 500ms 시작 간격으로 검사 API에 보낸다."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import httpx

from .dataset import SimulatorBundle, SimulatorDataset
from .position import SimulatorPositionStore
from .state import SimulatorStateService

logger = logging.getLogger(__name__)


class SimulatorRunner:
    """단일 프로세스 실행 루프와 완료 위치를 관리한다."""

    def __init__(
        self,
        *,
        dataset_root: Path | None,
        brix_csv_path: Path | None = None,
        position_path: Path | None,
        backend_url: str,
        state: SimulatorStateService,
        max_bytes: int,
        interval_ms: int = 500,
        fault_token: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._dataset_root = dataset_root
        self._brix_csv_path = brix_csv_path
        self._position_path = position_path
        self._backend_url = backend_url.rstrip("/")
        self._state = state
        self._max_bytes = max_bytes
        self._interval = interval_ms / 1000
        self._fault_token = fault_token
        self._client = client or httpx.AsyncClient(timeout=30)
        self._owns_client = client is None
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self._failed = False
        self._last_seen_ms: int | None = None

    @property
    def active(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def failed(self) -> bool:
        return self._failed

    @property
    def last_seen_ms(self) -> int | None:
        return self._last_seen_ms

    def prepare(self) -> tuple[SimulatorDataset, SimulatorPositionStore, int]:
        """시작 전에 dataset·위치 파일을 검증해 실패를 제어 응답에 반영한다."""

        if self._dataset_root is None or self._position_path is None:
            raise ValueError("Simulator dataset root와 position path 설정이 필요합니다")
        dataset = SimulatorDataset(
            self._dataset_root, self._max_bytes, self._brix_csv_path
        )
        store = SimulatorPositionStore(self._position_path, dataset)
        position = store.load()
        dataset.load(position)
        return dataset, store, position

    def start(
        self, prepared: tuple[SimulatorDataset, SimulatorPositionStore, int]
    ) -> None:
        if self.active:
            return
        self._stop = asyncio.Event()
        self._failed = False
        self._task = asyncio.create_task(self._run(*prepared), name="simulator-runner")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            await self._task

    async def shutdown(self) -> None:
        await self.stop()
        if self._owns_client:
            await self._client.aclose()

    async def _run(
        self, dataset: SimulatorDataset, store: SimulatorPositionStore, position: int
    ) -> None:
        loop = asyncio.get_running_loop()
        next_due = loop.time()
        next_position = position
        committed = position
        completed: set[int] = set()
        workers: set[asyncio.Task[None]] = set()
        position_lock = asyncio.Lock()

        async def send(sequence: int, bundle: SimulatorBundle) -> None:
            nonlocal committed
            inspection_id = str(uuid4())
            faults = self._state.claim_faults_for_inspection()
            files = [
                ("images", (name, content, mime))
                for name, content, mime in bundle.images
            ]
            try:
                result = await self._client.post(
                    f"{self._backend_url}/v1/inspections",
                    data={
                        "inspection_id": inspection_id,
                        "metadata": bundle.metadata_json,
                        "virtual_brix": bundle.virtual_brix,
                    },
                    files=files,
                    headers={
                        "X-CQC-Simulator-Token": self._fault_token,
                        "X-CQC-Simulator-Faults": ",".join(faults),
                        "X-CQC-Simulator-Bundle-ID": bundle.bundle_id,
                    },
                )
                result.raise_for_status()
            except httpx.HTTPError:
                # 요청 한 건의 실패는 이미 시도한 위치로 기록하고 다음 묶음을 보낸다.
                logger.exception(
                    "Simulator 검사 전송 실패: inspection_id=%s bundle_id=%s",
                    inspection_id,
                    bundle.bundle_id,
                )
            async with position_lock:
                completed.add(sequence)
                while committed in completed:
                    completed.remove(committed)
                    committed += 1
                    await asyncio.to_thread(store.save, committed)
            self._last_seen_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

        try:
            while not self._stop.is_set():
                done = {worker for worker in workers if worker.done()}
                for worker in done:
                    workers.remove(worker)
                    worker.result()
                if len(workers) >= self._state.get_state().concurrency:
                    done, _ = await asyncio.wait(
                        workers, return_when=asyncio.FIRST_COMPLETED
                    )
                    for worker in done:
                        workers.remove(worker)
                        worker.result()
                    continue
                delay = next_due - loop.time()
                if delay > 0:
                    try:
                        await asyncio.wait_for(self._stop.wait(), timeout=delay)
                        break
                    except TimeoutError:
                        pass
                if self._stop.is_set():
                    break
                bundle = await asyncio.to_thread(dataset.load, next_position)
                worker = asyncio.create_task(send(next_position, bundle))
                workers.add(worker)
                next_position += 1
                next_due = max(next_due + self._interval, loop.time() + self._interval)
        except Exception:
            self._failed = True
            logger.exception("Simulator 실행 루프가 중단되었습니다")
        finally:
            if workers:
                results = await asyncio.gather(*workers, return_exceptions=True)
                if any(isinstance(result, BaseException) for result in results):
                    self._failed = True
                    logger.error("Simulator 진행 중 검사 요청이 실패했습니다")
            if self._failed:
                self._state.force_stop()
