"""CQC 물류 API: 출품·입찰(WebSocket)·낙찰·자동배차·배송·고장 대체배차.

로컬 실행 (apps/api에서):
    python -m venv .venv && .venv\\Scripts\\Activate.ps1
    pip install -e ".[dev]"
    uvicorn app.main:app --reload     # 문서 /docs, 상태 /api/v1/health
    pytest                            # 자동 시험

배포는 저장소 루트 compose.yaml의 logistics-mongodb·logistics-api(8100)·logistics-web(3100)로 하며
Jenkins가 함께 빌드·기동한다. MongoDB는 외부 포트를 열지 않는다. 범위·명세·작업 기록은
docs/wbs/LOGISTICS.md와 docs/wbs/reference/LOGISTICS/를 따른다.
"""

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
