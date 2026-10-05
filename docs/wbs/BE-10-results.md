# BE-10 통합시험 결과 기록

- 작성일: 2026-10-05
- 계획·계약·입력·기대 결과: [BE-10.md](BE-10.md)
- 현재 단계: **2/4 로컬·격리 핵심 통합 검증 수행. OBS-01 Backend 수정·로컬 회귀 확인; 3/4~4/4 미실행**
- 1/4에서는 시험을 실행하지 않았다. 이번 2/4 실행 결과는 §9에 새 기준선과 함께 기록하며, 과거 단위/CI 기록을 이번 PASS로 전환하지 않는다.
- 아래 표는 결과 기록 틀이다. `미실행`과 `차단`은 실패를 관측했다는 뜻이 아니다. 향후 실행 시 동일 ID의 분기별 결과·증거를 모두 연결하고, 일부 분기 통과만으로 전체 ID를 PASS 처리하지 않는다.

## 1. 기준선과 실행 전 확인

| 항목 | 1/4에서 확인한 기준선 | 향후 실제 시험환경 기록 |
|---|---|---|
| 기능 코드 | feat/backend `b820b5d1423d54768ed6074279e870b4e8b80ab7` | 통합환경 확인 필요 |
| 최신 dev 문서 | `fd0b5c37d3ba5934902bc34584b449b94d139a68`; 기능 코드/계약 차이 없음 | 시작 전 dev 및 실제 release 재확인 |
| 관제 / Inference OpenAPI | 각각 info.version `1.0.0`; hash는 계획 §2.1 | 배포 OpenAPI/공유 JSON 비교 필요 |
| 모델 | `mobilenet_v3_small_multiview`, `cqc-apple-separate12-focal-v2-cal-20260930`; pt/json hash 계획 §2.2 | 배포 pt/json hash·health·응답 버전 확인 필요 |
| Dataset | realtime-apple-arrival-demo, index hash 계획 §2.2 | mount·입력 manifest 확인 필요 |
| DB | 코드 migration head `20260929_02`; 12 normal + TEST_REINSPECTION_BIN | DB migration/seed/활성 mapping 확인 필요 |
| 라인 | interval 1000/2000/3000ms, 기본 2000ms | 실제 Settings·interval·concurrency 확인 필요 |
| Compose/Jenkins/FE | 계획 §2.3. #92는 기준선 밖 열린 FE PR | 실제 image ID/배포 SHA/worker/Volume/FE API 모드 확인 필요 |

실행 전 기록에는 secret/token/DB password를 넣지 않는다. 이후 blocker 수정이나 FE merge로 HEAD가 바뀌면 과거 기준선을 덮어쓰지 않고 run별 새 SHA와 변경 범위를 추가한다.

## 2. 시험별 실행 현황

총 **47개**: 2/4 **27개**, 3/4 **15개**, 4/4 **5개**. 상세 명세는 계획의 INPUT/EFFECTS 두 표에서 같은 ID를 결합한다. 담당도 계획 표를 따른다.

| 시험 ID | 단계 | 상태 | Run ID / 결과·증거 | 실행 전 참고 |
|---|---|---|---|---|
| BE10-INS-01 | 2/4 | PASS (L) | §9 INS-01 / local evidence | 실제 모델 6후보×당도2, 정상 bin 12종 |
| BE10-INS-02 | 2/4 | PASS (C/L) | §9 INS-02 / local evidence | 제어된 HTTP 품종 저신뢰·실DB·이미지 |
| BE10-INS-03 | 2/4 | PASS (C/L) | §9 INS-03 / local evidence | 제어된 HTTP 및 실제 모델 자연 품질 저신뢰 |
| BE10-INS-04 | 2/4 | PASS (C/L) | §9 INS-04 / local evidence | 제어된 HTTP 양쪽 저신뢰·실DB·이미지 |
| BE10-INS-05 | 2/4 | PASS (C/L) | §9 INS-05 / local evidence | threshold 바로 아래·등호·위 |
| BE10-INS-06 | 2/4 | PASS (C/L) | §9 INS-06 / local evidence | 당도 누락 재검사·통계 비제외 |
| BE10-INS-07 | 2/4 | PASS (C/L) | §9 INS-07 / local evidence | 실제 접속 거부, ConnectTimeout 대역·1/2/3초 |
| BE10-INS-08 | 2/4 | PASS (C/L) | §9 INS-08 / local evidence | 실제 모델 손상 이미지422 및 HTTP500 responder |
| BE10-INS-09 | 2/4 | PASS (C/L) | §9 INS-09 / local evidence | ID/frames/null/JSON 손상/필수 field 누락 |
| BE10-INS-10 | 2/4 | PASS (C/L) | §9 INS-10 / local evidence | Mock Virtual Control 거부 후 재검사 성공 |
| BE10-INS-11 | 2/4 | PASS (C/L) | §9 INS-11 / local evidence | Mock Virtual Control 무응답·재호출 없음 |
| BE10-INS-12 | 2/4 | PASS (C/L) | §9 INS-12 / local evidence | Mock Virtual Control 실패·호출1 |
| BE10-TIM-01 | 2/4 | PASS (C/L) | §9 TIM-01 / local evidence | 1/2/3초 business/hard 및 HTTP budget trace |
| BE10-TIM-02 | 2/4 | PASS (C/L) | §9 TIM-02 / local evidence | snapshot A=2000 유지, B=3000; Runner/API 회귀 |
| BE10-TIM-03 | 2/4 | PASS (C/L) | §9 TIM-03 / local evidence | 동시 1/2/3초 값 격리 |
| BE10-TIM-04 | 2/4 | PASS (C/L) | §9 TIM-04 / local evidence | socket 지연 late 진단과 ReadTimeout 대역 분리 |
| BE10-TIM-05 | 2/4 | PASS (C/L) | §9 TIM-05 / local evidence | 2/3/4초 hard 취소·단위 한도·반복10건 |
| BE10-TIM-06 | 2/4 | PASS (C/L) | §9 TIM-06 / local evidence | 1초 A late 중 B 정상·DB 집계 불변 |
| BE10-TIM-07 | 2/4 | PASS (C/L) | §9 TIM-07 / local evidence | header 없는 500/2000 fallback·설정 회귀 |
| BE10-TIM-08 | 2/4 | PASS (C) | §9 TIM-08 / 이번 회귀 | 미인증403·허용 밖422·정상200 |
| BE10-TIM-09 | 2/4 | PASS (C/L) | §9 TIM-09 / local evidence | 두 fault×NEXT/ALL×1/2/3초, 병렬 claim |
| BE10-BND-01 | 2/4 | PASS (C/L) | §9 BND-01 / local evidence | 실제 모델1~12장·13장413·누락422 |
| BE10-BND-02 | 2/4 | PASS (C/L) | §9 BND-02 / local evidence | 개수·중복·비연속422·MIME415·호출0 |
| BE10-BND-03 | 2/4 | PASS (L) | §9 BND-03 / local evidence | 실제 Uvicorn socket에서 CL 있음 L−1/L/L+1 |
| BE10-BND-04 | 2/4 | PASS (C/L) | §9 BND-04 / local evidence | 실제 chunked 경계 + ASGI 과소CL/추가part/파일 정리 |
| BE10-DUP-01 | 2/4 | PASS (C/L) | §9 DUP-01 / 실MySQL 전용 pytest | 현재 migration 실DB 순차409·기존 행 불변 |
| BE10-DUP-02 | 2/4 | PASS (C/L) | §9 DUP-02 / 실MySQL 전용 pytest | 독립 persistence 동시200 하나·409 하나 |
| BE10-DB-01 | 3/4 | 미실행 | — | LKG warm, 실제 DB 장애 / 장애 주입 구분 |
| BE10-DB-02 | 3/4 | 미실행 | — | DB 복구·새 이력 저장 |
| BE10-DB-03 | 3/4 | 미실행 | — | cold/LKG 부재·잘못된 mapping |
| BE10-OPS-01 | 3/4 | 미실행 | — | 이력·필터·pagination·KST |
| BE10-OPS-02 | 3/4 | 미실행 | — | 정상/저신뢰/시스템 오류/당도 누락 집계 |
| BE10-OPS-03 | 3/4 | 미실행 | — | 필터 전체 CSV·BOM・행 집합 |
| BE10-OPS-04 | 3/4 | 미실행 | — | 조회 성능 수치는 DEC-02 승인 대기 |
| BE10-RET-01 | 3/4 | 미실행 | — | 86,400 / 8,640, 격리 시험 DB 필수 |
| BE10-IMG-01 | 3/4 | 미실행 | — | 4종 시스템 / 3종 저신뢰 저장·sidecar |
| BE10-IMG-02 | 3/4 | 미실행 | — | 이미지 100 / 200 독립 순환 |
| BE10-IMG-03 | 3/4 | 미실행 | — | category / inspectionId / 기존 sidecar |
| BE10-IMG-04 | 3/4 | 미실행 | — | DB 이력 없이 sidecar 독립 조회 |
| BE10-IMG-05 | 3/4 | 미실행 | — | preview / delete / cache 금지 |
| BE10-LOG-01 | 3/4 | 미실행 | — | 저장 결과 ERROR 추적·저신뢰 성공 무ERROR |
| BE10-SIM-01 | 3/4 | 미실행 | — | position 복구·OFF |
| BE10-E2E-01 | 4/4 | 미실행 | — | 정상 판정·저장 100건; DEC-03 |
| BE10-E2E-02 | 4/4 | 미실행 | — | 2초 자연 timeout; DEC-01 승인 대기 |
| BE10-E2E-03 | 4/4 | 미실행 | — | FE-DEP-01: PR #92 merge·배포 확인 |
| BE10-E2E-04 | 4/4 | 미실행 | — | 실제 배포·재시작·로그·Volume |
| BE10-E2E-05 | 4/4 | 미실행 | — | 최종 장애 시연·복구 |

## 3. 개별 실행 기록 틀

향후 시험마다 아래 항목을 복사해 기록한다. 증거 파일 생성·API 호출은 2/4~4/4 별도 지시를 받은 뒤 수행한다.

| 항목 | 기록 |
|---|---|
| Run ID / 시험 ID / 하위 분기 | 미실행 |
| 수행자 / 확인자 / 일시(KST) | 미실행 |
| 실행 환경(C/L/S) / release SHA / image ID | 통합환경 확인 필요 |
| Backend/OpenAPI hash / Simulator SHA / FE SHA | 통합환경 확인 필요 |
| 모델 이름·버전·pt/json hash / Dataset·manifest hash | 통합환경 확인 필요 |
| DB migration / mapping / Settings 적용값 | 통합환경 확인 필요 |
| interval / concurrency / 적용 threshold / fault 모드 | 미실행 |
| Jenkins build·deploy 상태 / CPU·메모리·thread / 경쟁 부하 | 미실행 |
| 입력 ID 집합 / 이미지 수·byte 수·metadata / brix | 미실행 |
| 실제 API status·body / 처리 시간 / request correlation | 미실행 |
| 실제 검사 상태·사유 / 제어 상태·호출 횟수·최종 bin | 미실행 |
| 실제 DB 행·오류·control_attempts / late payload | 미실행 |
| 통계 before/after·포함/제외 / CSV 데이터 행·ID 집합 | 미실행 |
| 이미지 목록·sidecar·preview/delete / 보존 전후 집합 | 미실행 |
| application/error.log / 저장 결과 / system ID·사유 | 미실행 |
| timer/task start·business 결정·late 완료·hard 취소 시각 | 미실행 |
| 계획 E1~E7 증거 링크 / 관찰된 차이 / PASS·FAIL·BLOCKED | 미실행 |
| 장애 주입 해제·DB/Simulator 복구 / 다음 시험 영향 | 미실행 |

PASS는 계획의 API·판정·제어·DB·통계·CSV·이미지·로그 조건을 모두 확인한 경우에만 기록한다. 의도된 DB 장애의 미저장·sidecar 순환 만료는 해당 명세대로이면 FAIL이 아니다. Skip/환경 부재/증거 부재는 PASS가 아니다.

## 4. 정량 기준 승인 기록

| 후보 | 측정 조건 | 후보 수용 기준 | 현재 승인 |
|---|---|---|---|
| Q1 | interval2000, concurrency1, 유효 요청 N=100 | 자연 timeout 0건(0%); 짧은 smoke만 의미 | 승인 대기 |
| Q2 권장 | 동일 조건 N=300, 약10분+warmup | 최대1건(1/300=0.33%); 짧은 시연 안정성 기준 후보 | 승인 대기 |
| Q3 | 동일 조건 N=1000, 약33분20초+warmup | 최대1건(0.1%); 더 긴 점유·표본 필요 | 승인 대기 |

- 최종 N / 허용 건수·비율 / 반복 횟수 / timer 허용 오차 / 조회 부하·성능 gate: **미확정**.
- 장애 주입 제외, Jenkins build/test/deploy 없는 조용한 구간, 동일 모델·SHA·Settings. warmup은 집계 시작 전 별도 수행.
- 분모는 측정 구간의 유효 검사 요청. 자연 저신뢰도 포함한다. 연결 오류·DB 장애·배포·입력 오류는 별도 건수/사유와 제외 규칙을 공개하고 임의로 조용히 제거하지 않는다.
- 자연 timeout 분자는 business deadline 초과 및 응답 지연 timeout. 같은 검사 중복 계수는 금지한다. 장애 주입 TIMEOUT은 별도 시험이며 이 비율에 넣지 않는다.
- 기록값: 전체 시도 / 유효 분모 / 자연 timeout / 각 기타 오류 / 주입 제외 / 저신뢰 / 성공 / 평균·p95·최대 RTT / 지연·CPU 경쟁 상황. `inference_time_ms`만으로 Backend business 타이머를 입증하지 않는다.
- 0/N 관찰은 장기 timeout 확률이 0이라는 증명이 아니다. 표본과 관측 구간을 함께 보고한다.

## 5. 정상 100건 수용 기록

구성은 계획 §5: 정상 후보 6묶음 × brix 13.9/14.0의 12종을 8회(96), fuji L/yanggwang L의 두 당도 구간을 1회씩 추가(4). 후보의 현재 실제 정상 여부를 먼저 확인한 뒤 입력 manifest를 고정한다. 이 100건은 독립 사과 100개 또는 모델 정확도 시험이 아니다.

| 수용 항목 | 기대값 | 실제값 |
|---|---|---|
| 고유 inspection_id / 요청 수 | 각각100, run별 unique, 요청 데이터는 사전 고정 | 미실행 |
| HTTP200 | 100. 이 조건만으로 정상100 통과 아님 | 미실행 |
| NORMAL / COMPLETED / control SUCCESS / persistence SUCCEEDED | 각100, review/excluded 각0 | 미실행 |
| 검사 DB / control_attempts / inspection_errors | 100 / 100 / 0 | 미실행 |
| 통계 total / normal / excluded / reinspection / inferenceCount | 100 / 100 / 0 / 0 / 100 | 미실행 |
| 품종 / 품질 / 당도 | fuji50·yanggwang50, L36·M32·S32, 두 당도 각50 | 미실행 |
| 정상 bin별 수 | 01·02·07·08 각각9, 나머지8개 각각8 | 미실행 |
| 검사 이력 CSV | BOM, 헤더 제외100행, ID 집합=DB=manifest, KST ms | 미실행 |
| 통계 CSV | 집계 수량 합계100; CSV 행 수가100일 필요 없음 | 미실행 |
| 신규 검수 이미지 / 시스템 오류 | 각각0 | 미실행 |
| 자연 timeout / 저신뢰 / 당도 누락 / 제어 실패 | 각각0; 발생하면 해당 run 실패, 실패 건 대체 금지 | 미실행 |

자연 저신뢰가 섞이는 전체 Dataset 시험(BE10-E2E-02)은 별도 run/집계다. 정상100의 prequalification/warmup/다른 운영 트래픽을 정상100 저장 수에 섞지 않는다. 측정 DB/기간/ID 집합을 격리하고 공용 DB 초기화·이력 삭제로 숫자를 맞추지 않는다.

## 6. 미해결 사항과 단계 수용

| ID | 현재 상태 | 다음 조치 / 책임 | 차단 범위 |
|---|---|---|---|
| KB-01 | 해소: 초기 INSERT 중복 409 차단, 단위/API·MySQL·전체 회귀 통과 | §7 증거 참조; 배포환경 DUP 수용시험은 후속 | KB-01 구현 blocker 해제, 2/4 전체 완료와 구분 |
| KB-02 | 해소: 검사 전용 파싱 전 body gate·24MiB 경계·chunk 누적·부분 파일 정리·전체 회귀 통과 | §8 증거 참조; 실제 HTTP 서버 BND 수용시험은 후속 | KB-02 구현 blocker 해제, 2/4 전체 완료와 구분 |
| ENV-01 | 실제 배포·DB·Inference·mount·worker 미확인 | MO/DM 환경 제공 및 run 기준선 기록 | 실제 환경 시험 |
| FE-DEP-01 | 기준선 FE parser/generator와 #55 차이; PR #92 open | FE merge·배포·Backend OpenAPI 일치 확인 | FE E2E, Backend 저장/API 단독 시험은 독립 |
| DEC-01 | N/자연 timeout 허용률/반복 미확정 | 사용자 최종 승인 | E2E-02 PASS 판정 |
| OBS-01 | 2/4 당시 추가 재현 FAIL: 점 포함 ID의 이미지 필터422·목록500. 이후 Backend 수정·로컬 회귀 통과 | 과거 증거 §9.4, 수정 검증 §9.5 | Backend 구현 blocker 해소. 3/4 실제 DB·보존 수용은 미실행, FE 파서는 후속 동기화 필요 |
| DEC-02 | timer 오차·조회 부하·응답시간 수치 미확정 | 사용자 최종 승인, BE/MO 측정 협의 | 정량 timer/조회 성능 PASS 판정 |
| DEC-03 | 정상100 후보 최신 실제 판정·manifest 미확인 | 2/4 BE+DM 후보 확인, 별도 run 고정 | 정상100 실행 |

| 단계 | 현재 결과 | 완료 판단 조건 |
|---|---|---|
| 1/4 | 기준선·47개 명세·결과 틀 작성. 정량 후보 승인 대기 | 사용자 계획 확인, 미확정/의존성 인지. 제품 blocker 해결이나 실시험 통과를 뜻하지 않음 |
| 2/4 | 정의된 27개 로컬 PASS, 별도 OBS-01 관측 FAIL 후 Backend 수정·로컬 회귀 통과 | C/L 분기 증거 §9. 실제 배포 S 수용을 대체하지 않음. 과거 OBS-01 관측도 보존 |
| 3/4 | 미실행 | 15개 실제 DB·보존·조회·복구 증거 확보, MySQL skip를 PASS로 대체하지 않음 |
| 4/4 | 미실행 | 5개 동일 배포 기준선 수용, 정상100·승인 정량 기준·FE·운영 복구 통과 |

BE-10 2/4 로컬 핵심 검증은 §9에 기록했다. 3/4~4/4는 아직 미실행이며 아래 KB·OBS 수정 검증이나 로컬 PASS를 BE-10 종료 또는 Issue #66 완료로 사용하지 않는다. 후속 단계는 환경 준비 후 별도 지시로 진행한다.

## 7. KB-01 수정 검증

- 날짜: 2026-10-05. 코드 기준선: `6102344` + 이번 미commit 변경.
- 별도 KB-01 수정 지시의 검증 결과다. 위 47개 BE-10 시험의 전체 수용 실행 결과를 대체하지 않는다.
- 확정 계약: 이미 저장된 inspection_id의 초기 INSERT PK 충돌은 409, body `{"detail":"inspection_id가 이미 존재합니다"}`. 추론·제어·미리보기 게시·이미지 보관·late task를 수행하지 않는다.
- PK 분류: 초기 flush에 한정한 MySQL 1062 + PRIMARY key. 다른 unique/NOT NULL/FK 무결성 오류는 기존 저장 실패 정책을 유지한다. 사전 ID SELECT, ORM/migration, 공개 관제/Inference 계약 변경 없음.
- 적용 범위: DB에 현재 남아 있는 ID. DB 장애 중 전역 멱등 보장과 순환 삭제된 ID의 영구 거부는 추가하지 않는다.

| 검증 | 실행 / 증거 | 결과 |
|---|---|---|
| 수정 전 기준 | API·Service·Repository 관련 기존 시험 | 67 passed |
| 신규 단위/API | `tests/api/test_duplicate_inspections.py` | 15 passed |
| 실제 MySQL PK | `tests/api/test_duplicate_inspections_mysql_integration.py`; MySQL 8.4.11, 별도 임시 container/DB, 현재 ORM schema | 2 passed |
| 순차 재요청 | 첫 요청200 저장 성공, 후속409; 기존 모든 DB 검사 컬럼 비교 | 통과 |
| 동시 재요청 | 독립 Persistence 두 개, 같은 ID 병렬 요청, 실제 PK race | 200 하나+409 하나; 검사1·제어기록1·오류0 |
| 후속 처리 차단 | 정상/저신뢰/지연 응답 후보로 중복 요청; 호출 계수·storage spy·late manager 관찰 | 중복 Inference/제어/이미지 저장0, late task/result0 |
| 일반 저장 실패 | 일반 실패·다른 unique 충돌의 API 검사 | HTTP200·persistence FAILED·추론/제어 유지 |
| 전체 회귀 / #67/#87/#55 | `python -m pytest tests/api tests/simulator tests/test_service_logging.py -q -rs -p no:cacheprovider --tb=short` | 최종 345 passed, 8 skipped, 2 deprecation warnings (101.79s) |
| Ruff / diff | `ruff check src/api tests/api`, 변경 Python 6개 `ruff format --check`, `git diff --check` | 통과 |

임시 MySQL은 운영 DB/Volume과 분리했고 종료 후 시험 container/Volume을 정리했다. 실제 서버 배포와 Inference 모델 전체 E2E는 이 시험 범위가 아니다. MySQL 전용 두 시험은 별도 실행했으며, 기본 전체 회귀에서 CQC_TEST_DATABASE_URL 미설정으로 skip되는 것과 구분한다.

회귀 실행 참고: 샌드박스 실행은 Windows 임시 폴더 접근 거부로 유효한 전체 결과를 얻지 못해 권한 있는 환경에서 재실행했다. 재실행에서 기존 30ms 응답/1ms deadline 기반 late-task 한도 시험이 1회 실패해 재확인했다. 원인은 확정하지 않았으며 해당 시험/late manager는 수정하지 않았다. 임시 폴더 정리와 겹친 중간 실행은 결과에서 제외했다. 진행 중 시험이 없는 상태에서 잔여 폴더가 0개임을 확인한 뒤 독립적으로 실행한 최종 전체 회귀는 345 passed / 8 skipped였다.

최종 판단: **KB-01 구현 blocker 해제**. #67 연결/응답 timeout 분류, #87 요청별 timeout·late-result, #55 이미지 보관·조회 회귀 범위 통과. 기본 회귀의 8 skip은 MySQL URL/격리 보존 DB 미설정에 의한 것이며 신규 중복 MySQL 2개만 별도 실DB 통과를 확인했다. 기존 MySQL 통합 전체를 통과했다고 확대 해석하지 않는다. KB-02 후속 수정 검증은 §8에 별도 기록하며 통합환경 확인과 BE-10 2/4 전체 수용시험은 구분한다. commit·배포는 하지 않았다.

## 8. KB-02 수정 검증

- 날짜: 2026-10-05. 코드 기준선: `6102344` + 기존 KB-01 및 이번 KB-02 미commit 변경.
- 별도 KB-02 수정 지시의 로컬 단위/API 회귀 결과다. BE-10 2/4~4/4 통합 수용시험을 실행하거나 완료한 기록이 아니다.
- 계약: `POST /v1/inspections`의 multipart **본문 전체** 24MiB(25,165,824 bytes). boundary·part header·모든 field/file 포함, 외부 HTTP header·요청 줄·chunk framing 제외. 정확히 제한은 허용, 초과는 기존 detail의 413.
- 구현: 검사 전용 custom APIRoute에서 Content-Length 초과를 파싱 전에 거부한다. 헤더 유무·유효성에 관계없이 실제 ASGI body chunk byte를 누적하고 초과 chunk는 parser에 전달하지 않는다. `request.body()` 재적재·전역 middleware는 추가하지 않았으며 기존 Router validation을 유지했다.

| 검증 | 결과 | 증거 / 범위 |
|---|---|---|
| 수정 전 관련 회귀 | 39 passed | `tests/api/test_inspections.py tests/api/test_duplicate_inspections.py` |
| 새 body 제한 시험 | 16 passed | `tests/api/test_inspection_request_size.py`; 아래 관련 실행에 포함 |
| 관련 단위/API 회귀 | 55 passed | `python -m pytest tests/api/test_inspection_request_size.py tests/api/test_inspections.py tests/api/test_duplicate_inspections.py -q -p no:cacheprovider --tb=short` |
| 실제 24MiB 경계 | 통과 | B=L−1/L은 200, B=L+1은 413. 정확한 Content-Length/헤더 없음 양쪽; 정상 PNG와 사용하지 않는 file part로 전체 bytes 구성 |
| 헤더 우회 및 추가 part | 통과 | CL 없음/과소/잘못된 숫자/음수 모두 실제 body 초과 413. 이미지·known field 합계가 제한 이하인 overhead 초과 및 추가 field/file 초과 차단 |
| 파싱 전 조기 차단 | 통과 | Content-Length>L에서 body read 0회·parser 호출 0회 |
| 초과 chunk 및 파일 정리 | 통과 | body 수신 L+1 bytes 중 parser 전달 L bytes. 부분 업로드 2개 handle 모두 closed, 디스크 spool 포함. `Request.body()` 호출 시 실패하도록 검증 |
| 후속 처리 차단 | 통과 | 초과 요청 Service/Inference/Virtual Control/이미지 저장 호출 0회, late task 0개 |
| endpoint 범위 | 통과 | 검사 route 전용. 별도 `/health`는 같은 크기 설정/초과 CL로도 기존 200 유지 |
| Backend·Simulator·로그 전체 회귀 | **361 passed / 8 skipped** | `python -m pytest tests/api tests/simulator tests/test_service_logging.py -q -rs -p no:cacheprovider --tb=short`; 105.98s. KB-01·#67·#87·#55 회귀 포함 |
| Ruff / diff | 통과 | `ruff check src/api tests/api`, 변경 Python 2파일 `ruff format --check`, `git diff --check` |

8 skip은 MySQL URL 또는 격리 보존 DB 미설정에 의한 것이다. 이번 단계에서는 실DB 시험을 추가 실행하지 않았다. KB-01의 별도 MySQL 검증 기록은 §7에 유지한다. 의존성 deprecation warning 2개가 있었으며 시험 실패는 없었다.

로컬 시험은 httpx ASGITransport로 실제 multipart byte stream을 공급한 것이다. 과소·잘못된 Content-Length는 ASGI 수신 계층의 제한 검증이며 HTTP 서버가 잘못된 framing을 먼저 거부하는 경우까지 통과했다고 해석하지 않는다. 실제 Uvicorn·배포환경의 chunked/wire 경계와 의존성은 BE10-BND-03/04 통합 수용시험에서 별도 확인한다.

최종 판단: **KB-02 구현 blocker 해제**. KB-01도 해소 상태이며 두 코드 blocker로 인한 BE-10 2/4 차단은 제거됐다. 실제 시험환경·배포 기준선 준비와 사용자의 후속 실행 지시가 필요하며 2/4 전체 수용시험은 아직 미실행이다. Simulator/FE/Inference/DB 계약·migration은 변경하지 않았고 commit·배포도 하지 않았다.

## 9. BE-10 2/4 로컬·격리 통합 검증

### 9.1 실행 기준선과 환경

2026-10-05 KST, Codex 실행·사용자 최종 검토 대기. Issue #66을 GitHub API로 읽어 실제 Inference·MySQL/연속 요청·오류·CSV 목표와 open 상태를 재확인했다. 정상100과 CSV 종합 수용은 4/4·3/4에 유지한다.

| 항목 | 이번 실행값 / 제한 |
|---|---|
| 기능 HEAD | `feat/backend` `3cf2b9e57a2a4b18ffb108125d017d083fd35313`, 시작 시 clean; KB-01/02 포함. 이번 제품 코드 변경 없음 |
| 로컬 dev ref | `origin/dev` `51c6e325213d50ac1781a223f454d7eaeaf64285`; 이번 실행에서 fetch/merge하지 않음 |
| Backend | Windows Python 3.13.15, checkout 소스. ASGITransport와 별도 Uvicorn localhost socket 사용; Compose Backend를 호출하지 않음 |
| 의존성 | FastAPI 0.141.1, Starlette 1.6.0, python-multipart 0.0.32, httpx 0.28.1, Uvicorn 0.53.0 |
| 실 Inference | 시험 전용 `cqc-be10-2-inference`, localhost:18011, image `sha256:462d4d9fc3022b3fdbe1bedf1ff099573a95bdb4afbd6798302f7ccbfa40809b`. 현재 src를 `/app/src` read-only mount하여 소스 기준선 일치 |
| Inference 소스 SHA256 | api `bab47958ab956edb50ccca911d9acabb9a85c2fdd310042b426bcd26d06cc51f`; predictor `2cf91c35adb612e00154a1bf3ede8c01a69b5f886aff99c218364725d9ea39fc` |
| 모델 / health | `mobilenet_v3_small_multiview`, `cqc-apple-separate12-focal-v2-cal-20260930`, CPU, views12, decode_workers8, ready/model_loaded=true. `approval_status=unverified_candidate`, `threshold_status=calibrated_dev_oof`; 품질 승인을 뜻하지 않음 |
| 모델 SHA256 | pt `b254206e4091732a49c5db02c12e5fb6dc3d996dbce694c2e82d442a2ba8753a`; json `b4c5a6df0d7b01d4cee890be99f1e55fa6474c67a0110d8a99328c51eea7ccd8` |
| Dataset | realtime-apple-arrival-demo; index SHA256 `dc866e0ccd91f8cff9ce9a523d1707c4df678d564ace24016c5344537ba7e959`. 계획 §5의 정상6후보 및 자연 저신뢰 `demo-601031028000-000`; request.json 순서·metadata 유지 |
| 독립 MySQL | `cqc-be10-2-mysql`, mysql:8.4, localhost:13316, 전용 be10 DB·임의 비밀번호. 기존 Alembic을 신규 격리 DB에 적용, head `20260929_02`, 기존 정상12+재검사 seed. 새 migration 작성 없음 |
| 제어 / 저장소 | 제품 기본 MockVirtualControl; 제어 예외는 결과 대역 주입. 시스템100/저신뢰200, 시험별 임시 root·서로 독립. 실제 장치 시험 아님 |
| timeout / 인증 | 각 검사 1000/2000/3000 및 hard2000/3000/4000, connect200. threshold0.50/0.60. 내부 token은 임의 생성·증거에서 제외, bundle header 포함 |
| 공유 환경 보호 | 기존 cqc-backend/simulator/inference/mysql/frontend 및 Jenkins를 중단·재설정하지 않음. 별도 localhost container/server만 사용. 실제 배포 SHA/FE/browser/Jenkins 무부하 조건은 이번에 확인하지 않음 |

**C와 L의 구분:** 낮은 confidence·HTTP 오류·지연은 localhost HTTP responder(C)로 결과를 제어하고 실제 Backend HTTP client·Service·MySQL·저장소를 연결했다. ConnectTimeout/ReadTimeout은 결정적 httpx transport 대역이며, ConnectError는 실제 loopback 접속 거부다. 정상6후보·1~12장·손상 이미지·자연 품질 저신뢰는 실제 모델 HTTP(L)다. 이들을 전부 실모델 오류 재현이라고 기록하지 않는다.

### 9.2 시험별 결과와 증거

정의된 2/4 ID **27개: PASS 27 / FAIL 0 / BLOCKED 0 (표준 Simulator ID·C/L 범위)**. 추가 탐색 **OBS-01: FAIL 1**은 별도 공개한다. local PASS가 실제 배포 S·모델 품질 승인·3/4 조회 종합 수용을 대체하지 않는다.

실행 자료: [시험 코드](../../tests/api/test_be10_core_integration.py), [DB·통계·CSV 효과 감사](../../tests/api/test_be10_evidence_audit.py), [raw API/DB/이미지/budget 증거](BE-10-2-local-evidence.jsonl). JSONL의 `run`, `test_id`, `inspection_id`로 연결한다. 초기 실패 fixture/구 이미지 run도 보존했으므로 **파일 전체를 PASS 집합으로 해석하지 않는다**. 현재 소스로 완주한 `be10-2-fd436b9c`(69 pytest PASS), 최종 전체 회귀 `be10-2-63f2ca4e` 및 같은 run의 EFFECTS-AUDIT를 참조한다. 세부 pytest case와 BE10 ID는 1:1 건수 관계가 아니다.

| 시험 ID | 환경·입력 | 실제 결과 / 기대 일치 | ID·증거 / 후속 |
|---|---|---|---|
| INS-01 | L, 계획 정상6후보×13.9/14.0, 12장 | 12요청 모두200/NORMAL·정상bin01~12·제어/저장SUCCEEDED·비제외. 현재 모델에서6후보 재확인 | `*-601031008000-000-*` 등 JSONL INS-01, raw confidence/버전/DB. 정상100은4/4 |
| INS-02 | C→L DB, cc0.49/qc0.8 | LOW_CULTIVAR_CONFIDENCE, 재검사/review=true/비제외, 통계 total/normal 각각+1, low이미지1 | `*-LOW_CULTIVAR_CONFIDENCE-*`; category/reason/errorCode=null/threshold/CSV, ERROR 없음 |
| INS-03 | C qc0.59 및 L `demo-601031028000-000` | LOW_QUALITY_CONFIDENCE; 실제 모델12장 low이미지12, 통계 비제외·재검사 | `*-real-low-quality`, INS-03 API/DB/이미지/CSV. 자연 저신뢰를 정상100에 섞지 않음 |
| INS-04 | C cc0.49/qc0.59 | LOW_BOTH_CONFIDENCE, 재검사·비제외·이미지근거·low 성공 ERROR 없음 | `*-LOW_BOTH_CONFIDENCE-*`, INS-02/03/04/05 tag |
| INS-05 | C 각 기준±0.000001/등호 및 기존 policy 시험 | 아래는 low, 등호/위 정상. 실제 적용threshold0.50/0.60 저장 | INS-02/03/04/05 tag + 이번 test_inspection_policy 회귀 |
| INS-06 | C 정상 모델 응답, brix 없음 | 200/VIRTUAL_BRIX_MISSING·재검사·비제외, 가상당도 null, 보존이미지0 | `*-control-MISSING_BRIX`, INS-06/10/11/12 tag |
| INS-07 | L 접속거부/C ConnectTimeout ×1/2/3초 | 200/INFERENCE_CONNECTION_ERROR·통계 제외·재검사, 관제ERROR/INFERENCE_ERROR | `*-ConnectError-*`, `*-ConnectTimeout-*`; 실제 저장·공개 이력·CSV |
| INS-08 | L PNG MIME의 손상bytes, C HTTP500 | Backend200/INFERENCE_HTTP_ERROR·관제ERROR/INFERENCE_ERROR·제외. 실Inference 손상입력422 | `*-damaged`, `*-invalid-*`, API/DB/CSV |
| INS-09 | C ID/frames 불일치·null·손상JSON·필수field 누락 | 모두200/INFERENCE_INVALID_RESPONSE·재검사·제외·관제INFERENCE_ERROR | `*-invalid-*`, INS-08/09 tag; 손상JSON/누락은추가실행 포함 |
| INS-10 | C MockControl REJECTED→SUCCEEDED | 판정NORMAL 유지, 재검사fallback1회·제어총2회, 공개FALLBACK/REVIEW·비제외, 이미지0 | `*-control-REJECTED`, DB/CSV/제어 기록 |
| INS-11 | C MockControl NO_RESPONSE | NORMAL·원target·무응답1회, 추가제어0·비제외·이미지0 | `*-control-NO_RESPONSE`, DB/CSV |
| INS-12 | C MockControl FAILED | NORMAL·원target·FAILED1회·비제외·이미지0 | `*-control-FAILED`, DB/CSV |
| TIM-01 | C socket/HTTP request hook, 1/2/3초 | business1/2/3, read/write/pool2/3/4, connect 항상0.2초. 빠른결과 정상 회귀 | TIM-01/03 budget trace + test_line_deadlines |
| TIM-02 | C State snapshot A2000 시작 후3000 변경 | A2000/hard3000 유지·지연2.3초는timeout, B3000/hard4000 정상 | `*-snapshot-a/b`; State revision·Runner interval header·공개 PUT는 이번 회귀로 보완 |
| TIM-03 | C 세 interval 동시, 각각delay1.2초 | A1000만timeout, B2000/C3000 정상. transport budget2/3/4 서로 독립 | `*-mixed-1000/2000/3000`, TIM-01/03 tag |
| TIM-04 | C socket business+0.3초, 별도 ReadTimeout 대역 | business 후재검사 확정, late는진단payload만저장·bin/제어/통계 불변. ReadTimeout도timeout으로분류 | `*-late-1000/2000/3000`, `*-ReadTimeout-*`; 주입과구분 |
| TIM-05 | C socket business+1.5초, 단위진단한도 | 총hard2/3/4초에서Backend HTTP task 취소·진단payload 없음. max_tasks초과추가진단만취소 | `*-hard-*`, TIM-04/05 tag + late task limit 회귀. 원격CPU작업중단을보장하는시험 아님 |
| TIM-06 | C A delay1.7초/interval1000, A timeout 뒤 B즉시 | B정상 완료 시에도 A late active=1; B0.043초, A진단후DB집계전체 불변·제어추가0 | `*-late-a/normal-b`, TIM-06 stats before/after. 실배포자원경합은E2E-05 |
| TIM-07 | C interval header없음, default delay0.7초 | 기존business500/hard2000·connect200 fallback, 재검사후late진단 | `*-fallback`; fallback 설정변경은 test_line_deadlines 회귀 |
| TIM-08 | C 미인증/인증1500/정상/누락 | 미인증403·허용밖422·정상200·거부후속0 | 이번 test_internal_interval_header_validation 파라미터 실행 |
| TIM-09 | C State 원자claim→Backend, 2fault×NEXT/ALL×3interval, 각2병렬 | NEXT 주입정확1건/나머지정상, ALL2건. 실제Inference 호출은비주입만, 주입late task0 | `*-NEXT/ALL-INFERENCE_TIMEOUT/ERROR-*`, TIM-09 claim/API/DB; Runner/API 설정회귀 포함 |
| BND-01 | L 실제 모델1~12장, C13장·이미지없음 | 유효입력200·used_frame_count일치·정책대로판정, 13장413·없음422·거부후속0 | `*-real-one`, `*-real-frames-2..11`, INS-01의12장 및 BND-01/02 tag |
| BND-02 | C 개수불일치·중복/비연속index·MIME 및 기존필수검증 | 422/415, Inference/제어0·DB행0 | `*-input-metadata_count/duplicate/gap/mime`; 기존JSON/필수field회귀 |
| BND-03 | L Uvicorn/socket, 실제CL=L−1/L/L+1 | 전체body25,165,823/24는200,25는413·Inference추가0 | JSONL BND-03/04 declared=true; validPNG+unusedfile로본문정확구성 |
| BND-04 | L 실chunked 및 C 잘못된/과소CL·추가part | CL없는L−1/L는200,L+1은413; field/file/overhead우회413, parser초과chunk 미전달·부분파일closed | declared=false + test_inspection_request_size. 잘못된wire framing은서버먼저거부가능, ASGI증거와분리 |
| DUP-01 | L 실제MySQL 초기PK 충돌 | 첫200/SUCCEEDED·후속409, 기존모든컬럼불변·추론/제어/보관/late추가0 | 이번 test_mysql_duplicate_requests_process_once_and_preserve_row[False], `kb01-UUID`; pytest가검증후자체행정리 |
| DUP-02 | L 독립Persistence2개·같은ID동시 | 200하나/409하나·검사1/제어기록1/오류0, 추가이미지/late0 | 같은시험[True], 실PK race. 일반DB장애선별지속은이번회귀 |

위 표의 ID는 `BE10-` prefix를 생략했다. 실제 검사 상태·제어·threshold·DB행은 raw JSONL에 보존했다. 공개 관제 변환 및 검사별 CSV 증거를 확인했으며, 기간필터·CSV 전체 수용/DB outage/복구/보존 종합은3/4로 남긴다. 시스템 오류 이미지의 ID·reason·saved ERROR와 low 성공 ERROR 없음은 신규 caplog 및 이번 기존 review-image 회귀로 확인한다. 배포 `error.log` 운영 파일 자체 수용은3/4·4/4다.

### 9.3 timeout·late 측정과 정지 관찰

대표 완주 run `be10-2-fd436b9c`에서 측정한 **Backend POST 시작부터** 응답·수집까지의 시간이다. 업로드·DB·제어 비용도 포함하므로 내부 Inference 송신 시점의 business/hard와 수치를 동일시하지 않는다. 추가 timer 허용률을 운영 수용 기준으로 확정한 것이 아니다.

| interval | late POST응답 / 진단완료 | hard POST응답 / 취소완료 |
|---|---|---|
| 1000 | 1.104s / 1.385s | 1.087s / 2.057s |
| 2000 | 2.136s / 2.397s | 2.098s / 3.022s |
| 3000 | 3.119s / 3.396s | 3.113s / 4.025s |

late 정상 응답이 도착해도 원래 timeout의 예측 null·재검사 bin·control·exclude 플래그는 불변이다. A late 중 B의 POST 완료는 0.0427초였으며 A 진단이 완료되기 전에 B가 완료됐다. DB 통계 before/after가 완전히 동일하다.

장애 주입은 실제 predict task를 만들지 않는다. NEXT/ALL 시험과 실제 socket 지연의 late/hard 증거를 섞지 않았다. `test_late_task_is_cancelled_at_hard_timeout` 및 `test_late_manager_cancels_each_task_at_its_own_total_hard_timeout`를 각 5회 실행해 **10회 PASS**, 정지 재현 없음.

전체 회귀의 `faulthandler_timeout=30`이 이미지 100/200 순환 시험 중 stack을 출력했다. 첫 실행은 `fault_image_storage._stored_images_locked → _prune_locked → save`, `test_review_images.py:158`이었다. logging 수정 전 후속 실행은 pathlib 파일명 처리의 부분 stack이었으며 둘 다 이후 진행됐다. 최종 실행에서는 해당 stack 출력이 없었다. hard-timeout 정지 증거라고 분류하지 않으며 보존 성능 수용은 3/4 범위다.

### 9.4 발견 결함과 시험환경 수정

**OBS-01 — 검수 이미지 공통 ID 계약 불일치, 미해결 FAIL.** `POST /v1/inspections`는 점이 들어간 `be10-2-63f2ca4e.filter-observation`을 200으로 수락하고 저신뢰 이미지 1장을 저장했다. 이미지 필터는 `^[A-Za-z0-9_-]+$` 때문에 422, 필터 없는 목록은 응답 `items[0].inspectionId`의 같은 pattern 검증에서 ResponseValidationError로 500이다. 기존 정상 ID 이미지까지 같은 목록에서 조회할 수 없게 될 수 있다. 독립 임시 저장소에서 재현했으며 공유 저장소를 오염시키지 않았다.

- 증거: JSONL `OBS-01`, 신규 strict xfail. 관측 500을 PASS로 바꾸지 않는다.
- 코드 근거: `quality_fault_images.py`의 inspectionId Query 및 공개 FaultImages 응답 schema. 검사 요청은 같은 pattern을 강제하지 않는다.
- 대응: 3/4 이미지 조회 전 ID 허용 범위를 정하고 쓰기/필터/응답 계약을 일치시키는 최소 수정이 필요하다. 현재 표준 Simulator ID에는 문제없어 2/4 정상·timeout·제어 검증과 별도 분류한다. 임의 계약 변경·#55 재설계는 하지 않았다.

시험환경/fixture 수정은 제품 결함 수정과 구분한다:

1. 초기 fixture가 필수 bundle header를 빠뜨려 422·11실패: header 보완. 다음 3실패는 DB에 없는 decision_reason을 참조한 시험 오류여서 error_code로 정정.
2. threshold 숫자를 ID에 붙여 점을 만든 fixture에서 이미지 조회 실패 8건: 표준 ID의 시험은 허용 문자 ID로 수정하고 실제 부작용은 위 OBS-01로 별도 보존.
3. Docker image의 Inference api hash가 구버전 `5facd101...`이어서 현재 src를 read-only mount하여 재검증. 모델·predictor checksum은 일치. 공용 image를 rebuild/교체하지 않음.
4. 신규 Uvicorn 시험 서버가 기본 logging 설정으로 전역 logger를 변경해 전체 회귀의 `test_uvicorn_errors_reach_error_file`이 1실패: fixture에 `log_config=None, log_level=None`을 적용. 제품 logging 코드는 수정하지 않음.

### 9.5 실행 집계·잔여 범위

| 실행 | 결과 | 해석 |
|---|---|---|
| 작업전 Backend/Simulator/log 회귀 | 361 passed / 8 skipped,118.20s | 신규시험전기준. MySQL전용환경변수미설정의8 skip |
| 현재src격리통합 완주 | 69 passed,83.85s | 신규67 case + 실제MySQL중복2. 실제모델·1~12장·timeout·NEXT·경계 포함 |
| JSON/필수field 추가 및 OBS 탐색 | JSON오류6 PASS; OBS에서목록500재현 | 후속strict xfail로미해결결함을명시 |
| hard-timeout 반복 | 10 PASS | 2시험×5회, 정지재현없음 |
| logging 오염 수정 전 전체회귀 | 429 passed / 1 failed / 8 skipped / 1 xfailed,185.83s | 실패는신규fixture의전역logging오염. OBS-01 xfail은별도제품결함 |
| 최종 전체 회귀 | **430 passed / 8 skipped / 1 xfailed**,177.75s | API·Simulator·service logging 전 범위. 신규 통합 69 PASS, OBS-01 strict xfail. 8 skip은 기존 MySQL 전용 변수 미설정이며 중복 PK 2개는 앞선 전용 실행에서 실DB PASS |
| 완료 run 저장 효과 감사 | **1 passed**,1.98s | `be10-2-63f2ca4e`의 API 기록 ID 85개: 실제 DB 결과·제어 횟수·CSV 한 행씩·target 일치. 전체 격리 DB 489행의 total489/normal265/excluded224/inferenceCount265를 SQL 결과와 대조. 이 누적 trial DB를 정상100 수용이라고 해석하지 않음 |
| Ruff / format / diff | 통과 | src/api·tests/api·tests/simulator Ruff, 신규 Python 2파일 format, git diff --check |

이번 변경은 시험 코드·증거·BE-10 계획/결과표뿐이다. 제품 코드/FE/Simulator/Inference/DB 설정·새 migration 변경 없음. commit·배포 없음. 모든 시험과 감사 종료 후 `cqc.test=be10-2` label을 확인한 시험용 컨테이너 2개·임시 volume을 정리했다. 임시 UploadFile/저장소도 닫거나 정리됐으며 기존 Compose 5서비스와 Jenkins는 그대로 실행 중이다. DB 삭제 전 감사 결과와 raw 증거를 보존했다.

**3/4는 조건부 진행 가능:** OBS-01 Backend 구현 blocker는 §9.5의 로컬 회귀에서 해소했다. DB/보존/조회 전용 환경 준비 후 실제 MySQL·이미지 조회 수용을 실행한다. 이번 2/4 임시 DB는 운영 DB나 3/4 공유 fixture가 아니다. DB 장애/복구·86,400/8,640·CSV 종합·이미지100/200 수용·Simulator position 복구는 이번 수용 결과에 추가하지 않는다.

**4/4 필요:** 실제 배포 HEAD/image/worker·model hash/mount 재확인, 2초 정상100 및 승인된 N/자연 timeout 비율·Jenkins 무부하 조건, 실 Inference CPU 자원 경합에서 1초 late A/B, 실제 FE 브라우저/API 모드/#55 표시·필터, 배포 network/proxy body 제한·Volume·재시작·error.log 운영 복구. 이미 실행한 localhost wire 검증을 배포환경 검증이라고 확대하지 않는다.

### 9.5 OBS-01 후속 수정·검증 (2/4 종료 후)

과거 §9.4의 FAIL·JSONL 원본은 당시 관측으로 보존한다. 이후 검사 ID 규칙을 **1~64자, 영문 대소문자·숫자·`-`·`_`·`.`**로 확정해 검사 입력, 검수 이미지 필터·응답, 이력·snapshot, review, live/recent jobs 및 공유 OpenAPI에 적용했다. 공백과 `/`·`\` 등 허용 문자 밖의 입력은 검사 시작 전에 422로 거부한다. preview/delete의 개별 이미지 ID 규칙과 DB 구조는 변경하지 않았다. OBS-01 strict xfail은 일반 통합 테스트로 전환했다.

| 검증 | 결과 | 범위·한계 |
|---|---|---|
| 점 포함 ID의 실제 POST→저신뢰/시스템 오류 이미지 저장→필터·전체 목록 | PASS 2 | 격리 로컬 API, 임시 이미지 저장소. 기존 sidecar·preview/delete 별도 PASS |
| 1~64자·UUID·일반 ID·금지 문자·history/snapshot·review·live/recent jobs | PASS | 관련 단위/API 회귀에 포함 |
| Backend·Simulator 전체 회귀 | 374 passed / 79 skipped | 추가 POST→이미지 2건 전에 실행. 격리 MySQL 환경변수 미설정으로 BE-10 전용 통합 테스트 포함 skip |
| 최종 관련 API 회귀 | 103 passed | 추가 POST→이미지 2건 포함 |
| Ruff / format / `git diff --check` | PASS | 변경 Python 파일 및 작업공간 diff 검사 |

OBS-01의 **Backend 구현 blocker는 로컬 기준 해소**했다. 전환한 MySQL 기반 BE-10 통합 테스트는 이번 환경에서 실행되지 않았으므로 3/4 전용 MySQL·보존·조회 수용 결과로 간주하지 않는다. FE의 현재 이미지·이력 파서는 점 포함 ID를 거부하므로 공개 OpenAPI 변경에 맞춘 FE 후속 연동과 4/4 브라우저 확인이 필요하다.
