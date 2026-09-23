# CQC 문서 안내

**기획은 [project-plan.md](project-plan.md), 일정·담당은 [wbs.md](wbs.md), 실행 내역은 아래 WBS 문서에서 확인한다.**

## 읽는 순서

| 목적 | 위치 |
|---|---|
| 프로젝트 범위·방향 | [기획서](project-plan.md) |
| 기능·수용 기준 | [요구사항](planning/requirements.md) |
| 서비스 구조·책임 경계 | [아키텍처](planning/architecture.md) |
| 결정 근거·변경 이력 | [의사결정 기록](planning/decision-log.md) |
| 담당·일정·선행 작업 | [WBS 원본](wbs.md) |
| 파트별 통합 현황·잔여 작업 | [ALL-02](wbs/ALL-02.md) |
| 실제 API 계약 | [Inference OpenAPI](contracts/inference-openapi.json) |

## 작업 기록과 부속 명세

| 구분 | 본문 | 부속 자료 |
|---|---|---|
| 데이터 확인·가공 | DM-01~04 (`wbs/`) | [데이터 명세](wbs/reference/DM/data-spec.md) |
| 학습·모델 비교 | DM-05~06 (`wbs/`) | [모델 스택](wbs/reference/DM/model-stack.md), [가상 당도 조사](wbs/reference/DM/virtual-brix-plan.md) |
| 추론·배포 | DM-07 (`wbs/`) | [연동 공지 이력](wbs/협업공지/모델-추론-계약-공지.md) |
| 신뢰도·성능 | DM-08 (`wbs/`) | [목표 CPU 시험 절차](wbs/reference/DM/i7-4790-acceptance.md) |
| 최종 평가·모델 카드 | DM-09 (`wbs/`) | [v1 카드](wbs/reference/DM/model-card.md), [카드 양식](wbs/reference/DM/model-card-template.md) |
| 백엔드 | 최신 dev의 BE 작업 문서 | [백엔드 스택](wbs/reference/BE/backend-stack.md) |
| 프론트엔드 | 공유된 FE 작업 기록 미확인 | [프론트 스택](wbs/reference/FE/frontend-stack.md) |
| MLOps | MO-01~06 (`wbs/`) | [MLOps 스택](wbs/reference/MO/mlops-stack.md), [CPU 성능시험](wbs/MO-06.md) |
| 파트 간 전달 | ALL-02 (`wbs/`) | [QC·물류 연결](wbs/reference/ALL/qc-logistics-handoff.md), [협업 요청](wbs/협업공지/파트별-협업-요청.md) |

최신 후보 모델 상태는 DM-09 본문을 따른다. 과거 공지·v1 카드·실험 결과를 현재 승인 상태로 해석하지 않는다. 백엔드 문서는 브랜치에 따라 차이가 있으며 이 정리는 다른 브랜치를 병합하지 않는다.

## 폴더 규칙

```text
docs/
├─ README.md          문서 안내
├─ project-plan.md    최상위 기획
├─ wbs.md             확정 일정·담당
├─ planning/          요구사항·아키텍처·의사결정
├─ contracts/         기계 판독용 API 계약
├─ wbs/               WBS 코드별 작업·검증·잔여 내역
│  ├─ reference/      DM·BE·FE·MO·ALL별 부속 명세·절차
│  ├─ results/        검증 JSON 원본
│  └─ 협업공지/       전달용 공지·협업 기록
└─ 중간발표/           날짜별 발표 자료·이미지
```

- 새로운 작업 요약·회고·진행 상태 파일을 루트에 만들지 않고 해당 WBS 본문을 갱신한다.
- 상세 명세·긴 실행 절차는 `wbs/reference/<파트>/`에 두고 해당 WBS에서 연결한다.
- 숫자 증거는 `wbs/results/`에 보존한다. 문서 존재와 기능 완료는 구분한다.
- WBS ID·담당·일정은 폴더 정리를 이유로 바꾸지 않는다.
