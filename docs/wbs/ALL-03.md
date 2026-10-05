# ALL-03 전체 통합 현황

- WBS 코드: `ALL-03` (전체 흐름 1차 통합, 예정 10-08)
- 기준: dev `b820b5d` (2026-10-05, PR #91까지 병합, 14:19 서버 배포). 서버컴 확인은 같은 날 13~14시, 읽기 전용(설정 변경 없음)
- 역할: **프로젝트 작업 현황의 단일 원본.** 다른 문서에는 현황을 따로 적지 않고 이 문서를 링크한다. 파트별 상세는 각 WBS 문서(DM-xx, FE-xx, BE-xx, MO-xx)를 따른다.
- 파트 간 요청·결과·결정은 10-01부터 Git Issue로 주고받는다(#39). 남은 일은 이슈 번호로 적는다.
- WBS의 ID·담당·일정은 바꾸지 않는다.

## 1. 자동 시험

| 대상 | 결과 (2026-10-05, dev `dee8c54`) |
|---|---|
| Python (`tests/api`, `tests/simulator`, `tests/ci`, `tests/test_service_logging.py`, Jenkins와 같은 범위) | 346 통과, 6 건너뜀(MySQL 실DB 등 조건부, `dee8c54` 기준. #91은 웹만 변경) |
| 웹 (`cqc-logistics-platform/apps/web`) | `npm test` 48 통과(`b820b5d`, FE #55·#53 후속 작업본은 50), `tsc` 통과, `next build` 성공, ESLint 오류 0·경고 5(기존) |
| 물류 API (`cqc-logistics-platform/apps/api`) | 12 통과 |
| Jenkins (MO-07, #69) | Python·웹 시험 통과 후 빌드·배포. 10-02 #89 정상 배포 성공(Python 295·웹 48), 빌드 실패 주입 시 기존 7개 컨테이너 유지, 상태 확인 실패 주입(#90) 시 이전 이미지로 자동 복구 확인 |

## 2. 서버컴 1차 통합 확인 (10-05 13시)

| 구간 | 결과 |
|---|---|
| Simulator → Backend | Simulator `healthy`(검사 전송 중), 라인 속도 2000ms·순차 1 |
| Backend → Inference | Inference `healthy`, 판정 정상 |
| Backend → MySQL | MySQL `healthy`, 이력 조회 정상(누적 2만 건, 86,400건 순환) |
| Backend → 웹(관제) | 웹 3100 `서버 관제`(실제 Backend), 처리 중 사과 12장·재검사·오류 목록·처리량 추이 표시 |
| Jenkins → 배포 | 14:19 배포 완료(#88~#91, 컨테이너 교체 공백 40초). 그 전에는 10-02 17:33 이후 버전이 그대로였다: 서버가 10-02 17:33에 꺼져 #88(17:39 병합)이 빌드되지 않았고, 10-05 12:50쯤 다시 켠 뒤의 빌드는 **웹 시험 실패**로 배포를 건너뛰었다(MO-07 실패 시 기존 유지). #90이 공개 계약 JSON에 필수 필드를 추가했는데 FE 참조 응답·생성기는 그대로라, 웹 시험 `fault image reference response validates against the Backend-published OpenAPI`가 실패했다. #91(MO)이 고쳐 배포됐다 |

- 10-05 배포 전(12:54~14:19) 시간 초과는 13:00~13:20(서버 기동·실패한 빌드)과 14:10~14:20(#91 빌드·배포)에 몰렸다. #87(제한시간 = 라인 속도)은 14:19부터 적용돼 다시 측정한다.
- 10-02 분석: 500ms 기한에서 하루 13,119건 중 534건(4.1%)이 시간 초과. 조용한 시간 0%, Jenkins 빌드 중 8.8%, 그 밖 2.9%. 같은 CPU에서 빌드·시험이 돌 때 몰린다([문제 해결 사례 13](../최종발표/개발%20중%20문제%20해결%20사례.md)).

## 3. 파트별 현황

| 파트 | dev에 반영된 범위 | 남은 핵심 |
|---|---|---|
| DM (조현재) | DM-01~08. `separate`·12장 모델, Inference HTTP API, 시연 묶음 996개·가상 당도 14°Brix 구간. v2 보정 패키지 `cqc-apple-separate12-focal-v2-cal-20260930`(임계값 품종 0.50·품질 0.60, 재검사 23.7%→16.4%). 서버컴 실제 사진 추론 내부 p95 309ms. 입력 간격 2000ms(10-01 재측정 초당 0.50건). 요구사항·결정 기록·QA를 10-05 결정(#55·#56·#87)에 맞춤 | DM-09 최종 Test·모델 카드(#75), 수용 기준 재합의 기록(#65), 10-08 발표 시연 캡처(#64) |
| FE (강성민, FE-01~10 작업은 조현재) | 실제 Backend 관제(API 모드), 처리 중 사과 12장(마지막 사과 유지, #84), 조회 시작 기준 1초(#85), 재검사·오류 사과 목록, Chart.js 처리량 추이, 라인 속도 1·2·3초, 이력·통계·CSV, 물류 목업 결제 단계 | `recentCompletedJobs` 표시와 검수 이미지 창(#53·#55, 작업본 PR 예정), 8시간 관제(#73), 화면 동결(#74) |
| BE (홍준희) | BE-01~09. 검사·관제·이력·통계·CSV·검수 API, DB 장애 시 선별 지속(LKG)·이력 순환, 처리 중 사과 축소본·완료 후 3초 유예·`recentCompletedJobs`(#53·#88), 연결 실패 분류(#67·KI-3 해결), **추론 제한시간 = 라인 속도**(#87·#89), **저신뢰 재검사 이미지 보관**(#55·#90, 오류 100·저신뢰 200장) | 연속 요청·오류·CSV 통합시험(#66), API·DB 계약 동결(#68), snapshot 경량화 문의(#53 댓글) |
| MO (홍유나) | MO-01~07. Compose 7개(품질 4·물류 3), healthcheck·기동 순서, 볼륨, 서비스별 `error.log` 10MiB×5 순환(#57), Jenkins 시험 단계·실패 시 이전 버전 복구(#69, PR #78·#81·#82·#86) | 위치 복구·로그 순환·장애 시험(#70), 수용시험 자동화(#71), 버전 태그·복구 절차 동결(#72) |
| 물류 | LOGISTICS-01~06: 출품·입찰·배차·배송 API와 화면 | MVP 제외(10-01, #48). 브라우저 가상 물류로 확장 시연만 유지. 상세는 [LOGISTICS](LOGISTICS.md) |
| 발표 | `docs/최종발표/` 초안 HTML 36쪽·PDF·대본, 문제 해결 사례 13건, `docs/중간발표/10월 8일/` 변경 표시 사본·시연 대본 | 시연 캡처, 10월 8일 사본 PDF(#64) |

## 4. 관제 API 계약 대비 Backend 구현

| FE 계약 (`docs/contracts/quality-operations.openapi.json`) | Backend |
|---|---|
| `GET /snapshot`, `/inspections`, `/inspections.csv`, `/statistics`, `/statistics.csv` | 구현 (BE-05). snapshot `state.recentCompletedJobs` 추가(#88) |
| `GET·DELETE /fault-images`, `GET /previews/{id}` | 구현 (BE-06). `category`·`decisionReason`·신뢰도·적용 기준값, `?category`·`?inspectionId` 조회, 최대 300장(#90) |
| `PUT /simulator` | 구현 (BE-07) |
| `PATCH /inspections/{id}/review` | 구현 (BE-07) |

계약 JSON은 FE 생성기(`apps/web/scripts/quality-openapi.cjs`)와 내용이 같다(10-05 확인).

## 5. MLOps 세부

| 작업 | 상태 | 확인한 범위 | 다음 확인 |
|---|---|---|---|
| MO-01~04 | 완료 | 규칙, Compose, Jenkins 파이프라인, Dockerfile·`/health`·기동 순서 | - |
| MO-05 | 완료 | MySQL·장애 이미지·Simulator 위치·로그 볼륨, `.env`·Credentials, 모델 패키지 Git 관리(10-01) | - |
| MO-06 | 완료 | 서버컴 합성 입력·실제 사진 측정(DM-08) | - |
| MO-07 | 완료 (#69) | Python·웹 시험 단계, 배포 전 복구 정보 저장, 빌드 실패 시 기존 유지, 상태 확인 실패 시 이전 이미지 복구(실서버 실패 주입 확인) | - |
| MO-08~10 | 진행 전 | - | #70·#71·#72 |

## 6. 동결까지 핵심 경로

```text
#87 시간 초과 재측정 → FE 검수 이미지·recentCompletedJobs 반영 → ALL-03 1차 통합 (10-08)
→ ALL-04 정상 100건·장애 5종 수용시험 (10-12, #65) → ALL-05 기능 동결 (10-13, #76) → ALL-06 리허설·main 표시
```

시연·수용시험 중에는 dev 푸시를 하지 않는다. 같은 서버컴에서 Jenkins 빌드가 돌면 시간 초과가 늘어난다.

## 7. 문서 위치

| 내용 | 문서 |
|---|---|
| 일정·담당 원본 | [WBS](WBS.md) |
| 문서 안내 | [README](README.md) |
| 09-23 독립 실행 점검 기록 | [ALL-02](ALL-02.md) |
| 파트 간 요청 | [파트별 협업 요청](협업공지/파트별-협업-요청.md) |
| 발표용 문제 해결 사례 | [개발 중 문제 해결 사례](../최종발표/개발%20중%20문제%20해결%20사례.md) |
| 확정 범위 QA (ALL-04 사전 점검) | [QA 테스트 케이스](reference/ALL/qa-test-cases.md) |
| 기획·요구사항·결정 | [기획서](../project-plan.md), [요구사항](../planning/requirements.md), [결정 기록](../planning/decision-log.md) |
