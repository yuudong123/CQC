# CQC Logistics Platform

CQC의 농산물 품질 판정 결과를 B2B 거래와 자동배차로 연결하는 시연용 플랫폼이다.

## 한 줄 흐름

```text
CQC 판정 → 농가 출품 → 구매자 입찰 → 낙찰 → 차량 자동배차 → 다중 경유 배송 → 완료/대체배차
```

## 이번 MVP의 경계

- 구현: 경매, 낙찰, 적재량 기반 차량 선택, 경유지 추가, 경로 재계산, 상·하차 확인, 차량 고장 시 대체배차, 관제 화면
- 연동: 기존 CQC 결과는 HTTP 이벤트 또는 데모 데이터로 수신
- 시뮬레이션: 차량 GPS 이동, 운임, 경로, 알림
- 제외: 실제 차량 제어, 실제 결제, 실제 도매시장 크롤링, 실제 자율주행 안전 판단

발표에서는 **자율주행 차량을 직접 제어하는 시스템**이 아니라 **자율주행 화물차를 배차하고 배송 상태를 관제하는 플랫폼**이라고 표현한다.

## 추천 기술 구성

| 영역 | 선택 | 이유 |
|---|---|---|
| Web | Next.js + TypeScript | 사용자 화면과 관제 화면을 한 프로젝트에서 구현 |
| API | FastAPI + Python | 기존 CQC Python 코드와 연결이 쉬움 |
| DB | MongoDB | GeoJSON, 경유지 배열, CQC JSON 저장에 적합 |
| 실시간 | WebSocket | 경매 호가와 주요 상태 이벤트 |
| 차량 위치 | 2초 Polling | 발표용 구현이 단순하고 안정적 |
| 지도 | Google Maps JavaScript API | 차량·농가·구매처 좌표와 경로를 브라우저에서 시각화 |
| 실행 | Docker Compose | web, api, mongodb를 한 번에 실행 |

## 문서 읽는 순서

1. [`docs/01-product-scope.md`](docs/01-product-scope.md)
2. [`docs/02-user-flows.md`](docs/02-user-flows.md)
3. [`docs/03-domain-model.md`](docs/03-domain-model.md)
4. [`docs/04-api-contract.md`](docs/04-api-contract.md)
5. [`docs/05-architecture.md`](docs/05-architecture.md)
6. [`docs/06-build-order.md`](docs/06-build-order.md)
7. [`docs/07-demo-scenario.md`](docs/07-demo-scenario.md)

## 구현 시작 전 확정할 값

- 지도 API 공급자와 키 발급 여부
- 데모 지역과 농가·구매처 좌표
- 경매 종료 조건: 제한시간 또는 관리자 즉시 종료
- 차량 용량 단위: MVP에서는 `kg`로 통일
- 팀원이 맡을 화면/API 범위

## 현재 실행 방법

### 현재 구현 상태

- 완료: CQC 결과 → 출품 → WebSocket 입찰 → 낙찰 주문 → 용량·거리 기반 자동배차
- 완료: 차량 위치 단계 이동, 농가 상차·구매처 하차 확인 게이트, 배송 완료 상태 전이
- 완료: 잔여 적재량이 있는 운행 차량에 신규 주문을 삽입하는 동적 경유지 MVP
- 완료: 고장 차량 격리, 기존 노선 취소, 잔여 경유지 대체배차 MVP
- 완료: `/control` 차량 관제 시뮬레이터 화면
- 완료: 발표용 seed reset과 장애·알림 요약 패널
- 다음: 발표 리허설용 5분 데모 스크립트 마감

### Web

```powershell
cd apps/web
npm install --ignore-scripts
npm run dev
```

브라우저에서 `http://localhost:3000`을 연다.

### API

```powershell
cd apps/api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

API 문서는 `http://localhost:8000/docs`, 상태 확인은 `http://localhost:8000/api/v1/health`다.

## 공통 Docker·Jenkins 배포

물류 서비스는 GPU 서버나 별도 홈 서버에서 실행하지 않는다. 저장소 루트의 `compose.yaml`에서 기존 CQC 서비스와 함께 관리한다.

```powershell
docker compose build logistics-api logistics-web
docker compose up -d logistics-mongodb logistics-api logistics-web
```

- 웹: `http://배포호스트:3100`
- API 문서: `http://배포호스트:8100/docs`
- MongoDB: 외부 포트를 열지 않고 Compose 내부 네트워크에서만 접근
- Jenkins: 루트 `Jenkinsfile`의 Build, Deploy, Verify 단계에서 세 서비스를 함께 처리

배포 호스트 주소가 `localhost`가 아니라면 Jenkins Job 환경변수 `LOGISTICS_PUBLIC_WEB_ORIGIN`, `LOGISTICS_PUBLIC_API_URL`을 실제 주소로 설정한다. 지도 키는 저장소에 넣지 않고 `GOOGLE_MAPS_API_KEY` 환경변수 또는 Jenkins Credentials로 주입한다.
