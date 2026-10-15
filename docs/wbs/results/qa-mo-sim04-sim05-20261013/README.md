# MO SIM-04·05 전용 실환경 시험 결과 (2026-10-13)

SIM-04 및 SIM-05의 원문 기대값을 모두 충족했다. **MO 실행 결과이며 공식 QA 판정·기록표 반영은 BE 검수 후 진행한다.**

## 실행 기준

- 요청: [BE의 SIM-04·05 실제 테스트 요청](https://github.com/yuudong123/CQC/issues/103#issuecomment-6137428894)
- 실행자: 홍유나(Codex), 시험 시각: **2026-10-13T12:36:31.098586+09:00 ~ 2026-10-13T12:40:10.871113+09:00 (KST)**
- Jenkins: **#147 SUCCESS**, 소스 SHA `91e0cd0b191935d0a3359b08285421b9dfe847c1`
- Backend·Inference·Simulator 실행 이미지와 해당 빌드 digest **3/3 일치**. MySQL도 현재 배포 이미지 ID로 고정. [출처](deployment-provenance.json)
- 프로젝트: `cqc-mo103-sim0405-20261013-122650`. 전용 MySQL DB·position·검수 이미지·서비스 로그·internal network. 기존 데이터셋 볼륨만 읽기 전용 공유.
- Windows 루프백 포트 연결이 거부되어, **전용 Backend 컨테이너에서 실제 HTTP로 Backend API 및 Simulator 상태 API를 호출**했다. 요청의 실제 URL·시각·HTTP 응답은 원자료에 보존했다.
- 기동 초기 입력 허용 후 Backend API로 Simulator 정지. jobs 0 및 검사 수 `11`가 3회 연속 같음을 확인한 뒤 시험했다. [준비 조건](startup-drain-summary.json)
- DB migration `20260929_02` 및 bin mapping 13개는 DB 조회 증거에 기록했다. 모델 파일별 체크섬은 [model-checksums.json](model-checksums.json)에 보존했다.

## SIM-04 결과

| 절차 | 실제 결과 |
|---|---|
| R=1, concurrency=2 요청 | HTTP 200, revision=2, 실제 concurrency=2 |
| 이전 R=1, concurrency=1 요청 | HTTP 409 `REVISION_CONFLICT`, revision=2·concurrency=2 유지 |
| 현재 R=2, concurrency=1 복원 | HTTP 200, revision=3, 실제 concurrency=1 복원 |

각 단계 Backend snapshot과 Simulator `/state`의 설정·revision 일치, 검사 수 `11` 유지, jobs 0, `Cache-Control: no-store`를 확인했다. [11개 조건 대조](sim04-checks.json)

## SIM-05 결과

| 입력 행 | HTTP 결과 | 전후 상태 | 실행 결과 |
|---|---|---|---|
| a | 422 INVALID_SETTINGS | 설정·revision·검사 수 불변, jobs 0 | 충족 |
| b | 422 INVALID_SETTINGS | 설정·revision·검사 수 불변, jobs 0 | 충족 |
| c | 422 INVALID_SETTINGS | 설정·revision·검사 수 불변, jobs 0 | 충족 |
| d | 422 INVALID_SETTINGS | 설정·revision·검사 수 불변, jobs 0 | 충족 |
| e | 422 INVALID_SETTINGS | 설정·revision·검사 수 불변, jobs 0 | 충족 |
| f | 422 INVALID_SETTINGS | 설정·revision·검사 수 불변, jobs 0 | 충족 |
| g | 422 INVALID_SETTINGS | 설정·revision·검사 수 불변, jobs 0 | 충족 |
| h | 422 INVALID_SETTINGS | 설정·revision·검사 수 불변, jobs 0 | 충족 |
| i | 422 INVALID_SETTINGS | 설정·revision·검사 수 불변, jobs 0 | 충족 |
| j | 422 INVALID_SETTINGS | 설정·revision·검사 수 불변, jobs 0 | 충족 |

10종 모두 Backend·Simulator 설정 및 revision=3 불변을 확인했다. [입력 10종](sim05-request-matrix.json) · [70개 조건 대조](sim05-checks.json). 각 행의 요청·응답, 전후 Simulator 상태, Backend snapshot, DB 검사 수는 `sim05-a-*`부터 `sim05-j-*` 파일에 보존했다.

## 종료 및 영향 확인

- 시험 종료 설정: running=false, concurrency=1, intervalMs=2000, faults=[], scope=ALL, revision=3.
- **전용 컨테이너 4개 모두 중지**했으며 DB·position·이미지·로그 볼륨은 보존했다. [종료 상태](qa-stopped-runtime.json)
- 종료 시 MySQL·Inference·Simulator는 exit 0, Backend는 Compose의 25초 종료 유예 뒤 exit 137이었다. OOMKilled=false, State.Error는 빈 값이다. 정상 종료 완료를 확인한 것으로 확대하지 않으며 종료 지연 원인은 이번 시험 범위에서 미확정이다. SIM-04·05 완료 및 증거 export 이후의 정리 단계 기록이다. [종료 코드](qa-stop-exit-codes.json)
- 공용 E1 7개 컨테이너의 ID·이미지·StartedAt·실행 상태·health는 전후 동일하고 모두 healthy였다. [전](e1-before.json) · [후](e1-after.json)
- 격리 환경도 E1과 호스트 CPU·메모리·디스크를 공유한다. 전후 상태 확인을 검사 지연 영향이 전혀 없었다는 증거로 확대하지 않는다.
- 시험 실행 단계에서 신규 제품 코드·테스트 코드 수정, build/pull, E1/E2 제어·DB 변경, Commit·Push·이슈 댓글 등록은 수행하지 않았다. 이 문서와 증거는 이후 `feat/mlops`에서 별도 커밋·공유한다.
- #65 정상 100건 FAIL, #117/INS-13 보류, 나머지 Simulator QA 판정은 그대로 유지한다.

## 준비 중단 기록

시험 요청 전 준비 단계에서 두 번 중단됐다. 첫 회차는 Windows 루프백 HTTP 연결 거부, 두 번째는 Simulator 준비 전에 상태를 조회한 실행 스크립트의 준비 대기 처리 부족이다. 컨테이너 내부 HTTP로 전환하고 준비 대기를 보완한 뒤, 같은 전용 환경을 재사용했다. 두 회차의 `cases`는 비어 있고 SIM-04·05 요청은 없다. 중단 결과와 초기 자동 입력·정리 로그는 `setup-attempts/`에 그대로 보존했다. 제품 QA FAIL 회차로 집계하지 않는다.

## 증거와 후속

- [전체 요약](summary.json), [SIM-04 조건](sim04-checks.json), [SIM-05 조건](sim05-checks.json)
- 실제 요청·응답·상태·snapshot·DB 조회, 전용 DB dump, position, Backend·Simulator·Inference·MySQL 로그, 실행 스크립트·Compose 설정 포함
- 전용 비밀번호·토큰은 메모리에서만 사용했고 저장본은 제거·치환 여부를 검사했다. [SHA-256 목록](manifest.sha256)
- BE가 원자료를 검수해 공식 판정 및 QA 기록표를 반영하면 된다. [#103 댓글 초안](issue-comment-draft.md)은 로컬 준비본이다.
