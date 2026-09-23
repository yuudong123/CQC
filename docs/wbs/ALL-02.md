# ALL-02 독립 실행 점검 및 통합 기록

- 기준일: 2026-09-23
- 상태: 점검 기록 작성, 독립 실행 전체 완료 미확인
- WBS의 ID·담당·일정은 변경하지 않는다.

## 문서 구조 정리 (2026-09-23)

- 문서 진입점은 [docs 안내](../README.md)로 통일한다.
- 기획 기준은 `docs/planning/`, 작업 부속 명세는 `docs/wbs/reference/<파트>/`로 분류했다.
- 검증 JSON은 `docs/wbs/results/`, 공유 공지는 `docs/wbs/협업공지/`에 모았다.
- 24개 문서를 이동하고 내용은 보존했다. 루트에 작업 요약 파일을 추가하지 않는다.
- 발표 자료와 API 계약은 용도가 달라 기존 전용 폴더를 유지했다.
- 다른 브랜치의 문서를 이 브랜치에 복제하거나 기존 WBS ID·담당·일정을 변경하지 않았다.

## 코드별 문서 작성 현황

| 파트 | 확인된 명세 | 비고 |
|---|---|---|
| DM | DM-01~09 | 모든 작업 문서 존재. 최신 실험·최종 학습 준비는 DM-06·09에 보완 |
| MO | MO-01~05 | origin/dev 기준 존재. MO-06~10 작업 기록은 미확인 |
| BE | BE-01~04 | 최신 origin/dev 2490cfe에 PR #10으로 통합 확인. 로컬 문서는 복제하지 않음 |
| FE | 개별 WBS 기록 미확인 | 담당자 미푸시 작업 여부는 확인하지 않음 |

미래 작업의 실행 결과를 미리 작성하거나 문서 존재를 기능 완료로 간주하지 않는다.


## 이번 결정

- 최상위 기획에 QC → 출품 → 경매 → 단순 자동배차 → 배송·고장 대체배차를 포함했다.
- QC MySQL과 물류 MongoDB를 분리하고 통합 목표를 8개 서비스로 명시했다.
- 동적 배차는 첫 미완료 하차 앞의 고정 삽입으로 단순화했다. 향후에도 단순 구현을 우선하며 프론트 흐름에 따라 계약·검증을 함께 변경한다.
- 기존 WBS의 작업 ID·일정·담당은 변경하지 않았다.
- 프레임워크 미확정 문구를 PyTorch·MobileNetV3 Small 확정으로 정정했다.
- 기존 27개 Test 재평가는 회귀 비교이며 독립적인 최종 승인에는 신규 holdout이 필요하다.
- 가상 당도 결합보다 이미지 단독의 개발 강건 점수가 높아 이미지 단독을 최종 학습 후보로 기록했다.

## 통합 잔여 작업

| 항목 | 현재 확인 상태 | 완료 조건 |
|---|---|---|
| 실제 QC → 물류 | 필드·전달 기준 문서화 | [QC 물류 연결 기준](<reference/ALL/qc-logistics-handoff.md>) 기준 실제 연결 시험 |
| 가상 당도 표시 | 생성 CSV·학습 실험 구현 | API·화면에 출처·비실측 표시 연결 |
| QC Compose | origin/dev의 QC 4개 앱은 placeholder | 실제 이미지·명령·healthcheck 연결 |
| CI | 구조 검사·기동 검사 중심 | 파트 테스트와 dev 배포 조건 반영, 실제 Job 설정 확인 |
| QC 프론트 | 확인한 저장소에서 구현 미확인 | 담당자 최신 작업 반영 후 mock 독립 실행 |
| QC Backend | origin/dev에 BE-01~04 mock 정책·DB 스키마 통합 | 실제 HTTP·DB·조회·Simulator 연결 |
| CPU 성능 | i7-4790 시험 스크립트 존재 | 목표 장비에서 실제 측정 |
| 최종 모델 | 4 epoch 완료·후보 패키지·체크섬·HTTP 계약 검증 완료(DM-09·07) | 독립 평가 자료 확보·신뢰도 검증·목표 CPU 시험 |

기능 구현이 없는 항목은 문서 수정으로 완료 처리하지 않는다. 다른 파트의 mock을 임의의 서비스로 바꾸거나 API 응답에 새 필드를 강제로 추가하지 않고, 해당 구현과 계약 검증 단계에서 처리한다. 이번 작업은 학습 프로세스를 변경하거나 Test를 실행하지 않았다.


## 기준 문서의 역할 및 미결정 사항


## 기준 문서

| 문서 | 목적 | 현재 상태 | 다음 갱신 조건 |
|---|---|---|---|
| `project-plan.md` | 프로젝트 배경, 데이터 조사, 범위와 실행 원칙 | 고도화 합의 반영 | 범위·성능 정책 변경 시 |
| `docs/planning/requirements.md` | 기능·비기능 요구와 수용 기준 | 고도화 합의 반영 | API·화면 계약 변경 시 |
| `docs/wbs/reference/DM/data-spec.md` | 원본 데이터, 그룹 분할, 모델·MySQL 논리 명세 | 로컬 데이터 확인 결과 반영 | 백엔드 물리 DB 설계 완료 시 |
| `docs/planning/architecture.md` | HTTP 서비스, 상태, 저장·배포 구조 | 고도화 합의 반영 | 파트별 기술 스택 확정 시 |
| `wbs.md` | 09-16~10-16 역할별 일정·의존성·완료 조건 | 전면 개정 완료 | 실제 진행 지연·범위 변경 시 |
| `docs/planning/decision-log.md` | 기획 인터뷰 확정 사항 | 최신 | 새 결정 즉시 |
| `docs/wbs/reference/BE/backend-stack.md` | Backend 기술 선택·버전·실행법 | FastAPI·MySQL·HTTP 기초 합의 반영 | 세부 라이브러리·버전 선정 시 |
| `docs/wbs/reference/DM/model-stack.md` | 데이터·모델 기술 선택·실행법 | 구현·평가 결과 반영 | v2 결과와 i7-4790 수용시험 완료 시 |
| `docs/wbs/reference/FE/frontend-stack.md` | Frontend 기술 선택·실행법 | 담당자 작성 대기 | 담당자 기술 선정 시 |
| `docs/wbs/reference/MO/mlops-stack.md` | MLOps 기술 선택·실행법 | MO-01~05와 현재 통합 기반 반영 | QC 5개와 물류 3개 서비스 통합 시 |

## 확정 사항

- 프로젝트명: CQC
- 프로젝트 기간: 2026-09-16~2026-10-16
- MVP: 부사·양광의 품종과 특·상·보통 품질 판정
- 입력 단위: 동일 `group_no`의 다각도 사과 그룹
- 입력 방식: Simulator 전용, 그룹당 각도 기준 대표 12장 전송
- 데이터 분할: seed 42, 그룹 층화 70/15/15, 5-Fold Group CV
- 입력 장수 실험: 4·8·12·16·40장
- 처리 목표: 500ms 간격 입력과 초당 사과 그룹 2개, Inference HTTP 구간 500ms, 가상 제어 100ms
- 서비스: QC 5개와 logistics-mongodb·logistics-api·logistics-web, Kafka 제외
- 데이터베이스: MySQL 검사 이력·통계, MongoDB 거래·배송 상태
- 기능 동결: 2026-10-13
- 담당: 조현재(DM), 강성민(FE), 홍준희(BE), 홍유나(MO)

## 담당자 작성 문서

| 문서 | 담당자 | 작성할 핵심 내용 |
|---|---|---|
| `docs/wbs/reference/DM/model-stack.md` | 조현재 | 프레임워크, 그룹 모델, 전처리, CPU 최적화, 실행법 |
| `docs/wbs/reference/BE/backend-stack.md` | 홍준희 | FastAPI 세부 라이브러리·버전, OpenAPI, 오류 코드, MySQL 물리 설계, 마이그레이션 |
| `docs/wbs/reference/FE/frontend-stack.md` | 강성민 | 프레임워크, 차트, 화면 상태, 빌드·테스트 |
| `docs/wbs/reference/MO/mlops-stack.md` | 홍유나 | Compose, dev CI/CD, healthcheck, 볼륨·로그·복구 |

## 남은 결정

- v2 품질 승인 여부와 신규 독립 holdout 확보 방식
- i7-4790 실측에 따른 최종 병렬 처리 수
- 최종 대시보드 차트 종류
- 두 번째 농산물 품목 확장 여부
