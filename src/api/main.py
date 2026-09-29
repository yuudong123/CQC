"""CQC 백엔드 FastAPI 애플리케이션 진입점."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from .clients.inference import HttpInferenceClient, MockInferenceClient
from .control.virtual_control import MockVirtualControl
from .core.config import Settings, get_settings
from .db.session import create_db_engine, create_session_factory
from .repositories import BinMappingRepository, InspectionPersistence
from .repositories.quality_history import QualityHistoryRepository
from .repositories.quality_statistics import QualityStatisticsRepository
from .routers.inspections import router as inspections_router
from .routers.quality_history import router as quality_history_router
from .routers.quality_operations import router as quality_operations_router
from .services.inspections import InspectionService
from .services.late_results import LateResultManager
from .services.quality_operations import QualityOperationsService


def create_app(
    settings: Settings | None = None,
    inspection_service: InspectionService | None = None,
) -> FastAPI:
    """명시적으로 주입할 수 있는 설정으로 백엔드 애플리케이션을 생성한다."""

    runtime_settings = settings or get_settings()
    late_result_manager = LateResultManager(
        hard_timeout_ms=runtime_settings.inference_hard_timeout_ms,
        max_tasks=runtime_settings.max_late_tasks,
    )
    inference_client = (
        (
            HttpInferenceClient(
                runtime_settings.inference_url,
                timeout_ms=runtime_settings.inference_hard_timeout_ms,
            )
            if runtime_settings.inference_client_mode == "http"
            else MockInferenceClient()
        )
        if inspection_service is None
        else None
    )
    db_engine = (
        create_db_engine(runtime_settings)
        if inspection_service is None and runtime_settings.database_url
        else None
    )
    session_factory = (
        create_session_factory(db_engine) if db_engine is not None else None
    )
    runtime_inspection_service = inspection_service or InspectionService(
        inference_client,
        MockVirtualControl(),
        cultivar_confidence_threshold=(runtime_settings.cultivar_confidence_threshold),
        quality_confidence_threshold=runtime_settings.quality_confidence_threshold,
        inference_business_deadline_ms=(
            runtime_settings.inference_business_deadline_ms
        ),
        late_result_manager=late_result_manager,
        bin_mapping_repository=(
            BinMappingRepository(session_factory)
            if session_factory is not None
            else None
        ),
        persistence=(
            InspectionPersistence(session_factory)
            if session_factory is not None
            else None
        ),
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            await runtime_inspection_service.shutdown()
            if isinstance(inference_client, HttpInferenceClient):
                await inference_client.close()
            if db_engine is not None:
                db_engine.dispose()

    application = FastAPI(title=runtime_settings.app_name, lifespan=lifespan)
    application.state.settings = runtime_settings
    application.state.inspection_service = runtime_inspection_service
    application.state.quality_history_repository = (
        QualityHistoryRepository(session_factory)
        if session_factory is not None
        else None
    )
    application.state.quality_operations_service = (
        QualityOperationsService(
            application.state.quality_history_repository,
            QualityStatisticsRepository(session_factory),
        )
        if session_factory is not None
        else None
    )
    application.include_router(inspections_router)
    application.include_router(quality_history_router)
    application.include_router(quality_operations_router)

    @application.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": runtime_settings.app_name,
            "environment": runtime_settings.app_env,
        }

    return application


app = create_app()


def main() -> int:
    """설정된 호스트와 포트로 백엔드를 실행한다."""

    settings = get_settings()
    uvicorn.run(
        app,
        host=settings.app_host,
        port=settings.app_port,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
