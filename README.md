# CQC — 사과 품질 판정 및 선별 시스템

AI Hub 농산물 품질(QC) 이미지를 이용해 사과의 품종과 품질 등급을 판정하고, 판정 결과를 가상 선별 흐름으로 연결하는 1개월 팀 프로젝트입니다.

## MVP 범위

- 대상: 부사(`fuji`)·양광(`yanggwang`) 2개 품종
- 입력: Simulator가 `data/processed/realtime-apple-arrival-demo/index.json`의 시연 전용 12장 묶음을 순서대로 전송. 모델 목표는 12장이며 요청은 1~12장을 허용
- 출력: 품종·품질(`특/상/보통`) 예측, 각각의 확률·신뢰도, 선별 목적지
- 자동화 목표: 시뮬레이터 자동 입력, 저신뢰·오류 재검사 분기, 품종 2종 × 외관 3단계 × 가상 당도 2단계의 정상 12 bin과 재검사 bin 1개를 사용하는 가상 제어. 가상 당도 구간은 14°Brix 미만/이상이며, 당도가 없으면 재검사로 보낸다
- 처리 목표: 서버컴(RAM 16GB) CPU 환경에서 500ms 간격 입력과 초당 사과 그룹 2개 처리. Inference 제한시간은 현재 라인 속도와 같고(10-05 결정, #87) Backend 요청 전송부터 응답 전체 수신까지 적용. 현재 시연 입력 간격 2000ms(09-30 결정, 서버컴 실측 초당 0.63건으로 500ms는 요청이 밀림)
- 조건부 확장: 사과 MVP 완료 후 두 번째 농산물 품목 검토
- 제외: 스마트폰 카메라 입력, 사용자 이미지 파일 업로드, 실제 산업용 카메라·PLC·선별 장비 연동, 설비 고장예지

## 서비스 구성

```text
simulator → FastAPI backend → inference HTTP API
                    ├─ MySQL
                    ├─ 내부 가상 제어 API
                    └─ web (품질 관제)

web (입찰·배송 관제) → logistics-api → MongoDB
```

서비스 간 통신은 HTTP를 사용하며 Kafka는 사용하지 않습니다. Docker Compose 실행 단위는 QC 5개(`simulator`, `inference`, `backend`, `frontend`, `mysql`)와 물류 3개(`logistics-mongodb`, `logistics-api`, `logistics-web`)입니다. 품질 관제·입찰·배송 관제 화면은 모두 `cqc-logistics-platform/apps/web`에 있습니다.

검사 한 건은 사과 한 개, 즉 `group_no` 한 개이며 모든 구성 요소는 동일한 `inspection_id`로 이 흐름을 추적합니다. 모델 목표 입력은 12장, 요청 제한은 1~12장·24MiB, 품종·품질 confidence threshold의 운영 기본값은 각각 0.50입니다. 이 값은 v1 검증 예측으로 정했으며 v2 후보 기준 재보정은 남아 있습니다.

## 폴더 역할

| 폴더 | 역할 |
|---|---|
| `docs/` | 기획·요구사항·아키텍처·API 계약. 작업 기록과 현황은 `docs/wbs/`에만 둠 |
| `data/raw/` | AI Hub 원본 이미지와 라벨. 원본은 수정하지 않음 |
| `data/processed/` | 학습용 매니페스트와 가공·분할 데이터 |
| `notebooks/` | 데이터 탐색과 모델 실험 기록 |
| `src/data/` | 데이터 읽기, 검증, 전처리와 그룹 분할 코드 |
| `src/models/` | 다각도 그룹 모델 구조와 생성 코드 |
| `src/training/` | 학습, 평가와 비교 실험 코드 |
| `src/inference/` | 모델 후보의 통합 검증과 승인 모델 배포에 공통으로 사용하는 HTTP 추론 서비스 코드 |
| `src/api/` | 검사 오케스트레이션, 정책, 이력과 가상 제어 백엔드 코드 |
| `cqc-logistics-platform/` | 웹(품질 관제·입찰·배송 관제)과 물류 API. 루트 `src/web/`은 사용하지 않음 |
| `tests/` | 데이터·모델·API·통합 흐름 검증 코드 |
| `configs/` | 분할, 전처리, 모델과 실행 설정 |
| `scripts/` | 데이터 준비, 학습, 평가와 실행 보조 스크립트 |
| `models/` | 모델 패키지(`selected`=서비스 모델, `model_<버전·특징>`=버전별). Git 추적. 학습 체크포인트는 `outputs/`(Git 제외) |
| `outputs/` | 로컬 평가표, 그래프와 실험 산출물. Git 제외 |

## 현재 상태와 문서

- 작업 현황: [`docs/wbs/ALL-03.md`](docs/wbs/ALL-03.md) (단일 원본)
- 문서 안내: [`docs/wbs/README.md`](docs/wbs/README.md)
- 최상위 기획: [`docs/project-plan.md`](docs/project-plan.md), 결정 기록: [`docs/planning/decision-log.md`](docs/planning/decision-log.md), 일정·담당: [`docs/wbs/WBS.md`](docs/wbs/WBS.md)

프로젝트 기간은 2026-09-16부터 2026-10-16까지이며, 2026-10-13에 기능을 동결합니다.
