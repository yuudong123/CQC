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

`npm test` 20개, lint 및 production build 통과. 계약·페이지 고정·CSV·revision 충돌·NEXT·이미지 만료·DB 장애·통계·proxy를 검사한다. 8시간 시험은 상태 로직 가속 시험이며 실제 8시간 브라우저 시험은 남아 있다.

구현: `src/lib/quality-api.ts`, `quality-proxy.ts`, `quality-reference.ts`, `quality-statistics.ts`, `src/components/useQualityConnection.ts`, `QualityHistory.tsx`, `QualityStatistics.tsx`. 계약 재생성: `npm run quality:contract`.

이후 사용자 요청에 따라 WBS 작업 단위로 커밋·푸시한다.