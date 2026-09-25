# CQC Backend 작업 중단·복귀 상태 정리

- 기준 상태: BE-01~BE-04 완료 직후
- 목적: 추석 연휴 후 현재 구현과 미결정 사항을 다시 탐색하지 않고 Backend 작업을 이어가기 위한 인수인계 문서
- 담당: 홍준희
- 현재 구현 범위: FastAPI 검사 API, MySQL 물리 Schema, Mock Inference, 판정·bin·Virtual Control, timeout·late-result 정책
- 다음 WBS: BE-05 검사 이력·통계·필터·CSV API

이 문서는 실제 `src/api/` 코드, Alembic migration, Backend 테스트와 `docs/wbs/BE-01.md`~`BE-04.md`를 기준으로 작성했다. 완료·임시·미결정을 구분하며 실제 `.env` 값과 인증정보는 기록하지 않는다.

## 1. 한눈에 보는 현재 상태

### 완료

- FastAPI 애플리케이션과 `/health`
- `POST /v1/inspections` multipart 요청·validation
- SQLAlchemy ORM 4개 테이블과 Alembic initial migration
- 로컬 MySQL 전용 DB에서 migration upgrade·downgrade·re-upgrade 검증
- `MockInferenceClient`와 `InspectionService`
- confidence 정상·저신뢰 판정
- 검사·제어·저장 상태 표현 분리
- 정상 6개 임시 bin과 재검사 bin
- `MockVirtualControl`과 정상 bin 거부 대체 요청 1회
- 500ms Inference business deadline과 timeout 재검사 처리
- bounded late task, hard timeout과 종료 cleanup
- Mock 기반 Backend 수직 흐름·Uvicorn HTTP 검증

### 아직 연결되지 않음

- 실제 Inference HTTP Client
- Repository와 실제 검사·제어·오류 DB 저장
- DB `bin_mappings` 조회와 운영 bin seed
- 실제 Virtual Control 통신
- 검사 이력·통계·필터·CSV API
- Simulator·Frontend 전체 통합

### 현재 검증 상태

```text
pytest tests/api
→ 79 passed, 2 warnings

ruff check src/api tests/api
→ All checks passed

ruff format --check src/api tests/api
→ 45 files already formatted
```

pytest는 이 문서 작성 시 다시 실행하여 `79 passed, 2 warnings`를 확인했다. Ruff 결과는 BE-04 완료 시점의 최종 검증 결과다. 경고 2건은 FastAPI·Starlette TestClient 내부 deprecation 경고다.

## 2. BE-01~BE-04 작업 요약

### 2.1 BE-01 — FastAPI 실행 골격과 검사 입력 계약

구현 내용:

- `src/api/main.py`의 FastAPI app factory와 실행 진입점
- `pydantic-settings` 기반 `Settings`
- `GET /health`
- `POST /v1/inspections`
- `multipart/form-data` 파싱
- `inspection_id`, 반복 `images`, JSON text `metadata`
- Simulator가 시연용 `request.json`에서 읽어 보낸 이미지와 metadata 순서 유지

현재 검사 요청 validation:

1. `inspection_id`가 비어 있지 않은지 확인
2. 이미지가 1~12장인지 확인
3. multipart 전체 요청이 24MiB를 넘는지 확인
4. PNG·JPEG Content-Type인지 확인
5. metadata가 유효한 JSON 배열인지 확인
6. metadata 필수 필드와 타입 확인
7. images와 metadata 개수 일치 확인
8. `view_index` 중복 금지
9. `view_index`가 이미지 순서대로 `0..N-1`인지 확인
10. `angle_direction`이 `top` 또는 `bottom`인지 확인

이미지별 metadata:

```text
view_index
angle_direction
verticality_angle
horizontality_angle
```

두 각도 값은 현재 정수 타입만 검사하며 최종 허용 범위는 정하지 않았다.

### 2.2 BE-02 — SQLAlchemy ORM과 Alembic

구현한 업무 테이블:

```text
inspections
├─ 1:N control_attempts
└─ 1:N inspection_errors

bin_mappings
└─ 독립적인 현재 매핑 테이블
```

주요 구현:

- SQLAlchemy 2.0 Declarative Base
- naming convention
- PyMySQL 기반 sync Engine·Session factory
- `DATABASE_URL` Settings
- PK·FK·unique·복합 index
- MySQL `DATETIME(3)`, `DECIMAL`, `JSON`
- Alembic `target_metadata = Base.metadata`
- initial revision `20260922_01`
- 앱 실행 시 `Base.metadata.create_all()` 미사용

실제 MySQL 검증 이력:

- Docker가 아닌 로컬 MySQL Server 사용
- 검증 당시 MySQL `8.4.11`, Windows 서비스 `MySQL84`, 포트 `3306`
- 별도 DB `cqc_test`에서만 검증
- `upgrade head → schema 확인 → downgrade base → 재-upgrade` 성공
- 최종 `alembic check`에서 추가 변경 없음 확인
- 업무 테이블 4개, FK 2개, unique 5개, 명시적 index 14개 검증

주의:

- 위 내용은 BE-02 수행 시점의 검증 이력이다.
- 복귀 시 로컬 MySQL 서비스와 `cqc_test` 현재 상태는 다시 확인해야 한다.
- Repository와 실제 INSERT·UPDATE는 아직 없다.

### 2.3 BE-03 — Mock Inference 검사 API

구현 내용:

- `InferenceRequest`
- `InferenceResponse`
- `MockInferenceClient`
- `InspectionService`
- Router → Service → Mock Client 수직 흐름
- 응답 `inspection_id`와 `used_frame_count` 정합성 검증
- 이미지·metadata 순서 유지
- deterministic Mock 응답

현재 내부 Inference 논리 요청:

```text
inspection_id
images: list[bytes], 1~12장
metadata: 이미지별 metadata, 1~12개
```

Mock은 요청 ID를 그대로 반환하고 `used_frame_count`를 전달 이미지 수로 계산한다. 실제 모델이나 HTTP 서버는 호출하지 않는다.

### 2.4 BE-04 — 판정·bin·Virtual Control·timeout·late-result

구현 내용:

- `InspectionStatus`, `ControlStatus`, `PersistenceStatus`
- `InspectionDecision`과 내부 판정 사유
- confidence 기반 정상·저신뢰 판정
- 정상 6개 임시 bin과 재검사 bin
- `MockVirtualControl`
- 정상 bin `REJECTED` 시 재검사 bin 대체 요청 1회
- `NO_RESPONSE`, `FAILED` 표현
- 500ms business deadline
- timeout과 저신뢰 구분
- timeout의 정상 통계 제외
- bounded late task와 hard timeout
- FastAPI lifespan 종료 cleanup

판정 차이:

| 구분 | 정상 | 저신뢰 | Inference timeout |
|---|---|---|---|
| Inference 응답 | 있음 | 있음 | business deadline 시점에는 없음 |
| `inspection_status` | `COMPLETED` | `REINSPECTION_REQUIRED` | `REINSPECTION_REQUIRED` |
| `review_required` | `false` | `true` | `true` |
| `exclude_from_normal_stats` | `false` | `false` | `true` |
| 목적 bin | 정상 6개 중 하나 | 재검사 bin | 재검사 bin |

## 3. 현재 Backend 실제 처리 흐름

### 3.1 정상 또는 저신뢰 응답

```text
POST /v1/inspections
→ Router multipart parsing·validation
→ InspectionService
→ UploadFile을 순서대로 bytes 변환
→ InferenceRequest 생성
→ MockInferenceClient task 시작
→ business deadline 안에 InferenceResponse 수신
→ inspection_id·used_frame_count 정합성 검증
→ confidence 판정
→ target bin 결정
→ MockVirtualControl
→ InspectionResponse 반환
```

정상 판정 조건:

```text
cultivar_confidence >= 0.50
AND
quality_confidence >= 0.50
```

하나라도 미만이면 저신뢰로 판정해 처음부터 재검사 bin을 요청한다.

### 3.2 Virtual Control 흐름

```text
정상 bin → SUCCEEDED
         → 종료

정상 bin → REJECTED
         → 재검사 bin 대체 요청 1회
         → 결과와 관계없이 종료

정상 bin → NO_RESPONSE 또는 FAILED
         → 추가 호출 없이 종료

저신뢰·timeout → 재검사 bin 직접 요청 1회
                → 결과와 관계없이 추가 재시도 없음
```

검사 판정 상태와 제어 상태는 분리되어 있다. 정상 모델 판정 후 제어가 실패해도 confidence 판정 자체를 다른 값으로 덮어쓰지 않는다.

### 3.3 Timeout 이후 late-result 흐름

```text
Inference task 시작
→ 500ms business deadline 초과
→ HTTP 검사 결과를 timeout으로 즉시 확정
→ REINSPECTION_REQUIRED
→ 정상 통계 제외
→ 재검사 bin Virtual Control
→ InspectionResponse 반환

동시에:
초과한 Inference task
→ LateResultManager 등록
→ 최대 4개까지만 유지
→ 전체 시작 시점 기준 최대 2000ms까지 대기
   ├─ 응답 도착: 메모리 LateInferenceResult에 진단용 저장
   └─ hard timeout: task 취소
```

late-result가 도착해도 다음 값은 변경하지 않는다.

- `inspection_status`
- `review_required`
- `exclude_from_normal_stats`
- `decision_reason`
- `target_bin_code`
- `control_status`
- 이미 수행한 Virtual Control

late task 한도를 초과하면 검사 응답과 재검사 제어는 그대로 수행하고 추가 진단 수집만 포기한다. 서버 종료 시 FastAPI lifespan이 남은 watcher와 Inference task를 취소한다.

## 4. 현재 HTTP 응답 의미

`InspectionResponse`는 Inference 응답을 그대로 노출하는 Schema가 아니라 Backend 판정과 제어까지 포함하는 별도 Schema다.

정상·저신뢰 응답에는 다음이 포함된다.

- Inference 품종·품질 예측과 confidence·probabilities
- 추론 시간과 모델·전처리 버전
- `used_frame_count`
- 검사 상태와 판정 사유
- 통계 제외 여부
- 최종 target bin
- 최종 control 상태

timeout 응답에서는 유효한 Inference 응답이 없으므로 예측·confidence·probabilities·모델 버전·`used_frame_count`가 `null`이다. 임의 예측값은 만들지 않는다.

## 5. 앞으로 남은 Backend 작업

### 5.1 실제 Inference HTTP 연동

- `httpx.AsyncClient` 기반 Client
- FastAPI lifespan에서 Client 생성·종료와 연결 풀 재사용
- `POST /v1/predict` multipart 구성
- 이미지·metadata 순서 보존
- 실제 응답 Pydantic 검증
- connect·read·write·pool timeout
- business deadline·hard timeout과 실제 HTTP task 연계
- 연결 오류·처리 오류·잘못된 응답의 재검사 정책 연결

현재 `src/inference` 구현과 Backend 확정 계약 차이:

| 항목 | Backend 확정 계약 | 현재 `src/inference` |
|---|---|---|
| 요청 `inspection_id` | 필수 | 없음 |
| 요청 이미지별 metadata | 필수 | 없음 |
| 응답 `inspection_id` | 필수 | 없음 |
| 응답 `used_frame_count` | 필수 | 없음 |
| 예측·confidence·probabilities | 필수 | 있음 |
| 모델·전처리 정보 | 필수 | 있음 |

실제 Inference 담당 코드 수정은 데이터·모델 담당자와 계약을 맞춘 뒤 해당 담당 영역에서 진행해야 한다.

### 5.2 Repository와 검사 저장

- 검사 INSERT와 최종 UPDATE
- confidence 판정에 실제 사용한 threshold 저장
- `inspection_status`, `control_status`, `persistence_status` 저장
- prediction·confidence·model version·추론시간 저장
- timeout·통계 제외·검수 대상 저장
- DB 저장 실패가 판정·제어를 변경하지 않도록 분리
- sync SQLAlchemy 작업의 threadpool 경계 적용

### 5.3 제어·오류·late-result 저장

- 최초 정상 bin 요청과 대체 재검사 요청을 `control_attempts`에 각각 저장
- `command_id`, `attempt_no`, command type과 응답 시각 기록
- Inference·DB·Virtual Control 오류를 `inspection_errors`에 저장
- 메모리 `LateInferenceResult`를 `inspections`의 late-result 컬럼에 진단용 저장
- 요청 처리용 DB Session을 late task에서 재사용하지 않음

### 5.4 DB bin mapping

- 실제 `mapping_key`와 운영 `bin_code` 확정
- 정상 6개·재검사 1개 seed 방식 확정
- `bin_mappings` Repository 조회
- in-memory `TEST_*` mapping 제거
- 매핑 변경을 재시작 없이 적용하는 BE-09 검증

### 5.5 BE-05 — 이력·통계·필터·CSV

- 검사 이력 최신순 pagination
- 기간·품종·품질·bin·상태·오류·검수·모델 버전 필터
- 오늘 통계와 최근 시계열
- 품종·품질·bin별 수량과 비율
- 재검사율과 평균 추론시간
- timeout·시스템 오류의 정상 통계 제외
- 필터 전체 결과 CSV, UTF-8 BOM

### 5.6 BE-06 — 이미지 생명주기

- 처리 중 이미지만 메모리에서 제공
- 처리 완료 후 이미지 메모리와 임시 접근 제거
- 브라우저 캐시 금지
- 장애 이미지만 파일 저장소에 최대 100개 보관
- 101번째 저장 시 가장 오래된 이미지 삭제
- 관리자 조회·개별 삭제·전체 삭제

현재 Backend는 입력 이미지를 DB나 디스크에 저장하지 않지만, 처리 중 이미지 API와 장애 이미지 보관 기능도 아직 없다.

### 5.7 BE-07 — Simulator와 장애 시연

- 시연 전용 `realtime-apple-arrival-demo/index.json` 기본 12장 묶음 순회
- 각도 기준 대표 이미지 최대 12장 선택
- Backend 검사 API 호출
- 500ms 간격 전송
- 시작·정지·반복 실행
- 마지막 위치 파일 저장과 재시작 복구
- timeout·Inference·DB·제어 거부·무응답 장애 토글

### 5.8 BE-08~BE-11 통합·안정화

- BE-08: 실제 Inference·DB·Frontend 전체 HTTP 흐름과 late-result 진단 저장
- BE-09: DB 장애 중 선별 지속, 86,400/8,640 순환 삭제, 동적 bin mapping
- BE-10: 정상 100개, 연속 요청, 장애·필터·CSV 통합시험
- BE-11: OpenAPI·DB·migration·설계 문서와 실제 구현 동결

## 6. 의존관계를 고려한 권장 작업 순서

### 우선순위 1 — 복귀 직후 변경사항과 계약 재확인

- `dev` 최신 변경 반영 전 작업 트리와 충돌 확인
- `docs/planning/decision-log.md`, `docs/wbs/reference/BE/backend-stack.md`, `wbs.md` 변경 확인
- 실제 `src/inference`와 생성 OpenAPI 재확인
- 최대 12장 계약과 상위 문서의 최대 40장 표현 정리 여부 확인

### 우선순위 2 — BE-05 전에 필요한 DB 계약 최소 확정

- 최종 상태 문자열과 상태 전이
- 공통 error code
- command ID·command type
- 운영 bin code·mapping key·seed 방식
- `source_reference` 사용 여부
- `Asia/Seoul` 시간을 MySQL `DATETIME(3)`에 넣고 API로 표시하는 구체적인 애플리케이션 규칙

### 우선순위 3 — BE-05 Repository와 저장 수직 흐름

Mock Inference·Mock Control을 유지한 상태에서 먼저 다음을 연결한다.

```text
InspectionService
→ 검사·control attempt·error 저장
→ persistence_status 반영
→ DB 실패 중에도 기존 판정·제어 유지
```

### 우선순위 4 — BE-05 조회·통계·CSV

실제 저장 데이터가 생긴 뒤 이력 pagination, 필터, 오늘 통계, 최근 시계열과 CSV를 구현한다.

### 우선순위 5 — BE-06·BE-07 후속 기능

이미지 생명주기와 Simulator를 각각 구현한다. Simulator는 최신 12장 계약을 기준으로 하되 다른 문서의 40장 표현을 먼저 동기화한다.

### 우선순위 6 — DM-07 준비 후 실제 Inference 통합

Inference 담당자가 확정 계약을 반영한 뒤 실제 `httpx.AsyncClient`, transport timeout과 실제 late-result를 연결한다. 계약이 맞지 않은 상태에서 Backend만 임시 adapter로 추측 구현하지 않는다.

### 우선순위 7 — BE-09~11 안정화

동적 bin, 순환 삭제, DB 장애, 정상 100개와 오류 시나리오를 검증하고 최종 계약을 동결한다.

## 7. 미결정 또는 동기화가 필요한 사항

최신 문서에서 이미 확정된 12장·24MiB·threshold 0.50·business deadline 500ms·`Asia/Seoul` 업무 시각은 이 목록에서 제외했다.

### 7.1 실제 Inference 요청·응답 구현 동기화

항목: Backend↔Inference 실제 HTTP 계약 반영

현재 상태: 논리 계약은 확정됐지만 `src/inference` 구현과 OpenAPI가 따라오지 않은 상태다.

현재 임시값: Backend는 같은 계약을 사용하는 `MockInferenceClient`로 대체 중이다.

결정이 필요한 이유: 실제 연동 시 `inspection_id`, metadata와 `used_frame_count`가 없으면 요청 추적과 정합성 검증이 불가능하다. metadata의 multipart 직렬화가 실제 Inference endpoint에도 일치해야 한다.

영향받는 코드/문서: `src/api/clients/`, `src/api/schemas/inference.py`, `src/inference/api.py`, `src/inference/schemas.py`, Inference OpenAPI, `docs/wbs/reference/BE/backend-stack.md`.

### 7.2 최종 상태 문자열과 상태 전이

항목: `inspection_status`, `control_status`, `persistence_status`

현재 상태: 논리 분리는 확정됐지만 현재 Enum 문자열과 전체 전이표는 최종 팀 계약으로 동결되지 않았다.

현재 임시값: `PROCESSING`, `COMPLETED`, `REINSPECTION_REQUIRED` 등 BE-04 Enum.

결정이 필요한 이유: DB 저장, 이력 필터와 Frontend 상태 표시가 동일한 문자열을 사용해야 한다.

영향받는 코드/문서: `src/api/schemas/inspection_results.py`, `inspections`·`control_attempts` ORM, OpenAPI, Frontend 계약.

### 7.3 최종 error code와 공통 오류 응답

항목: 입력·Inference·DB·Virtual Control 오류 코드

현재 상태: HTTP 413·415·422와 일부 단순 `detail`, Inference 정합성 실패 HTTP 500만 구현되어 있다.

현재 임시값: 판정 사유 `NORMAL`, `LOW_*`, `INFERENCE_DEADLINE_EXCEEDED`는 내부 업무 사유이며 최종 error code가 아니다.

결정이 필요한 이유: `inspection_errors`, 이력 필터, Frontend 오류 표시와 장애 시연이 같은 코드를 사용해야 한다.

영향받는 코드/문서: Router, Service 예외 처리, `inspection_errors`, `inspections.error_code`, OpenAPI, Frontend.

### 7.4 운영 bin code와 mapping 규칙

항목: 정상 6개·재검사 bin의 실제 코드, `mapping_key`, seed 방식

현재 상태: ORM 구조와 unique 제약은 있으나 운영 데이터는 없다.

현재 임시값: `TEST_NORMAL_BIN_1`~`6`, `TEST_REINSPECTION_BIN`.

결정이 필요한 이유: Repository 조회, 과거 검사 snapshot, 제어 명령과 Frontend 표시가 실제 코드를 공유해야 한다.

영향받는 코드/문서: `src/api/services/bin_policy.py`, `bin_mappings`, seed·migration 정책, Virtual Control, 이력 API.

### 7.5 재검사 mapping 단일성

항목: 활성 재검사 bin을 DB에서 정확히 하나로 보장하는 방식

현재 상태: `is_reinspection`과 index는 있으나 단일성 DB 제약은 없다.

현재 임시값: 코드 상수 재검사 bin 한 개.

결정이 필요한 이유: 재검사 매핑이 0개 또는 여러 개면 timeout·저신뢰 목적지를 결정할 수 없다.

영향받는 코드/문서: `BinMapping`, Alembic 후속 revision, seed, bin Repository.

### 7.6 Virtual Control 실제 계약

항목: command ID, command type, 시각, 오류·거부 사유와 통신 방식

현재 상태: Mock 요청은 `inspection_id`, `target_bin_code`만 포함한다. ORM에는 `command_id`, `command_type`, 요청·응답 시각과 실패 사유 컬럼이 준비되어 있다.

현재 임시값: 프로세스 내부 `MockVirtualControl`, 기본 `SUCCEEDED`.

결정이 필요한 이유: 실제 제어 시도 저장과 Frontend 장애 표시를 위해 명령 식별·응답 계약이 필요하다.

영향받는 코드/문서: `src/api/control/`, `schemas/control.py`, `control_attempts`, Virtual Control API 문서.

### 7.7 Inference transport timeout

항목: connect·read·write·pool timeout 값

현재 상태: business deadline 500ms만 확정·구현되었고 transport timeout은 없다.

현재 임시값: 없음.

결정이 필요한 이유: 연결 실패와 늦은 정상 결과를 구분하고 HTTP 자원을 무제한 점유하지 않도록 해야 한다.

영향받는 코드/문서: 실제 Inference Client Settings, `httpx.Timeout`, late task·hard timeout 정책.

### 7.8 Hard timeout과 late task 한도

항목: late task 최대 생존시간과 동시 추적 수

현재 상태: bounded task 구조는 구현됐지만 운영 성능시험으로 확정하지 않았다.

현재 임시값: `INFERENCE_HARD_TIMEOUT_MS=2000`, `MAX_LATE_TASKS=4`.

결정이 필요한 이유: 실제 HTTP 연결 수, 메모리, 초당 2그룹 처리량과 shutdown 시간을 좌우한다.

영향받는 코드/문서: `Settings`, `LateResultManager`, MLOps·CPU 성능시험.

### 7.9 DB 시간 적용 방식

항목: 확정된 `Asia/Seoul` 업무 시각을 `DATETIME(3)`과 API에서 일관되게 처리하는 구현 규칙

현재 상태: 팀 정책은 `Asia/Seoul`, 밀리초 단위로 확정됐다. ORM은 timezone 정보가 없는 `DATETIME(3)`이며 애플리케이션 변환·저장 코드는 아직 없다. BE-02 문서와 ORM TODO에는 과거의 UTC/KST 미정 표현이 남아 있다.

현재 임시값: DB timezone default나 `NOW()` 없이 애플리케이션이 값을 전달하는 구조만 준비됐다.

결정이 필요한 이유: 정책 자체가 아니라 timezone-aware Python 값의 변환·naive 저장·API offset 표기 규칙을 코드로 통일해야 한다.

영향받는 코드/문서: Repository, 통계 날짜 경계, CSV, ORM TODO, `docs/wbs/BE-02.md`.

### 7.10 `source_reference`

항목: 검사 원본 추적값의 API 포함 여부와 필수 여부

현재 상태: `inspections.source_reference`는 nullable 컬럼만 존재하고 검사 API에는 없다.

현재 임시값: `NULL` 전제.

결정이 필요한 이유: Simulator 위치·원본 그룹 추적과 장애 이미지 연결에 사용할지 확정해야 한다.

영향받는 코드/문서: 검사 요청 Schema, Simulator, `Inspection` ORM, 이력 API.

### 7.11 각도 범위와 파일별 크기 제한

항목: `verticality_angle`, `horizontality_angle` 허용 범위와 이미지 한 장당 최대 크기

현재 상태: 각도는 정수 타입만 검증하고 전체 multipart 24MiB만 제한한다.

현재 임시값: 범위·파일별 제한 없음.

결정이 필요한 이유: 잘못된 Simulator 데이터와 한 파일에 편중된 큰 요청을 일관되게 거부하려면 계약이 필요하다.

영향받는 코드/문서: `schemas/inspections.py`, Router validation, Simulator, OpenAPI.

### 7.12 개발·운영 MySQL 계정과 최소 권한

항목: CQC 전용 DB 사용자와 migration·runtime 권한 분리

현재 상태: BE-02 실제 검증은 로컬 `root@localhost`와 `cqc_test`를 사용했다.

현재 임시값: 개인 로컬 검증 계정.

결정이 필요한 이유: 실제 개발·운영에서 root 계정 사용을 피하고 migration과 애플리케이션 권한을 제한해야 한다.

영향받는 코드/문서: `.env`, MLOps secret, MySQL 초기화, Alembic 적용 절차.

## 8. 임시 데이터와 임시 설정

### 8.1 임시 bin code

| 현재 값 | 사용 위치 | 임시인 이유 | 향후 교체 대상 |
|---|---|---|---|
| `TEST_NORMAL_BIN_1` | `bin_policy.py`, fuji+L | BE-04 흐름 테스트용 | DB `bin_mappings` 운영 seed |
| `TEST_NORMAL_BIN_2` | `bin_policy.py`, fuji+M | BE-04 흐름 테스트용 | DB `bin_mappings` 운영 seed |
| `TEST_NORMAL_BIN_3` | `bin_policy.py`, fuji+S | BE-04 흐름 테스트용 | DB `bin_mappings` 운영 seed |
| `TEST_NORMAL_BIN_4` | `bin_policy.py`, yanggwang+L | BE-04 흐름 테스트용 | DB `bin_mappings` 운영 seed |
| `TEST_NORMAL_BIN_5` | `bin_policy.py`, yanggwang+M | BE-04 흐름 테스트용 | DB `bin_mappings` 운영 seed |
| `TEST_NORMAL_BIN_6` | `bin_policy.py`, yanggwang+S | BE-04 흐름 테스트용 | DB `bin_mappings` 운영 seed |
| `TEST_REINSPECTION_BIN` | 저신뢰·timeout·대체 요청 | BE-04 흐름 테스트용 | 실제 재검사 bin code |

### 8.2 정책·task 설정

| 현재 값 | 확정 여부 | 사용 위치 | 향후 조치 |
|---|---|---|---|
| `CULTIVAR_CONFIDENCE_THRESHOLD=0.50` | 최신 모델 검증으로 확정 | Settings·판정 정책 | 운영 검사 이력에 적용값 저장 |
| `QUALITY_CONFIDENCE_THRESHOLD=0.50` | 최신 모델 검증으로 확정 | Settings·판정 정책 | 운영 검사 이력에 적용값 저장 |
| `INFERENCE_BUSINESS_DEADLINE_MS=500` | 팀 정책으로 확정 | InspectionService | 실제 HTTP 구간 측정으로 연결 |
| `INFERENCE_HARD_TIMEOUT_MS=2000` | 임시 초안 | LateResultManager | 실제 HTTP·CPU 시험 후 확정 |
| `MAX_LATE_TASKS=4` | 임시 초안 | LateResultManager | 처리량·메모리·연결 풀 시험 후 확정 |

### 8.3 MockInferenceClient 고정값

| 현재 값 | 사용 위치 | 임시인 이유 | 향후 교체 대상 |
|---|---|---|---|
| `crop_type=apple` | Mock 응답 | 사과 MVP 계약을 재현 | 실제 Inference 응답 |
| `predicted_cultivar=fuji` | Mock 응답 | deterministic 테스트 | 실제 모델 예측 |
| 품종 확률 `fuji=0.9`, `yanggwang=0.1` | Mock 응답 | deterministic 테스트 | 실제 모델 확률 |
| `cultivar_confidence=0.9` | Mock 응답 | 정상 판정 기본 경로 | 실제 모델 confidence |
| `predicted_grade=L` | Mock 응답 | deterministic 테스트 | 실제 모델 예측 |
| 품질 확률 `L=0.8`, `M=0.1`, `S=0.1` | Mock 응답 | deterministic 테스트 | 실제 모델 확률 |
| `quality_confidence=0.8` | Mock 응답 | 정상 판정 기본 경로 | 실제 모델 confidence |
| `inference_time_ms=12.5` | Mock 응답 | 고정 계약 테스트 | 실제 측정값 |
| `model_name=mock-separate` | Mock 응답 | Mock 식별 | 실제 모델명 |
| `model_version=mock-cqc-separate12-v1` | Mock 응답 | Mock 식별 | 승인 모델 버전 |
| `preprocessing_version=mock-v1` | Mock 응답 | Mock 식별 | 실제 전처리 버전 |
| `response_delay_ms=0` | Mock 기본값 | 즉시 정상 경로 | 실제 HTTP 지연 |

`used_frame_count`는 고정값이 아니라 전달 이미지 수로 계산한다.

### 8.4 MockVirtualControl 고정 동작

| 현재 값 | 사용 위치 | 임시인 이유 | 향후 교체 대상 |
|---|---|---|---|
| 기본 `SUCCEEDED` | `MockVirtualControl` | 정상 제어 흐름 반복 테스트 | 실제 Virtual Control 응답 |
| 주입 결과 목록 | 거부·무응답·실패 테스트 | deterministic 장애 재현 | 실제 통신·장애 토글 |
| `reason=null` | Mock 응답 | 상세 장치 오류 계약 없음 | 실제 거부·실패 사유 |
| 메모리 `requests`, `status_histories` | 테스트 검증 | DB 저장 전 시도 확인 | `control_attempts` Repository |

### 8.5 개발·검증용 데이터

- `cqc_test`: Alembic 왕복 검증용 로컬 DB이며 운영 DB가 아니다.
- `root@localhost`: BE-02 로컬 검증 계정이며 운영 계정으로 사용하면 안 된다.
- `LateInferenceResult` 메모리 목록: DB 연결 전 진단 구조이며 서버 재시작 시 유실된다.
- `hard_timeout_inspection_ids`, `dropped_inspection_ids`: 테스트·진단용 메모리 목록이며 영구 이력이 아니다.

## 9. 이미 확정된 항목

복귀 시 다시 미정으로 되돌리지 않아야 할 최신 결정:

- 대표 이미지 선택 책임: Simulator
- 대표 이미지 수: 최대 12장
- Backend는 이미지·metadata 재선택·재정렬 금지
- PNG·JPEG, 전체 multipart 24MiB
- 품종·품질 threshold 각각 0.50
- Inference business deadline 500ms
- timeout은 재검사 bin과 정상 통계 제외
- 저신뢰는 재검사 bin이지만 정상 품종·품질 통계에는 포함
- 정상 bin `REJECTED`에만 재검사 bin 대체 요청 1회
- `NO_RESPONSE`는 추가 호출 없음
- 업무 시각은 `Asia/Seoul`, 밀리초 단위
- 상태는 검사·제어·저장·error code로 논리 분리
- Kafka·Redis·Celery를 사용하지 않음
- 정상 이미지를 DB에 저장하지 않음

## 10. 문서와 코드 사이의 주의할 불일치

### 10.1 최대 40장과 최대 12장 표현 혼재

최신 `docs/planning/decision-log.md` 후반과 `docs/wbs/reference/BE/backend-stack.md`, 실제 Backend 코드는 최대 12장으로 확정·구현되어 있다. 그러나 다음 문서 일부에는 과거 최대 40장 표현이 남아 있다.

- `docs/planning/requirements.md` 일부 항목
- `docs/planning/architecture.md` 일부 설명
- `wbs.md`의 Simulator 관련 완료 기준
- `template-status.md`
- `docs/planning/decision-log.md`의 과거 결정 구간

과거 결정 이력 자체는 보존할 수 있지만, 현재 요구사항·WBS 완료 기준과 충돌하는 부분은 팀 합의 후 최신 계약으로 동기화해야 한다.

### 10.2 UTC/KST 미정 표현

최신 `docs/planning/decision-log.md`는 모든 업무 시각을 `Asia/Seoul` 기준 밀리초로 확정했다. 반면 BE-02 문서와 ORM TODO에는 UTC/KST 미정 표현이 남아 있다.

정책은 KST로 확정된 것으로 보고, Repository 구현 전에 저장·API 직렬화 규칙을 구체화하고 오래된 TODO를 동기화해야 한다.

### 10.3 `docs/wbs/reference/BE/backend-stack.md`의 구현 전 표현

`docs/wbs/reference/BE/backend-stack.md` 일부에는 Backend 구현 전, DB 물리 Schema 미정, endpoint 미정 같은 과거 표현이 남아 있다. 실제로는 BE-01~04와 BE-02 migration이 완료되어 있으므로 복귀 후 문서 갱신 범위를 별도로 정하는 편이 안전하다.

## 11. 복귀 후 첫 작업 체크리스트

### 1. 저장소와 문서 변경 확인

```text
git status
git log --oneline --decorate -n 20
dev 최신 변경 확인
```

다른 담당자가 `src/inference`, WBS, `decision-log`, OpenAPI를 변경했는지 먼저 확인한다. 사용자 변경사항이 있으면 덮어쓰지 않는다.

### 2. Backend 기준선 재검증

```text
ruff check src/api tests/api
ruff format --check src/api tests/api
pytest tests/api
```

현재 기준선은 `79 passed`다. 테스트 수가 달라졌다면 새 테스트 추가인지 누락인지 확인한다.

### 3. 실제 Inference 계약 재확인

다음 필드가 실제 Inference OpenAPI와 구현에 반영됐는지 확인한다.

```text
요청: inspection_id, images, 이미지별 metadata
응답: inspection_id, used_frame_count, 기존 예측·확률·버전 필드
```

아직 반영되지 않았다면 실제 HTTP Client를 먼저 추측 구현하지 않고 담당자와 변경 시점을 맞춘다.

### 4. BE-05 선행 DB 계약 확정

상태 문자열, error code, command ID/type, 운영 bin seed, `source_reference`, KST 저장·표시 구현 방식을 확정한다.

### 5. BE-05 Repository·저장 수직 흐름 시작

처음부터 통계 전체를 만들지 말고 다음 최소 흐름부터 연결한다.

```text
Mock 검사 1건
→ inspections 저장
→ control_attempts 저장
→ 필요 시 inspection_errors 저장
→ persistence_status 확인
→ 단건 조회 테스트
```

## 12. 다음 작업 전에 특히 주의할 위험

1. **실제 Inference 계약 불일치**  
   현재 Backend Mock은 확정 계약을 따르지만 `src/inference`는 추적 ID·metadata·사용 프레임 수를 지원하지 않는다.

2. **문서의 40장·12장 혼재**  
   Simulator를 과거 40장 WBS대로 구현하면 현재 Backend 최대 12장 validation에서 즉시 거부된다.

3. **상태·error code를 확정하기 전 DB·Frontend 결합 위험**  
   문자열이 변경되면 저장 데이터, 필터와 화면 조건을 함께 수정해야 한다.

4. **DB 동기 I/O를 async Service에서 직접 실행할 위험**  
   Repository 연결 시 Inference 대기 중 transaction을 열어두지 말고 sync 작업에 명시적 threadpool 경계를 둬야 한다.

5. **late task와 실제 httpx 연결 풀의 자원 관계 미검증**  
   현재 2000ms·4개는 Mock 기준 초안이다. 실제 연결 풀보다 late task가 많거나 취소 정리가 불완전하면 연결 고갈이 발생할 수 있다.

6. **DB 저장 실패가 선별 결과를 바꾸는 결합 위험**  
   DB는 기록 계층이다. 저장 실패 때문에 이미 정해진 정상 bin이나 제어 성공 상태를 재검사로 바꾸면 안 된다.

7. **임시 TEST bin의 운영 노출 위험**  
   실제 통합 전에 반드시 DB seed와 운영 bin code로 교체해야 한다.

8. **시간 정책 문서와 코드 TODO 불일치**  
   KST 정책은 확정됐지만 Repository가 없으므로 날짜 경계·API offset·DB 저장 방식은 아직 실제 검증되지 않았다.

## 13. 관련 문서와 코드

완료 기록:

- `docs/wbs/BE-01.md`
- `docs/wbs/BE-02.md`
- `docs/wbs/BE-03.md`
- `docs/wbs/BE-04.md`

주요 기준 문서:

- `docs/wbs/reference/BE/backend-stack.md`
- `docs/planning/decision-log.md`
- `docs/planning/requirements.md`
- `docs/planning/architecture.md`
- `docs/wbs.md`

주요 코드:

- `src/api/main.py`
- `src/api/routers/inspections.py`
- `src/api/services/inspections.py`
- `src/api/services/inspection_policy.py`
- `src/api/services/bin_policy.py`
- `src/api/services/control_policy.py`
- `src/api/services/late_results.py`
- `src/api/clients/inference.py`
- `src/api/control/virtual_control.py`
- `src/api/db/`

## 14. 복귀 시 한 문장 요약

현재 Backend는 “최대 12장 multipart 요청 → Mock Inference → confidence 또는 500ms timeout 판정 → 정상/재검사 bin → Mock Virtual Control → late-result 진단”까지 독립 실행되며, 다음 핵심 작업은 확정된 계약을 기준으로 Repository·DB 저장과 BE-05 이력·통계 API를 연결하는 것이다.
