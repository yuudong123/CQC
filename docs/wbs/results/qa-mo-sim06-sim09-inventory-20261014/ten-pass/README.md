# SIM-06·09 원자료 추가 조사 10회 (2026-10-14)

**10개 범위를 모두 조사했고, 10번째 E1 DB 대조에서 실제 제어 원자료13행을 추가 확보했다.** 무응답 검사11건의 검사/제어/오류 각11행, 기존 E1 추론 timeout/error 검사2건의 제어 각1행이다. 기존 저장 행을 읽기 전용으로 조회했으며 새 검사·장애 주입·서비스 변경은 하지 않았다. 공식37/44는 유지한다.

| 차수 | 조사 범위 | 결과 |
|---|---|---|
| [1](01-latest-pr-heads.json) | 최신 remote·PR91개·미병합2개 | 미병합 PR에 QA 원본 없음 |
| [2](02-binary-lfs-history.json) | 전체 Git의 binary/압축/LFS 후보59개 | 추가 원본 묶음·LFS 증거 없음 |
| [3](03-portfolio-copy.json) | 포트폴리오 복사본 QA 파일341개 | 원본 작업 폴더와 모두 동일 |
| [4](04-exported-locations.json) | 다른 export/workspace 파일 이름4107개 | BE 명명 원본 없음. 별도 CQC copy의 outputs 텍스트 자료0개 |
| [5](05-nested-archive-search.json) | 압축본3개·Jenkins workspace | 압축본 추가 원자료 없음, workspace JSON4개도 기존 원본과 해시 동일 |
| [6](06-related-discussions.json) | 관련 이슈·PR13개, 댓글12개 | 추가 첨부 없음 |
| [7](07-reflog-dangling-objects.json) | reflog146개·unreachable blob407개 | 일치3개는 기존 복구 JSON·조사 문서, BE stash 없음 |
| [8](08-field-structure-census.json) | 로컬 QA JSON/JSONL819개 구조 | 새 무응답/FAILED 명령 행 없음. stats 전후34기록은 저신뢰·late 시험 |
| [9](09-alternative-id-tool-history.json) | 다른 CQC16개 채팅의 도구 출력1113개 | 관련1개는 기존 BE 문서 출력 |
| [10](10-e1-exact-id-db-search.json) | Git 공개 CSV·이미지 metadata의 ID를 실제 E1 DB로 대조 | **무응답 제어11행·추론 timeout/error 제어2행 추가 확보** |

## 추가 확보한 실제 행

Git의 [E1 공개 CSV](https://github.com/yuudong123/CQC/blob/9723907f2a9cd3c4cb747ca80bc9b72892e2d4d0/docs/wbs/results/qa-be-proxy-20261008/supplement/ops10-inspections.csv)에 있던 무응답 검사11건을 현재 E1 MySQL에서 SELECT로 읽었다. 10/08 원래 검사 시각·bin·모델 버전이 CSV와11/11 일치했고 UTC DB 완료 시각을 KST로 바꾸면 CSV 시각과도11/11 일치한다. 각 used_frame_count12, mobilenet_v3_small_multiview, 저장SUCCEEDED이며 실제 source_reference도 보존했다.

각 제어 행에는 command_id·inspection_id·attempt_no1·요청 bin·ROUTE_TO_BIN·NO_RESPONSE·요청/응답 시각·응답시간이 있다. 각 검사별 저장 제어 행은 정확히1개다. 오류11행도 같은 ID에 CONTROL_NO_RESPONSE로 연결된다. [원본 TSV](10-e1-exact-ids-raw.tsv) · [행별 JSON](10-e1-exact-ids-records.json) · [실행 SQL](10-e1-exact-ids-readonly.sql). 원본 TSV와 query SHA를 보존했으며 SQL은 read-only transaction의 SELECT만 수행한다.

추가로 기존 Git 이미지 metadata의 검사 `qa-be-10081526-ins08`, `qa-be-10081626s-ins01-FS-15.0`에 대한 실제 제어 각1행도 남아 있었다. attempt1·재검사 bin·SUCCEEDED·저장SUCCEEDED다. 검사 DB 오류 코드는 각각 **INFERENCE_HTTP_ERROR**, **INFERENCE_DEADLINE_EXCEEDED**이며 프레임·모델 필드는 NULL인 상태 그대로 보존한다. [원본 TSV](10-e1-failed-inference-raw.tsv) · [행별 JSON](10-e1-failed-inference-records.json) · [실행 SQL](10-e1-failed-inference-readonly.sql). 현재 E1 DB의 제어FAILED 행은0이며, 이것을 과거 다른 E2 회차에서도 없었다는 증거로 사용하지 않는다.

**원래 10/06 E2와는 다른 E1 회차다.** 해당 회차의 Simulator NEXT 헤더·자동 해제 기록, 입력 이미지 원본, 배포 SHA 전체를 새로 확보한 것은 아니다. E1 제어 상세의 SIM-06 대체 인정은 BE·DM 확인이 필요하다. 저장된 행1개라는 관찰과 실행 중 미기록 호출 추적은 구분한다.

## 여전히 미완료

- SIM-06: 원래 E2 회차 및 CONTROL_FAILED 실제 개별 명령 행, 성공 bin 통계의 동일 회차 전후 제외, DB_ERROR 대상 ID와 저장 실패 로그 연결. 새 E1/WSL 제어·이미지 대체 인정도 남는다.
- SIM-09: 동일 장애 회차의 중단/복구 시각, 복구 후30초 자동 저장 수·검사ID, 무재시작 및 공개 Simulator 상태 시계열.

조회 전부터 추가 SELECT 종료 후까지 E1 컨테이너7개의 ID·이미지·StartedAt·RestartCount·health가 같고 모두healthy였다. [전](10-e1-before.json) · [첫 조회 후](10-e1-after.json) · [전체 조회 후](10-e1-final-after.json). 이는 **이번 원자료 조회의 서비스 유지** 증거이며 과거 SIM-09의 무재시작 증거를 대신하지 않는다.

[10회 요약 JSON](summary.json) · [전체 조사 보고서](../README.md). 조사 보고서·원자료·댓글 초안을 `feat/mlops` Git 보존 대상으로 정리했다. 이슈 댓글은 게시하지 않았다.
