# ALL-03 전체 통합 현황

> **10-06 갱신** (dev `101bbe4`, PR #100까지). 아래 10-05 감사 기록 이후 바뀐 점:
> - BE: PR #100 병합으로 feat/backend 미병합 커밋 0개. BE-10 2단계 27/27 통과, 검사 ID 규칙(`.` 허용, 1~64자) 통일
> - MO: MO-08 완료(#70 종료, 서버 검증)
> - FE: FE-08 반응형 점검 완료. 검사 ID 규칙(#100)에 맞춘 FE 파서·계약 생성기 수정(PR 예정, 웹 시험 51 통과)
> - 발표: 32~35쪽에서 내부 감사 결과를 빼고 현재 상태·문제 해결 사례로 정리(발표 범위). 감사 항목(#95~#99)은 QA 뒤 정리

- WBS 코드: `ALL-03` (전체 흐름 1차 통합, 예정 10-08)
- 감사일: **2026-10-05**, 코드 기준 **dev `51c6e32` (PR #94까지 병합)**. 로컬 dev는 clean 상태에서 fast-forward했다.
- 실서버 확인: **10-05 16:36 KST**, HTTP 읽기 전용. 서버의 정확한 배포 SHA는 Jenkins API 403으로 확인하지 못했으므로 코드 기준 SHA와 같다고 단정하지 않는다.
- 역할: **작업 현황의 단일 원본**. 일정·담당·완료 기준은 [WBS](WBS.md), 현재 계약은 코드·OpenAPI와 대조한다. 상세 문서의 과거 결과는 당시 기록으로 읽는다.
- 이슈 규칙: [#39 댓글](https://github.com/yuudong123/CQC/issues/39#issuecomment-5925738486)의 `[담당][WBS]` 제목, 파트·종류·우선순위 라벨을 사용한다. 신규 요청이 다른 담당 에이전트의 자동 착수를 의미하지 않는다. #39의 규칙 채택 제안 자체는 아직 열려 있다.
- 이번 이슈 생성·종료는 사용자의 직접 지시에 따른다. WBS ID·담당·일정, 미합의 수용 기준을 변경하지 않는다.
- 원본 증거: [이번 감사 JSON](results/wbs-audit-20261005.json). 코드 구현·로컬 회귀·목표 서버 관찰·최종 수용 통과를 구분한다.

## 1. 자동 시험과 산출물 확인

| 범위 | 이번 실행 결과 | 한계 |
|---|---|---|
| DM focused unittest | **45 통과**. manifest·image quality·split·multiview·package·calibration·inference·evaluation·model card | 전체 학습 재실행·독립 정확도 승인 아님 |
| 실제 선정 패키지 로컬 smoke | CPU 로딩, 합성 JPEG 12장 추론·확률합 확인 | 목표 서버 성능·실사과 정확도 시험 아님 |
| 웹 | **50 통과**, `tsc --noEmit` 통과 | 이번 감사에서는 production build·8시간 브라우저 시험을 다시 실행하지 않음 |
| CI 배포·복구 harness | **16 통과** | 로컬 모의 Docker 명령 시험. 실제 Jenkins 최종 배포 결과와 구분 |
| 물류 API | **12 통과** | 기본 MemoryStore 시험. MongoDB·실제 QC 출품 연동을 증명하지 않음 |
| Backend·Simulator·서비스 로깅 | **327 통과 / 6 skip / 3 실패** (Windows Python 3.11.9, 최초 pytest 8.4.2) | pytest **9.1.1**로 실패 3항목을 다시 실행해 동일 실패 확인. MySQL 등 6 skip을 실DB 통과로 계산하지 않음 |
| Backend 실패 분리 | 이미지 순환 2개: workspace 임시 디렉터리 rename WinError 5 반복. hard-timeout 1개: 묶음 실패·단독 통과 | [#99](https://github.com/yuudong123/CQC/issues/99)·[#66](https://github.com/yuudong123/CQC/issues/66). 이미지 저장 OS Temp 대조는 110건 저장·100건 보존 성공. Linux 운영 실패로 확대하지 않음 |
| 발표 PDF | 최종·10-08 변경 사본 모두 **36쪽**, 31쪽 이미지 각 3개 포함 | 신규 발표 제작이 아니라 기존 산출물 완료조건 확인 |

이전 10-05 `dee8c54`의 Python 346 통과·6 skip 및 `b820b5d`의 웹 48 통과는 당시 기록이다. 이번 Windows 결과를 전체 통과로 덮어쓰지 않는다. PR #92의 웹 50 통과·build 성공, #94의 Simulator 8 통과는 각 PR에 기록된 검증이다.

## 2. 실서버 읽기 전용 관찰

| 확인 항목 | 10-05 16:36 KST 결과 |
|---|---|
| Backend·Inference·웹 proxy health | HTTP 200. snapshot의 Simulator·Inference·Backend·MySQL 모두 healthy |
| 입력 설정 | Simulator running, **2000ms·순차 1** |
| 서비스 모델 | `cqc-apple-separate12-focal-v2-cal-20260930`, `calibrated_dev_oof`, **unverified_candidate** |
| checkpoint SHA-256 | `b254206e4091732a49c5db02c12e5fb6dc3d996dbce694c2e82d442a2ba8753a` (로컬 패키지·실서버 health 일치) |
| 최근 저장 이력 | 200건, 16:29:41.015~16:36:19.003. **0.5000건/초**, 완료 간격 중앙값 2.003초·p90 2.178초·최대 2.645초 |
| 판정·오류 | PASS 181 / REVIEW 19(9.5%). errorCode NONE 200건, 시간 초과·추론 오류 0건 |
| 추론 시간 | Inference 내부 p95 **153.615ms**. Backend→Inference HTTP 전체 구간 측정값 아님 |
| 관제 | `recentCompletedJobs` 응답, 이력 200건 조회, `source=backend`, 1분 30건·5분 150건 |
| 검수 이미지 | 시스템 오류 100장·저신뢰 200장(합계 300장), 종류·사유 필드 조회 |
| 배포 버전 | 정확한 SHA 미확인. PR #94까지 코드 병합은 확인, Jenkins Job/API 증빙은 [#96](https://github.com/yuudong123/CQC/issues/96) |

저장된 이력의 사후 조회이므로 저장 유실 부재, 정확한 투입 간격, 정상 100건 수용 통과, 장애 5종·복구·순환 정책 종합 통과를 증명하지 않는다. [#65 결과 댓글](https://github.com/yuudong123/CQC/issues/65#issuecomment-5990266976)에 같은 범위를 기록했다.

기존 운영 증거는 보존한다. 10-02 500ms 기한의 13,119건 중 시간 초과 534건(4.1%), 10-05 14:19 배포 전 서버 재기동·Jenkins 부하와 시간 초과 집중, #91 계약 수정 후 배포는 당시 관찰이다. 현재 **제한시간 = 검사 시작 시 라인 속도**(#87·PR #89), 간격 정보 없는 직접 요청은 기본 500ms다. 2건/초 목표 미달과 수용 기준 제안은 [#65](https://github.com/yuudong123/CQC/issues/65)에 남긴다.

## 3. 전체 담당자와 실제 작업자

| 파트 | WBS 책임자 | 확인한 실제 작업·Git 상태 | 다음 우선순위 |
|---|---|---|---|
| DM | **조현재** / yuudong123 | 데이터·학습·모델·추론·발표·현황 문서. feat/data 고유 미병합 커밋 0개 | #97 CPU 비교 범위, #98 문서 구분, #65 수용 합의, #75 동결 후 평가·카드 |
| FE | **강성민** (WBS 책임 유지) | ALL-03·FE 이슈에는 **조현재가 FE-01~10 구현**한 것으로 기록. feat/front 미병합 0개, FE 이슈 실제 assignee yuudong123 | #73 8시간·탭 복귀, #74 화면 동결. 책임자 이름만으로 미확인 개인 작업을 완료 처리하지 않음 |
| BE | **홍준희** / cyanaria89 | 검사·DB·Simulator·검수·이력. feat/backend **3커밋 미병합**, 열린 PR 없음 | #95 메모리 누적, #99 Windows 회귀, #66 통합시험·PR, #68 계약 동결 |
| MO | **홍유나** / h-yuna-lab | Compose·Jenkins·로그·실패 복구. feat/mlops 미병합 0개 | #96 PR/배포 경계, #70 운영 복구·로그, #71 자동 수용, #72 버전·절차 동결 |

GitHub 공동 이슈 #65·#76에는 조현재를 조정 담당자로 지정했다. 각 파트의 기존 assignee는 유지했다. 책임자별 완료율은 구현·실측·동결 조건이 달라 숫자로 환산하지 않는다.

## 4. WBS별 완료조건 감사

### DM — 조현재

| WBS | 판단 | 근거·미충족 조건 |
|---|---|---|
| DM-01 | 완료 | ZIP·JSON 매핑·group_no·라벨 매니페스트. 25,024쌍·179그룹 |
| DM-02 | 완료 | 손상 0·중복 5쌍·그룹별 장수 검사 |
| DM-03 | 완료 | seed 42, 125/27/27, 5-fold, 그룹 누수·Test CV 유입 0 |
| DM-04 | 완료 | 4·8·12·16·40장 선택·부족 뷰 마스킹. 시연 996묶음 |
| DM-05 | 학습·개발 평가 완료 | 기준선·5-fold 지표·재현 설정. 독립 품질 승인과 별도 |
| DM-06 | **부분 완료** | 50/50 GPU 비교·선정·선정 패키지 서버 측정 있음. 전체 후보 장수별 목표 서버 평균·최대·p95 표 없음 → #97 |
| DM-07 | 구현·패키지 제공 완료 | 실제 HTTP API·체크섬·모델 버전·확률/신뢰도. bin·DB는 Backend 소유 |
| DM-08 | 보정·측정 완료, 수용 합의 남음 | 임계값 0.50/0.60·OOF 보정·운영 순차1. 0.5건/초가 기존 2건/초 목표를 충족하는 것은 아님 → #65 |
| DM-09 | 진행 중 | 동결 전 SHA·수치 사전 점검 완료. 동결 후 평가·실패/한계/승인 해석 기록 → #75 |

모델 개발 품질 F1 0.8844, source 0.7932, v1 최초 Test 0.7778. 기존 Test 회귀 1.0000은 독립 승인 점수가 아니다. #75 완료기준에 Test 재사용·카드 자동 승인 문구 확인을 명시했다. 신규 독립 데이터 확보나 추가 학습을 자동으로 필수 선행조건에 넣지 않는다.

### FE — 강성민 책임, 조현재 구현 기록

| WBS | 판단 | 근거·미충족 조건 |
|---|---|---|
| FE-01 | 계약·상태 정의 완료 | frontend stack·mock/API 계약·오류 상태 |
| FE-02 | 골격 구현·단기 화면 확인 | 무스크롤 레이아웃. #93에서 오류 누적 시 그래프 높이 보완 |
| FE-03 | 관리 기능 구현 | 이력 필터·페이지·CSV. 실제 수용 대조는 #65 |
| FE-04 | 처리 카드·제어 구현 | 12장·정지/재개·순차/병렬 상태 |
| FE-05 | 실제 API 연동·서버 확인 | 시작 기준 1초 조회, Chart.js, recentCompletedJobs, #92·#93 병합. 과거 “PR 예정”은 해소 |
| FE-06 | 상태·토글·라인 속도 구현 | 1·2·3초 선택, 구성요소 상태. 종합 장애 검증은 #65 |
| FE-07 | 검수 기능 구현·서버 확인 | 시스템 오류/저신뢰 필터·사유·종류별 한도. 삭제·영속성 종합 수용은 별도 |
| FE-08 | **진행 중** | 반응형 완료(10-06): 서버 화면 7개 크기(1920×1080~390×844)에서 페이지·가로 스크롤 없음, 패널 4개 표시, 검사 이력·검수 이미지 창은 화면 안에서 스크롤. 장시간 관제·탭 복귀는 #73 |
| FE-09 | 동결 전 대기 | 10-13 이후 화면 동결·대본 흐름 → #74 |
| FE-10 (본표 밖 확장 시연) | 가상 흐름 구현 | 경매·결제·배차 목업. #48에 따라 MVP 제외, 실제 QC 출품 완료로 계산하지 않음 |

### BE — 홍준희

| WBS | 판단 | 근거·미충족 조건 |
|---|---|---|
| BE-01 | 계약·기반 구현 | multipart·inspection_id·상태·오류 분리 |
| BE-02 | DB 스키마·마이그레이션 구현 | 검사·제어·오류·bin·인덱스. 최종 동결 일치는 #68 |
| BE-03 | 독립 mock 검사 구현 완료 | 현재 실제 Inference HTTP와 병행 |
| BE-04 | 판정·제어 구현 | 현재 12+1 bin, 요청별 라인 속도 timeout, 거부 대체1회. 장수명 제어 기록 문제 #95 |
| BE-05 | 이력·통계·CSV 구현 | 한국시간 ms·필터·통계 제외·BOM. 일/주/월 추세는 #56에서 확장 방향 확정 |
| BE-06 | 이미지 정책 구현, Windows 회귀 확인 필요 | 시스템 오류100·저신뢰200·사유 sidecar·삭제 API. #99 |
| BE-07 | Simulator 로직 구현 | 독립 프로세스·위치·revision·NEXT·장애 설정·12장 요청. 운영 재시작은 #70·#65 |
| BE-08 | 실제 수직 연결 확인 | Inference·DB·관제 HTTP 연결, late 진단 저장, 오류 분류 #67. 진단 목록 누적 #95 |
| BE-09 | 구현·개별 운영 검증 근거 | 단일 프로세스 LKG, 86,400/8,640, 동적 mapping. #45 실DB 중단/복구는 과거 완료 증거 |
| BE-10 | **진행 중** | #66. PR #100 병합(10-05 20:27): 2단계 27/27 통과, 중복 ID 409·24MiB 경계·검사 ID 규칙 통일. 3·4단계(DB·보존·복구, FE 연동) 남음 |
| BE-11 | 동결 전 대기 | OpenAPI·migration·DB 문서·최종 구현 일치 → #68 |

BE 미병합 HEAD `3cf2b9e`: 중복 ID 409 차단·파싱 전 24MiB gate·신규 시험·BE-10 계획/결과 문서. 기록된 361 통과·8 skip/실DB 중복2건은 **해당 브랜치의 기존 기록**이다. 기준 SHA와 “#92 미반영” 문구는 현재 dev에 맞춰야 한다. [#66 감사 댓글](https://github.com/yuudong123/CQC/issues/66#issuecomment-5990266299), [Backend 브랜치](https://github.com/yuudong123/CQC/tree/feat/backend).

### MO — 홍유나

| WBS | 판단 | 근거·미충족 조건 |
|---|---|---|
| MO-01 | 규칙·환경 문서 있음 | 실제 Job 설정과 옛 feat/mlops 주석 대조는 #96 |
| MO-02 | 실제 Compose 기반 완료 | 품질4·물류3, 7개 서비스. frontend placeholder 제거, 실제 logistics-web API 모드 |
| MO-03 | **부분 완료 / 증빙 부족** | dev 시험·배포 구현. PR checks/reviews·branch protection 없음, 실제 Jenkins PR 검사/dev 전용 경계 미확인 → #96 |
| MO-04 | healthcheck·기동 순서 구현 | MySQL·Inference→Backend→Simulator·web. 실제 snapshot healthy |
| MO-05 | 모델·볼륨·Secret 기반 구현 | Git 모델·DB·이미지·위치·로그 볼륨. 운영 복구·비밀값 절차는 #70·#72 |
| MO-06 | **환경·선정12장 측정 완료 / 비교 재현 범위 미충족** | 동일 Compose 장수×동시수 비교 근거 부족. DM-06와 함께 #97 |
| MO-07 | 구현·개별 실패 복구 검증 완료 | #69 과거 실서버 정상·빌드 실패 유지·상태 실패 rollback. #94 이후 정확한 배포 SHA는 별도 #96 |
| MO-08 | **완료** | #70 종료(10-05 17:31). 서버에서 Simulator 재시작 후 위치 이어 재생, 장애 토글 OFF 초기화, 로그 한도(현재 1 + 백업 5) 확인 |
| MO-09 | **미완료** | QA 전체 수용 결과 자동화·반복 실행 → #71 |
| MO-10 | 동결 전 대기 | 버전 태그·모델 SHA·실행·복구·Secret 절차 → #72 |

PR #93·94의 checks/reviews가 비어 있다는 사실만으로 사람이 검토하지 않았거나 Job이 잘못 배포한다고 단정하지 않는다. Jenkinsfile의 브랜치 가드 부재와 실제 Job 제한은 #96에서 함께 확인한다.

### 공통 통합·발표

| WBS | 판단 | 다음 조건 |
|---|---|---|
| ALL-01 | 계약·역할 문서 존재 | 네 담당자의 합의 기록과 현재 계약 동결은 별도 |
| ALL-02 | 당시 독립 실행 점검 기록 존재 | 09-23 기준 [기록](ALL-02.md). 현재 전체 수용으로 해석하지 않음 |
| ALL-03 | 1차 실서버 연결 확인·현황 갱신 | #63 이미 종료, 이번 최신 감사·미충족은 #95~99에 분리 |
| ALL-04 | **미완료** | #65 정상100·장애5종·보존·복구·CSV·화면. 0.5건/초 수용조건은 10-08 확정 전 제안 |
| ALL-05 | 예정 10-13 | #76, ALL-04 선행 완료 후 기능 동결 |
| ALL-06 | 예정 10-15~16 | #76, 같은 버전 리허설·발표/카드/배포 일치·main 최종 표시 |
| 발표 준비 | **#64 완료 종료** | d39db97 캡처3장·PDF2종·대본·상처 한계 정정. 실제 리허설·최종 동결과 구별 |
| 물류 LOGISTICS-01~06 | MVP 밖 가상 확장 시연 | #48 결정 유지. Mongo/API·실제 출품 연동을 필수 작업에 새로 넣지 않음 |

## 5. 코드 흐름과 확인한 경계

`data/manifest·split·multiview → training/평가·보정·패키지 → inference HTTP → simulator multipart → backend 판정·제어·DB → quality API → web`를 기준으로 대조했다.

| 경계 | 구현 위치·현재 내용 |
|---|---|
| 데이터/모델 | `src/data`, `src/models`, `src/training`, `src/inference`. group_no 누수 방지, 12장·마스킹, 실제 selected 패키지 |
| 검사·제어 | `src/api/routers/inspections.py`, `services/inspections.py`, `clients/inference.py`. 인증된 Simulator 간격을 검사별 기한에 적용; 연결 단계200ms; 늦은 결과는 bin 변경 없이 진단 |
| DB·보존 | `src/api/db/migrations`, `repositories`, `services/bin_mapping_lkg.py`. 12+1·LKG·이력 순환·검수 이미지 |
| 관제 API | snapshot·이력·CSV·통계·Simulator 설정·review·fault/live images 구현, OpenAPI와 FE 생성기 계약 대조 |
| Simulator | `src/simulator`. 위치·revision·동시성·NEXT·전송 실패 후 지속·내부 HTTP |
| FE | `cqc-logistics-platform/apps/web`. Backend proxy/API 모드·1초 조회·처리 카드·검수·Chart.js·가상 물류 |
| CI/운영 | `Jenkinsfile`, `compose.yaml`, `scripts/ci`, `src/logging_config.py`. rollback·health·로그 회전. PR 검사/Job 경계는 미확인 |

새 #95는 시험 spy용 무제한 기록이 실제 장수명 프로세스에 연결된 문제다. 로컬에서 제어 50,000회에 29.64MiB, late 결과1,000건에 2.74MiB 유지됨을 재현했다. **실서버 RSS 증가량을 측정한 결과는 아니다.**

## 6. 이번 이슈 정리

| 조치 | 번호 | 담당·내용 |
|---|---|---|
| 생성 | [#95](https://github.com/yuudong123/CQC/issues/95) | BE/P2 버그 — 가상 제어·late 진단 목록 무제한 메모리 |
| 생성 | [#96](https://github.com/yuudong123/CQC/issues/96) | MO/P2 요청 — PR 검사·리뷰·dev 전용 배포 증빙 |
| 생성 | [#97](https://github.com/yuudong123/CQC/issues/97) | DM/P2 요청 — 목표 서버 CPU 비교와 MO-06 범위 |
| 생성 | [#98](https://github.com/yuudong123/CQC/issues/98) | DM/P2 요청 — 과거 기록·현행 모델/QA 계약 구분 |
| 생성 | [#99](https://github.com/yuudong123/CQC/issues/99) | BE/P2 버그 — Windows 작업공간 이미지 시험 rename 실패 |
| 완료 종료 | [#64](https://github.com/yuudong123/CQC/issues/64) | 체크박스·산출물 근거 댓글을 기록하고 completed로 종료 |
| 진행 동기화 | [#66](https://github.com/yuudong123/CQC/issues/66) | 미병합3커밋·47항목 미실행·현재 Windows 실패를 댓글로 반영 |
| 관찰·담당 보완 | [#65](https://github.com/yuudong123/CQC/issues/65), [#76](https://github.com/yuudong123/CQC/issues/76) | 조정 담당 지정. #65 실서버200건 결과·미합의 범위 기록 |
| 완료조건 정정 | [#70](https://github.com/yuudong123/CQC/issues/70), [#75](https://github.com/yuudong123/CQC/issues/75) | 로그 현재1+백업5, 재사용 Test의 독립 승인 오해 방지 |
| 유지 | #39·65·66·68·70~76 | 규칙 결정·실운영·최종 수용·동결·모델 평가가 남은 이슈는 닫지 않음 |

## 7. 동결까지 핵심 경로

`#95·99 BE 결함/회귀 확인 + BE 미병합 PR + #96 배포 경계/버전 증빙 + #97 CPU 비교 범위`
→ `#65 수용조건 확정·#70 복구·#71 자동화·#73 8시간 관제`
→ `ALL-04 최종 수용(10-12)`
→ `#76 기능 동결(10-13)`
→ `#68·72·74·75 계약/배포/화면/모델 동결`
→ `ALL-06 리허설·main 표시`

시연·수용시험 중 dev push로 같은 CPU의 Jenkins 부하를 만들지 않는다. 이번 감사에서는 서버 설정 변경·장애 주입·배포·추가 학습·최종 Test를 실행하지 않았다. 새 요청 이슈는 담당자의 착수·PR 검토 절차로 이어진다.

## 8. 문서 위치

- 일정·책임: [WBS](WBS.md), [문서 안내](README.md)
- 감사 증거: [JSON](results/wbs-audit-20261005.json)
- 기능·수용 기준: [QA](reference/ALL/qa-test-cases.md), [요구사항](../planning/requirements.md), [기획](../project-plan.md), [결정](../planning/decision-log.md)
- 발표·문제 해결: [10-08 자료](../중간발표/10월%208일/), [문제 해결 사례](../최종발표/개발%20중%20문제%20해결%20사례.md)
