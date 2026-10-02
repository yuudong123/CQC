"""CQC 백엔드 FastAPI 애플리케이션 진입점."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from src.logging_config import configure_service_logging

from .clients.inference import HttpInferenceClient, MockInferenceClient
from .clients.simulator import SimulatorClient
from .control.virtual_control import MockVirtualControl
from .core.config import Settings, get_settings
from .db.session import create_db_engine, create_session_factory
from .repositories import BinMappingRepository, InspectionPersistence
from .repositories.inspections import InspectionReviewRepository
from .repositories.quality_history import QualityHistoryRepository
from .repositories.quality_statistics import QualityStatisticsRepository
from .routers.inspections import router as inspections_router
from .routers.quality_fault_images import router as quality_fault_images_router
from .routers.quality_history import router as quality_history_router
from .routers.quality_live_images import router as quality_live_images_router
from .routers.quality_operations import router as quality_operations_router
from .routers.quality_review import router as quality_review_router
from .routers.quality_simulator import router as quality_simulator_router
from .services.fault_image_storage import FaultImageStorage
from .services.inspections import InspectionService
from .services.late_results import LateResultManager
from .services.live_inspections import LiveInspectionStore
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
    fault_image_storage = (
        FaultImageStorage(
            runtime_settings.fault_image_storage_root,
            limit=runtime_settings.fault_image_limit,
        )
        if runtime_settings.fault_image_storage_root is not None
        else None
    )
    live_inspections = LiveInspectionStore(
        limit=runtime_settings.live_preview_limit,
        max_age_seconds=runtime_settings.live_preview_max_age_seconds,
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
            InspectionPersistence(
                session_factory,
                history_limit=runtime_settings.inspection_history_limit,
                history_delete_batch=runtime_settings.inspection_history_delete_batch,
            )
            if session_factory is not None
            else None
        ),
        fault_image_storage=fault_image_storage,
        live_inspections=live_inspections,
    )
    simulator_client = (
        SimulatorClient(
            runtime_settings.simulator_internal_url,
            timeout_ms=runtime_settings.simulator_internal_timeout_ms,
            state_timeout_ms=runtime_settings.simulator_state_timeout_ms,
        )
        if runtime_settings.simulator_internal_url
        else None
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            live_inspections.clear()
            await runtime_inspection_service.shutdown()
            if simulator_client is not None:
                await simulator_client.close()
            if isinstance(inference_client, HttpInferenceClient):
                await inference_client.close()
            if db_engine is not None:
                db_engine.dispose()

    application = FastAPI(title=runtime_settings.app_name, lifespan=lifespan)
    application.state.settings = runtime_settings
    application.state.inspection_service = runtime_inspection_service
    application.state.fault_image_storage = fault_image_storage
    application.state.live_inspections = live_inspections
    application.state.simulator_fault_token = runtime_settings.simulator_fault_token
    application.state.simulator_client = simulator_client
    application.state.inference_client = inference_client
    application.state.quality_history_repository = (
        QualityHistoryRepository(session_factory)
        if session_factory is not None
        else None
    )
    application.state.inspection_review_repository = (
        InspectionReviewRepository(session_factory)
        if session_factory is not None
        else None
    )
    application.state.quality_operations_service = (
        QualityOperationsService(
            application.state.quality_history_repository,
            QualityStatisticsRepository(session_factory),
            fault_image_storage,
            live_inspections,
        )
        if session_factory is not None
        else None
    )
    application.include_router(inspections_router)
    application.include_router(quality_history_router)
    application.include_router(quality_live_images_router)
    application.include_router(quality_fault_images_router)
    application.include_router(quality_operations_router)
    application.include_router(quality_simulator_router)
    application.include_router(quality_review_router)

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

    configure_service_logging()
    settings = get_settings()
    uvicorn.run(
        app,
        host=settings.app_host,
        port=settings.app_port,
        log_config=None,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
