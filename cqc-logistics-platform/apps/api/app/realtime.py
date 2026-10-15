from collections import defaultdict

from fastapi import WebSocket


class AuctionHub:
    def __init__(self) -> None:
        self.connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, lot_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections[lot_id].add(websocket)

    def disconnect(self, lot_id: str, websocket: WebSocket) -> None:
        self.connections[lot_id].discard(websocket)
        if not self.connections[lot_id]:
            self.connections.pop(lot_id, None)

    async def broadcast(self, lot_id: str, message: dict[str, object]) -> None:
        stale: list[WebSocket] = []
        for websocket in self.connections.get(lot_id, set()):
            try:
                await websocket.send_json(message)
            except Exception:
                stale.append(websocket)
        for websocket in stale:
            self.disconnect(lot_id, websocket)

