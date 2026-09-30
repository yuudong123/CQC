# CQC 작업 문서 안내

**작업 현황은 [ALL-03](ALL-03.md) 한 곳에만 적는다. 일정·담당은 [WBS](WBS.md), 기획은 [기획서](../project-plan.md)를 따른다.**

## 읽는 순서

| 목적 | 위치 |
|---|---|
| 현재 작업 현황 (단일 원본) | [ALL-03 전체 통합 현황](ALL-03.md) |
| 담당·일정·완료 기준 | [WBS](WBS.md) |
| 프로젝트 범위·방향 | [기획서](../project-plan.md) |
| 기능·수용 기준 | [요구사항](../planning/requirements.md) |
| 서비스 구조·책임 경계 | [아키텍처](../planning/architecture.md) |
| 결정 근거·변경 이력 | [의사결정 기록](../planning/decision-log.md) |
| 실제 API 계약 | [Inference OpenAPI](../contracts/inference-openapi.json), [관제 OpenAPI](../contracts/quality-operations.openapi.json) |

## 작업 기록과 부속 명세

| 구분 | 본문 | 부속 자료 |
|---|---|---|
| 데이터 확인·가공 | DM-01~04 | [데이터 명세](reference/DM/data-spec.md) |
| 학습·모델 비교 | DM-05~06 | [모델 스택](reference/DM/model-stack.md), [가상 당도 조사](reference/DM/virtual-brix-plan.md) |
| 추론·배포 | DM-07 | [연동 계약 공지](협업공지/모델-추론-계약-공지.md) |
| 신뢰도·성능 | DM-08 | [목표 CPU 시험 절차](reference/DM/server-acceptance.md) |
| 최종 평가·모델 카드 | DM-09 | [v2 카드(현재 서비스 모델)](reference/DM/model-card-v2.md), [v1 카드](reference/DM/model-card.md), [카드 양식](reference/DM/model-card-template.md) |
| 백엔드 | BE-01~06 | [백엔드 스택](reference/BE/backend-stack.md) |
| 프론트엔드 | FE-01~10, [종합 정리](Frontend-작업-종합정리.md) | [프론트 스택](reference/FE/frontend-stack.md), [관제 API 인계](협업공지/Frontend-관제-API-계약-인계.md) |
| MLOps | MO-01~06 | [MLOps 스택](reference/MO/mlops-stack.md), [Simulator 배포·데이터 볼륨](reference/MO/simulator-deployment.md) |
| 물류 | [LOGISTICS](LOGISTICS.md) | [물류 명세 01~08](reference/LOGISTICS/01-product-scope.md), [QC·물류 연결](reference/ALL/qc-logistics-handoff.md) |
| 통합·파트 간 전달 | [ALL-02](ALL-02.md)(09-23 기록), [ALL-03](ALL-03.md)(현재) | [협업 요청](협업공지/파트별-협업-요청.md), [12-bin 정책](협업공지/12-bin-가상당도-배차-인계.md), [확정 범위 QA 테스트 케이스](reference/ALL/qa-test-cases.md) |

최신 후보 모델 상태는 DM-09 본문을 따른다. 과거 공지·v1 카드·실험 결과를 현재 승인 상태로 해석하지 않는다.

## 폴더 규칙

```text
docs/
├─ project-plan.md    최상위 기획
├─ planning/          요구사항·아키텍처·의사결정
├─ contracts/         기계 판독용 API 계약
├─ wbs/               작업 기록의 유일한 위치
│  ├─ README.md       이 안내
│  ├─ WBS.md          일정·담당·완료 기준 원본
│  ├─ ALL-03.md       현재 작업 현황 (단일 원본)
│  ├─ DM·FE·BE·MO·ALL·LOGISTICS 작업 문서
│  ├─ reference/      파트별 부속 명세·절차
│  ├─ results/        검증 JSON 원본
│  └─ 협업공지/       전달용 공지·협업 기록
├─ 중간발표/           날짜별 발표 자료
└─ 최종발표자료/        최종 발표 근거 자료
```

- 작업 현황·진행 상태는 ALL-03에만 적고, 다른 문서는 링크한다. 코드 폴더에는 README를 두지 않고 사용법은 해당 파일 주석에 적는다.
- 상세 명세·긴 실행 절차는 `reference/<파트>/`에 두고 해당 WBS에서 연결한다.
- 숫자 증거는 `results/`에 보존한다. 문서 존재와 기능 완료는 구분한다.
- WBS ID·담당·일정은 폴더 정리를 이유로 바꾸지 않는다.
- 최신 상태와 맞지 않는 안내·스냅샷 문서는 고치기보다 삭제하고 ALL-03을 갱신한다.
