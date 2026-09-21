from fastapi import APIRouter, HTTPException, Query, Request, status

from app.domain.market import CQCResultCreate, CQCResultRead, LotCreate, LotRead
from app.store import Store

router = APIRouter(tags=["market"])


def get_store(request: Request) -> Store:
    return request.app.state.store


@router.post("/cqc-results", response_model=CQCResultRead, status_code=status.HTTP_201_CREATED)
def receive_cqc_result(payload: CQCResultCreate, request: Request) -> CQCResultRead:
    return CQCResultRead.model_validate(get_store(request).save_cqc_result(payload))


@router.post("/lots", response_model=LotRead, status_code=status.HTTP_201_CREATED)
def create_lot(payload: LotCreate, request: Request) -> LotRead:
    store = get_store(request)
    cqc = store.get_cqc_result(payload.cqcId)
    if cqc is None:
        raise HTTPException(status_code=404, detail="CQC 결과를 찾을 수 없습니다.")
    return LotRead.model_validate(store.create_lot(payload, cqc))


@router.get("/lots", response_model=list[LotRead])
def list_lots(request: Request, auction_status: str | None = Query(default=None)) -> list[LotRead]:
    return [LotRead.model_validate(lot) for lot in get_store(request).list_lots(auction_status)]


@router.post("/lots/{lot_id}/open", response_model=LotRead)
def open_lot(lot_id: str, request: Request) -> LotRead:
    lot = get_store(request).open_lot(lot_id)
    if lot is None:
        raise HTTPException(status_code=409, detail="출품이 없거나 이미 시작된 경매입니다.")
    return LotRead.model_validate(lot)

