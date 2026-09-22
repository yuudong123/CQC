"""늦은 Inference task의 수명과 메모리 진단 결과를 관리한다."""

from __future__ import annotations

import asyncio

from ..schemas.inference import InferenceResponse
from ..schemas.late_results import LateInferenceResult


class LateResultManager:
    """제한된 수의 늦은 task를 hard timeout까지 유지한다."""

    def __init__(self, *, hard_timeout_ms: int, max_tasks: int) -> None:
        if hard_timeout_ms <= 0:
            raise ValueError("Inference hard timeout은 0보다 커야 합니다")
        if max_tasks < 0:
            raise ValueError("late task 최대 개수는 0 이상이어야 합니다")

        self._hard_timeout_seconds = hard_timeout_ms / 1000
        self._max_tasks = max_tasks
        self._watchers: set[asyncio.Task[None]] = set()
        self.results: list[LateInferenceResult] = []
        self.hard_timeout_inspection_ids: list[str] = []
        self.dropped_inspection_ids: list[str] = []

    @property
    def active_count(self) -> int:
        """현재 진단 결과를 기다리는 late task 수를 반환한다."""

        return len(self._watchers)

    def track(
        self,
        *,
        inspection_id: str,
        inference_task: asyncio.Task[InferenceResponse],
        started_at: float,
    ) -> bool:
        """한도 안의 task만 hard timeout까지 추적한다."""

        if self.active_count >= self._max_tasks:
            self.dropped_inspection_ids.append(inspection_id)
            inference_task.cancel()
            inference_task.add_done_callback(self._consume_task_result)
            return False

        elapsed = asyncio.get_running_loop().time() - started_at
        remaining_seconds = self._hard_timeout_seconds - elapsed
        watcher = asyncio.create_task(
            self._collect(
                inspection_id=inspection_id,
                inference_task=inference_task,
                remaining_seconds=remaining_seconds,
            )
        )
        self._watchers.add(watcher)
        watcher.add_done_callback(self._watcher_finished)
        return True

    async def wait_until_idle(self) -> None:
        """현재 등록된 late task의 수집 또는 취소가 끝날 때까지 기다린다."""

        while self._watchers:
            await asyncio.gather(*tuple(self._watchers), return_exceptions=True)

    async def shutdown(self) -> None:
        """서버 종료 시 watcher와 연결된 Inference task를 모두 정리한다."""

        watchers = tuple(self._watchers)
        for watcher in watchers:
            watcher.cancel()
        if watchers:
            await asyncio.gather(*watchers, return_exceptions=True)
        self._watchers.clear()

    async def _collect(
        self,
        *,
        inspection_id: str,
        inference_task: asyncio.Task[InferenceResponse],
        remaining_seconds: float,
    ) -> None:
        try:
            if remaining_seconds <= 0:
                raise TimeoutError
            inference_response = await asyncio.wait_for(
                asyncio.shield(inference_task),
                timeout=remaining_seconds,
            )
        except TimeoutError:
            self.hard_timeout_inspection_ids.append(inspection_id)
            inference_task.cancel()
            await asyncio.gather(inference_task, return_exceptions=True)
        except asyncio.CancelledError:
            inference_task.cancel()
            await asyncio.gather(inference_task, return_exceptions=True)
            raise
        else:
            self.results.append(
                LateInferenceResult(
                    inspection_id=inspection_id,
                    inference_response=inference_response,
                )
            )

    @staticmethod
    def _consume_task_result(task: asyncio.Task[InferenceResponse]) -> None:
        """한도 초과로 취소한 task의 예외가 유실되지 않게 회수한다."""

        if task.cancelled():
            return
        task.exception()

    def _watcher_finished(self, watcher: asyncio.Task[None]) -> None:
        """완료된 watcher를 제거하고 처리되지 않은 예외를 회수한다."""

        self._watchers.discard(watcher)
        if watcher.cancelled():
            return
        watcher.exception()
