# ALL-03 전체 통합 현황

- WBS 코드: `ALL-03` (전체 흐름 1차 통합, 예정 10-08)
- 기준: dev (2026-10-01, PR #27~#33 병합 후). 학원 서버에서 Simulator 자동 재생 확인, 입력 간격 2000ms 배포 후 재측정은 서버 재가동 뒤
- 역할: **프로젝트 작업 현황의 단일 원본.** 다른 문서에는 현황을 따로 적지 않고 이 문서를 링크한다. 파트별 상세는 각 WBS 문서(DM-xx, FE-xx, BE-xx, MO-xx)를 따른다.
- WBS의 ID·담당·일정은 바꾸지 않는다.

## 1. 자동 시험

| 대상 | 결과 (2026-09-29, dev `b0b08dd`) |
|---|---|
| Python (`tests`, `data/sampling/tests`) | 243 통과, 3 건너뜀(MySQL 통합: `CQC_TEST_DATABASE_URL` 지정 시 실행) |
| MySQL 8.4 + `alembic upgrade head` | 두 리비전 적용, MySQL 통합 시험 5개 통과 (09-29 17시 기준) |
| 웹 (`cqc-logistics-platform/apps/web`) | `npm test` 31 통과, `tsc` 통과, `next build` 성공, ESLint 오류 0·경고 5 |
| 물류 API (`cqc-logistics-platform/apps/api`) | 12 통과 |

2026-09-30 추가: 보정 시험 7개(`tests/test_calibration.py`) 통과, 웹 `npm test` 35개 통과(feat/front + 표시 수정).

Jenkins에는 아직 이 시험 단계가 없다. Compose 검사·빌드·기동·health 확인만 한다.

## 2. 파트별 현황

| 파트 | dev에 반영된 범위 | 남은 핵심 |
|---|---|---|
| DM (조현재) | DM-01~09. `separate`·12장 모델, Inference HTTP API, 시연 묶음 996개(12장 869개)·가상 당도 14°Brix 구간. v2 보정 실행 완료(09-30): 품질 T=0.391·ECE 0.259→0.081, **임계값 품종 0.50·품질 0.60 결정**, 패키지 `cqc-apple-separate12-focal-v2-cal-20260930`(가중치 동일, `model.json`만 변경), Compose 임계값 전달. 개발 OOF 기준 재검사 23.7%→16.4%·자동 처리 품질 92.2%→92.9%, 시연 36묶음 재검사 13.9%→8.3%. 배포 후 서버컴 실제 사진 서버 내부 전체 p95 309ms(해제 149·모델 161ms, 동시 처리 1, 500ms 초과 0/36). **Simulator 운영 경로 실측 초당 0.63건·시간 초과 3%** → 입력 간격 2000ms로 조정([PR #33](https://github.com/yuudong123/CQC/pull/33)) | PR #33 병합 후 처리량·시간 초과 재확인. 초당 2건은 현재 구조로 미달(결정 기록 09-30). 독립 holdout 부재는 모델 카드 한계에 명시됨 |
| FE (강성민, FE-01~10 작업은 조현재) | FE-01~10: 품질 관제·이력·통계·장애 관리, 12장 그룹 관제, 브라우저 자동 경매·배차 시연. 09-30 BE-06 개별 장애 이미지 계약 반영, **실제 Backend 연결 확인**(snapshot·이력·필터·통계·CSV·장애 이미지 미리보기/삭제, DB 중단·복구, 장애 이미지 100장 순환), 신뢰도 표시 자리수 수정, 프로덕션 빌드 31.5분·3,600건 연속 관제(heap 중앙값 22~23MB에서 안정, DOM 2,074 고정) | 실제 Simulator 제어·검수 화면 확인(학원 웹 3100은 아직 브라우저 예시 모드), 목표 배포 환경 8시간 시험·실제 브라우저 탭 전환 확인 |
| BE (홍준희) | BE-01~07: 검사 API, 실제 Inference 호출, 500ms 기한·지연 결과, 12-bin migration·13개 seed, 저장·이력·통계·CSV, 장애 이미지(최대 100장). 09-30 PR #30: 독립 Simulator(목록 순환·위치 복구·동시 처리 1·2·4·장애 6종·다음 1건), `PUT /simulator`, 검수 API | 검사 1건 실패 시 Simulator 전체 정지, 지연 결과 DB 저장, 이력 보존 삭제(86,400/8,640, 현재 DB 무한 증가), BE-08 이후 통합. 09-30 통합 점검 요청 4건: DB 중단 시 선별 중단, 처리량 0 표시, 연결 오류 코드, Inference 상태([협업 요청](협업공지/파트별-협업-요청.md)) |
| MO (홍유나) | MO-01~06. Compose 8개 서비스(QC 5·물류 3), healthcheck·기동 순서, MySQL·Mongo Volume, Jenkins Credentials, 서버컴 합성 입력 측정. 09-30 PR #25: Backend 기동 시 `alembic upgrade head`, 장애 이미지 Volume. PR #31·#32: Simulator 이미지·데이터 볼륨·위치 볼륨, 자동 재생, 재생 여부 health·Jenkins 검증([배포 문서](reference/MO/simulator-deployment.md)) | frontend placeholder 교체, Jenkins 테스트 단계, 실패 시 이전 버전 유지(MO-07), MO-08~10 |
| 물류 | LOGISTICS-01~06: 출품·입찰·배차·배송 API와 화면, Compose·Jenkins. FE-10이 정상 선별 결과를 브라우저에서 출품·입찰·배차까지 보냄 | MVP 포함 여부 미정, Backend 기반 출품 연결. 상세는 [LOGISTICS](LOGISTICS.md) |
| 발표 | `docs/최종발표/`: 최종 발표 초안 HTML(32쪽)·PDF·대본, 데이터 분석·모델 선정 근거, 개발 중 문제 해결 사례 (10-01 저장소 추가) | PDF 재출력, 실제 시연 캡처·단계별 소요시간·장애 복구 결과 추가 |

2026-09-30 Backend 후속 확인: BE-07 Backend 구현은 완료됐고, BE-08 1/4 기준선과 2/4 late result DB 진단 저장을 완료했다. 늦은 응답은 기존 검사 행의 진단 필드에만 저장하며 확정 판정·bin·제어·통계를 바꾸지 않는다. Backend·Simulator 219건 통과·MySQL 실DB 5건 통과(조건부 테스트는 별도 실행). 위 dev 기준 표의 당시 기록은 유지한다. 실제 Inference·MySQL 수직 통합 검증(3/4)과 MLOps E2E(4/4)는 이후 범위다.

## 3. 관제 API 계약 대비 Backend 구현

| FE 계약 (`docs/contracts/quality-operations.openapi.json`) | Backend |
|---|---|
| `GET /snapshot`, `/inspections`, `/inspections.csv`, `/statistics`, `/statistics.csv` | 구현 (BE-05) |
| `GET·DELETE /fault-images`, `GET /previews/{id}` | 구현 (BE-06) |
| `PUT /simulator` | 구현 (BE-07) |
| `PATCH /inspections/{id}/review` | 구현 (BE-07) |

## 4. MLOps 세부 (MO 작성 09-28 기록을 09-29 기준으로 갱신)

| 작업 | 상태 | 확인한 범위 | 다음 확인 |
|---|---|---|---|
| MO-01~03 | 완료 | 규칙, Compose 골격, Jenkins 기본 파이프라인 | Jenkins Job 대상 브랜치(`dev`)와 트리거 확인. `Jenkinsfile`은 `githubPush()`, 운영 설명은 Poll SCM |
| MO-04 | 완료 | 실제 Inference·Backend Dockerfile, `/health`, `service_healthy` 기동 순서 | 배포 서버 실행 로그 |
| MO-05 | 부분 완료 | MySQL Volume, `.env`·Credentials(MySQL·Google Maps 키), 모델 경로 | 장애 이미지·Simulator 위치·로그 Volume, 운영 Secret 절차 |
| MO-06 | 부분 완료 | 서버컴 모델 단독 p95 138.50ms, Compose HTTP p95 205.76ms·6.00건/초(합성 JPEG 12장) | 09-30 DM이 실제 시연 사진 서버 내부 지연 측정(동시 처리 1 p95 309ms, 2는 528ms). Compose 운영 경로 측정은 남음 |
| MO-07 | 부분 완료 | Compose Backend↔Inference, 물류 서비스 빌드·배포 연결 | 배포 전 테스트, 실패 시 이전 버전 유지, migration 적용 |
| MO-08~10 | 미착수 | - | 위치 복구·로그 순환·최종 수용시험·버전 동결 |

## 5. 동결까지 핵심 경로

```text
Simulator 입력 간격 조정(PR #33) → 루트 Compose에 FE 연결(API 모드) → Simulator 실패 시 계속 전송·DB 중단 시 선별 지속(BE)
→ ALL-03 전체 흐름 1차 통합 (10-08) → ALL-04 정상 100건·장애 5종 수용시험 (10-12) → ALL-05 기능 동결 (10-13)
```

## 6. 문서 위치

| 내용 | 문서 |
|---|---|
| 일정·담당 원본 | [WBS](WBS.md) |
| 문서 안내 | [README](README.md) |
| 09-23 독립 실행 점검 기록 | [ALL-02](ALL-02.md) |
| 파트 간 요청 | [파트별 협업 요청](협업공지/파트별-협업-요청.md) |
| 발표용 문제 해결 사례 | [개발 중 문제 해결 사례](../최종발표/개발%20중%20문제%20해결%20사례.md) |
| 확정 범위 QA (ALL-04 사전 점검) | [QA 테스트 케이스](reference/ALL/qa-test-cases.md) |
| 기획·요구사항·결정 | [기획서](../project-plan.md), [요구사항](../planning/requirements.md), [결정 기록](../planning/decision-log.md) |
