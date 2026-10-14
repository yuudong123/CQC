# MO SIM-06·09 기존 원자료 보존 위치 조사 (2026-10-14)

**추가 조사10회를 완료했고, 마지막 E1 읽기 전용 DB 대조에서 무응답 제어11행·추론 timeout/error 제어2행을 새로 확보했다. 기존 SIM-07의 CONTROL_REJECTED9행·INFERENCE_TIMEOUT6행과 함께 SIM-06 대체 후보이며 회차·환경 인정은 미확정이다. 원래 E2 상세·DB_ERROR 연결 로그·SIM-09 자동 저장 복구/무재시작 원자료는 여전히 미확보다.** 새 검사·장애 주입·서비스 변경은 하지 않았고 공식 QA37/44를 유지한다. [10회 조사와 신규 실제 행](ten-pass/README.md).

요청: [BE 잔여 SIM QA 후속 요청](https://github.com/yuudong123/CQC/issues/103#issuecomment-6159100555). 조사 완료: 2026-10-14T11:04:23.294798+09:00 KST. 이 문서는 10/06 시험을 10/14에 다시 실행한 결과가 아니다.

## 1. BE가 바로 열람할 기존 원자료

| 항목 | 로컬 원본 | 기존 Git 보존본 | 확인 |
|---|---|---|---|
| SIM-06 상세 회차 | `outputs/mo09-e2-detailed-20261006/fault-evidence.json` | [고정 커밋 JSON](https://github.com/yuudong123/CQC/blob/d6de6b846472c71ef6ed08d4e5cfc4ae4ad2c6c2/docs/wbs/results/qa-mo-be-followup-20261012/historical-detailed-fault-evidence.json) | 원본·보존본 바이트 동일 |
| SIM-09 복구 회차 | `outputs/mo09-e2-recovery2-20261006/recovery-evidence.json` | [고정 커밋 JSON](https://github.com/yuudong123/CQC/blob/6dd8853d41791d0491317a57f88e766b692238ac/docs/wbs/results/qa-mo-20261007-evidence/20261006-recovery-recovery-evidence.json) | 원본·보존본 바이트 동일 |
| SIM-09 중복 보존본 | 같은 원본 | `docs/wbs/results/qa-mo-be-followup-20261012/historical-recovery-evidence.json` | 위 원본과 바이트 동일 |

[복사·해시·기존 보존본 대조](source-index.json), [조건별 필드 대조](condition-map.json). `preserved/`는 원본을 바이트 그대로 복사했다. `original-results`는 당시 자동 결과이며 공식 PASS 근거로 사용하지 않는다. SIM-09의 최초 전체 통과 표시와 INS-13 통과 표시는 10/07 [재판정 결과](preserved/sim09-corrected-results.json)에서 각각 차단·실패로 구분돼 있다.

## 2. SIM-06: 확보된 것과 미보존 필드

프로젝트 `cqc-mo09-e2-final-20261006`, 10/06 11:32:53~11:33:23 KST. 당시 metadata의 script HEAD는 `3504195`, working_tree_dirty=true, 배포 SHA는 unverified다. 현재 배포·10/13 BE WSL 시험·10/14 Docker 회차와 합치지 않는다.

| 장애 | 보존된 장애 검사 ID | 제어 횟수 | 후속 정상 검사 ID |
|---|---|---:|---|
| INFERENCE_TIMEOUT | 5e85ae9c-0549-47a4-8445-eca477465a2e | 1 | d6d5d20c-02db-493d-8de4-baa3ca5434fd |
| INFERENCE_ERROR | dcec597f-4bc8-4b1f-bb2e-8f04a7476974 | 1 | bb57f84e-dca3-4281-9c67-92d5273d7948 |
| DB_ERROR | 미보존 | 미보존 | 74927e8d-01e6-41e6-b257-8b866cbdabf7 |
| CONTROL_REJECTED | 59927979-f841-45ea-ac1f-90c7537b3fae | 2 | 61a0923e-bee6-4b5f-bba0-5b639c6c863b |
| CONTROL_NO_RESPONSE | 0693b8aa-8328-4c5e-b7e8-907bdc6eb14b | 1 | 581d56a1-337a-42cf-80c6-bb0fe574320c |
| CONTROL_FAILED | 29d70749-2320-4733-8be4-2a483e532851 | 1 | a440c461-8225-4932-a641-b527e2232150 |

- 추론 timeout/error의 공개 장애 상태·저장 성공·재검사 bin, 장애 이미지 **각 12장이라는 개수**는 보존됐다. 개별 이미지 ID·목록·해시는 이 회차에 없다.
- CONTROL_REJECTED는 FALLBACK·재검사 bin 및 제어 **2회**, CONTROL_NO_RESPONSE·CONTROL_FAILED는 제어 **각 1회**라는 개수가 있다. `control_attempts` 개별 행의 attempt_no·명령·bin·응답·순서·시각은 없다. 개수를 원본 행 전체나 완전한 재시도 추적으로 바꾸지 않는다.
- CONTROL_NO_RESPONSE의 성공 bin 통계 제외를 입증할 전후 집계는 없다.
- DB_ERROR는 revision 5→6 자동 해제, fault_row=null, 후속 정상 `74927e8d-...`만 있다. **장애 검사 ID와 그 ID를 저장 실패 로그에 연결하는 자료는 미보존**이다. 이력 부재만으로 오류 검사의 추적 조건을 충족하지 않는다.
- [현재 수집기 사본](preserved/sim06-current-collector.py)은 COUNT(*)와 이미지 목록의 len만 JSON에 남기는 구조다. 당시 실행 스크립트 해시가 없어 이 사본을 정확한 실행 파일로 단정하지 않는다. 원자료 자체의 필드 한계와 함께 참고한다.

## 3. SIM-09: 직접 probe와 자동 입력 증거 구분

프로젝트 `cqc-mo09-e2-recovery2-20261006`, 시작 `2026-10-06 14:55:24 KST`. source_sha는 `1f521804`, 실행 이미지 SHA 출처는 당시 미확인이다.

| 요청 | 검사 ID | 관찰 결과 |
|---|---|---|
| DB 중단 중 직접 probe | `qa-mo09-mysql-down-e87f0b64e1624fbc` | HTTP200, 정상 DEMO_BIN_12·제어 SUCCEEDED·저장 FAILED, **4.938초** |
| DB 복구 후 직접 probe | `qa-mo09-mysql-recovered-d6ecd322e9494b34` | HTTP200, 정상 DEMO_BIN_12·제어/저장 SUCCEEDED, 1.594초 |

- Simulator `/health`의 running=true, lastSeenAt **1791266156248→1791266194501**은 중단 구간의 입력 지속을 뒷받침하는 부분 증거다. 자동 검사별 ID·판정·제어·저장 실패 로그 연결은 없다.
- 복구 성공 ID는 `qa-mo09-mysql-recovered-...` **직접 probe**이며 자동 재생 검사 ID가 아니다. 복구 후 30초간 자동 저장 수 증가·자동 검사 ID 목록은 없다.
- Backend·Simulator container ID와 비교 결과 true는 남았다. **동일 ID는 재생성 없음과 관련되며, `docker restart`는 ID를 유지하므로 무재시작 증거가 되지 않는다.** StartedAt·RestartCount·Docker events의 전후 기록이 없다. 기존 요약의 '재시작 없이' 표현을 원자료가 완전히 증명한다고 확대하지 않는다.
- 수집 코드에는 `time.sleep(20)`이 있으나 MySQL 실제 stop/start 완료 시각과 복구 후 30초 관찰열이 없다. 코드상의 대기를 동일 장애 회차의 정확한 실행 시각 증거로 대체하지 않는다.
- health 응답의 status=ok는 `components.Simulator.status`의 연속 기록이 아니다. 해당 공개 상태가 error로 변하지 않았다는 직접 관찰은 미확인이다.
- INS-13의 4.938초 FAIL·수정 보류, SIM-09 공식 보류/차단을 유지한다.

## 4. 추가 자료 검색 범위

- `docs`·`outputs`의 ignored 파일까지 포함해 관련 검사 ID **24개**를 검색했다. 개인 포트폴리오 복제본·node_modules·.git·이번 조사 생성물은 제외. [검색 기록](text-search.json).
- 압축본 **2개**의 텍스트 자료를 추출 없이 검사했다. 기존 부분 JSON의 중복 보존본만 찾았다. [압축본 검색](archive-search.json).
- 공용 E1 Backend·Simulator 보존 error.log에는 10/06 기록이 있지만 대상 24개 ID의 문자열 일치는 0건이다. 별도 E1 회차의 로그를 E2 회차의 연결 로그로 사용하지 않는다. [로그 파일 해시·범위·검색 수](persistent-log-search.json). 수집 시점의 파일 metadata이며 로그 원문 전체를 새 증거로 복제하지 않았다.
- 현재 Docker 컨테이너·볼륨 목록에는 해당 10/06 E2 프로젝트 이름/label의 보존 자원이 없다. 과거 삭제를 단정하지 않는다. [컨테이너](docker-container-inventory.json), [볼륨](docker-volume-inventory.json).
- 10/06 생성 anonymous MySQL 볼륨 7개와 비활성 `cqc_mysql_data` **총 8개**를 읽기 전용·network none helper로 확인했다. 해당 schema들은 주로 `cqc_test`/`cqc_retention`이며 선택한 검사·제어·오류 `.ibd` 파일의 대상 ID literal 일치는 0건이었다. **DB 서버를 시작하거나 논리 행 복구를 하지 않았다.** 압축·삭제 페이지·redo/binlog 전체 복원 및 다른 컴퓨터까지 검사한 것이 아니다. [읽기 전용 조사](cold-volume-search.json).
- Ubuntu의 /home·/root·/tmp 하위 depth3까지 CQC 이름의 디렉터리를 찾았지만 후보가 없었다. WSL 전체 내용 검색이나 BE의 D 전용 PC 조사로 확대하지 않는다. [WSL 경로 조사](wsl-location-search.json).
- E1 7개 서비스의 ID·이미지·StartedAt·health 전후 동일 및 모두 healthy. [전](e1-before.json) · [후](e1-after.json).

## 4.1 확대 조사: 당시 실행 기록 및 Git 비참조 객체

앞선 파일·볼륨 검색에 더해 10/06·10/07 Codex의 **원본 도구 출력**을 검색했다. 전체 대화나 추론은 복제하지 않고 아래 서비스 상태·정리 출력만 별도로 회수했다.

- **SIM-06:** 2026-10-06 **11:34:01 KST** 도구 완료 출력에 전용 `mysql_data`·`backend_logs`·`simulator_logs`·이미지·position 볼륨의 `Removed`가 기록돼 있다. [당시 정리 출력](recovered/sim06-compose-cleanup.txt).
- **SIM-09:** 2026-10-06 **14:57:25 KST** 완료 출력에도 해당 회차 DB·서비스 로그·이미지·position 볼륨의 `Removed`가 기록돼 있다. [당시 완료·정리 출력](recovered/sim09-run-completion-and-cleanup.txt).
- 이는 **특정 전용 볼륨 제거 사실의 직접 기록**이다. 다른 곳의 백업까지 없었다거나 디스크의 삭제 페이지 복원이 불가능하다는 뜻은 아니다. 이전 현재 볼륨 목록만으로는 제거 여부를 단정하지 않았으나, 이번에는 당시 출력으로 두 회차의 제거를 확인했다.
- SIM-09 14:56:57 KST의 `docker ps`에는 Backend Up2minutes·Simulator UpAboutaminute 상태가 남아 있다. [당시 상태](recovered/sim09-during-recovery-container-status.txt). 일부 시점의 연속 가동을 뒷받침하지만 정확한 StartedAt/RestartCount 전후 및 전체 시험의 무재시작 증거를 대체하지 않는다.
- 원본 session 파일·해당 JSONL 행 해시·tool call ID·UTC 시각·추출 필드를 [출처 기록](recovered/session-provenance.json)에 보존했다. 저장된 도구 출력 문자열을 그대로 추출했으며, 과거 터미널 인코딩 손실과 잘림은 보정하지 않았다.
- 대상 ID24개가 포함된 10/06·10/07 도구 출력 **7개**를 확인했지만 공개 요약·문서 출력이며 개별 제어 `attempt_no` 행이나 성공 bin 전후 통계가 추가로 보존된 출력은 찾지 못했다. DB_ERROR 목표 ID·실패 로그와 복구 후30초 자동 저장 관찰열도 회수하지 못했다. [검색 인덱스](recovered/session-target-search.json).
- Git의 비참조 blob **396개·총2,860,946바이트**를 모두 검사했다. 관련 blob1개는 기존 SIM-09 복구 JSON과 값이 완전히 같으며 추가 필드가 없다. [Git 객체 검색](recovered/unreachable-git-search.json) · [동일성 대조](recovered/orphan-comparison.json).
- 별도 Documents/Codex 작업 폴더의 CQC 인계 ZIP(3파일), 관련 텍스트 폴더, 휴지통의 CQC 조사 메모에서도 해당 상세 행·로그를 찾지 못했다. [인계 ZIP](recovered/handoff-archive-search.json) · [CQC 휴지통 메모 검색](recovered/recycle-search.json). 무관한 개인 DB·문서 내용은 조사하지 않았다.
- 최초 remote 확인은 SIM-06/09 파일 이름 중심이었다. 이 범위만으로 다른 QA 폴더의 재사용 가능한 증거가 없다고 판단할 수 없으며, 이후 Git 원자료 전체 대조에서 아래 SIM-07 제어 상세를 추가 발견했다. Jenkins build 보관 경로의 SQL/evidence/recovery/ZIP 후보에서는 추가 자료를 찾지 못했다. BE-09/#45의 기술 검증 요약은 별도 회차다.

**10/06 회차 복원 결론:** 당시 실행 기록에서 회수한 것은 상태·볼륨 제거 기록이며, 원래 회차의 제어 상세·DB_ERROR 연결 로그·자동 저장 복구 원자료를 복원하지 못했다. 별도 Git 회차에서 찾은 대체 후보는 아래와 같이 구분한다.

## 4.2 Git 최신 브랜치·PR 원자료 재조사

사용자 확인에 따라 공유 경로는 없고, Git을 원자료 확인 경로로 사용했다. [PR #131](https://github.com/yuudong123/CQC/pull/131)은 **10/14 08:54:23 KST 병합 완료**, 변경 파일 133개다. 그중 BE SIM 원자료 폴더는 SIM-03 24개·SIM-07 42개·SIM-11 22개·SIM-12 42개로 **총 130개**다. 현재 Backend 고정 HEAD는 `9723907f2a9cd3c4cb747ca80bc9b72892e2d4d0`이다. 과거 댓글과 일부 원본 README의 '미커밋·미Push'는 작성 당시 상태이며 현재 Git 공개 상태를 뜻하지 않는다. [게시 파일 전체 목록](git-review/pr131-published-files.json).

BE는 **핵심 파일을 선별 보존**했다. SIM-07 README에는 원본 94개 중 반복 누적 history·전체 DB·자원 로그·계측 스크립트·대용량 이미지를 제외했다고 명시돼 있다. 따라서 원본 전부가 Git에 올라왔다고 단정할 수는 없다. 4개 폴더의 Git 보존본 manifest 121항목을 실제 Git blob 바이트로 검증했다. 119항목 일치, SIM-11/12의 `.gitattributes` 2개는 Git LF와 manifest CRLF 해시의 차이이며 CRLF로 계산하면 일치한다. 시험 데이터 파일의 해시 불일치는 없다. 원본·manifest는 수정하지 않았다. source-manifest는 Git에 없는 원본 파일도 포함하므로 Git 보존본 manifest와 구분했다. [해시 검증](git-review/be-core-manifest-verification.json).

| 새로 확인한 Git 원자료 | 내용 | SIM-06 재사용 한계 |
|---|---|---|
| [CONTROL_REJECTED 개별 행](https://github.com/yuudong123/CQC/blob/9723907f2a9cd3c4cb747ca80bc9b72892e2d4d0/docs/wbs/results/qa-be-sim07-local-20261013/independent/CONTROL_REJECTED-joined.json) | 장애 검사 5건·제어 9행. 4건은 attempt 1 정상 bin REJECTED→attempt 2 재검사 bin SUCCEEDED, 1건은 이미 재검사 대상이라 REJECTED 1행 | WSL ALL 회차. Docker NEXT 자동 해제 조건을 대신하지 않으며 BE·DM 인정 필요 |
| [INFERENCE_TIMEOUT 개별 행](https://github.com/yuudong123/CQC/blob/9723907f2a9cd3c4cb747ca80bc9b72892e2d4d0/docs/wbs/results/qa-be-sim07-local-20261013/independent/INFERENCE_TIMEOUT-joined.json) | 장애 검사 6건·제어 6행, 각 attempt 1 재검사 bin SUCCEEDED·오류 행 연결 | 같은 환경·scope 인정 필요. 원래 E2 회차 행이나 이미지 원본은 아님 |
| [E1 공개 CSV](https://github.com/yuudong123/CQC/blob/9723907f2a9cd3c4cb747ca80bc9b72892e2d4d0/docs/wbs/results/qa-be-proxy-20261008/supplement/ops10-inspections.csv) | CONTROL_NO_RESPONSE 공개 검사 11건 | 개별 명령 행·재시도 부재·성공 bin 통계 제외의 전후 집계가 아님 |
| [E1 장애 이미지 metadata](https://github.com/yuudong123/CQC/blob/9723907f2a9cd3c4cb747ca80bc9b72892e2d4d0/docs/wbs/results/qa-be-proxy-20261008/supplement/img02-fault-images.json) | `qa-be-10081626s-ins01-FS-15.0` TIMEOUT 이미지 ID 12개·index 0..11 | 다른 E1 회차의 대체 인정 필요. 이미지 바이트 해시는 미확보 |

제어 명령의 ID·attempt_no·bin·응답·시각을 직접 대조했고 원본 Git JSON 8개를 바이트 그대로 보존했다. [출처·해시](git-review/source-index.json) · [검사별 제어 대조](git-review/sim06-alternative-controls.json). 서로 다른 회차를 이어 하나의 시험으로 만들지 않았다. 동시 ALL 회차의 `result.json=TEST_INTERRUPTED`는 BE가 수집기 단일 장애 비교 조건 오류로 재검수한 자료이며, [원본 review.json](git-review/combined--review.json)을 함께 확인했다. 공식 QA 판정은 변경되지 않았다.

현재 origin 모든 브랜치의 `docs/wbs/results` **고유 Git blob 623개**를 조건 문자열과 구조로 확인했다. DB_ERROR·CONTROL_NO_RESPONSE·CONTROL_FAILED·SIM-06/09 일치 blob 20개는 기존 요약·문서·스키마·자동 테스트 결과·공개 CSV 등이며, 추가 DB_ERROR 검사/실패 로그 연결, NO_RESPONSE/FAILED 개별 제어 행, SIM-09 동일 장애 회차의 자동 저장 복구 시계열은 찾지 못했다. 전체 과거 커밋·Git LFS·binary artifact를 전부 복원한 조사로 확대하지 않는다. [브랜치 SHA·파일별 검색 인덱스](git-review/remote-condition-search.json).

## 4.3 로컬 실행 이력·이미지 metadata 추가 대조

CQC 관련 다른 채팅 16개의 도구 item 1,294개, 전체 명령 완료 출력 1,062개와 과거 실행의 보존 runtime log 1,000개를 읽기 전용으로 확인했다. 기존 원래 회차의 상세 필드는 추가 확보하지 못했다. 전체 대화·추론·DB는 복제하지 않고 검색 metadata만 보존했다. [앱 도구 이력](second-pass/app-history-search.json) · [명령 출력](second-pass/full-execution-output-search.json) · [runtime 검색](second-pass/runtime-log-search.json).

E1 TIMEOUT 이미지 metadata 12개는 원본 300개 목록에서 추출해 ID 중복 없음·index 0..11을 확인했다. 현재 E1 저장 폴더에서 해당 12개 이미지 그룹은 발견되지 않아 이미지 내용 해시는 확보하지 못했다. 이미지 정리를 유발할 수 있는 목록 API는 호출하지 않았다. 이 snapshot의 INFERENCE_ERROR 해당 검사에는 1개 항목만 남아 있어 ERROR 12장 전체 목록으로 사용하지 않는다. [추출 결과](second-pass/e1-image-alternative.json) · [원본 목록](second-pass/e1-img02-source.json) · [현재 파일 보존 확인](second-pass/e1-file-preservation-check.json).

발견한 Docker VHDX 백업은 9/30 수정본으로 10/06 시험 이전이다. 활성 Docker 디스크를 복사·마운트하거나 전체 복구 작업을 하지 않았다. [백업 metadata](second-pass/disk-backup-metadata.json).

## 4.4 추가 조사: 전체 Git 이력·문서 밖 원자료·CI 보관함

현재 브랜치 끝뿐 아니라 이 PC의 Git에서 도달 가능한 커밋 **434개**에 걸쳐 `docs`·`outputs`의 텍스트 blob **1,258개·24,519,120바이트**를 조사했다. 장애 이름 외에도 NO_RESPONSE/FAILED 상태, 저장 실패 문구, 제어 행 구조를 검색했다. `docs/wbs/results` 밖의 아래 자료를 발견했다. [전체 이력 검색](deeper-pass/historical-git-search.json) · [삭제 파일 이력](deeper-pass/deleted-file-history.json). 삭제 이력에서 QA 원자료 파일 삭제는 발견되지 않았다. 이 범위는 로컬 Git refs의 도달 가능 이력이며 모든 컴퓨터의 비공개 stash/ignored 원본을 포함하지 않는다.

**새 원자료:** [BE-10-2-local-evidence.jsonl](https://github.com/yuudong123/CQC/blob/9723907f2a9cd3c4cb747ca80bc9b72892e2d4d0/docs/wbs/BE-10-2-local-evidence.jsonl)은 491개 기록이며 10/05 커밋 `02cdb90`부터 Git에 있다. BE 설명에 따라 최종 회차 `be10-2-63f2ca4e`의 다음 2건을 선택했다. 초기 fixture 실패·다른 회차 기록까지 전체 PASS로 해석하지 않았다.

| 원본 행 | 검사 ID | 원자료 확인 |
|---|---|---|
| 476 | `be10-2-63f2ca4e-control-NO_RESPONSE` | API·검사 DB·history·CSV 모두 무응답, DB error_code CONTROL_NO_RESPONSE, 정상 DEMO_BIN_02·저장 SUCCEEDED |
| 477 | `be10-2-63f2ca4e-control-FAILED` | API·검사 DB·history·CSV 모두 FAILED, DB error_code CONTROL_FAILED, 정상 DEMO_BIN_02·저장 SUCCEEDED |

선택한 원본 JSONL 행을 바이트 그대로 [보존](deeper-pass/be10-final-control-outcomes.jsonl)하고 원본 파일/행 SHA·줄 번호를 [출처 대조](deeper-pass/be10-source-review.json)에 기록했다. **Mock Inference·MockVirtualControl·직접 ASGI 요청·1-frame fixture**의 실제 검사 DB 저장 시험이다. Simulator NEXT 또는 실제 Inference 12-frame E2 시험으로 인정하지 않는다. 정상 예측 통계 제외 플래그 false와 성공 bin 통계 포함 여부도 구분한다.

원본 491행의 [EFFECTS-AUDIT](deeper-pass/be10-effects-audit.jsonl)는 API/DB/control/CSV 일치 true 및 최종 통계 total489를 남겼다. 시험 코드가 무응답·실패의 요청1회/제어 count1을 assert하지만 **명령별 attempt_no·bin·응답 시각을 JSONL로 내보내지 않는다**. audit는 normal/excluded/inferenceCount를 대조하며 **성공 bin 전후 제외를 별도로 assert/export하지 않는다**. 저장된 단일 `db` 객체 412건만으로 total489 전체 통계를 재구성할 수도 없으므로, 이 boolean·집계를 원래 SIM-06의 개별 제어 행·성공 bin 제외 원자료로 확대하지 않는다.

**별도 원본 위치를 더 확인했다:** [BE-10 결과 §11.1](https://github.com/yuudong123/CQC/blob/9723907f2a9cd3c4cb747ca80bc9b72892e2d4d0/docs/wbs/BE-10-results.md#111-환경증거와-판정-범위)은 `outputs/be10-3/acceptance-evidence.jsonl`, `core-evidence.jsonl`, `error.log`, `mysql.log`, `container-recovery.json`에 DB_ERROR 주입·실제 DB 중단·검사/로그 연결 원본이 있다고 설명한다. 이 PC에는 해당 폴더가 없고 Git 이력에서도 파일을 찾지 못했다. 문서의 기술 검증 표를 원본 로그 확보로 표시하지 않는다.

[#117 최종 조사 댓글](https://github.com/yuudong123/CQC/issues/117#issuecomment-6051555754)은 계측 회차 HTTP4.559266초 FAIL, DB await3336.707ms, 별도 DNS 측정 및 원본 `outputs/qa-be-117-*`, `outputs/qa-e2-restore-20261008/`와 stash `993cc4c...`의 로컬 보존을 명시한다. 해당 5개 명명 폴더와 stash 객체는 이 PC에 없다. 이들은 Simulator 없는 직접 INS-13 시험이어서 원자료가 공유돼도 SIM-09 자동 저장30초 관찰을 그대로 대신하지 않는다. 실패·보류 결정은 유지한다.

**외부 보관함:** GitHub 이슈 collection132개(PR 포함)·PR91개 본문과 관련 #45/65/103/117 댓글64개, 관련 PR52/100/104/112 discussion을 확인했다. 별도 ZIP/SQL 원본 첨부는 없고 링크된 SQL2개는 이미 확인한 기존 repository query다. GitHub Actions PR checks 실행26개의 artifact 목록은 모두0, Release도0이다. Jenkins `/var/jenkins_home/jobs`의 깊이 제한 없는 archive 디렉터리 및 SQL/ZIP/fault/recovery/evidence 파일 이름 검색에서도 후보가 없었다. 로컬 workspace나 console log 전체를 원본이 없는 것으로 단정하는 조사는 아니다. [이슈·PR·Actions·Jenkins 대조](deeper-pass/external-artifact-search.json).

**추가 조사 결론:** 무응답·실패의 별도 Mock 시험 API/검사 DB/CSV 연결 2건과 원본 위치를 추가 확보했다. 원래 SIM-06 제어 명령별 행·DB_ERROR 연결 로그·성공 bin 전후 자료, SIM-09 동일 장애 회차의 자동 저장 복구30초/무재시작 원자료는 여전히 미확보다. 새 시험과 공식 판정 변경은 하지 않았다.

## 4.5 요청에 따른 추가 조사10회 및 E1 실제 제어 행 확보

최신 미병합 PR·전체 binary/LFS 후보·포트폴리오 복제본·별도 로컬 export·압축/CI workspace·추가 이슈/PR·reflog/orphan·JSON 구조·새 BE ID의 도구 이력·기존 E1 DB의 **10개 범위를 각각 조사**했다. [차수별10회 결과](ten-pass/README.md) · [조사 완료 인덱스](ten-pass/summary.json).

10차에서 기존 Git 공개 CSV의 무응답 검사11개 ID를 E1 DB에 읽기 전용으로 조회했다. 검사11행·**개별 제어11행**·오류11행이 남아 있었고, 각 ID에 attempt_no1·NO_RESPONSE인 명령이 정확히1개다. command_id·요청 bin·ROUTE_TO_BIN·요청/응답 시각·응답시간과 오류 연결을 확보했다. 10/08 저장된 원래 bin·모델 버전·UTC→KST 완료 시각이 CSV와11/11 일치하며 각12 frames·mobilenet_v3_small_multiview·저장SUCCEEDED다. [원본 TSV](ten-pass/10-e1-exact-ids-raw.tsv) · [행별 JSON](ten-pass/10-e1-exact-ids-records.json) · [실행 SQL](ten-pass/10-e1-exact-ids-readonly.sql).

기존 E1 이미지 metadata의 추론오류 `qa-be-10081526-ins08` 및 timeout `qa-be-10081626s-ins01-FS-15.0`에서도 재검사 bin·SUCCEEDED·attempt1의 제어 각1행을 추가 확보했다. 검사 DB 오류는 각각 INFERENCE_HTTP_ERROR·INFERENCE_DEADLINE_EXCEEDED이고 frame/model 필드NULL을 그대로 보존했다. [추가 원본 TSV](ten-pass/10-e1-failed-inference-raw.tsv) · [행별 JSON](ten-pass/10-e1-failed-inference-records.json). **이번 신규 실제 제어 행은 총13행**이다. 현재 E1의 FAILED 명령 행은0으로 추가 후보가 없지만 과거 다른 E2의 발생 부재를 증명하는 값은 아니다.

이 원자료는 **기존 별도 E1 회차의 보존 행**이며 원래10/06 E2의 부실 수집 필드가 복원된 것은 아니다. E1→E2 인정, 원래 NEXT 자동 해제·입력/소스 출처 전체와 함께 판정할지는 BE·DM 확인이 필요하다. 성공 bin 전후 통계·DB_ERROR 연결·SIM-09 자동 복구30초 자료는 새로 확보하지 못했다. 제어 행1개라는 저장 관찰과 미기록 실행 호출 추적도 구분한다.

E1 7개 컨테이너의 ID·이미지·StartedAt·RestartCount·health는 조회 전부터 전체 SELECT 종료 후까지 동일하고 모두healthy였다. 이는 이번 읽기 전용 조사의 영향 확인이며 과거 SIM-09 무재시작 증거가 아니다. [조회 조건·검증](ten-pass/10-e1-exact-id-db-search.json) · [최종 상태](ten-pass/10-e1-final-after.json).

## 5. BE 확인이 필요한 최소 후속 범위

1. SIM-06: 새로 확보한 SIM-07 CONTROL_REJECTED·INFERENCE_TIMEOUT 개별 행과 E1 이미지 metadata의 대체 인정 범위를 먼저 확인한다. 추가 E1 무응답11행·추론 제어2행의 대체 인정도 확인한다. 원래 E2 행과 실제 FAILED 개별 명령, 성공 bin 통계 제외, DB_ERROR 대상 ID·실패 로그 연결, 원래 NEXT 조건과 이미지 상세는 미완료다. [조건별 최종 대조](second-pass/remaining-conditions.json).
2. SIM-09: 동일 장애 회차의 DB 중단/복구 완료 시각, 중단 중 자동 검사별 기록, 복구 후30초 자동 저장 증가, StartedAt/RestartCount 등 무재시작 원자료, 공개 Simulator 상태 관찰이 필요하다. 기존 직접 probe는 전체 조건을 대신하지 못한다.
3. BE가 인정 범위·필수 부족 조건을 확정한 뒤 필요한 경우에만 최소 추가 격리 시험을 협의한다. 이번 조사에서 재시험이나 공식 QA 판정 변경은 하지 않았다.

[BE 답글 초안](issue-comment-draft.md) · [전체 SHA-256](manifest.sha256). 조사 보고서와 신규 원자료를 `feat/mlops` Git 보존 대상으로 함께 정리했다. 댓글은 초안이며 별도로 게시하지 않았다. 과거 원자료의 고정 GitHub 링크와 이 폴더의 Git 보존본을 구분한다.
