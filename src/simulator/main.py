"""Backend와 독립 실행되는 Simulator HTTP 애플리케이션."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .config import SimulatorSettings
from .dataset import SimulatorDatasetError
from .position import SimulatorPositionError
from .runner import SimulatorRunner
from .schemas import SimulatorSettingsUpdate, SimulatorStatus
from .state import (
    RevisionMismatchError,
    SimulatorStateService,
)


def create_app(
    settings: SimulatorSettings, *, inspection_client: httpx.AsyncClient | None = None
) -> FastAPI:
    """상태·runner·내부 제어 API를 한 Simulator 프로세스에 묶는다."""

    state = SimulatorStateService()
    runner = SimulatorRunner(
        dataset_root=settings.simulator_dataset_root,
        brix_csv_path=settings.simulator_brix_csv_path,
        position_path=settings.simulator_position_path,
        backend_url=settings.simulator_backend_url,
        state=state,
        max_bytes=settings.simulator_max_request_bytes,
        interval_ms=settings.simulator_interval_ms,
        fault_token=settings.simulator_fault_token,
        client=inspection_client,
    )
    control_lock = asyncio.Lock()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            await runner.shutdown()

    app = FastAPI(title="CQC Simulator", lifespan=lifespan)
    app.state.simulator_state_service = state
    app.state.simulator_runner = runner

    def status() -> SimulatorStatus:
        current = state.get_state()
        return SimulatorStatus(
            revision=current.revision,
            running=current.running,
            concurrency=current.concurrency,
            faults=list(current.faults),
            scope=current.scope,
            status="error"
            if runner.failed
            else "healthy"
            if runner.active
            else "stopped",
            lastSeenAt=runner.last_seen_ms,
        )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/state", response_model=SimulatorStatus)
    async def get_state() -> SimulatorStatus:
        return status()

    @app.put("/state", response_model=SimulatorStatus)
    async def update_state(
        update: SimulatorSettingsUpdate,
    ) -> SimulatorStatus | JSONResponse:
        async with control_lock:
            if update.expected_revision != state.get_state().revision:
                return JSONResponse(
                    status_code=409, content={"code": "REVISION_CONFLICT"}
                )
            prepared = None
            if update.running is True and not runner.active:
                try:
                    prepared = await asyncio.to_thread(runner.prepare)
                except (
                    OSError,
                    ValueError,
                    SimulatorDatasetError,
                    SimulatorPositionError,
                ):
                    return JSONResponse(
                        status_code=503,
                        content={"code": "SIMULATOR_DATASET_UNAVAILABLE"},
                    )
            try:
                state.update_state(update)
            except RevisionMismatchError:
                return JSONResponse(
                    status_code=409, content={"code": "REVISION_CONFLICT"}
                )
            if prepared is not None:
                runner.start(prepared)
            if update.running is False and runner.active:
                await runner.stop()
            return status()

    return app


def main() -> None:
    """`python -m src.simulator.main`으로 독립 서버를 실행한다."""

    settings = SimulatorSettings()
    uvicorn.run(
        create_app(settings),
        host=settings.simulator_bind_host,
        port=settings.simulator_bind_port,
    )


if __name__ == "__main__":
    main()
