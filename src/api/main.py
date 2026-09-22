"""FastAPI application entrypoint for the CQC Backend."""

from __future__ import annotations

import uvicorn
from fastapi import FastAPI

from .core.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the Backend application with explicitly injectable settings."""

    runtime_settings = settings or get_settings()
    application = FastAPI(title=runtime_settings.app_name)
    application.state.settings = runtime_settings

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
    """Run the Backend with its configured host and port."""

    settings = get_settings()
    uvicorn.run(
        app,
        host=settings.app_host,
        port=settings.app_port,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
