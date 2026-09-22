"""CQC 백엔드 FastAPI 애플리케이션 진입점."""

from __future__ import annotations

import uvicorn
from fastapi import FastAPI

from .clients.inference import MockInferenceClient
from .control.virtual_control import MockVirtualControl
from .core.config import Settings, get_settings
from .routers.inspections import router as inspections_router
from .services.inspections import InspectionService


def create_app(
    settings: Settings | None = None,
    inspection_service: InspectionService | None = None,
) -> FastAPI:
    """명시적으로 주입할 수 있는 설정으로 백엔드 애플리케이션을 생성한다."""

    runtime_settings = settings or get_settings()
    runtime_inspection_service = inspection_service or InspectionService(
        MockInferenceClient(),
        MockVirtualControl(),
        cultivar_confidence_threshold=(runtime_settings.cultivar_confidence_threshold),
        quality_confidence_threshold=runtime_settings.quality_confidence_threshold,
        inference_business_deadline_ms=(
            runtime_settings.inference_business_deadline_ms
        ),
    )
    application = FastAPI(title=runtime_settings.app_name)
    application.state.settings = runtime_settings
    application.state.inspection_service = runtime_inspection_service
    application.include_router(inspections_router)

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
