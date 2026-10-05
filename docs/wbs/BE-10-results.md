# BE-10 통합시험 결과 기록

- 작성일: 2026-10-05
- 계획·계약·입력·기대 결과: [BE-10.md](BE-10.md)
- 현재 단계: **1/4 문서 작성. 2/4~4/4 전 항목 미실행**
- 과거 단위/CI 시험 통과 기록은 이 문서의 PASS로 전환하지 않는다. 실제 서버 조회·모델 실행·통합시험은 이번 단계에서 하지 않았다.
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
| BE10-INS-01 | 2/4 | 미실행 | — | 정상 12-bin |
| BE10-INS-02 | 2/4 | 미실행 | — | 품종 저신뢰 |
| BE10-INS-03 | 2/4 | 미실행 | — | 품질 저신뢰 |
| BE10-INS-04 | 2/4 | 미실행 | — | 양쪽 저신뢰 |
| BE10-INS-05 | 2/4 | 미실행 | — | threshold 동일 값 경계 |
| BE10-INS-06 | 2/4 | 미실행 | — | virtual_brix 누락 |
| BE10-INS-07 | 2/4 | 미실행 | — | ConnectError / ConnectTimeout |
| BE10-INS-08 | 2/4 | 미실행 | — | Inference HTTP 오류 |
| BE10-INS-09 | 2/4 | 미실행 | — | 응답 계약 오류 |
| BE10-INS-10 | 2/4 | 미실행 | — | 제어 거부·1회 fallback |
| BE10-INS-11 | 2/4 | 미실행 | — | 제어 무응답·재호출 없음 |
| BE10-INS-12 | 2/4 | 미실행 | — | 제어 실패 |
| BE10-TIM-01 | 2/4 | 미실행 | — | 1/2/3초 business/hard |
| BE10-TIM-02 | 2/4 | 미실행 | — | A 시작 후 interval 변경, B부터 적용 |
| BE10-TIM-03 | 2/4 | 미실행 | — | 서로 다른 interval 동시 처리 |
| BE10-TIM-04 | 2/4 | 미실행 | — | late-result / ReadTimeout 분리 |
| BE10-TIM-05 | 2/4 | 미실행 | — | hard 취소·late task 한도 |
| BE10-TIM-06 | 2/4 | 미실행 | — | 1초 A late 동안 B 정상 |
| BE10-TIM-07 | 2/4 | 미실행 | — | interval 없는 요청 fallback |
| BE10-TIM-08 | 2/4 | 미실행 | — | 내부 header 인증·허용 interval |
| BE10-TIM-09 | 2/4 | 미실행 | — | TIMEOUT/INFERENCE_ERROR, NEXT/ALL |
| BE10-BND-01 | 2/4 | 미실행 | — | 1/12/13장·필수 images |
| BE10-BND-02 | 2/4 | 미실행 | — | metadata 대응·MIME |
| BE10-BND-03 | 2/4 | 미실행 | — | Content-Length 있는 24MiB 전체 body 경계 |
| BE10-BND-04 | 2/4 | 미실행 | — | KB-02: Content-Length 없는 전체 body 상한 |
| BE10-DUP-01 | 2/4 | 미실행 | — | KB-01: 순차 중복 409 |
| BE10-DUP-02 | 2/4 | 미실행 | — | KB-01: 동시 중복 1건만 제어·저장 |
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
| KB-01 | 중복 ID 409 목표와 현재 INSERT 실패 후 계속 처리 불일치 | BE 별도 수정 지시 및 409 body/code 계약 확인 | DUP-01/02, 2/4 전체 완료 |
| KB-02 | Content-Length 없는 전체 multipart 상한 증거/처리 공백 | BE/MO raw body gate 또는 ingress 제한 확인·필요 변경 별도 승인 | BND-04, 2/4 전체 완료 |
| ENV-01 | 실제 배포·DB·Inference·mount·worker 미확인 | MO/DM 환경 제공 및 run 기준선 기록 | 실제 환경 시험 |
| FE-DEP-01 | 기준선 FE parser/generator와 #55 차이; PR #92 open | FE merge·배포·Backend OpenAPI 일치 확인 | FE E2E, Backend 저장/API 단독 시험은 독립 |
| DEC-01 | N/자연 timeout 허용률/반복 미확정 | 사용자 최종 승인 | E2E-02 PASS 판정 |
| DEC-02 | timer 오차·조회 부하·응답시간 수치 미확정 | 사용자 최종 승인, BE/MO 측정 협의 | 정량 timer/조회 성능 PASS 판정 |
| DEC-03 | 정상100 후보 최신 실제 판정·manifest 미확인 | 2/4 BE+DM 후보 확인, 별도 run 고정 | 정상100 실행 |

| 단계 | 현재 결과 | 완료 판단 조건 |
|---|---|---|
| 1/4 | 기준선·47개 명세·결과 틀 작성. 정량 후보 승인 대기 | 사용자 계획 확인, 미확정/의존성 인지. 제품 blocker 해결이나 실시험 통과를 뜻하지 않음 |
| 2/4 | 미실행 | 27개 전 분기 증거 확보, KB-01/02 해결 후 중복·경계도 통과, #67/#87 회귀 없음 |
| 3/4 | 미실행 | 15개 실제 DB·보존·조회·복구 증거 확보, MySQL skip를 PASS로 대체하지 않음 |
| 4/4 | 미실행 | 5개 동일 배포 기준선 수용, 정상100·승인 정량 기준·FE·운영 복구 통과 |

이 문서에는 실제 통합시험 결과가 아직 없다. BE-10 종료나 Issue #66 완료로 사용하지 않는다. 다음 단계 전체 실행은 blocker/환경 준비 후 별도 지시로 진행한다.
