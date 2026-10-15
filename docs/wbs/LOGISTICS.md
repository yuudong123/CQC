# LOGISTICS 판매·물류 시연 플랫폼

- 작업 코드: `LOGISTICS-01~06` (WBS 원본에는 없는 추가 범위)
- 코드 위치: `cqc-logistics-platform/apps/api`(FastAPI·MongoDB), `cqc-logistics-platform/apps/web`(Next.js, 품질 관제와 공용)
- MVP 포함 여부: **제외** (2026-10-01 결정, [#48](https://github.com/yuudong123/CQC/issues/48)). 확장 방향 시연(브라우저 가상 물류)으로 유지
- 현재 현황은 [ALL-03](ALL-03.md)을 따른다.

## 1. 흐름과 경계

```text
CQC 판정 → 농가 출품 → 구매자 입찰 → 낙찰 → 차량 자동배차 → 다중 경유 배송 → 완료/대체배차
```

- 구현: 경매, 낙찰, 적재량 기반 차량 선택, 경유지 추가, 상·하차 확인, 고장 시 대체배차, 관제 화면
- 연동: CQC 결과는 HTTP 이벤트 또는 데모 데이터로 받는다. FE-10은 정상 선별 결과를 브라우저 탭에서 출품·입찰·배차까지 자동으로 보낸다
- 시뮬레이션: 차량 GPS 이동, 운임, 경로, 알림
- 제외: 실제 차량 제어, 실제 결제, 실제 도매시장 데이터, 자율주행 안전 판단
- 발표 표현: 자율주행 차량을 직접 제어하는 시스템이 아니라 **화물차를 배차하고 배송 상태를 관제하는 플랫폼**

## 2. 기술 구성

| 영역 | 선택 | 이유 |
|---|---|---|
| Web | Next.js + TypeScript | 품질 관제·입찰·차량 관제를 한 프로젝트에서 구현 |
| API | FastAPI + Python | 기존 CQC Python 코드와 연결이 쉬움 |
| DB | MongoDB | GeoJSON, 경유지 배열, CQC JSON 저장 |
| 실시간 | WebSocket | 경매 호가와 주요 상태 이벤트 |
| 차량 위치 | 2초 Polling | 발표용으로 단순·안정 |
| 지도 | Google Maps JavaScript API | 차량·농가·구매처 좌표와 경로 표시 |
| 실행 | 루트 `compose.yaml` | `logistics-mongodb`, `logistics-api`, `logistics-web` |

## 3. 구현 결과

| 작업 | 결과 |
|---|---|
| LOGISTICS-01 | 제품 범위·사용자 흐름·도메인·API 계약 정의 |
| LOGISTICS-02 | 경매·자동배차·배송 API. 용량·거리 기반 배차, 유휴 차량이 없으면 운행 차량의 첫 미완료 하차 앞에 신규 픽업·하차 삽입 |
| LOGISTICS-03 | 입찰·관리자·차량 관제 화면(`/market`, `/control`) |
| LOGISTICS-04 | Docker 실행 환경, 발표 시나리오, seed reset·장애·알림 패널 |
| LOGISTICS-05~06 | 루트 Compose·Jenkins 배포 연결, 배포 호스트 주소(`192.168.133.106`) 설정 |

- 차량 위치 단계 이동, 상차·하차 확인 게이트, 배송 완료 상태 전이, 고장 차량 격리·기존 노선 취소·대체배차를 구현·검증했다
- 자동 시험: 물류 API 12개 통과 (2026-09-29)
- 남은 것: 시연 목업 유지·점검. Backend 기반 출품 연결은 MVP 밖이라 선택 과제

## 4. 배포

- Compose 서비스: `logistics-mongodb`(외부 포트 없음), `logistics-api`(8100), `logistics-web`(3100)
- Jenkins는 `LOGISTICS_PUBLIC_WEB_ORIGIN`, `LOGISTICS_PUBLIC_API_URL`을 Web 빌드에 넣고, 지도 키는 Credentials `google-maps-api-key`로 넣는다
- 로컬 실행 방법은 `apps/api/app/main.py`, `apps/web/next.config.ts` 상단 주석에 있다

## 5. 상세 명세

| 순서 | 문서 |
|---|---|
| 1 | [제품 범위](reference/LOGISTICS/01-product-scope.md) |
| 2 | [사용자 흐름](reference/LOGISTICS/02-user-flows.md) |
| 3 | [도메인 모델](reference/LOGISTICS/03-domain-model.md) |
| 4 | [API 계약](reference/LOGISTICS/04-api-contract.md) |
| 5 | [아키텍처](reference/LOGISTICS/05-architecture.md) |
| 6 | [작업 순서와 단계별 결과](reference/LOGISTICS/06-build-order.md) |
| 7 | [시연 시나리오](reference/LOGISTICS/07-demo-scenario.md) |
| 8 | [공통 Compose·Jenkins](reference/LOGISTICS/08-common-compose-jenkins.md) |
| - | [QC·물류 연결 기준](reference/ALL/qc-logistics-handoff.md) |
