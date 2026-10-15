# [MO] BE 잔여 QA 협조 요청 대응 — 2026-10-12

[BE 요청 댓글](https://github.com/yuudong123/CQC/issues/103#issuecomment-6119487084)에 대한 배포 확인·통계 CSV 읽기 검증·기존 증거 조사·격리 환경 준비 자료. 실행자 홍유나. 실제 신규 장애 시험이나 공식 QA 판정 변경 없이, 지금 확인 가능한 요청과 후속 절차를 구분했다.

## 대응 상태

| 요청 | 수행 결과 | 남은 일 |
|---|---|---|
| OPS-13 최신 배포·수정 포함 근거 | #143 SUCCESS / 실제 Backend 소스 `0094807`·수정 `ee2987f` 포함 확인 | BE의 최종 QA 판정 |
| OPS-13 날짜 없는 CSV | 16:25:13~16:25:15 KST 읽기 확인, 18개 대조 항목 충족 | 기존 기간/분 CSV와 BE 최종 취합 |
| SIM-03·12 기존 증거 | 10/07 재시작 후 기본값·이어 재생 증거 추출 | 명시적 정지 10초·3000/1000ms 각 60초 부족 |
| SIM-06 기존 장애 자료 | 10/06 상세 회차에서 이미지 개수·제어 시도 개수 추가 확보 | 개별 이미지 목록·제어 행·성공 bin 집계·DB_ERROR 연결 로그 부족 |
| 전용 Simulator·Backend·MySQL | 이미지 고정·독립 저장소·네트워크 구성 작성, Compose 정적 검증 12개 충족 | BE와 사용 환경·일정 확정 및 실제 기동/시험 |
| SIM-04·05·07·09·11 후속 준비 | 항목별 절차·원자료 목록·SIM-05 10종 요청표·일정안 작성 | 실제 실행 및 FE 웹 경고 증거 |

## 1. 최신 E1 배포 확인

- 확인 시각: **2026-10-12 16:22:06 KST**
- Jenkins `CQC-CICD #143`: **SUCCESS**, 시작 **14:24:08.779**, 완료 **14:37:57.400 KST**
- checkout SHA: `0094807a159e4bedadd2700fd689b3c848ee803f`
- OPS-13 수정 SHA: `ee2987fb820e2fa1654184edbfdfddffaf9d29d4`
- `git merge-base --is-ancestor`로 수정 커밋의 checkout SHA 포함 확인
- Backend·Inference·Simulator·Frontend 실행 이미지 ID와 #143 빌드 manifest digest **4/4 일치**
- 실제 Backend `/app/src/api/services/quality_operations.py`와 checkout SHA 파일의 바이트·SHA-256 일치
- 파일 SHA-256: `04bbe5f4f20b1c3ac029ec6857caef513679ef930cb17189c99e43db53d76427`
- Backend·Inference·Simulator·Frontend·MySQL healthy 확인

`deployment-provenance.json`, `jenkins-builds.json`, `jenkins-selected-log.txt`, `deployed-quality-operations.py.txt`에 근거 보존. Jenkins 내부 `docker info`는 35초 timeout으로 daemon ID를 이번 회차에 재대조하지 못했다. 따라서 daemon 동일성 추가 확인과 실행 이미지 digest·파일 바이트 일치 증거를 구분한다.

실시간 Jenkins queue API는 HTTP 403으로 확인 불가. 영속 `queue.xml`은 0항목이나 실시간 대기열·executor 부재를 증명하지 않는다. 날짜 없는 CSV 조회 전 **사용자가 측정·서버 QA·새 빌드 모두 없음을 확인**했고, 조회 직후 최신 빌드 번호는 #143으로 유지됐다.

## 2. OPS-13 날짜 없는 CSV 읽기 검증

- 실행: **2026-10-12 16:25:13.080~16:25:15.501 KST**
- GET 2회만 수행: 날짜 없는 `statistics.csv`와 같은 업무 날짜·동일 `snapshotAt`의 통계 JSON
- 날짜 없는 CSV에서 `CULTIVAR_SUSPECT`, `QUALITY_SUSPECT`, `OTHER` 각 **정확히 1행**, 모두 **0** 출력
- 세 집계값은 동일 snapshot JSON과 일치
- `today`, `grades`, `varieties`, `bins`, `suspicions` 섹션 확인
- total **11097**, normal **11068**, excluded **29**, reinspection **1179**의 CSV·JSON 일치
- 재검사율 **0.10624493106244931**, 평균 추론시간 **171.5021681423925ms**의 CSV·JSON 계산값 일치
- 헤더 `mode,date_kst,section,key,value,last_saved_at`, `mode=BACKEND`, BOM·CRLF·모든 칸 따옴표 확인
- 총 **18개 검토 항목 모두 충족**. 마지막 평균 추론시간 대조는 이미 확보한 두 응답으로 계산했으며 추가 요청 없음

원문 바이트 `ops13-date-free-statistics.csv`, `ops13-same-day-statistics.json` 및 `ops13-review.json` 보존. 과거 기간/분 단위 CSV 증거는 재사용 대상으로 유지했고 이번 회차에서 다시 요청하지 않았다. 신규 검사·설정 PUT·DB 쓰기 없음. 이번 자료는 BE의 최종 판정용이며 공식 QA 기록표·집계·#65 FAIL을 변경하지 않았다.

## 3. SIM-03·12 기존 증거

10/07 `cqc-mo09-e2-final-20261007`, Jenkins #115 / 소스 `328baaaf702f42687204b9d904815676479ae3e0`의 재시작 원자료를 바이트 그대로 복사했다.

- 재시작 후 `faults=[]`, `concurrency=1`, `intervalMs=2000`, `running=true`, `revision=0`
- 정지 전 마지막 dataset index 20, 재시작 후 첫 세 묶음 index **21·22·23** 확인
- 현재 E1 #143과 다른 회차이며 현재 성능/설정 시험 결과로 합치지 않음

이 자료는 재시작 기본값·위치 복구의 부분 근거이다. **SIM-03 명시적 정지 10초 관찰·진행 중 최대 1건·unhealthy·수동 재개 다음 묶음**과 **SIM-12 3000/1000ms 각각 60초·대기열·속도 변경 후 재시작 복원**의 전체 원자료는 확인한 범위에서 찾지 못했다. `sim03-sim12-evidence-review.json`에 부족 조건을 명시했다.

## 4. SIM-06 기존 장애 증거 보완

BE가 인용한 10:35 회차와 별도로 **10/06 11:32:53 KST**, 프로젝트 `cqc-mo09-e2-final-20261006`의 상세 원자료를 찾았다. 원본 메타데이터의 deployed SHA는 **unverified**, 당시 script SHA는 `3504195`이며 둘을 동일 배포 SHA로 간주하지 않는다. 일부 과거 status 문자열의 인코딩 손상은 원문 보존했고 공식 판정의 근거로 사용하지 않았다.

| 장애 | 상세 회차의 보존 수치 | 아직 없는 직접 근거 |
|---|---|---|
| INFERENCE_TIMEOUT | 지정 검사 ID·이미지 개수 12·제어 개수 1 | 검사별 이미지 ID 12개·metadata·파일 연결 |
| INFERENCE_ERROR | 지정 검사 ID·이미지 개수 12·제어 개수 1 | 검사별 이미지 ID 12개·metadata·파일 연결 |
| CONTROL_REJECTED | 지정 검사 ID·제어 개수 2 | 정상 bin 거부→재검사 성공의 순서·필드별 control_attempts |
| CONTROL_NO_RESPONSE | 지정 검사 ID·제어 개수 1 | 개별 제어 행·재시도 추적·성공 bin 통계 제외 |
| CONTROL_FAILED | 지정 검사 ID·제어 개수 1 | 개별 제어 행·재시도 추적 |
| DB_ERROR | NEXT 해제 revision·후속 정상 검사 ID | 오류 검사 ID·저장 실패 로그·후속 저장 연결 |

`historical-detailed-run.json`, `historical-detailed-fault-evidence.json`, `sim06-evidence-review.json`에 수치와 ID를 분리 보존. 요약 개수만으로 전체 원문 조건 충족을 확정하지 않는다.

`docs`, `outputs`의 JSON/JSONL/SQL/CSV/log/text/Markdown를 지정 ID로 검색했으나 위 개별 DB export·이미지 ID 목록·DB_ERROR 연결 로그를 추가 확보하지 못했다. 다른 컴퓨터·WSL 내부·오프라인 DB 볼륨·바이너리 archive는 조사하지 않았으며 자료 삭제로 단정하지 않는다. `historical-search.json`에 검색 범위를 기록했다.

별도 10/06 MySQL 복구 원자료는 정상 판정/가상 제어 성공과 `persistence_status=FAILED`, 복구 후 `SUCCEEDED`, Backend·Simulator 컨테이너 동일성을 보여준다. 다만 SIM-06 주입 회차와 다른 프로젝트이며 새 요청의 **정확히 20초 중단·30초 관찰**을 충족한 것으로 확대하지 않는다. 이 부분 근거는 `historical-recovery-evidence.json`에 보존했다.

## 5. 전용 환경 준비 결과

- 현재 Docker: **8 CPU**, 메모리 **16,641,286,144 bytes**
- 확인 시 C 여유 약 **17.81GiB**, D 여유 약 **329.96GiB**. 순간 상태이며 장시간 시험의 충분성을 보장하지 않음
- 기존 데이터셋: **869묶음**, 첫·마지막 묶음 각각 이미지 **12장** 읽기 확인
- index SHA-256 `dc866e0ccd91f8cff9ce9a523d1707c4df678d564ace24016c5344537ba7e959`
- 가상 당도 CSV SHA-256 `72377db48cc9ff5bd4f4978364e41b2c1e9807cb99eebb428a6a22f1a851c346`
- 현재 모델: `cqc-apple-separate12-focal-v2-cal-20260930`, CPU·12 views, 기존 checkpoint `b254206e4091732a49c5db02c12e5fb6dc3d996dbce694c2e82d442a2ba8753a`
- 모델 health의 approval_status 원문은 `unverified_candidate`로 보존. 이번 작업에서 모델 승인을 새로 판정하지 않음
- 고유 프로젝트 `cqc-mo103-e2-20261012`, 루프백 포트 28000/28001/28002, 전용 DB·position·이미지·로그·내부 네트워크 구성
- 이미지 ID 고정, build/pull 없음, 기존 데이터셋만 RO 공유
- `docker compose config` 정적 확인 **12개 모두 충족**, 포트 미사용·프로젝트 볼륨 미생성 확인
- 실제 신규 컨테이너·볼륨 생성·기동·재시작·장애 주입은 미실행

현재 실제 Simulator 코드에 `SIMULATOR_AUTO_START=false` 기능이 없음을 확인했다. 정지 기동이 필수라면 별도 제품 옵션 협의가 필요하다. 기동 후 새 전용 DB에서만 입력을 허용하고 기존 설정 API로 정지하는 대안은 BE와 협의하도록 준비했다.

기동 시 같은 호스트의 CPU/RAM/디스크는 E1과 공유하므로 E1 100건 측정과 겹치지 않는 실행 창을 확보해야 한다. `execution-plan.md`에 항목별 순서·원자료·복원·일정안을 정리했고, `sim05-request-matrix.json`에 10종 입력표를 작성했다. 일정안은 예약 확정이 아니다.

## 파일·공유 안내

- 배포: `deployment-provenance.json`, `jenkins-builds.json`, `jenkins-selected-log.txt`, `deployed-quality-operations.py.txt`
- CSV: `ops13-date-free-statistics.csv`, `ops13-same-day-statistics.json`, `ops13-review.json`
- 기존 자료: `historical-*.json`, `sim06-evidence-review.json`, `sim03-sim12-evidence-review.json`
- 환경: `isolated-compose.json`, `isolated-compose-rendered-redacted.json`, `isolated-preflight.json`, `dataset-check.json`, `volume-availability.json`, `resource-preflight.json`
- 후속: `execution-plan.md`, `sim05-request-matrix.json`, `issue-comment-draft.md`
- 무결성: `.gitattributes`, `manifest.sha256`, `verification.json`

공유 경로는 `feat/mlops`의 `docs/wbs/results/qa-mo-be-followup-20261012/`이며 공유 ZIP은 `outputs/qa-mo-be-followup-20261012.zip`에 생성했다. 이번 수집은 기존 배포·CSV 읽기 확인·보존 증거 조사·구성 준비로 수행했다. 판정 및 추가 실행 여부는 BE가 자료와 환경안을 검토한 뒤 확정한다.
