from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect, status

from app.domain.market import AuctionCloseRead, BidCreate, BidRead, LotRead
from app.realtime import AuctionHub
from app.store import Store

router = APIRouter(tags=["auction"])


def get_store(request: Request) -> Store:
    return request.app.state.store


def get_hub(request: Request) -> AuctionHub:
    return request.app.state.auction_hub


@router.post("/lots/{lot_id}/bids", response_model=BidRead, status_code=status.HTTP_201_CREATED)
async def place_bid(lot_id: str, payload: BidCreate, request: Request) -> BidRead:
    try:
        bid = get_store(request).place_bid(lot_id, payload)
    except ValueError as error:
        messages = {
            "auction_not_open": "진행 중인 경매가 아닙니다.",
            "below_reserve": "최저 낙찰가보다 낮은 입찰입니다.",
            "not_highest": "현재 최고 입찰가보다 높아야 합니다.",
        }
        raise HTTPException(status_code=409, detail=messages[str(error)]) from error
    bid_read = BidRead.model_validate(bid)
    await get_hub(request).broadcast(
        lot_id,
        {"type": "BID_PLACED", "bid": bid_read.model_dump(mode="json")},
    )
    return bid_read


@router.get("/lots/{lot_id}/bids", response_model=list[BidRead])
def list_bids(lot_id: str, request: Request) -> list[BidRead]:
    if get_store(request).get_lot(lot_id) is None:
        raise HTTPException(status_code=404, detail="출품을 찾을 수 없습니다.")
    return [BidRead.model_validate(bid) for bid in get_store(request).list_bids(lot_id)]


@router.post("/lots/{lot_id}/close", response_model=AuctionCloseRead)
async def close_lot(lot_id: str, request: Request) -> AuctionCloseRead:
    store = get_store(request)
    lot = store.close_lot(lot_id)
    if lot is None:
        raise HTTPException(status_code=409, detail="경매가 없거나 이미 종료되었습니다.")
    bids = store.list_bids(lot_id)
    order = store.create_order(lot, bids[0]) if bids else None
    result = AuctionCloseRead(
        lot=LotRead.model_validate(lot),
        winningBid=BidRead.model_validate(bids[0]) if bids else None,
        order=order,
    )
    await get_hub(request).broadcast(
        lot_id,
        {"type": "AUCTION_CLOSED", **result.model_dump(mode="json")},
    )
    return result


@router.websocket("/ws/auctions/{lot_id}")
async def auction_socket(websocket: WebSocket, lot_id: str) -> None:
    hub = get_hub(websocket)
    if hub is None:
        await websocket.close(code=1011)
        return
    await hub.connect(lot_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        hub.disconnect(lot_id, websocket)
