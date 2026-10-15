# [MO] QA-INS-14·17 기존 DB 증거 보완 — 2026-10-12

[BE 요청 댓글](https://github.com/yuudong123/CQC/issues/103#issuecomment-6117222988)에 대한 기존 기록 조회 결과. 신규 검사 실행 없이 E1 MySQL을 읽기 전용 transaction으로 조회했으며, 조회 기준 시각은 **2026-10-12 12:35:52.411 KST**이다. 실행자는 홍유나, 조회 대상은 `cqc-cicd-mysql-1`의 `cqc` DB(MySQL 8.4.11)이다. DB 원자료의 시각은 UTC이다.

## 확인 결과

| 구분 | 확보한 자료 | 남은 확인 |
|---|---|---|
| INS-17 지정 검사 | `inspections` 1행 및 `inspection_errors` 1행, 기존 공유 CSV 1행 | BE 보유 API·이력·이미지 원자료와 최종 대조 |
| INS-14 원래 E2 회차 `be10-2-63f2ca4e` | 기존 JSONL의 지정 12건 API·검사 DB 기록 | 지정 E2 DB·원래 `control_attempts` 상세 확보 여부 미확인 |
| INS-14 E1 대안 `qa-be-10081636t-ins01-*` | 기존 검사 12행 및 `control_attempts` 12행, 정상 bin 12개 | BE의 기존 E1 API 응답 대조 및 재사용 범위 판단 |

이 자료는 증거 보완용이며 INS-14·17 PASS 판정이나 Backend 30/44 집계를 변경하지 않는다.

## INS-17 — 지정 오류 행 확보

| 항목 | 실DB 원자료 |
|---|---|
| inspection_id | `qa-e1-20261008-091125-45628a-ins08` |
| inspection_errors.id | `979` |
| component | `inference` |
| error_code | `INFERENCE_HTTP_ERROR` |
| occurred_at (UTC) | `2026-10-08 00:11:29.856` |
| occurred_at (KST) | `2026-10-08 09:11:29.856` |
| 검사 완료 (KST) | `2026-10-08 09:11:29.860` |

원본 행은 조회 당시 보존되어 있었다. `ins17-db-check.json`과 `mysql-result.jsonl`에 원시 값을 그대로 보존했다.

기존 [ops10-inspections.csv](https://github.com/yuudong123/CQC/blob/dev/docs/wbs/results/qa-be-proxy-20261008/supplement/ops10-inspections.csv)에서 같은 ID는 헤더 포함 **11095행**, 완료 시각 `09:11:29.860`, `error_codes=INFERENCE_ERROR`로 확인됐다. 원본 CSV SHA-256은 `c186020e62e801f0459d109192b9ccd4b35357334c829a55532a0a7b28e7379e`이며 선택한 행은 `existing-csv-extract.json`에 보존했다.

현재 배포된 Backend의 `src/api/services/quality_history.py`는 내부 코드 `INFERENCE_HTTP_ERROR`를 공개 코드 `INFERENCE_ERROR`로 변환한다. `deployed-error-code-mapping.py.txt`와 컨테이너·이미지 출처 `deployed-mapping-source.json`을 함께 보존했다. 이는 현재 배포 코드 확인이며 10/08 당시 코드 전체의 동일성을 추가로 증명한 것은 아니다. BE가 보유한 과거 API 응답·필터 이력·이미지 목록은 이 환경에 없어 직접 재검수하지 않았다.

## INS-14 — 원래 E2 자료의 확인 범위

요청한 12개 ID는 [BE-10-2-local-evidence.jsonl](https://github.com/yuudong123/CQC/blob/0a4521ecd862a1626f7301ac2920e15bee467a07/docs/wbs/BE-10-2-local-evidence.jsonl)의 **408~419행**에 있으며, API `target_bin_code`와 검사 DB `target_bin_code`는 `DEMO_BIN_01`~`DEMO_BIN_12`와 12/12 일치했다. 지정 행만 `ins14-existing-evidence-extract.json`에 추출하고 원본 파일 해시·행 번호를 기록했다. GitHub `dev`의 같은 12건도 API·DB bin 일치를 확인했다(`remote-source-check.json`).

이 환경의 활성 Docker context는 `desktop-linux`이며 실행 중이거나 정지된 **E2 MySQL 컨테이너를 찾지 못했다**. 공용 E1 `cqc` DB에서 요청한 E2 ID의 검사·제어 행은 각각 0행이었으나, **이 결과로 원래 E2 DB의 삭제나 데이터 소실을 확정하지 않는다**. 원래 E2 DB 자체를 직접 조회하지 않았다.

`docs`, `outputs`, `scripts`의 로컬 JSON/JSONL/SQL/CSV/Markdown/text/log 보존 자료를 ID로 검색했다. 확인한 기존 원자료에서는 위 E2 12건의 개별 `control_attempts`·응답시간 상세를 추가 확보하지 못했다. 다른 컴퓨터의 DB·미게시 export, 오프라인 Docker 볼륨 내부, 바이너리 archive는 확인 범위에 포함하지 않았다. `docker-inventory.json`과 `local-search.json`에 범위와 결과를 기록했다. 검색 결과에 포함된 이번 생성 파일은 과거 export로 취급하지 않는다.

## INS-14 — 별도 E1 대안 증거

BE가 대안 검토 대상으로 언급한 **2026-10-08 16:36 회차**의 `qa-be-10081636t-ins01-*` 12건은 E1 DB에 보존되어 있었다. 검사마다 `control_attempts`가 정확히 1행이며, 모두 `attempt_no=1`, `command_type=ROUTE_TO_BIN`, `control_status=SUCCEEDED`였다. 제어 bin과 **검사 DB**의 `target_bin_code`는 **12/12 일치**, 응답시간 최대는 **0.090ms < 100ms**였다.

| 검사 ID 끝부분 (`qa-be-10081636t-ins01-` 뒤) | 검사 DB·제어 bin | 응답시간(ms) |
|---|---|---:|
| FL-13.9 | DEMO_BIN_01 | 0.065 |
| FL-15.0 | DEMO_BIN_02 | 0.073 |
| FM-13.9 | DEMO_BIN_03 | 0.049 |
| FM-15.0 | DEMO_BIN_04 | 0.044 |
| FS-13.9 | DEMO_BIN_05 | 0.086 |
| FS-15.0 | DEMO_BIN_06 | 0.090 |
| YL-13.9 | DEMO_BIN_07 | 0.089 |
| YL-15.0 | DEMO_BIN_08 | 0.045 |
| YM-13.9 | DEMO_BIN_09 | 0.044 |
| YM-15.0 | DEMO_BIN_10 | 0.042 |
| YS-13.9 | DEMO_BIN_11 | 0.067 |
| YS-15.0 | DEMO_BIN_12 | 0.078 |

`e1-fallback-db-check.json`은 실제 조회 행, `e1-fallback-control-review.json`은 행별 대조 결과, `e1-fallback-control-table.csv`는 검토용 표이다. 응답시간은 기존 DB의 가상 제어 응답시간으로 HTTP 전체 검사 시간이나 모델 추론 시간이 아니다. E2 회차를 대체한 것으로 판정하지 않았으며, 기존 E1 API 응답과의 대조 및 재사용 승인 여부는 BE 판단 대상으로 남겼다.

## 파일 안내

- `query.sql`, `mysql-result.jsonl`: 동일 read-only snapshot의 SQL 및 DB 원자료
- `requested-targets.json`: BE가 지정한 원래 ID·bin 목록
- `ins17-db-check.json`: 지정 검사와 오류 행
- `ins14-db-check.json`: 원래 E2 ID를 E1 DB에서 조회한 결과
- `ins14-existing-evidence-extract.json`: 기존 E2 API·검사 DB 12건 추출
- `e1-fallback-db-check.json`, `e1-fallback-control-review.json`, `e1-fallback-control-table.csv`: E1 대안 원자료·대조·표
- `existing-csv-extract.json`, `deployed-error-code-mapping.py.txt`, `deployed-mapping-source.json`: INS-17 CSV·현재 공개 코드 변환 근거
- `database-container.json`, `docker-inventory.json`, `local-search.json`, `remote-source-check.json`: 출처·검색 범위
- `summary.json`: 실제 수량 및 조회 시각 요약
- `collect-existing-evidence.py`: 이번 조회·추출 코드 보존본(재실행은 새 출력 폴더 사용)
- `issue-comment-draft.md`: 사용자가 게시할 댓글 초안
- `manifest.sha256`: 묶음 파일 해시 목록(해시 목록 자체 제외)

증거 수집은 기존 DB의 읽기 전용 조회와 보존 파일 확인으로 수행했다. 신규 검사·장애 주입·서비스 설정 변경은 없으며, 최종 QA 판정은 BE 검토 대상으로 유지한다. 이 폴더의 `.gitattributes`는 원자료의 바이트와 기록된 SHA-256을 Git에서도 보존한다. 공유 ZIP은 `outputs/qa-mo-ins14-ins17-20261012.zip`에 생성했다.
