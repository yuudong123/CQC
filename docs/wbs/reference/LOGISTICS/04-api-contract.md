# API 계약 초안

기본 경로는 `/api/v1`이다. 현재 MVP 오류 응답은 FastAPI의 `detail` 문자열을 사용하며, 운영 단계에서 `code`, `message`, `correlationId`를 확장한다.

## CQC와 출품

| Method | Path | 용도 |
|---|---|---|
| POST | `/cqc-results` | 기존 CQC 판정 결과 수신 |
| POST | `/lots` | 출품 생성 |
| GET | `/lots` | 공개 출품 조회 |
| POST | `/lots/{lotId}/open` | 경매 시작 |

## 입찰과 낙찰

| Method | Path | 용도 |
|---|---|---|
| POST | `/lots/{lotId}/bids` | 입찰 |
| POST | `/lots/{lotId}/close` | 경매 종료·낙찰 |
| GET | `/lots/{lotId}/bids` | 입찰 목록 |
| WS | `/api/v1/ws/auctions/{lotId}` | 최고가·종료 이벤트 |

## 배차와 배송

| Method | Path | 용도 |
|---|---|---|
| POST | `/orders/{orderId}/dispatch` | 자동배차 실행 |
| POST | `/fleets/{fleetId}/simulate-step` | 차량을 다음 경유지 방향으로 이동 |
| POST | `/fleets/{fleetId}/breakdown` | 고장 처리와 긴급 대체배차 |
| POST | `/orders/{orderId}/load-complete` | 농가 상차 확인 |
| POST | `/orders/{orderId}/unload-complete` | 구매처 하차 확인 |
| GET | `/fleets` | 차량 목록과 현재 위치 |
| GET | `/routes/{routeId}` | 노선과 경유지 조회 |
| GET | `/control/overview` | 관제 요약 |

## 차량 위치 Polling

`GET /fleets?updatedAfter=<ISO8601>`를 2초마다 호출한다. 응답에는 서버 시각을 포함하고 다음 호출의 `updatedAfter`로 사용한다.

## 관제 요약·발표 초기화

| Method | Path | 용도 |
|---|---|---|
| GET | `/control/overview` | 차량·주문·노선·장애 알림과 요약 통계 조회 |
| POST | `/control/seed-reset` | 발표용 샘플 경매·주문·차량 상태 복구 |

## 주요 이벤트

- `BID_PLACED`
- `AUCTION_CLOSED`
- `ORDER_MATCHED`
- `FLEET_ASSIGNED`
- `ROUTE_RECALCULATED`
- `FLEET_ARRIVED`
- `LOAD_COMPLETED`
- `UNLOAD_COMPLETED`
- `FLEET_BROKEN_DOWN`
- `REPLACEMENT_ASSIGNED`

## 배송 상태 게이트

- `simulate-step`은 한 번에 최대 20km를 이동시키고, 경유지에 도착하면 차량을 `WAITING_LOAD` 또는 `WAITING_UNLOAD`로 멈춘다.
- 상차 완료 전에는 `load-complete`가 409를 반환한다.
- 하차 완료 전에는 `unload-complete`가 409를 반환한다.
- 하차 완료 시 주문은 `DELIVERED`, 노선은 `COMPLETED`, 차량 적재량은 출고 전 값으로 돌아간다.

## 운행 중 추가 배차

대기 차량이 없고 운행 중인 차량에 잔여 적재 공간이 있으면 같은 `dispatch` API가 해당 노선을 재사용한다. 새 픽업·하차 쌍은 기존 미완료 하차 지점 앞에 삽입되고 `route.version`이 1 증가한다.

## 고장·대체배차

`breakdown`은 기존 차량을 `OUT_OF_SERVICE`로 바꾸고 기존 노선을 `CANCELLED` 처리한다. 남은 경유지와 주문을 적재할 수 있는 `IDLE` 차량 중 가장 가까운 차량에 새 노선을 만들며, 대체 차량이 없으면 고장 상태와 취소 노선만 반환한다.

## 동시성 규칙

- 입찰 접수 시 경매가 `OPEN`인지 서버에서 다시 확인한다.
- 경매 종료와 낙찰 생성은 하나의 원자적 갱신으로 처리한다.
- 차량 적재량 변경은 현재 값 조건을 포함한 원자적 갱신으로 초과 적재를 막는다.
- 노선 수정 시 `version`을 비교해 오래된 요청을 거부한다.
