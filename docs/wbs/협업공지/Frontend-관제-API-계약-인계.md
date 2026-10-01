# 품질 관제 API 구현·협업 인계

확인일: 2026-09-29. 이 문서는 이전 FE 선행 작업 목록의 최신 상태를 대체한다.

## 완료 범위

FE-01~07의 관제 화면, 이력·기간 통계·CSV, Simulator 제어, 장애 설정, 이미지 관리, 오판 의심 표시를 HTTP 클라이언트와 동일출처 proxy에 연결했다. 요청 취소·시간 제한·중복 제출 방지·오류 표시·연결 끊김 시 마지막 결과 유지가 포함된다. 화면 전체는 고정하고 내부 목록만 스크롤한다.

[OpenAPI 3.1 계약](../../contracts/quality-operations.openapi.json)을 먼저 구현했다. Backend는 기존 `POST /v1/inspections`를 유지하고 아래 관제용 조회·제어 adapter를 추가하면 된다. 실제 서비스 적용은 협업 검토와 통합 검증이 필요하다.

## 실행

`cqc-logistics-platform/apps/web`에서 `npm ci`, `npm run quality:reference`를 실행한다. 별도 터미널에서 아래 환경을 `.env.local`에 설정하고 `npm run dev`를 실행한다.

```dotenv
CQC_QUALITY_MODE=api
CQC_QUALITY_BACKEND_URL=http://127.0.0.1:8101
```

참조 서버는 브라우저와 별도 프로세스로 실행된다. 메모리 기반이며 재시작하면 이력·위치가 초기화된다. `source=reference`로 표시하고 실제 모델·MySQL 연결로 표현하지 않는다. 정적 사과 이미지와 추론 시간은 예시이며 1초 입력은 실제 500ms Simulator 및 목표 CPU 성능 증명이 아니다. 브라우저 전용 시연은 `CQC_QUALITY_MODE=demo`다.

## API 경로

기준 경로는 `/v1/quality`, 브라우저는 `/api/quality` proxy를 사용한다. 상세 필드·필터·응답은 OpenAPI가 기준이다.

| 메서드 | 경로 | 동작 |
|---|---|---|
| GET | /snapshot | 상태·오늘 통계·진행 중 작업·최근 결과·기간 합계 |
| GET | /inspections | 필터·50/100/200행 페이지 조회 |
| GET | /inspections.csv | 필터에 맞는 보존 이력 전체 CSV |
| GET | /statistics | 날짜 범위 집계 |
| GET | /statistics.csv | 날짜 또는 시간 범위 통계 CSV |
| PUT | /simulator | 실행·병렬 수·장애 종류·적용 범위 변경 |
| PATCH | /inspections/{id}/review | 오판 의심 지정·해제 |
| GET, DELETE | /fault-images | 목록 및 지정 ID 삭제 |
| GET | /previews/{id} | 진행 중 또는 장애 이미지 |

### 현재 Simulator 라인 속도 계약 (2026-10-01)

`PUT /v1/quality/simulator`는 기존 부분 변경 요청에 `intervalMs`를 추가한다. `expectedRevision`은 필수이며 `intervalMs`는 1000·2000·3000 중 하나다. 성공하면 revision이 증가하고 전체 snapshot을 반환한다. 실행 중에도 변경할 수 있으며 다음 검사 투입 예약부터 적용된다. FE는 `GET /v1/quality/snapshot` 또는 PUT 응답의 `state.intervalMs`에서 현재 값을, `capabilities.intervals`에서 선택 목록을 읽는다. Simulator 연결이 없으면 선택 목록은 빈 배열이며 기존 제어 불가 상태를 유지한다. `intervalMs`는 이전 검사 완료 후 대기 시간이 아닌 검사 투입 **시작 시점 간격**이다.

Simulator 프로세스 재시작 시 현재 값은 `SIMULATOR_INTERVAL_MS`에서 다시 읽는다. 런타임 변경은 저장하지 않는다. 공개 필드와 허용값은 [OpenAPI 계약](../../contracts/quality-operations.openapi.json)의 `Settings`, `Snapshot` 정의를 따른다.

## 서버가 지켜야 할 동작

- 계약 버전은 `1`. 실제 연결만 `source=backend`로 응답한다. 4개 구성요소 상태는 실제 상태 확인 결과를 사용한다. 미구현 기능은 capabilities에서 비활성화한다.
- 제어 요청은 `expectedRevision`을 검사하고 충돌 시 409를 반환한다. NEXT 장애는 병렬 요청 전체에서 정확히 한 건만 원자적으로 소비한다. FE는 성공 응답 후 상태를 확정한다.
- 목록은 `snapshotAt`을 기준으로 조회해 새 검사 때문에 페이지가 밀리지 않게 한다. 보존 만료로 과거 항목은 사라질 수 있다. CSV는 현재 페이지가 아닌 필터 전체다.
- 삭제는 확인 창을 열 때 포착한 ID만 대상으로 한다. 이후 도착한 장애 이미지와 검사 이력·오판 의심 기록은 보존한다.
- 모든 응답은 no-store. 정상 이미지는 처리 완료 후 404/410, 장애 이미지는 별도 보존한다. previewUrl은 `/api/quality/previews/{id}`만 허용한다. 실제 파일 삭제는 Backend 책임이다.
- 품종 fuji/yanggwang은 부사/양광, 등급 L/M/S는 특/상/보통으로 adapter에서 변환한다. 신뢰도 0~1은 0~100으로 변환한다. 통계 제외 결과의 예측·신뢰도·추론 시간은 null이다. 누락 가상 당도도 null이며 `brixMeasured=false`를 유지한다.
- 검사·제어·저장 상태를 독립적으로 매핑한다. 저장 성공은 SAVED, 실패는 FAILED다. 알 수 없는 오류를 정상으로 바꾸지 않는다. DB 장애 시 선별은 계속하고 저장 통계는 마지막 저장 시점에 고정한다. 조회 실패는 503으로 알린다.
- 오늘 누적은 KST 기준이다. 날짜 통계와 CSV는 서버 보존 범위가 기준이다. 참조 서버는 이력 2,000건·장애 이미지 100개·오류 50개·시계열 1,800개를 보관한다. snapshot은 최근 이력 200건과 차트 30개 및 기간 합계만 보내 1초 조회 크기를 제한한다.

## 협업 잔여

| 담당 | 구현 요청 |
|---|---|
| Backend BE-05~07 | OpenAPI에 맞춘 실제 DB 조회·CSV·집계·제어 adapter, 파일 만료·삭제, 상태 조회 |
| Simulator | 실제 500ms 입력, bundle 연동, position 저장·재시작 복구, 원자적 NEXT 소비 |
| DM | 실제 모델 버전·두 신뢰도·추론 시간·제외 결과 제공 |
| MLOps | 서비스 주소·접근 정책·볼륨·재시작 구성, 목표 CPU 병렬 수 측정 |
| 공동 FE-08~09 | 실제 검사→저장→조회 통합, 5종 장애·복구·보존 시험, 장시간 브라우저 메모리 측정, M5 수용시험·동결 |

FE는 위 API 호출까지 구현되어 있어 다른 파트 완료 후 주소를 교체하고 실제 결과와 대조한다. 참조 서버 검증을 실제 모델·DB 수용시험 완료로 간주하지 않는다.

## 검증과 코드

`npm test` 31개(2026-09-29 FE-10 병합 후 dev), lint 및 production build 통과. 계약·페이지 고정·CSV·revision 충돌·NEXT·이미지 만료·DB 장애·통계·proxy를 검사한다. 8시간 시험은 상태 로직 가속 시험이며 실제 8시간 브라우저 시험은 남아 있다.

구현: `src/lib/quality-api.ts`, `quality-proxy.ts`, `quality-reference.ts`, `quality-statistics.ts`, `src/components/useQualityConnection.ts`, `QualityHistory.tsx`, `QualityStatistics.tsx`. 계약 재생성: `npm run quality:contract`.

이후 사용자 요청에 따라 WBS 작업 단위로 커밋·푸시한다.
## dev 병합 및 배포 인계 (2026-09-29)

PR #18이 dev `2fa187b`에 병합됐다. MLOps는 기존 `cqc-logistics-platform/apps/web/Dockerfile`을 루트 Compose의 frontend placeholder 대신 연결하고 포트 3000·healthcheck를 구성한다. `CQC_QUALITY_MODE=api`, `CQC_QUALITY_BACKEND_URL=http://backend:8000`을 서버 실행 환경에 제공한다. 2026-09-29 BE-05 병합으로 Backend에 조회 계약 5개(`snapshot`, `inspections`, `inspections.csv`, `statistics`, `statistics.csv`)가 구현됐다. 시연 제어(`PUT /simulator`), 검수(`PATCH /inspections/{id}/review`), 장애 이미지(`/fault-images`), 미리보기(`/previews/{id}`) 4개는 아직 Backend에 없으므로 해당 화면 기능은 API 모드에서 동작하지 않는다.

참조 서버는 별도 개발/계약 검증용이다. 실제 Backend·Inference Compose 및 서버컴 합성 입력 측정은 이미 존재하므로 이를 재구현 대상으로 요청하지 않는다. 실제 DB·Simulator 연결과 실제 사진 기반 통합시험은 남아 있다.

## 2026-09-30 BE-06 개별 장애 이미지 계약 반영

Backend PR #24가 포함된 dev `b0b08dd`의 OpenAPI를 기준으로 FE를 수정했다.

- `/fault-images`는 별도로 조회하며 한 항목은 사진 한 장이다. id는 이미지 ID, inspectionId는 검사 ID, imageIndex는 입력 view_index다.
- preview/delete는 이미지 ID를 사용한다. 오판 의심 지정은 inspectionId로 요청한다. snapshot.state.images는 기존 검사 단위 Result[]를 유지하며 이미지 목록으로 사용하지 않는다.
- 전체 삭제도 확인 창을 열 때의 이미지 ID 목록만 보낸다. 서버가 삭제를 확인한 ID만 우선 반영하고 목록을 다시 조회한다. 삭제 실패로 남은 항목은 경고하며 신규 도착 사진은 보존한다.
- 표시 장수는 API 모드에서 retention.images를 사용한다. 최대 보존 한도 100장과 실제 장수를 구분하며 capabilities.deleteImages가 허용한 경우에만 삭제한다.
- 브라우저 demo와 reference 서버도 검사 기록과 개별 이미지 목록을 분리했다. 추론 오류/시간초과 검사의 각 시연 view를 개별 항목으로 보관하며 100장 초과 시 오래된 사진부터 제거한다. 참조 모드의 원본 시연 자산은 공유 정적 파일이므로 목록/접근권 만료를 재현하며 원본 파일을 지우지 않는다.
- 기존 계약 schema는 Backend 변경을 그대로 사용한다. 프론트에서 Backend OpenAPI를 다시 정의하거나 덮어쓰지 않았다.

검증: FE 자동 시험 33개 통과. 개별 삭제 후 같은 검사 나머지 view·이력 보존, 확인 후 새 이미지 보호, 100장 순환, preview 만료, 실제 보존 장수, Backend OpenAPI 응답 검증 포함. 실제 배포 Backend의 파일 시스템을 대상으로 한 브라우저 통합시험은 별도 확인이 필요하다.

조회 실패 격리: `/fault-images` 실패는 snapshot 반영을 막지 않는다. FE는 두 요청을 병렬로 보내고 이미지 목록 오류는 장애 이미지 창에만 표시한다. 배포 시 Backend `FAULT_IMAGE_STORAGE_ROOT` Volume이 없으면 목록은 계속 503이므로 MO-05 설정이 필요하다.
