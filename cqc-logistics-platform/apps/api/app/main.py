from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.realtime import AuctionHub
from app.routes.auction import router as auction_router
from app.routes.control import router as control_router
from app.routes.delivery import router as delivery_router
from app.routes.dispatch import router as dispatch_router
from app.routes.market import router as market_router
from app.store import MemoryStore, create_store

settings = get_settings()


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    if not hasattr(application.state, "store") or settings.store_mode.lower() == "mongo":
        application.state.store = create_store(settings)
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
if settings.store_mode.lower() == "memory":
    app.state.store = MemoryStore()
app.state.auction_hub = AuctionHub()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(market_router, prefix=settings.api_prefix)
app.include_router(auction_router, prefix=settings.api_prefix)
app.include_router(dispatch_router, prefix=settings.api_prefix)
app.include_router(delivery_router, prefix=settings.api_prefix)
app.include_router(control_router, prefix=settings.api_prefix)


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": settings.app_name, "docs": "/docs"}


@app.get(f"{settings.api_prefix}/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "environment": settings.environment,
        "storage": app.state.store.storage_name,
        "serverTime": datetime.now(UTC).isoformat(),
    }
