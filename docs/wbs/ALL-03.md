# ALL-03 전체 통합 현황

- WBS 코드: `ALL-03` (전체 흐름 1차 통합, 예정 10-08)
- 기준: dev `b0b08dd` (2026-09-29 18:30, PR #23 feat/data·#24 feat/backend 병합 후) + 2026-09-30 feat/data(DM-08 보정)·feat/front(FE-07·실제 Backend 연결) 작업
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
| DM (조현재) | DM-01~09. `separate`·12장 모델, Inference HTTP API, 시연 묶음 996개(12장 869개)·가상 당도 14°Brix 구간. v2 보정 실행 완료(09-30): 품질 T=0.391·ECE 0.259→0.081, **임계값 품종 0.50·품질 0.60 결정**, 패키지 `cqc-apple-separate12-focal-v2-cal-20260930`(가중치 동일, `model.json`만 변경), Compose 임계값 전달. 개발 OOF 기준 재검사 23.7%→16.4%·자동 처리 품질 92.2%→92.9%, 시연 36묶음 재검사 13.9%→8.3%. 서버컴 실제 사진 모델 계산 p95 138ms(dev 배포본) | 학원 서버 모델 폴더 `model.json`을 보정본으로 교체한 뒤 Compose 임계값 배포(순서 중요), 배포 후 서버컴 `Server-Timing`으로 해제 포함 서버 지연 재측정. 독립 holdout 부재는 모델 카드 한계에 명시됨 |
| FE (강성민, FE-01~10 작업은 조현재) | FE-01~10: 품질 관제·이력·통계·장애 관리, 12장 그룹 관제, 브라우저 자동 경매·배차 시연. 09-30 BE-06 개별 장애 이미지 계약 반영, **실제 Backend 연결 확인**(snapshot·이력·필터·통계·CSV·장애 이미지 미리보기/삭제, DB 중단·복구, 장애 이미지 100장 순환), 신뢰도 표시 자리수 수정, 프로덕션 빌드 31.5분·3,600건 연속 관제(heap 중앙값 22~23MB에서 안정, DOM 2,074 고정) | BE-07 Simulator·검수 API 연결 후 제어·검수 화면 확인, 목표 배포 환경 8시간 시험·실제 브라우저 탭 전환 확인 |
| BE (홍준희) | BE-01~06: 검사 API, 실제 Inference 호출, 500ms 기한·지연 결과, 12-bin migration·13개 seed, 저장·이력·통계·CSV, 장애 이미지 저장·목록·미리보기·선택 삭제(최대 100장) | **BE-07 Simulator**(500ms 입력·시작/정지·위치 복구·장애 토글), 검수 API, 지연 결과 DB 저장, 이력 보존 삭제(86,400/8,640), BE-08 이후 통합. 09-30 통합 점검 요청 4건: DB 중단 시 선별 중단, 처리량 과소 표시, 연결 오류 코드, Inference 상태([협업 요청](협업공지/파트별-협업-요청.md)) |
| MO (홍유나) | MO-01~06. Compose 8개 서비스(QC 5·물류 3), healthcheck·기동 순서, MySQL·Mongo Volume, Jenkins Credentials, 서버컴 합성 입력 측정. 09-30 PR #25: Backend 기동 시 `alembic upgrade head`, 장애 이미지 Volume(`FAULT_IMAGE_STORAGE_ROOT`) | frontend·simulator placeholder 교체, 학원 서버 모델 폴더 `model.json` 보정본 교체(DM-08), Jenkins 테스트 단계, 실패 시 이전 버전 유지(MO-07), MO-08~10 |
| 물류 | LOGISTICS-01~06: 출품·입찰·배차·배송 API와 화면, Compose·Jenkins. FE-10이 정상 선별 결과를 브라우저에서 출품·입찰·배차까지 보냄 | MVP 포함 여부 미정, Backend 기반 출품 연결. 상세는 [LOGISTICS](LOGISTICS.md) |
| 발표 | 최종발표 HTML(좌측 목차 바, MVP 04쪽)·대본, 로컬 `docs/최종발표/` | PDF 재출력, 실제 시연 캡처·단계별 소요시간·장애 복구 결과 추가 |

## 3. 관제 API 계약 대비 Backend 구현

| FE 계약 (`docs/contracts/quality-operations.openapi.json`) | Backend |
|---|---|
| `GET /snapshot`, `/inspections`, `/inspections.csv`, `/statistics`, `/statistics.csv` | 구현 (BE-05) |
| `GET·DELETE /fault-images`, `GET /previews/{id}` | 구현 (BE-06) |
| `PUT /simulator` | 미구현 (BE-07) |
| `PATCH /inspections/{id}/review` | 미구현 |

## 4. MLOps 세부 (MO 작성 09-28 기록을 09-29 기준으로 갱신)

| 작업 | 상태 | 확인한 범위 | 다음 확인 |
|---|---|---|---|
| MO-01~03 | 완료 | 규칙, Compose 골격, Jenkins 기본 파이프라인 | Jenkins Job 대상 브랜치(`dev`)와 트리거 확인. `Jenkinsfile`은 `githubPush()`, 운영 설명은 Poll SCM |
| MO-04 | 완료 | 실제 Inference·Backend Dockerfile, `/health`, `service_healthy` 기동 순서 | 배포 서버 실행 로그 |
| MO-05 | 부분 완료 | MySQL Volume, `.env`·Credentials(MySQL·Google Maps 키), 모델 경로 | 장애 이미지·Simulator 위치·로그 Volume, 운영 Secret 절차 |
| MO-06 | 부분 완료 | 서버컴 모델 단독 p95 138.50ms, Compose HTTP p95 205.76ms·6.00건/초(합성 JPEG 12장) | 실제 시연 사진·동시 요청 기준 측정 |
| MO-07 | 부분 완료 | Compose Backend↔Inference, 물류 서비스 빌드·배포 연결 | 배포 전 테스트, 실패 시 이전 버전 유지, migration 적용 |
| MO-08~10 | 미착수 | - | 위치 복구·로그 순환·최종 수용시험·버전 동결 |

## 5. 동결까지 핵심 경로

```text
BE-07 Simulator → 루트 Compose에 FE·Simulator 연결, migration·장애 이미지 Volume
→ ALL-03 전체 흐름 1차 통합 (10-08) → ALL-04 정상 100건·장애 5종 수용시험 (10-12) → ALL-05 기능 동결 (10-13)
```

## 6. 문서 위치

| 내용 | 문서 |
|---|---|
| 일정·담당 원본 | [WBS](WBS.md) |
| 문서 안내 | [README](README.md) |
| 09-23 독립 실행 점검 기록 | [ALL-02](ALL-02.md) |
| 파트 간 요청 | [파트별 협업 요청](협업공지/파트별-협업-요청.md) |
| 기획·요구사항·결정 | [기획서](../project-plan.md), [요구사항](../planning/requirements.md), [결정 기록](../planning/decision-log.md) |
