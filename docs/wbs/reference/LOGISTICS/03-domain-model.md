# MongoDB 도메인 모델

## 공통 규칙

- 모든 문서: `_id`, `createdAt`, `updatedAt`
- 위치: GeoJSON `Point`, 좌표는 `[경도, 위도]`
- 금액: 정수 원화 `priceWon`
- 중량: 정수 kg
- 낙찰·배차 생성은 중복 요청에도 한 번만 실행되도록 `idempotencyKey` 사용

## 핵심 컬렉션

### `cqc_results`

```json
{
  "cqcId": "CQC-20260917-001",
  "farmId": "farm-001",
  "crop": "apple",
  "variety": "fuji",
  "qualityGrade": "SPECIAL",
  "confidence": 0.94,
  "quantityKg": 500,
  "rawPayload": {}
}
```

### `lots`

```json
{
  "lotId": "lot-001",
  "cqcId": "CQC-20260917-001",
  "sellerId": "farm-001",
  "origin": { "type": "Point", "coordinates": [127.017, 36.806] },
  "reservePriceWon": 1200000,
  "suggestedPriceWon": 1150000,
  "auctionStatus": "OPEN",
  "closesAt": "2026-09-17T09:10:00Z"
}
```

### `bids`

```json
{
  "bidId": "bid-001",
  "lotId": "lot-001",
  "buyerId": "buyer-001",
  "priceWon": 1250000,
  "destination": { "type": "Point", "coordinates": [127.028, 37.498] },
  "accepted": true,
  "placedAt": "2026-09-17T09:05:00Z"
}
```

### `orders`

```json
{
  "orderId": "order-001",
  "lotId": "lot-001",
  "sellerId": "farm-001",
  "buyerId": "buyer-001",
  "quantityKg": 500,
  "priceWon": 1250000,
  "status": "ASSIGNED",
  "fleetId": "fleet-001",
  "routeId": "route-001"
}
```

### `fleets`

```json
{
  "fleetId": "fleet-001",
  "name": "CQC Truck 01",
  "capacityKg": 2000,
  "currentLoadKg": 500,
  "location": { "type": "Point", "coordinates": [127.01, 36.81] },
  "status": "TO_PICKUP",
  "lastPositionAt": "2026-09-17T09:06:00Z"
}
```

### `routes`

```json
{
  "routeId": "route-001",
  "fleetId": "fleet-001",
  "version": 3,
  "status": "ACTIVE",
  "stops": [
    { "sequence": 1, "type": "PICKUP", "orderId": "order-001", "location": {}, "status": "PENDING" },
    { "sequence": 2, "type": "DROPOFF", "orderId": "order-001", "location": {}, "status": "PENDING" }
  ],
  "distanceKm": 82.4,
  "estimatedMinutes": 95
}
```

### `events`

감사·디버깅·알림 표시용 append-only 문서다.

```json
{
  "eventId": "evt-001",
  "type": "FLEET_ASSIGNED",
  "entityType": "order",
  "entityId": "order-001",
  "correlationId": "flow-001",
  "payload": {},
  "occurredAt": "2026-09-17T09:06:00Z"
}
```

## 필수 인덱스

- `fleets.location`: `2dsphere`
- `lots.origin`: `2dsphere`
- `bids`: `{ lotId: 1, priceWon: -1, placedAt: 1 }`
- `orders`: `{ fleetId: 1, status: 1 }`
- `routes`: `{ fleetId: 1, status: 1 }`
- `events`: `{ correlationId: 1, occurredAt: 1 }`
- 외부 중복 방지 키: unique index

## 배차 점수 MVP

후보 조건:

- `status`가 `IDLE` 또는 운행 중 추가 배차 가능 상태
- `capacityKg - currentLoadKg >= order.quantityKg`
- 기존 노선에 신규 픽업·하차를 넣어도 하차가 픽업보다 뒤에 위치

유휴 후보를 우선하며 현재 위치에서 픽업까지의 거리로 선택한다. 유휴 후보가 없으면 운행 후보를 거리 기준으로 비교하고 아래의 고정 삽입 규칙을 적용한다. 지연·적재율 가중 점수와 모든 삽입 위치 탐색은 사용하지 않는다.

