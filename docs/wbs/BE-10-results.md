# BE-10 통합시험 결과 기록

- 작성일: 2026-10-05
- 계획·계약·입력·기대 결과: [BE-10.md](BE-10.md)
- 현재 상태: **BE-10 Backend 기능·통합시험 완료, #66 완료 조건 충족, Close 가능. 현재 미해결 제품 FAIL 0. 최종 기록·ALL-04 인계·후속 범위는 §14 참조. §12·§13의 전체 배포 수용 관측과 당시 C 판정은 이력으로 보존한다.**
- 1/4에서는 시험을 실행하지 않았다. 이번 2/4 실행 결과는 §9에 새 기준선과 함께 기록하며, 과거 단위/CI 기록을 이번 PASS로 전환하지 않는다.
- 아래 표는 결과 기록 틀이다. `미실행`과 `차단`은 실패를 관측했다는 뜻이 아니다. 향후 실행 시 동일 ID의 분기별 결과·증거를 모두 연결하고, 일부 분기 통과만으로 전체 ID를 PASS 처리하지 않는다.
- `DEFERRED`는 사용자 결정에 따라 후속 Issue·단계로 이관한 항목이며 제품 FAIL이 아니다. 3/4의 두 DEFERRED 항목은 §11.5에 최종 분류했다.

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
| BE10-DB-01 | 3/4 | PASS (L) | §11 DB-01 | 실제 중단과 주입 구분·LKG·저장 실패 |
| BE10-DB-02 | 3/4 | PASS (L) | §11 DB-02 | Backend 무재시작 복구·mapping 갱신 |
| BE10-DB-03 | 3/4 | PASS (L) | §11 DB-03 | cold500·불완전 mapping500·제어0 |
| BE10-OPS-01 | 3/4 | DEFERRED (현행 API 검증 PASS) | §11 OPS-01 | model 필터 문서·계약 정합성 및 추가 필요성은 #68 BE-11로 이관 |
| BE10-OPS-02 | 3/4 | PASS (C/L) | §11 OPS-02 | 20행 정책·DB/API/snapshot 일치 |
| BE10-OPS-03 | 3/4 | PASS (L) | §11 OPS-03 | 필터 전체 CSV·BOM·KST/ms |
| BE10-OPS-04 | 3/4 | DEFERRED (관측 완료) | §11 OPS-04 | 정량 PASS/FAIL은 #65 및 BE-10 4/4 최종 수용 기준으로 이관 |
| BE10-RET-01 | 3/4 | PASS (L) | §11 RET-01 | 86,400 / 8,640·혼합/FK/cache·이미지 독립 |
| BE10-IMG-01 | 3/4 | PASS (C/L) | §11 IMG-01 | 4건 시스템·3건 low 및 제어 예외 비저장 |
| BE10-IMG-02 | 3/4 | PASS (L) | §11 IMG-02 | 이미지 100 / 200 독립 순환 |
| BE10-IMG-03 | 3/4 | PASS (L) | §11 IMG-03 | category / inspectionId / legacy |
| BE10-IMG-04 | 3/4 | PASS (L) | §11 IMG-04 | DB 없는 sidecar 독립 조회 |
| BE10-IMG-05 | 3/4 | PASS (L) | §11 IMG-05 | 300 ID·preview/delete·cache·경쟁 회귀 |
| BE10-LOG-01 | 3/4 | PASS (C/L) | §11 LOG-01 | 실제 error.log·DB/sidecar/late 연결 |
| BE10-SIM-01 | 3/4 | PASS (L) | §11 SIM-01 | process/container·position·OFF·실MySQL |
| BE10-E2E-01 | 4/4 | BLOCKED (정상100 직접 HTTP 기능 PASS) | §13 | 정상manifest100·통계+100·CSV100 일치. 계획의 인증 Simulator interval 경로·전용 MySQL·control_attempts SQL 증거 미확보 |
| BE10-E2E-02 | 4/4 | DEFERRED (관측 완료) | §12 | 저장된 혼합100에서 자연 timeout0; 투입 전체 denominator·정량 기준 미확정 |
| BE10-E2E-03 | 4/4 | PASS | §13 | #111 merge/#112 배포 후 CSV40392행 실제 다운로드·Backend bytes 일치, 삭제200/preview410·review PATCH·simulator PUT200, 금지 출처9건403 |
| BE10-E2E-04 | 4/4 | BLOCKED (health·schema·build 기준선 유지 PASS) | §13 | #112 SHA와 종료 추가build 없음 사용자 UI 확인. container/image·migration·pending·CPU/로그 직접 조회 불가 |
| BE10-E2E-05 | 4/4 | BLOCKED (NEXT 주입 분기 PASS) | §12 | 실제 연결 단절·late task·hard cancel·DB 중단 복구·DB/로그 직접 증거 미확보 |

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
| 고유 inspection_id / 요청 수 | 각각100, run별 unique, 요청 데이터는 사전 고정 | §13.4: `be10r.n100.f45b06c023.000`~`.099`, 각각100, 고정 manifest |
| HTTP200 | 100. 이 조건만으로 정상100 통과 아님 | 100 |
| NORMAL / COMPLETED / control SUCCESS / persistence SUCCEEDED | 각100, review/excluded 각0 | 정상·제어·저장 각100, 재검사·제외0; 공개 이력 PASS/SAVED100 |
| 검사 DB / control_attempts / inspection_errors | 100 / 100 / 0 | 실제 MySQL 기반 이력·CSV100, 응답 제어성공100·오류없음100. 최신100 직접 SQL 감사는 미수행 권장사항; 직접 control_attempts 행 수를 확인한 것으로 간주하지 않음 |
| 통계 total / normal / excluded / reinspection / inferenceCount | 100 / 100 / 0 / 0 / 100 | 전후 증가량 100 / 100 / 0 / 0 / 100 |
| 품종 / 품질 / 당도 | fuji50·yanggwang50, L36·M32·S32, 두 당도 각50 | 기대 분포와 일치 |
| 정상 bin별 수 | 01·02·07·08 각각9, 나머지8개 각각8 | 기대 분포와 일치 |
| 검사 이력 CSV | BOM, 헤더 제외100행, ID 집합=DB=manifest, KST ms | 전체 CSV40,612행 중 해당 ID100행 추출, 이력·manifest ID100 및 필드100건 일치, BOM/KST ms 확인. 직접 SQL 대조는 별도 권장사항 |
| 통계 CSV | 집계 수량 합계100; CSV 행 수가100일 필요 없음 | 이 run의 통계 API/snapshot 증가량+100. 통계 CSV 형식·집계 일치는 §11 OPS-03 기존 증거 재사용; 최신100 전용 통계 CSV 추가 측정 없음 |
| 신규 검수 이미지 / 시스템 오류 | 각각0 | 각각0 |
| 자연 timeout / 저신뢰 / 당도 누락 / 제어 실패 | 각각0; 발생하면 해당 run 실패, 실패 건 대체 금지 | 해당 정상100에서 각각0, 중복·누락0. 인증 Simulator 2초 경로 자연 timeout율 시험과 구분 |

자연 저신뢰가 섞이는 전체 Dataset 시험(BE10-E2E-02)은 별도 run/집계다. 정상100의 prequalification/warmup/다른 운영 트래픽을 정상100 저장 수에 섞지 않는다. 측정 DB/기간/ID 집합을 격리하고 공용 DB 초기화·이력 삭제로 숫자를 맞추지 않는다.

## 6. 미해결 사항과 단계 수용

아래 표는 계획·단계별 관측을 보존한 것이다. 과거 미확인 항목의 현재 Close 영향과 후속 인계는 §14의 최종 판정을 따른다.

| ID | 현재 상태 | 다음 조치 / 책임 | 차단 범위 |
|---|---|---|---|
| KB-01 | 해소: 초기 INSERT 중복 409 차단, 단위/API·MySQL·전체 회귀 통과 | §7 증거 참조; 배포환경 DUP 수용시험은 후속 | KB-01 구현 blocker 해제, 2/4 전체 완료와 구분 |
| KB-02 | 해소: 검사 전용 파싱 전 body gate·24MiB 경계·chunk 누적·부분 파일 정리·전체 회귀 통과 | §8 증거 참조; 실제 HTTP 서버 BND 수용시험은 후속 | KB-02 구현 blocker 해제, 2/4 전체 완료와 구분 |
| ENV-01 | 실제 배포·DB·Inference·mount·worker 미확인 | MO/DM 환경 제공 및 run 기준선 기록 | 실제 환경 시험 |
| FE-DEP-01 | 기준선 FE parser/generator와 #55 차이; PR #92 open | FE merge·배포·Backend OpenAPI 일치 확인 | FE E2E, Backend 저장/API 단독 시험은 독립 |
| DEC-01 | N/자연 timeout 허용률/반복 미확정 | 사용자 최종 승인 | E2E-02 PASS 판정 |
| OBS-01 | 2/4 당시 추가 재현 FAIL: 점 포함 ID의 이미지 필터422·목록500. 이후 Backend 수정·로컬 회귀 통과 | 과거 증거 §9.4, 수정 검증 §9.5, 실제 MySQL·이미지 연결 검증 §11 | Backend 구현 blocker 해소. FE 브라우저 검증은 4/4 |
| DEC-02 | timer 오차·조회 부하·응답시간 수치 미확정 | timer는 사용자 최종 승인, BE/MO 측정 협의. 조회/CSV 정량 판정은 DEFERRED로 #65 및 BE-10 4/4에 이관 | 정량 timer/조회 성능 PASS 판정; 3/4 실행 완료는 차단하지 않음 |
| DEC-03 | 정상100 후보 최신 실제 판정·manifest 미확인 | 2/4 BE+DM 후보 확인, 별도 run 고정 | 정상100 실행 |

| 단계 | 현재 결과 | 완료 판단 조건 |
|---|---|---|
| 1/4 | 기준선·47개 명세·결과 틀 작성. 정량 후보 승인 대기 | 사용자 계획 확인, 미확정/의존성 인지. 제품 blocker 해결이나 실시험 통과를 뜻하지 않음 |
| 2/4 | 정의된 27개 로컬 PASS, 별도 OBS-01 관측 FAIL 후 Backend 수정·로컬 회귀 통과 | C/L 분기 증거 §9. 실제 배포 S 수용을 대체하지 않음. 과거 OBS-01 관측도 보존 |
| 3/4 | 실행 완료: 13 PASS / 0 FAIL / 2 DEFERRED | 실제 DB·보존·조회·복구 증거 §11. model 필터 문서·계약은 #68 BE-11, 조회/CSV 정량 판정은 #65 및 4/4로 이관 |
| 4/4 | #111 재시험: 1 PASS / 0 FAIL / 1 DEFERRED / 3 BLOCKED | §13. FE CSV/삭제 실패 해소, 정상100 직접 HTTP 기능 PASS. 계획의 Simulator·전용DB·SQL/실제late/복구 증거는 미확인 |

BE-10 2/4 로컬 핵심 검증은 §9, 3/4 Linux·실제 MySQL 실행 결과는 §11에 기록했다. 3/4 실행은 완료했으며 두 DEFERRED 항목은 제품 FAIL이 아니다. 4/4의 과거 실패는 §12, #111 수정 후 재시험의 확장 수용 관측은 §13이다. 위 표의 미확인 분기를 #66 원래 완료 조건과 대조한 최종 상태는 §14를 따른다. Backend 기능·통합시험은 완료이며 전체 프로젝트 운영·배포 수용 완료를 뜻하지 않는다.

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

## 10. Issue #95 — 제어·late-result 메모리 보관 상한

2026-10-06 KST, `101bbe4` checkout 기준의 로컬 수정·검증이다. commit·공유 서비스 배포는 하지 않았다. GitHub #95 본문과 전체 댓글 1개를 다시 확인했으며, 기존에 보고된 29.64MiB/2.74MiB는 수정 전 로컬 모의 부하 측정이지 실서버 RSS 측정이 아니다.

### 10.1 최소 수정

- `VIRTUAL_CONTROL_HISTORY_LIMIT=200`: `MockVirtualControl.requests`와 `status_histories`를 같은 호출 구간에서 oldest부터 함께 정리한다. 기존 list 객체와 조회 형식을 유지한다.
- configured outcomes의 선택 순번은 `_call_count`로 분리한다. `call_count`는 성공적으로 결과를 선택한 총 호출 수이며, 보관 건수나 목록 정리에 영향받지 않는다. outcomes 소진 후 추가 호출은 기존과 같이 오류다.
- `LATE_RESULT_HISTORY_LIMIT=200`: `results`, `hard_timeout_inspection_ids`, `dropped_inspection_ids` 각각 독립적으로 oldest부터 정리한다. 공통 late 상한 하나를 사용하며 제어 상한과는 별도 설정이다.
- 두 Settings는 1 이상을 검증하고 `create_app()`에서 장수명 객체에 주입한다. `.env.example`에 기본값을 추가했다.
- `_watchers`, active task 한도, business/hard deadline, 취소·shutdown·callback·DB late 진단 저장 정책은 변경하지 않았다. 결과가 목록에서 제거되어도 callback은 현재 result 참조로 계속 수행한다.
- API·FE·DB schema·migration은 변경하지 않았다.

### 10.2 단위·회귀 검증

Windows Python 3.13.15의 기존 `.venv`에서 실행했다. 수정 전 제어·late·Settings 기준 시험은 **23 PASS**였다.

| 실행 | 결과 | 검증 범위 |
|---|---|---|
| 제어·late·Settings·신규 메모리 검증 | **44 PASS** | 제어14, 기존 late12, Settings9, 신규 보관/동시성/가속9 |
| Backend·Simulator·service logging 전체 | **397 PASS / 79 SKIP**, 116.34s | #87 요청별 dynamic timeout, #67 연결/응답 오류 분류, NEXT, 확정 판정 불변, hard 취소·shutdown 포함. 전용 DB/BE-10 환경을 주입하지 않은 실행의 skip이며 통합 PASS로 표시하지 않는다 |
| 격리 실제 Inference·MySQL 통합 | **78 PASS / 0 SKIP**, 79.21s | BE-10 핵심70, MySQL late1·중복2·Repository1·이력1·관제통계/CSV1·검수1·축소 순환삭제1. 기존 2/4 핵심 회귀이며 3/4 전체15항목 수용 완료를 뜻하지 않는다 |
| Ruff check / format check / diff check | PASS | 수정 Python 파일과 작업공간 diff |

최초 전체 실행은 Windows 기본 pytest 임시 디렉터리 접근 제한으로 setup error가 발생해 중단했다. 권한을 받아 같은 범위를 재실행한 결과가 위 397/79다. 제품 결함이나 회귀 FAIL로 분류하지 않는다. 기존 Starlette/httpx·anyio deprecation warning 2개는 남아 있다.

신규 시험은 N-1/N/N+1 및 반복 호출, oldest 제거, 제어 요청/상태 대응, outcomes 소진, 상한 이후 거부→대체를 검증한다. late 결과·hard·drop 목록을 각각 초과시키고, 진행 중 inference를 Event로 유지한 채 drop 기록이 순환해도 watcher가 유지되는지 확인한다. 별도 Event 기반 병렬 시험에서는 첫 결과가 보관 목록에서 제거된 상태에서도 대기 중 callback이 끝나고 최종 `active_count=0`이 되는지 확인한다. 고정 sleep으로 새 timing gate를 만들지 않았다.

### 10.3 가속 메모리 측정

`tests/api/test_memory_retention.py`의 동일 인스턴스 반복 시험이다. append-only RecordingPersistence를 사용하지 않으며, 각 batch 종료 후 idle·GC를 확인하고 `tracemalloc` 현재/peak bytes와 목록 길이를 측정한다. 첫 batch는 warm-up으로 제외한다.

| 대상 | 반복·batch | warm-up 이후 현재 할당량 | 최종 보관량 |
|---|---|---|---|
| Virtual Control | **60,000회**, 10,000회×6 | **114,168~116,360 bytes** | requests200 / status_histories200, 총 호출60,000 |
| LateResultManager | **1,500개 완료 응답**, 250개×6 | **547,623~549,204 bytes** | results200 / hard0 / drop0, active0 |

제어 40,000회 추가 구간의 변동 폭은 2,192 bytes, late 1,000개 추가 구간은 1,581 bytes였다. 측정 sample 자체의 작은 보관 비용도 포함한다. 목록은 매 batch 200건을 유지했고, warm-up 이후 할당량 변동은 시험 gate 128KiB 이내로 plateau를 확인했다. hard/drop 목록의 보존 경계는 별도 단위 시험에서 독립 검증했다.

이 결과는 **로컬 모의 가속 시험**이다. 실제 8시간 배포환경의 Backend RSS, 브라우저 heap/DOM, CPU·DB·네트워크 경합을 측정한 결과가 아니며 #73 완료를 대체하지 않는다. #95 수정 배포 후 해당 환경에서 장시간 관측이 필요하다. BE-10 3/4의 15개 DB·보존·조회·복구 수용시험과 4/4 배포환경 수용도 별도로 남는다.

### 10.4 통합 환경·후속 판단

시험 전용 `cqc-issue95-mysql`(mysql:8.4, localhost:13319)과 `cqc-issue95-inference`(로컬 cqc-inference image, localhost:18019)를 생성했다. MySQL은 임의 생성한 인증정보와 신규 독립 schema 3개를 사용하고 기존 Alembic head `20260929_02`를 적용했다. Inference는 현재 `src`와 `models/selected`를 read-only mount하고 CPU·decode_workers8로 실행했다. 기존 Compose 5서비스를 중단·재설정하지 않았다.

정상 후보·부분 프레임·손상 이미지·자연 저신뢰는 실제 모델 HTTP로, 응답 지연·HTTP 오류 등은 시험용 HTTP responder/transport 대역으로 검증했다. 후자를 실제 모델 장애라고 표현하지 않는다. 실제 MySQL late 진단 저장 후 원 판정·bin·제어·통계 불변을 재확인했다.

실행 자료는 로컬 `outputs/issue95-validation/integration.log`, `integration.xml`, `integration-evidence.jsonl`에 남겼다(기존 outputs ignore 정책 적용). 시험 종료 후 `cqc.test=issue95` label을 확인한 컨테이너 2개와 해당 임시 볼륨만 제거했다. 전체 회귀에서 skip된 조건부 통합78개는 별도 환경에서 PASS했고, 기존 완료 run 전용 evidence audit1개는 이번 범위에서 실행하지 않았다.

**#95의 코드·로컬 검증·기록 완료 조건은 충족했다.** GitHub Issue 상태는 변경하지 않았으며 commit·배포도 하지 않았다. 수정 배포 후 #73 8시간 시험을 진행할 수 있고, #95로 인한 BE-10 3/4 blocker는 로컬 기준 해소했다. 이번 검증은 #73 8시간 측정이나 BE-10 3/4 전체 수용 완료를 대체하지 않는다.

## 11. BE-10 3/4 실제 MySQL·Linux 검증

2026-10-06 KST, 기준 HEAD `2c859dd`(PR #102 merge). #66, #70, #95, #99, #101 본문·댓글을 확인했다. #95·#99·#101은 확인 시 CLOSED였다. #70의 운영 서버 결과는 참고 자료이며 아래 시험의 PASS 근거로 대체하지 않았다. FE parser 수정은 #101에 기록되어 있으나 실제 FE 브라우저 연결은 4/4에서 확인한다.

### 11.1 환경·증거와 판정 범위

- Backend/pytest는 **Linux 컨테이너 내부 `/app`**에서 실행했다. 현재 `src`·`tests`를 복사하고 공유 OpenAPI를 read-only mount했다. Python **3.11.17**, pytest **9.1.1**, Linux WSL2 kernel **6.18.33.2**다. 목표 서버/Python 3.13 환경의 성능 수용을 주장하지 않는다.
- 실제 `mysql:8.4`, Alembic head `20260929_02`, 활성 정상 12 + 재검사 1 mapping을 사용했다. `cqc-be10-3-*` 전용 컨테이너·network·MySQL volume만 생성/중단/삭제했다. 기존 Compose 5개 서비스, 공용 DB, Jenkins는 변경하지 않았다.
- schema는 수용 시험 `be10_3`, 핵심 통합 `be10_3_core`, 일반 MySQL 회귀 `cqc_test`, 축소 보존 `be10_3_retention`으로 분리했다. localhost 전용 기존 보존 시험에는 Linux runner의 loopback TCP forwarder를 사용했다. 실제 DB는 동일한 전용 MySQL이며 대역 DB가 아니다.
- 이미지·sidecar·임시 파일은 **Linux `/tmp/pytest-of-root/...`**에 저장했다. 증거 JSON/로그만 `outputs/be10-3/`로 반출했다. Windows 공유 경로에 fault 이미지 저장을 수행한 결과로 혼동하지 않는다.
- Inference는 3/4의 판정 fixture용 socket HTTP responder, 제어는 현재 Mock Virtual Control이다. 전체 회귀의 BE-10 핵심 시험에서는 승인 모델·대표 데이터셋을 별도 Linux Inference에 연결했다. 자연 timeout·CPU 경합 수용은 4/4다.
- 테스트용 DB를 실제 중단/재기동했다. 같은 Backend app/pool의 복구를 확인했으며 장애분 backfill은 하지 않았다. 초기 저장과 최종 저장 실패 시 API의 FAILED와 DB 미저장/PENDING의 차이는 유실 허용 계약대로 기록했다.

로컬 원본 증거(기존 outputs ignore 적용):

| 증거 | 내용 |
|---|---|
| `outputs/be10-3/environment.json` | HEAD·환경·격리 설명, 비밀값 없음 |
| `acceptance-evidence.jsonl` | 시험 ID별 API, 실제 DB 행·제어, sidecar, CSV·건수·성능·process 증거. 재실행 기록은 append하며 동일 ID의 최종 해당 기록을 사용 |
| `full-acceptance.log/xml` | Linux 9개 수용 pytest 최종 run |
| `regression.log/xml` | Backend·Simulator·MySQL·실모델 핵심·logging 전체 회귀 |
| `supplement-acceptance.log/xml` | 최종 정상 판정 저장 실패·DB_ERROR·errors 8·혼합 기본 보존 보완 검증 |
| `period-acceptance.log/xml` | 86,400건 중 KST 오늘43,200건의 기간 필터 조회·전체 CSV 관측 |
| `core-evidence.jsonl` | BE-10 핵심 회귀의 실제 API/DB/late 진단 |
| `container-recovery.json`, `container-simulator-*.log` | 독립 Simulator 컨테이너 재생성·position volume·OFF·MySQL 저장 |
| `error.log`, `mysql.log` | 실제 ERROR 파일 및 전용 MySQL 중단/복구 로그 |
| `run_linux.py`, `mysql_proxy.py`, `container_recovery.py` | 로컬 시험 orchestration. 임의 인증정보는 프로세스 환경에만 두고 증거에 기록하지 않음 |

### 11.2 15개 시험 ID의 결과

`D`는 JSONL의 `db`/`newest_db`/실SQL count, `A`는 `api`/`history`/`snapshot`/`statistics`, `F`는 sidecar/CSV/log/process 증거다. 각 행의 JSONL ID와 연결하면 입력·기대·실측 및 원래 inspection_id를 확인할 수 있다. 입력 fixture ID를 실제 시연 정상 100건 수용 집합으로 보지 않는다.

| 시험 ID | 판정 | 입력·기대 결과 | 실제 결과·inspection_id | DB/API/파일 증거 | 후속 |
|---|---|---|---|---|---|
| BE10-DB-01 | PASS | warm LKG 뒤 실제 MySQL 중단; 별도 DB_ERROR. 판정·제어 유지, persistence FAILED, DB GET/CSV503 | `be10-3.outage-normal/low`: 정상/저신뢰 제어 SUCCEEDED·저장 FAILED. DB 조회 5종 DB_UNAVAILABLE. low sidecar/preview200. 주입은 정상 DB에서 별도 확인 | D: outage 행0; A: DB-01/DB-01-INJECTED; F: sidecar·MySQL log | 장애분 유실 허용, backfill 없음 |
| BE10-DB-02 | PASS | DB 복구 후 같은 Backend/pool로 다음 검사 저장·유효 mapping 갱신 | `be10-3.recovered`: SUCCEEDED, 변경 `BE10_RECOVERED_BIN` 사용, 조회200. outage 두 ID는 복구 뒤도 없음 | D/A: DB-02의 API·실제 행; F: stop/start 로그 | 운영 서버 복구는 4/4 별도 |
| BE10-DB-03 | PASS | cold/no LKG outage 및 DB 정상 불완전 mapping은500·제어0 | `be10-3.cold-outage`: 행0. `be10-3.invalid-mapping`: COMPLETED·NOT_REQUESTED·SUCCEEDED, BIN_MAPPING_CONFIGURATION_ERROR, bin null, 추가 제어0 | D/A: DB-03; mapping active13→12 실SQL 변경·복원 | HTTP500 저장 행이 비제외인 기존 동작 유지 |
| BE10-OPS-01 | DEFERRED (현행 API 검증 PASS) | 기간·품종·등급·bin·상태·오류·검수, 50/100/200 page, KST/ms, 원 판정 불변 | 225행 최신순·page200+25와 SQL ID 순서 일치. 리뷰200/없는 ID404, invalid422. `.`, KST 자정±ms 및 snapshotAt 검증. **문서 model 필터 분기는 현 API 미지원** | D/A: OPS-01, OPS-01/03-KST, KB-01/OBS-01/STORAGE; F: 필터별 CSV ID 집합 | 문서·계약 정합성 및 model 필터 추가 필요성은 #68 BE-11로 이관. 3/4 신규 기능 구현 없음 |
| BE10-OPS-02 | PASS | 정상12+low3+system4+당도누락1, total20/normal16/excluded4/reinspection8/inferenceCount16 | 20행 fixture의 API·SQL·snapshot 일치. 품종/품질 분포 합16, 정상12bin+재검사. low 포함·system 제외 유지 | D/A: OPS-02의 20개 원 행·summary·snapshot | 정상100 수용 아님 |
| BE10-OPS-03 | PASS | API 동일 filters/snapshot의 전체 CSV, BOM·한글·KST·ms | pageSize50이어도225행 전체 출력, SQL/API ID 집합 일치. EFBBBF, 부사/특, `00:00:00.123`, 통계 CSV total225, 이미지 미포함·no-store | A/F: OPS-03, OPS-01/03-KST의 header/row/경계 증거 | 운영 다운로드 경로는 4/4 |
| BE10-OPS-04 | DEFERRED (관측 완료) | 86,400건 목록·통계·snapshot·CSV 관측; 사전 정량 합격 기준 없음 | 각200·CSV86,400행. p50/p95/max 아래 표, 전체 CSV 중앙값 **34.82초**. 사용자 답변 **관측값 기록, 정량 판정 보류**에 따라 임의 기준 및 성능 PASS/FAIL을 만들지 않음 | D/A/F: OPS-04의 5회 raw sample·bytes·rows | 정량 PASS/FAIL은 #65 및 BE-10 4/4 최종 수용 기준으로 이관 |
| BE10-RET-01 | PASS | 축소·기본 86,399→86,400, oldest8640삭제·잔존77760·FK·cache·이미지 독립 | 실제 기본 경계와 초과 DB 축소7→3, 외부 삭제 cache4 보정. 혼합 잔존77760 중 system15552/비제외62208, API·SQL·CSV 일치, 이미지7 유지 | D/A/F: RET-01, RET-01-MIXED; FK0, `.fixture-15` 삭제 뒤 sidecar/preview200 | 운영 장기 관측은 #73 |
| BE10-IMG-01 | PASS | 정상/당도누락/control 예외0, low3/system4 저장 및 진단 근거 | `.fixture-12~18` low3/system4. 정상·당도누락·실패·무응답·거부/대체는 추가 이미지0. low errorCode null·system 코드/사유, threshold0.5/0.6 | D/A/F: IMG-01의 DB20·API7·sidecar7 | 실모델/운영 입력 수용 별도 |
| BE10-IMG-02 | PASS | system101→100, low201→200, 독립 oldest 제거·DB 원 행 유지 | 각 `.SYSTEM_ERROR-000`/`.LOW_CONFIDENCE-000` 이미지만 제거; 최신 1~100/1~200, 합300. 해당 DB 검사·원 판정은 보존 | D/A/F: IMG-02의 ID 집합·DB 상태·Linux root | #99 Windows 결과와 분리 |
| BE10-IMG-03 | PASS | category/inspectionId·legacy 6-field·invalid422 | 두 category200, dotted ID200, invalid category/경로422. legacy SYSTEM_ERROR·미존재 confidence/threshold null | A/F: IMG-03의 legacy 실sidecar 변경·응답 | FE 표시·parser는 4/4 |
| BE10-IMG-04 | PASS | DB 없는 sidecar 독립 조회, 이력 복원 없음 | low outage 미저장 ID와 `.LOW_CONFIDENCE-200` 행 삭제 후 목록/preview200, 검수404. retention 삭제 sidecar도 유지 | D/A/F: DB-01, IMG-04, RET-01-MIXED | DB 장애 중 DB 기반 API503는 정상 계약 |
| BE10-IMG-05 | PASS | 두 root 선택/300 ID·중복·없는 ID·확인 후 새 이미지·만료 | 중복 선택1개 삭제, 남은299 bulk 삭제200, 이후 idempotent0, malformed422, 삭제 preview410, 확인 후 신규 preview200 | A/F: IMG-05, 전체 회귀의 save/prune/list/delete 경쟁 시험 | DB/검수 변경 없음 |
| BE10-LOG-01 | PASS | 실제 error.log saved/disabled/failed; low 성공 ERROR 없음·디스크실패ERROR; 정책 불변 | `.log-saved/disabled/failed/low/low-failed`의 원 verdict·제어·DB 저장 유지. 초기/최종 DB 장애 ID 추적. late는 원 판정과 분리 DB 진단 저장 | D/A/F: LOG-01, error.log, core TIM-04/06·MySQL late 회귀 | 배포 log rotation/Volume은 4/4 |
| BE10-SIM-01 | PASS | 정지/재개·process/container 재생성·position·OFF·HTTP 실패·동시 완료 | Linux process0→2→3, 재생성3→6. 별도 container0→3、재생성3→5, OFF, 실제 DB 신규5행/각12 frames·다음 demo-1 이어감. HTTP 실패·동시 완료·revision/NEXT는 회귀 포함 | D/A/F: SIM-01의 PID·state·DB·로그, container-recovery.json, Simulator 회귀 | 목표 서버 Volume 복구는 4/4 |

KB-01/OBS-01 추가 증거: `be10-3.duplicate-low` 최초200·3장 low 이미지 저장 뒤 동일 ID409, DB 행 전체 불변, Inference/Control/이미지/active task 증가0. 동시 ID는200 하나/409 하나·Inference1/Control1. dotted ID가 history/snapshot/review/이미지 preview/CSV/recent jobs에 연결되고 Backend500/422 없음. 직접 history `inspectionId` 필터는 현행 관제 계약에 없어422이며 목록의 정확한 ID 연결과 별개다.

### 11.3 86,400건 성능 관측

각 endpoint **5회**, p95는 nearest-rank(표본5이므로 최대값과 같음). 워밍업/운영 부하/목표 서버 CPU를 통제한 성능 수용이 아니다. 해당 실제 행 수에서 status200·CSV 행 수를 확인했으며, 아래 지연만으로 FAIL 또는 PASS를 정하지 않았다.

| API | p50(ms) | p95/max(ms) | 응답 bytes |
|---|---:|---:|---:|
| inspections(기본50) | 634.35 | 1089.06 | 25,150 |
| statistics | 1113.46 | 1454.85 | 215 |
| snapshot | 1531.47 | 1606.66 | 103,093 |
| inspections.csv 전체86,400 | 34816.87 | 36458.14 | 15,725,077 |

별도 기간 fixture는 정상86,400행 중 KST 오늘43,200/전일43,200이다. 오늘 from/to·동일 snapshotAt에서 목록5회 **p50 588.48ms / p95·최대604.49ms**, 필터 전체 CSV **1회16,068.65ms / 7,905,877bytes / 43,200행**이었다. SQL 선택 건수·API total·CSV 정확한 ID 집합이 일치했고 DB 총수86,400은 불변이었다. CSV 1회 표본의 p95를 주장하지 않는다(`BE10-OPS-04-PERIOD`).

전체 CSV 중앙값 **34.82초**(원 관측값 34,816.87ms)는 후속 성능 검토 입력으로 유지한다. 현재 `completed_at` 정렬·keyset 조회에 대응하는 index가 없는 것은 코드상 확인되지만, index 추가/스키마 변경은 이번에 하지 않았다. 기간·정렬·snapshot·전체 CSV 관측은 수행했고, 사전에 확정되지 않은 **정량 PASS/FAIL은 DEFERRED로 #65 및 BE-10 4/4 최종 수용 기준에 이관**한다.

### 11.4 실패 재현·원인·영향·조치

제품 결함으로 오인하지 않고 첫 FAIL 원본 `first-acceptance.*`, `first-regression.*`, `corrected.xml`을 보존했다.

1. 실행기 준비 시 없는 `pyproject.toml` 참조로 `cp` 실패: 테스트 준비 오류. 생성된 빈 경로 및 전용 리소스만 제거하고 잘못된 참조를 삭제했다.
2. 신규 malformed ID 시험이 유효 문자열 `bad`를422로 기대: 기존 계약은 유효한 미존재 ID 삭제200이다. `bad/path`로 fixture 수정 후 이미지 시험 PASS. 제품 변경 없음.
3. Simulator endpoint를 base URL 설정에 넣어 `/v1/inspections/v1/inspections` 404: position이 실패 요청 뒤 진행하는 현행 정책은 관측했지만 실제 DB 저장 증거가 없어 해당 실행을 PASS로 쓰지 않았다. base URL 수정 후 실제 HTTP·MySQL 저장으로 재검증.
4. SIGTERM 종료 코드를0만 기대: Uvicorn 종료 후 `-15` 전달은 정상 종료 방식이다. 0/-SIGTERM과 `Application shutdown complete` 로그를 함께 확인했다.
5. 전체 회귀의 계약 파일 미mount 6 FAIL, core/집계 fixture의 schema 공유로 total100 vs5 1 FAIL: 격리 harness 결함이다. 공유 계약 read-only mount, core·일반 회귀 DB 분리로 재실행했다. Linux MySQL 보존 전용 hostname guard skip도 loopback forwarder로 해결했다.
6. 컨테이너 복구 harness가 기존 입력 dataset 디렉터리를 재사용해 FileExistsError: Windows rename 접근 거부와 다른 준비 오류다. 새 고유 입력 경로를 사용해 실제 Linux container/position volume·MySQL 저장을 다시 검증했다.

이 실패들은 원인·영향이 시험 코드/준비에 한정되어 Backend 제품 코드를 수정하지 않았다. 최종 제품 FAIL은 없다.

### 11.5 최종 집계·4/4 인계

**15 ID: 13 PASS / 0 FAIL / 2 DEFERRED. 3/4 실행 완료.** 2026-10-06 사용자 최종 분류에 따라 아래 두 항목은 제품 FAIL이 아닌 후속 이관으로 기록한다. 현행 API 계약에 따른 기능 검증과 성능 관측은 완료했으며, 기존 계약의 4/4 착수는 가능하다. BE-10 전체 최종 수용은 4/4 결과를 별도로 따른다.

| 항목 | 최종 분류 및 이관 |
|---|---|
| OPS-01 model 필터 문서/API 차이 | DEFERRED → [#68 BE-11](https://github.com/yuudong123/CQC/issues/68). 문서·계약 정합성과 필터 추가 필요성을 검토하며 3/4에서는 신규 기능을 구현하지 않는다. |
| OPS-04 조회/CSV 정량 성능 | DEFERRED → [#65 ALL-04](https://github.com/yuudong123/CQC/issues/65) 및 BE-10 4/4 최종 수용 기준. 86,400건 CSV 중앙값 34.82초를 유지하고, 사전 합격 기준이 없어 임의 PASS/FAIL을 정하지 않는다. |

이번 최종 분류는 `BE-10-results.md`와 `BE-10.md`만 수정하며 제품 코드·테스트 변경, 테스트 재실행 및 commit은 하지 않는다. 아래 실행 결과는 기존 증거를 유지한 것이다.

| 최종 실행 | 결과 |
|---|---|
| Linux 수용 pytest | **9 PASS**, 326.38s |
| 정상 최종 저장 장애·DB_ERROR·오류8·혼합 보존 보완 | **5 PASS**, 115.70s (기존3case 재검증 포함) |
| 86,400건 기간 필터 보완 | **1 PASS**, 38.34s |
| 독립 Simulator 컨테이너 재생성 | **PASS**, position0→3→5, DB 신규5행, OFF |
| Backend·Simulator·logging 전체 회귀 | **475 PASS / 1 SKIP**, 108.51s. BE-10 핵심70·실제 MySQL8 포함, 해당78 모두 PASS |
| 유일한 skip | 기존 completed-run 증거 audit의 `CQC_BE10_AUDIT_RUN` 미설정. DB 연결/수용 시험 skip이 아님 |
| Ruff | Backend·Simulator 및 관련 전체 시험 **PASS** |
| format / git diff --check | 신규 Python format **PASS**, diff **PASS** |

서로 다른 run의 재검증 건수를 새 고유 testcase로 중복 집계하지 않는다(신규 opt-in pytest 고유12case, 실행15case). 정상 최종 저장 장애의 `be10-3.final-outage`는 **NORMAL·control SUCCEEDED·API persistence FAILED**, 실제 DB 초기 행 PENDING이었다. DB down으로 best-effort 실패 상태 갱신도 실패할 수 있는 계약이며, 복구 뒤 `.final-recovered`는 SUCCEEDED였다. `be10-2-1ef761d9-late-a`는 DB late payload/received_at만 추가되고 재검사 bin·원 제외 정책·통계가 불변이며 동시 `.normal-b`도 정상 저장됐다.

3/4 실행 당시 수정 파일은 신규 `tests/api/test_be10_operations_integration.py`와 이 결과 문서뿐이다. 로컬 증거·harness는 ignored outputs에 있다. 시험 종료 후 label을 확인하고 전용 컨테이너·MySQL volume·network·position volume만 정리했다.

4/4로 넘기는 범위는 FE 브라우저 E2E·API 모드/실제 표시, 정상100 전체 수용, 2초 자연 timeout 비율, 실모델 CPU 경합·목표 서버 성능, 배포 proxy/body 제한·Volume/log 운영 복구다. #99 Windows 재현 원인을 이번 Linux PASS로 해결했다고 주장하지 않는다. #73 8시간 실제 운영 관측도 이 로컬 시험으로 대체하지 않는다. 기존 기능·공유 API·DB schema·설정·FE·MLOps 배포 파일은 수정하지 않았으며 commit도 하지 않는다.

## 12. BE-10 4/4 실제 배포 서버 부분 실행

2026-10-06 KST **15:58~16:27:03**, 실제 `192.168.133.106`의 Backend:8000·Inference:8001·FE:3100을 사용했다. 클라이언트는 Windows/Python 3.13.15·설치된 Chrome headless(1600×900)이다. SSH는 사용자가 제공하지 않았고 비밀번호·토큰 입력 금지에 따라 Jenkins 로그인도 수행하지 않았다. 사용자는 Jenkins UI/HTTP로 가능한 시험을 진행하고 직접 DB/CPU/로그 접근 항목은 BLOCKED로 구분하도록 지시했다.

### 12.1 기준선과 증거 수준

| 항목 | 시작 기준선 / 출처 | 종료 확인 |
|---|---|---|
| Jenkins / branch / SHA | **사용자 제공** #110 / dev / `c24b2d9676b735bed99c9c5a1a3116c3d1afb007`. 로컬 HEAD도 동일 | 실행 서버 SHA·추가 배포 없음은 독립 확인 불가 |
| stage 결과 | 사용자 제공 Python413 PASS/91 SKIP, Web52 PASS/0 FAIL, Build→Deploy→Verify 성공 | 이 값을 이번 시험의 테스트 실행 건수로 합산하지 않음 |
| container/image | 사용자가 세 서비스 running/healthy·#110 로그와 일치를 확인. 실제 ID 문자열은 미제공 | 직접 inspect 불가. 과거 #109 ID를 #110 값으로 재사용하지 않음 |
| pending | 사용자 제공 `false` | 작업공간 직접 접근 불가, 종료값 BLOCKED |
| model/checkpoint | 실제 `/health`: `cqc-apple-separate12-focal-v2-cal-20260930`, `b254206e4091732a49c5db02c12e5fb6dc3d996dbce694c2e82d442a2ba8753a`, CPU·12 views·decode_workers8 | 동일. ready·model_loaded 유지 |
| migration / Settings | 과거 MO 기록 `20260929_02`, connect/business/hard 기본200/500/2000ms, threshold0.50/0.60, DB86400/8640, 이미지100/200, 제어/late200/200 | 현재 DB revision·실제 Settings·메모리 cap 직접 조회 BLOCKED. 오래된 기록을 #110 직접 측정으로 전환하지 않음 |
| interval/concurrency/faults | 실제 snapshot2000ms/1/[]/ALL | 동일로 복구, running=true. NEXT 시험 동안 revision만 변경 |
| health / OpenAPI | 실제 BE·FE·Inference health200. snapshot 4개 component healthy | 정상 유지, BE/Inference OpenAPI 원본 bytes 시작·종료 동일 |
| 기준선 유지 | 사용자 #110 기준선으로 시작 | 모델·공개 schema·라인 설정은 일치. 컨테이너·pending·Jenkins 무부하/배포 freeze는 미확인 |

Jenkins #110 API와 headless 웹 UI 모두 인증이 필요했다. 웹은 `403` 및 `/login?from=.../110/`로 이동해 `Sign in to Jenkins`를 표시했다. 사용자의 로그인된 UI 접근 가능 여부와 이 자동화 세션의 접근은 별개다. 비밀번호/토큰을 입력하지 않았다(`jenkins-ui.json/png`). 원격 Docker·SSH·DB 접근을 로컬 Docker의 상태로 대체하지 않았다. 종료 증거는 `baseline-final.json`, 모델/schema 시작 증거는 `inference-start.json`·`*-openapi.json`이다.

### 12.2 5개 시험 ID 판정

각 ID는 계획의 전체 범위를 기준으로 집계한다. 부분 분기 PASS를 ID 전체 PASS로 승격하지 않는다. 공통 실행 기준은 위 #110/`c24b2d9`이며 DB 칸의 API 기반 값과 SQL 직접 증거를 구분한다.

| 시험 ID | 판정 | 실행 / 입력·inspection_id | 실제 API·DB·FE 결과 | 증거 / 남은 항목 |
|---|---|---|---|---|
| BE10-E2E-01 | **BLOCKED** | 15:58:56.505~16:02:14.479 서버 완료시각, 기존 Simulator2000ms/1·장애OFF의 신규 혼합100. 첫 `15ac4e25-9b51-4c77-9c4b-53f4da784fba`, 끝 `66bd556a-b37c-4150-82fa-1eb15f19d9ca` | 고유100, 정상87·REVIEW13, control SUCCEEDED100·persistence SAVED100·error NONE100. CSV 선택100·필드100/100 일치. 서버 완료시각 경계의 통계 total+100·비제외normal+100·reinspection+13·excluded+0 | `observation.json`, `verified.json`, `statistics-window.json`, `history.csv`. 정상6후보×당도2 manifest의 정상100 시험을 실행한 것이 아님. 입력 고정·전체 요청 추적·SQL100/control_attempts100 직접 대조·전용 집계 미확보 |
| BE10-E2E-02 | **DEFERRED** | 같은 저장100, natural 관측과 NEXT 주입을 별도 구간으로 분리 | 저장 표본에서 자연 business timeout0/100(0%), connection/system error0. hard cancel은 관측 불가. 정상87%, low13% | 유실·HTTP 실패 요청은 이력에 없을 수 있어 전체 투입 기준 비율/누락0을 입증하지 않음. denominator·성능 gate 승인 전 정량 PASS/FAIL 없음 |
| BE10-E2E-03 | **FAIL** | 실제 Chrome90초·snapshot90회, 별도 이력/통계/이미지 모달·preview 및 dotted ID·CSV·삭제 재현 | snapshot200 90/90·source=backend, jobs20회·recent90회, 로드된 이미지 최대12, blank0, pageerror0. 이력50/200행·통계18행·이미지300/299행·preview 로드, dotted ID 두 건 표시 PASS. **FE 전체 CSV 약5초 후503, 이미지 삭제403·행 잔존** | `browser.json`, `browser-modals.json`, `browser-dotted.json`, `csv-repro.json`, `fe-*.png/txt`. §12.6 재현·원인·영향·blocker. Backend 직접 CSV/삭제는 PASS |
| BE10-E2E-04 | **BLOCKED** | 시작·종료 health/schema/설정 비교 | health 정상, 모델·checkpoint·공개 schema 동일, interval2000/concurrency1 유지. 서비스 재시작·DB 중단·재배포는 수행하지 않음 | `baseline-final.json`, `jenkins-ui.*`. container/image·pending 종료값 및 시험 중 배포/CPU 부하 유무는 BLOCKED. #69 과거 복구는 참고 증거이며 이번 재시험 결과 아님 |
| BE10-E2E-05 | **BLOCKED** | 16:06~16:07, 기존 공개 Simulator 설정으로 NEXT 각1건: TIMEOUT·INFERENCE_ERROR·CONTROL_REJECTED·CONTROL_NO_RESPONSE·DB_ERROR | timeout/추론 오류는 제외·재검사·제어SUCCEEDED·SAVED. 거부는 FALLBACK·재검사·SAVED, 무응답은 NO_RESPONSE·reviewRequired·SAVED. DB_ERROR live 완료 ID는 이력에 없고 후속 무주입 요청은 SUCCEEDED/SAVED. OFF·ALL·running 설정 복구 | `faults.json`, `faults-end.json`. 주입 timeout은 실제 inference task/late 증거가 아님. 실제 연결 단절·late/hard cancel·DB 중단/pool 복구·DB/로그 직접 대조 BLOCKED |

**정상100 정의를 변경하지 않았다.** 기본 Dataset의 저신뢰13건은 유효한 정책 결과로 제품 FAIL이 아니며, 추가 정상 결과로 대체해 정상100 성공이라고 표시하지 않는다. 통계의 `normal`은 low를 포함한 비제외 집계이므로 +100이 정상 판정100을 의미하지 않는다. 시작/종료 snapshot의 today 증분은 +97로 관측 시작 경계와 달랐으며 정상100 증거로 사용하지 않았다. `statistics-window.json`은 첫 서버 완료 timestamp 직전과 마지막 timestamp의 동일 snapshotAt 경계를 사용해 +100을 대조했다.

### 12.3 지연·자연 오류·FE 안정성 관측

| 측정 | n | 평균 | median | p95 | max |
|---|---:|---:|---:|---:|---:|
| Inference 응답의 inferenceMs(ms) | 100 | 174.729 | 166.777 | 234.879 | 311.302 |
| 서버 저장 완료 간격(s) | 99 | 1.99974 | 2.002 | 2.250 | 2.400 |
| history GET 클라이언트 RTT(ms) | 관측 반복 | 334.025 | 315.478 | 494.980 | 552.328 |
| snapshot GET 클라이언트 RTT(ms) | 2 | 815.433 | 815.433 | 888.173 | 888.173 |
| 전체 CSV GET(ms) | 1 | 16454.052 | 단일 표본 | 단일 표본 | 16454.052 |

RTT는 Windows 클라이언트↔서버 조회값이며 **검사 POST 전체 응답시간이 아니다**. Inference 내부값도 Backend→Inference 전체 HTTP 지연이 아니다. CPU·서버 RSS·동시 검사 경합은 접근 부족으로 BLOCKED. CSV는 **38,514행·8,964,192 bytes·UTF-8 BOM**, 관측100의 ID·KST ms·prediction·두 confidence·bin·model version·상태100/100 일치. 단일 표본에 p95를 주장하지 않는다. 별도 기존 MO-09 실행의 오늘 필터 CSV10,688행 및 1/5/10/30분 통계 CSV 형식도 통과했다(`live-checks/`).

FE 90회 polling에서 pageerror0·blank0·loaded views 최대12, jobs20/90·recent90/90이었다. 실패 요청2개는 `/market?..._rsc=`의 `net::ERR_ABORTED`이며 관제 snapshot 실패가 아니다. heap은 7,369,413~27,199,271 bytes, 종료18,337,646 bytes, 이전 표본보다 감소34회였다. DOM/이미지/canvas 크기는 `browser.json`에 기록했다. 이 짧은 관측을 메모리 plateau·8시간 안정성·#95 Backend cap 확인으로 해석하지 않는다. #73은 별도다.

### 12.4 저신뢰·NEXT 오류·이미지 결과

- 자연 low13건은 모두 LOW_QUALITY_CONFIDENCE에 연결됐고 이미지 API의 quality confidence<0.60·cultivar threshold0.50·quality threshold0.60·errorCode=null과 FE 사유 표시를 확인했다. 예: `bbfd29aa-1921-4508-a371-a639d7fa5b9e`. LOW_CULTIVAR_CONFIDENCE·LOW_BOTH_CONFIDENCE는 이번 입력에서 발생하지 않아 BLOCKED. 운영 threshold를 변경하거나 모델 응답을 가짜로 만들어 3종 통과를 주장하지 않았다.
- NEXT timeout: `ddf330d6-c0d3-4a19-b414-7a042c2055b6`, TIMEOUT/INFERENCE_TIMEOUT·excluded=true·재검사·control SUCCEEDED·SAVED. NEXT inference error: `824cabc0-79bb-45c1-b62a-68fbad02a867`, ERROR/INFERENCE_ERROR·excluded=true·재검사·SUCCEEDED·SAVED. 실제 connection 분류(#67)는 기존 이미지의 INFERENCE_CONNECTION_ERROR metadata만 읽었고 신규 단절로 재검증하지 않았다.
- NEXT 거부: `2adc09af-a160-4306-b59f-ffe0707fce21`, FALLBACK·CONTROL_REJECTED·재검사·SAVED. NEXT 무응답: `420f697e-4afe-4af7-bf54-c5f5a8229a20`, NO_RESPONSE·CONTROL_NO_RESPONSE·reviewRequired=true·기존 normal target bin 유지·SAVED. 실제 control_attempts 호출 수의 SQL 확인은 BLOCKED.
- DB_ERROR 후보 live ID `d7bf10b3-240a-4bfb-8d45-b1dbd1f78af7`는 완료 preview가 있으나 해당 구간과 이후 이력에 없었다. 후속 `fb7c908c-244a-41d9-b534-273a3ca67b8c`는 SUCCEEDED/SAVED. 이는 NEXT 저장 실패 관측으로 실제 MySQL shutdown/pool 복구·응답 persistence 상태 직접 증거와 구분한다.
- 이미지 목록은 시작/삭제 직전 SYSTEM_ERROR100·LOW_CONFIDENCE200 유지. 신규 NEXT 시스템 이미지24장이 기존 oldest24장을 교체했고 잔존76장의 createdAt보다 제거24장이 오래됨을 확인했다. low는 운영 스트림으로 기존200이 신규200으로 교체됐다(`prune-comparison.json`). category·inspectionId·decisionReason·threshold 연결은 실제 API 값으로 확인했으며 sidecar 파일 직접 조회는 BLOCKED.
- 이번 NEXT timeout이 만든 `10f3dc90cde345fb9e1f0d8d1dfdbe63_11` **1장만** preview200 → 계약의 `DELETE /v1/quality/fault-images` body `ids`로 삭제200 → preview410을 확인했다. 시스템99·low200으로 다른 category 불변. 사용자 요청 범위의 삭제 시험이며 기존 운영 이미지 전체 삭제는 하지 않았다. 첫 `/fault-images/{id}` 요청404는 시험 harness의 잘못된 경로로 제품 FAIL이 아니다. 첫 증거 `verified-first-attempt.json`·`images-first-attempt.json`도 보존했다.

### 12.5 Deferred·최종 판정·남은 조치

**5 ID 집계: 0 PASS / 1 FAIL / 1 DEFERRED / 3 BLOCKED.** 핵심 HTTP·FE·이미지·NEXT 분기의 실제 통과 증거는 위와 같으며, 관측하지 못한 분기를 기존 2/4·3/4 결과로 대신 통과시키지 않았다. 추가 검증에서 FE CSV·삭제 기능 실패를 재현해 E2E-03을 FAIL로 기록했다. 제품 코드는 수정하지 않았다. 입력/접근 제약에 따른 BLOCKED는 결함과 구분한다.

- model 필터: 현행 API 미지원, 제품 FAIL 아님, #68 BE-11 검토 유지.
- 조회/CSV 성능: 기존 86,400건 CSV 중앙값34.82초 유지. 이번 서버38,514건 단일16.454초는 데이터량·환경·표본이 달라 직접 향상/퇴행 판정하지 않는다. #65/4/4 정량 기준은 임의 확정하지 않는다.
- BE-10 최종 판정 **C: 미완료**, **#66 Close 불가**. FE CSV/삭제 기능 FAIL이 있고 고정 정상 manifest100·전용 집계·입력/POST/SQL 직접 증거가 아직 없으며 실제 late/DB 복구·배포 종료 증거도 부족하다. dotted FE는 추가 실제 입력으로 통과 확인했다.
- #66: 정상100 및 미검증 통합 분기, #65/#103: 최종 수용 기준·파트 실행 분담, #96: #110/종료 container·pending·배포 freeze 증거, #68: model 필터 계약, #73: 실제8시간 관제. #99 Windows 실패와 이번 실서버 HTTP/Chrome 결과는 별개이며 #69 복구를 재설계/재실행하지 않았다.
- 후속 실행은 담당자가 정상6후보 manifest·고유100 ID·2000ms/1·동시 입력 없는 집계를 마련하고 DB/로그/CPU/현재 image·pending 증거를 제공해야 한다. Jenkins 측정 중 배포 중지 여부는 아직 확인되지 않았다. 이번 사용자 제한에 따라 SSH·로그인 비밀번호/토큰 입력·서비스 중단·재배포·commit은 하지 않았다.

증거·임시 실행기는 ignored `outputs/be10-4/`에 보존했다. 변경된 tracked 파일은 이 결과 문서뿐이며 기존 MO 자동화·제품 코드·테스트 파일은 수정하지 않았다. 문서 `git diff --check`만 확인하고 전체 회귀/Ruff를 이번 실행 건수에 포함하지 않는다. Issue/PR 댓글·상태도 변경하지 않았다.

### 12.6 추가 실제 입력·FE 기능 실패 재현

승인된 12-view 묶음 `demo-601031008000-000` 및 `demo-601031028000-000`을 기존 metadata/순서 그대로 실제 `POST /v1/inspections`에 전송했다. 인증 토큰·가짜 모델 응답·운영 threshold 변경은 사용하지 않았다. Simulator interval 헤더 없는 직접 HTTP 분기이며 고정 Simulator 정상100이나 자연 timeout 표본과 별도다. 첫 두 건 뒤 CSV 재현에 시간이 걸려 UI 확인용 새 ID 두 건을 추가했으며 원 입력 결과도 `dotted-first.json`에 보존했다.

| 검사 | 결과 |
|---|---|
| `be10.4.normal.e05af398`, `be10.4.normal.2be7f80d` | HTTP200, NORMAL·12 frames·DEMO_BIN_02·control SUCCEEDED·persistence SUCCEEDED, 정상 보존 이미지0 |
| `be10.4.low.c1332198`, `be10.4.low.a4848618` | HTTP200, LOW_QUALITY_CONFIDENCE·12 frames·재검사·control SUCCEEDED·persistence SUCCEEDED, 각 low 이미지12·threshold0.50/0.60·errorCode=null |
| 실제 FE | 두 최신 dotted ID가 이력200건 페이지에 정상 표시, dotted low preview 로드. parser500/422/목록 전체 거부 없음(`browser-dotted.json`, `fe-dotted-history-final.png`, `fe-dotted-preview.png`) |

직접 POST4건의 클라이언트 RTT는 평균1280.182ms·median1315.547ms·p95/max1356.377ms이며 표본4의 기술 통계다. 앞선 Inference 내부값·2초 Simulator 저장 간격과 혼동하지 않는다.

**기능 FAIL 1 — FE 전체 이력 CSV 다운로드**

1. 재현: 실제 FE 검사 이력 → CSV 내보내기, 약39,039건 검색 상태. 요청 `/api/quality/inspections.csv?page=1&pageSize=50&snapshotAt=1791271190575`가 **4998ms 후503**, 다운로드0, UI `서비스에 연결할 수 없습니다.`. `csv-repro.json`·`fe-csv-failure.png`에 증거 보존.
2. 원인: `src/lib/quality-proxy.ts`의 `AbortSignal.timeout(5000)`가 CSV에도 적용됨. 동일 query를 Backend `/v1/quality/inspections.csv`에 직접 보내면 **200·39,039행·BOM·9,086,921bytes·13,921.531ms**에 완료되고 최초 dotted ID 각1행 포함(`csv-direct-repro.json`). FE client의 기본8000ms 제한도 코드상 존재하지만 실제 재현에서 먼저 반환된 실패는 프록시5초503이다.
3. 영향: 대량 이력의 실제 FE CSV export 기능. Backend CSV 내용 검증과 별개로 사용자가 다운로드할 수 없다. 임의의 정량 성능 기준을 만든 FAIL이 아니며 기존 성능 DEFERRED를 취소하지 않는다.
4. blocker: **4/4 E2E-03 최종 수용 blocker**. FE/배포 프록시 timeout과 CSV 경로를 담당자가 검토해야 한다. Backend 쿼리 최적화 필요성은 별도 분석이며 이번에 임의 index/기능/FE 코드를 변경하지 않았다.

**기능 FAIL 2 — FE 이미지 삭제의 403**

1. 재현: 이번 시험의 `be10.4.low.a4848618` 이미지 `102da278a15e452d806e9118abf9d8e7_11`에서 미리보기 → 삭제 → 삭제 확인. 실제 FE DELETE 응답 **403**, UI `요청을 처리하지 못했습니다 (403).`, 행 잔존·직접 preview200·이미지12 유지. `browser-dotted.json`·`fe-delete-result.png`·`ui-delete-audit.json`에 기록.
2. 원인 근거: 추가 삭제 없이 빈 `ids:[]`, 공개 FE Origin `http://192.168.133.106:3100`, `Sec-Fetch-Site:same-origin`으로 같은 FE endpoint를 호출해 **403 / CROSS_ORIGIN_WRITE** 재현(`fe-delete-empty-repro.json`). 코드 조건은 Origin와 request URL origin 불일치 또는 cross-site다. 이 요청의 same-origin 값으로 볼 때 **프록시가 인식한 request URL origin과 공개 Origin의 불일치가 원인이라는 추론**이며 내부 host/header 실제값은 서버 접근 부족으로 미확인이다.
3. 영향: 실제 FE 검수 이미지 삭제. 같은 프록시의 다른 쓰기 경로도 영향 가능성이 있으나 검수 PATCH·설정 PUT는 이번에 같은 403으로 재현하지 않았으므로 확정하지 않는다. Backend 직접 API의 owned timeout 이미지 삭제200→preview410과 구분한다.
4. blocker: **4/4 E2E-03 수용 blocker**. FE/MO가 공개 origin·reverse proxy host/protocol 및 쓰기 보호 조건을 대조해야 한다. 보호 검사를 우회하거나 FE 코드를 임의 수정하지 않았다.

첫 UI 삭제의 CDP response body 수집 오류와 최근50건 밖으로 이동한 ID 대기 timeout은 harness 문제로 구분했다. 이력200건 조회로 dotted 표시를 확인하고, 실패한 삭제의 실제403·행 잔존·preview200을 따로 수집했다. 최종 기능 판정은 이 증거에 근거하며 CDP 수집 실패 자체를 제품 결함으로 세지 않는다. 이번 실행에서 신규 Issue 생성·댓글 작성·Issue Close는 하지 않았다. 후속 FE/MO 결함 처리를 #65/#66 수용 결과에 연결한 뒤 수정을 배포하고 해당 두 경로를 재검증해야 한다.

## 13. #111 merge 후 BE-10 4/4 제한 재시험

2026-10-06 KST **17:10:39~17:18:28** 시작/종료 HTTP 기준선, FE CSV·쓰기 회귀와 정상100의 미완료 기능만 재시험했다. §12의 실패는 당시 증거로 보존한다. 결과는 ignored `outputs/be10-4-retest/`에 저장했으며 제품·테스트 소스 변경, 서버 재배포/서비스 중단, Issue 상태 변경, commit은 하지 않았다. 기존 변경 중인 이 결과 문서를 이어 갱신했다.

### 13.1 dev·배포 기준선

- `git fetch origin dev` 후 `git merge origin/dev`: Already up to date. HEAD/origin/dev 모두 **`35ac95250a39fd659ef46a8e4d064733bcc9e57c`**. GitHub PR #111 merged=true 및 merge SHA 일치 확인. #109/#110은 #111의 Closes로 CLOSED이며 재시험을 이유로 다시 열지 않았다.
- #111 변경은 FE proxy의 공개 Host 출처 판정과 CSV 전용60초, 브라우저 CSV60초 및 기존 계약 시험이다. Backend/Inference 기능 변경 없음. 일반 proxy5초·FE client8초는 diff에서 유지됨을 확인했다.
- **사용자 UI 확인:** Jenkins **#112 SUCCESS**, 배포 SHA 위 dev와 일치, Build→Deploy→Verify 성공. 시작 이후 추가build 없음 및 종료 확인 질문에도 추가build 없음으로 응답. 이 기준으로 build/SHA 유지 PASS. 자동 Jenkins API는 시작·종료403이며 로그인·비밀번호/토큰 입력을 하지 않았다.
- 시작/종료 BE·Inference·FE health200, snapshot source=backend·MySQL healthy. 모델 `cqc-apple-separate12-focal-v2-cal-20260930`, checkpoint `b254206e4091732a49c5db02c12e5fb6dc3d996dbce694c2e82d442a2ba8753a`, CPU/ready/model_loaded 동일. BE/Inference 공개 OpenAPI bytes hash 동일.
- 시작/종료 running=true·interval2000ms·concurrency1·faults=[]·scopeALL 동일. 쓰기 회귀와 정상100 집계 격리를 위한 일시 정지/재개로 revision은 변경됐다. 다른 설정이 바뀌면 복구를 거부하는 guard를 사용했고 실제 복구 성공.
- 현재 container/image ID·pending·MySQL alembic_version·전체 runtime Settings·CPU/RSS/로그는 SSH/직접 접근 없이 확인 불가. 사용자 build 확인을 Docker inspect나 SQL 측정으로 대체하지 않음. `start.json`, `end.json`, `baseline-comparison.json` 참조.

### 13.2 #109 CSV 및 일반 조회 회귀 — PASS

| 항목 | 실제 결과 | 증거 |
|---|---|---|
| 실제 FE3100 → 검사 이력 → CSV 내보내기 | HTTP200, **40,392행·9,403,218bytes**, 실제 `cqc-inspections.csv` 다운로드 완료, downloadFailure=null, **19,603ms** | `csv-browser.json`, `fe-history.csv`, `fe-csv-success.png` |
| 동일 snapshot query의 Backend 직접 CSV | HTTP200, **40,392행**, **15,117.159ms** | `backend-history.csv`, `csv-comparison.json` |
| 데이터 대조 | 모든 bytes·행·필드 동일, 양쪽 UTF-8 BOM. SHA256 `8f5366c9ea4d0976b52be7b2fd0ffc16a46c1469103cb23943fe0c2227b9f1cd` | `csv-comparison.json` |
| 일반 조회 | 다운로드 중 snapshot20회 전부200, pageerror0. 일반5초/8초 설정 유지 확인 | `csv-browser.json`, #111 diff |

고정 query는 `page=1&pageSize=50&snapshotAt=1791274247450`. 지연 값은 단일 실서버 표본이며 성능 정량 gate를 승인한 것이 아니다. 일반 조회를 실제 서버에서 6초 지연시키는 장애는 주입하지 않았다. #111의 6초CSV200/6초snapshot503 시험 기록은 PR 참고 증거이고 이번 실행 건수에 합산하지 않는다.

### 13.3 #110 FE 삭제·공유 쓰기 보호 회귀 — PASS

- 이번 시험 생성 이미지: 검사 **`be10r.pre.88bc68949a7b`**, image **`20a7764e4289421d8f5ebde0f9219ef0_11`**. 사전 확인의 실제500ms deadline timeout이 만든 시스템 이미지이며 기존 운영 이미지를 선택하지 않았다.
- 실제 FE 미리보기 로드·삭제 확인: **DELETE200**, 해당 행0·Backend 이미지 목록에서 제거. preview는 삭제 전200 → **Backend410 / FE410**. 다른 이미지는 삭제하지 않았다.
- FE 동일 출처 review PATCH: 시험 검사 `be10r.pre.8be27fe7bc26`의 QUALITY_SUSPECT 지정200 → NONE 복구200. 응답 ID/값 일치.
- FE 동일 출처 simulator PUT: 변경 전 상태 그대로 요청200, revision0→1, running/interval/concurrency/faults/scope 값 불변.
- 악성 Origin(`https://evil.example`)·공개 Origin+cross-site·Origin:null 각각 DELETE/PATCH/PUT: **9/9 HTTP403 / CROSS_ORIGIN_WRITE**. DELETE는 빈ids, PATCH는 없는 시험ID, PUT는 invalid revision으로 보호 거부 실패 시에도 실제 운영 설정/이미지가 바뀌지 않는 입력을 사용했다.
- `writes-browser.json`, `fe-delete-success.png`, `protection.json`. write 보호를 제거/우회하지 않았고 제품/FE/MO 코드를 수정하지 않았다.

### 13.4 고정 정상100 — 직접 HTTP 기능 PASS, E2E-01 전체는 BLOCKED

계획 §5의 6후보를 현재 모델로 재확인한 뒤 12 variant×8회+FL/YL의 두 당도4건 manifest를 고정했다. 각 묶음의 원12장·metadata 순서를 유지하고 13.9/14.0·고유ID·2초 간격·순차1·장애OFF로 **100건을 한 번** 보냈다. 후보검증/warm-up은 별도 ID이며 정상100에 합산하지 않았다. 운영 DB를 비우지 않고, HTTP Simulator를 잠시 정지해 진행 중jobs 소진 후 시험했다. 전용 MySQL을 만들었다고 표시하지 않는다.

처음 운영 스트림/CSV와 겹친 사전 확인에서 직접500ms 요청 두 건이 timeout이었다(`be10r.pre.4b1a2e31c2f5`, `be10r.pre.88bc68949a7b`). 이후 Simulator 정지 상태의 6후보는 전부 NORMAL, cultivar 최소0.999411821·quality 최소0.919440091. 그 다음 확정한100 manifest에서는 교체·추가 요청으로 실패를 제외하지 않았다. 인증 Simulator interval 헤더는 사용하지 않았으므로 실제 business deadline은 **직접 요청 fallback500ms**이며, 입력 간격2000ms와 같은 의미가 아니다.

| 항목 | 실제 결과 |
|---|---|
| inspection_id | `be10r.n100.f45b06c023.000`~`.099`, 고유100·HTTP200 100 |
| 판정/제어/저장 | **NORMAL100 / control SUCCEEDED100 / persistence SUCCEEDED100**, history PASS100·SAVED100. timeout·중복·누락0 |
| 이력/CSV | 최신 history의 입력ID집합 정확히100, CSV selected100·unique100·필드100/100 일치·BOM. CSV 전체40,612행 중 해당100을 대조 |
| 통계 및 snapshot | total+100·normal+100·inferenceCount+100·excluded+0·reinspection+0. history count+100. 집계구간의 입력 외 신규ID0 |
| 분포 | fuji/yanggwang50/50, L/M/S36/32/32. bin01/02/07/08 각각9, 나머지8개 각각8. 재검사bin+0 |
| 보존 이미지 | 정상100의 inspectionId에 해당하는 신규보존 이미지0 |
| POST RTT ms, n100 | 평균1062.729·median1062.252·p951134.005·max1173.581 |
| Inference 내부 ms, n100 | 평균151.539·median146.087·p95186.934·max219.343 |

`normal.json`, `normal-verified.json`, `normal-history.csv`에 응답·입력 manifest·전후통계·이력·이미지 증거를 보존했다. 저장100은 실MySQL 기반 공개 이력/CSV의 증거이며 **SQL 직접 inspection/control_attempts100 확인은 BLOCKED**. 계획 S의 Simulator→Backend 인증2초기한 경로·전용DB 조건을 이번 직접HTTP 입력으로 충족했다고 선언하지 않는다. 그러므로 정상100의 기능 미충족은 해소했지만 계획 전체 E2E-01은 부분 PASS/BLOCKED로 유지한다. 이는 새 요구사항이 아니라 기존 BE-10.md §5·INPUT/EFFECTS 범위다.

### 13.5 나머지 BLOCKED 및 최종 분류

| 기존 시험 ID | 재시험 후 판정 | 남은 범위 |
|---|---|---|
| BE10-E2E-01 | **BLOCKED**, 직접 정상100 기능 PASS | 인증 Simulator 경로·계획의 전용DB·control_attempts/DB 직접 증거 |
| BE10-E2E-02 | **DEFERRED** | 기존 혼합100 저장표본 natural timeout0 유지. 이번 직접500ms 사전timeout2 및 고정정상100은2초Simulator 자연율 표본에 합산하지 않음. #65/#103의N·정량 기준 미확정 유지 |
| BE10-E2E-03 | **PASS** | #109/#110 실제 배포 회귀 해소. 이전 관제/12-view/dotted 표시 PASS 증거와 결합 |
| BE10-E2E-04 | **BLOCKED**, 공개health/schema·사용자build확인 PASS | Docker image/container·migration·pending·직접CPU/RSS/로그 접근 불가 |
| BE10-E2E-05 | **BLOCKED**, 기존NEXT 분기 PASS 유지 | 현재 low 이미지는 LOW_QUALITY만 관측. LOW_CULTIVAR/LOW_BOTH·실제late 진단DB·hard cancel·실DB중단/pool복구·로그 직접 증거 미확인 |

사전timeout2의 수분 뒤 고정snapshot CSV는 여전히 TIMEOUT·재검사bin·예측빈값이었다(`additional.json`). 최신200건 페이지에는 이미 빠져 있어서 고정CSV로 대조했다. 이를 실제late 결과가 DB에 저장됐다는 증거로 확대하지 않는다. SSH·비밀번호/토큰 입력·실DB중단은 사용자 제한에 따라 수행하지 않았다.

- **4/4 전체5 ID: 1 PASS / 0 FAIL / 1 DEFERRED / 3 BLOCKED**. 누적47 ID는 기존2/4·3/4 결과를 포함해 **41 PASS / 0 FAIL / 3 DEFERRED / 3 BLOCKED**이며47개를 이번에 재실행한 수치가 아니다. 이번 범위에서 새 제품 결함은 확인되지 않았다.
- **BE-10 최종 C: 미완료, #66 Close 불가.** FE 제품 FAIL은 해소됐고 정상100 직접HTTP 기능은 통과했지만 기존 계획의 전체 S 경로/증거가 남았다. 접근/환경 미확인을 제품 FAIL로 기록하지 않았다. #66 실제상태는 OPEN이며 변경하지 않았다.
- 남은 연결: #66의S통합 미확인 범위, #65/#103의수용기준·실행분담, #96의직접배포/DB/runtime 증거, #68의model필터 계약 및API/DB 동결. #109/#110은CLOSED·실서버회귀PASS로 유지. 기존 종료Issue를 자동재개하거나 새Issue를 만들지 않았다.
- **BE-11 #68 착수 가능**: 현행OpenAPI/API 문서 대조와model필터 최종계약 검토는 별도로 진행할 수 있다. 실서버migration 일치·운영동결 완료는 확인되지 않은 조건이므로 #68 전체완료/Close는 아직 선언하지 않는다.

제품 코드·테스트 소스·BE-10 계획 문서는 변경하지 않았으며 전체Backend/FE 회귀·Ruff를 이번 재시험 건수에 포함하지 않는다. 결과 문서의 `git diff --check`를 확인한다. 종료 이후 CSV대조·문서정리는 배포기준선 확인시각과 구분한다.

## 14. #66 최종 완료 기록 및 ALL-04 증거 인계 (2026-10-06)

사용자 재판정의 **B: 조건부 완료 가능**에서 남은 조건은 ALL-04 기록 인계와 확장 운영 범위 분리였다. 이번 기록 정리로 두 조건을 충족한다. 추가 기능 시험 없이 기존 증거를 재사용했으며, **BE-10 완료 / #66 Close 가능 / 현재 미해결 제품 FAIL 0**으로 기록한다. Issue 상태는 변경하지 않는다.

### 14.1 #66 원래 완료 조건과 증거

| #66 완료 조건 | 완료 증거 | 판정 / ALL-04 연결 |
|---|---|---|
| 정상100 연속 처리 시 저장·통계 수량 일치 | §13.4 정상100/100, control success100, persistence success100, 통계 total/normal/inferenceCount +100, history·CSV·manifest ID/필드100건 일치, timeout·중복·누락0. 실제 Inference·MySQL 기반 공개 API 증거이며 최신100 직접 SQL 감사는 미수행 | 충족. QA-SIM-13에 정상100 기능 증거 연결; 인증 Simulator 전체 경로·정량 수용은 별도 |
| 장애별 상태·오류 코드·재검사 bin·통계 제외 정책 | §9 INS-02~12·TIM-01~09: 저신뢰3종은 유효 예측 통계 포함, 연결/HTTP/응답 오류·timeout은 제외, 거부 대체1회·무응답 추가호출 없음. 실제 socket late 결과는 진단만 저장하고 bin/제어/통계 불변, hard cancel·동시 검사 검증. §11 DB-01~02 실제 MySQL 중단/복구·pool/LKG 회복 및 LOG-01 DB/로그/sidecar/late 연결 | 충족. QA-INS-06·09~13·15, QA-OPS-02·04·14에 검증 범위별 연결 |
| 이력 필터·CSV BOM·KST 밀리초 수용 | §11 OPS-01~03: 현행 API 필터·페이지·고정 snapshot·SQL 대조·KST 경계/ms·CSV 전체 집합/BOM. §13.2 FE CSV200·다운로드40,392행, Backend와 bytes/필드/BOM 일치. §13.3 FE 삭제200·목록 제거·preview410·review PATCH/simulator PUT 정상·cross-site 보호9/9 | 충족. QA-OPS-03~07·09~10·12, QA-WEB-13·15에 해당 기대값 연결. model 필터 추가와 성능 gate는 별도 |
| ALL-04 기록표 및 BE-10 문서에 결과 기록 | 본 절·[BE-10.md §12](BE-10.md)·[ALL-04 QA 기록표 §6.4](reference/ALL/qa-test-cases.md)에 원 실행 환경·기준선·결과 연결. 일부 기대값만 검증한 QA 케이스는 차단(부분 증거)으로 유지 | 충족. ALL-04 전체 완료나 모든 QA 케이스 통과를 선언하지 않음 |

이미지 관련 증거는 §11 IMG-01~05의 Linux 실제 저장소·독립 시스템100/저신뢰200 순환·sidecar·조회/삭제 및 §13.3의 실제 FE 삭제 재시험을 함께 인계한다. DB 장애·복구, LOW_CULTIVAR/LOW_BOTH, 실제 HTTP late-result 정책은 2/4·3/4 증거로 #66에서 충족했으며 실서버 재주입을 Close 조건으로 추가하지 않는다.

### 14.2 당시 확장 수용 판정 보존

| 관측 시점 / 범위 | 당시 집계·판정 | 최종 기록과의 관계 |
|---|---|---|
| §12 최초 실제 배포 전체 4/4 | **0 PASS / 1 FAIL / 1 DEFERRED / 3 BLOCKED, C: 미완료** | 당시 정상87/저신뢰13 및 FE CSV503·삭제403 관측을 그대로 보존 |
| §13 #111/#112 재시험의 확장 5 ID | **1 PASS / 0 FAIL / 1 DEFERRED / 3 BLOCKED, C: 미완료** | #109 CSV PASS, #110 삭제 PASS, 정상100 PASS를 추가 확보했으나 당시 전체 S/운영 증거 기준의 미확인 분기는 유지 |
| 본 절 #66 원래 완료 조건 재판정·기록 인계 | **BE-10 완료, #66 Close 가능, 미해결 제품 FAIL 0** | 위 확장 집계의 BLOCKED를 임의 PASS로 바꾸지 않고, #66 기능 완료와 후속 프로젝트 수용을 분리 |

§2·§6·§12·§13의 시험 ID 집계는 각 실행 범위의 관측 이력이다. §13의 47 ID 집계를 #66 Close 체크리스트로 사용하지 않으며 과거 C 판정은 본 절의 최종 기능 완료 판정을 대체하지 않는다.

### 14.3 후속 범위 (#66 Close blocker 아님)

| 남은 항목 | 인계 대상 | 유지할 증거 / 후속 필요 |
|---|---|---|
| 인증 Simulator 전체 경로 최종 수용 | [#65 ALL-04](https://github.com/yuudong123/CQC/issues/65) / [#103 QA 분담](https://github.com/yuudong123/CQC/issues/103) | 직접 HTTP 정상100 증거와 Simulator 경로 증거를 구분; 전체 ALL-04 판정은 담당 수용 기록에서 수행 |
| 자연 timeout 정량 기준 | #65 | 승인된 분모·표본·허용률로 판정. 직접500ms 정상100과 사전 warm-up timeout을 인증2초 자연율로 합산하지 않음 |
| 목표환경 CPU·성능 및 조회/CSV 정량 기준 | #65 / #103 | 86,400건 CSV 중앙값34.82초, 최신 FE CSV19.603초/직접15.117초는 관측값. 임의 합격 기준 없이 DEFERRED 유지 |
| container/image/pending/runtime·migration 운영 증거 | [#96](https://github.com/yuudong123/CQC/issues/96) | Jenkins112/SHA `35ac95250a39fd659ef46a8e4d064733bcc9e57c` 시작·종료 동일은 사용자 UI 확인; HTTP health는 직접 확인. 직접 runtime/CPU/서버 로그 권한 제약은 운영 범위에 유지 |
| model 필터 문서·API 계약 | [#68 BE-11](https://github.com/yuudong123/CQC/issues/68) | 현행 API 검증은 완료, 필터 추가 필요성·계약 정합성은 DEFERRED |
| 최신 정상100 직접 SQL/control_attempts 추가 감사 | 권장사항; 필요 시 #65/#103 기록 보강 | 최신100 공개 실제 MySQL 이력/CSV 및 기존 실제 SQL 통합 증거로 #66 충족. 직접 SQL 접근을 새 Close 조건으로 만들지 않음 |

실제 8시간/장기 관제와 이번 단기 결과는 구분한다. 이번 작업은 문서 기록·증거 인계이며 제품/테스트 코드 수정·테스트 재실행·배포·commit·Issue 상태 변경은 하지 않는다. #109/#110은 재시험 PASS 증거로 연결하며, 남은 범위는 위 기존 Issue에 인계 대상으로 명시한다(댓글 작성이나 Issue 변경 없음).
