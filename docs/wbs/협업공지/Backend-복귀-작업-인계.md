# Backend 복귀 시 바로 읽을 작업 인계

기준: 2026-09-29 `dev`의 PR #18 병합 커밋 `2fa187b`에서 코드·WBS·Compose를 확인한 스냅샷. Backend 담당자가 돌아오면 **현재 브랜치·PR·파일 상태를 먼저 재확인**하고 아래 미완료 항목부터 이어간다. 이 문서는 기존 WBS 코드나 완료 기록을 고치지 않는다.

## 0. 2026-09-29 dev `1958fa5` 반영 상태

아래 1~5절은 `2fa187b` 시점 스냅샷이다. 이후 PR #20·#22로 다음이 반영됐다.

| 인계 항목 | 현재 상태 |
|---|---|
| 당도 누락 시 6-bin 경로 | 제거됨. `virtual_brix`가 없으면 `VIRTUAL_BRIX_MISSING` 재검사로 분기 |
| 당도 구간 bin 키·13개 seed | migration `20260929_02`로 구현 (`DEMO_BIN_01~12`, 재검사 bin) |
| 저장 Repository·이력·통계·CSV | BE-05로 구현. 관제 조회 API 5개(`/v1/quality/snapshot`, `inspections`, `inspections.csv`, `statistics`, `statistics.csv`) |
| 장애 이미지 | BE-06으로 저장 계층 구현. 저장 트리거와 조회·삭제 API는 미연결 |
| 테스트 | Python 218개 통과, MySQL 통합 5개 통과(`alembic upgrade head` 후) |
| 남은 것 | BE-07 Simulator, 관제 제어·검수·장애 이미지·미리보기 API, 지연 결과 DB 저장, 보존 삭제, 배포 시 migration 적용(MLOps와 협의) |

## 1. 지금 구현된 것과 구현되지 않은 것

- `src/api/`에는 BE-01~BE-04 범위의 FastAPI `POST /v1/inspections`, `/health`, 실제 HTTP 및 Mock Inference client/Virtual Control, 신뢰도·500ms timeout·late-result 정책이 있다. `src/api/db/`에는 ORM과 **초기** Alembic migration이 있지만 검사 결과를 실제 MySQL에 저장하는 Repository는 없다.
- 2026-09-26 추가: 검사 multipart의 선택 필드 `virtual_brix`(9~18)를 받으면 품종 2종 × v2 외관 L/M/S × 14°Brix 미만/이상의 **정상 12 bin**으로 배차하고 응답에 `virtual_brix`, `brix_is_measured=false`, `sweetness_band`를 담는다. 경계값 14.0은 `sweet`이다. 저신뢰·timeout은 재검사 bin으로 간다.
- Inference client는 mock/http 선택이 가능하며 루트 Compose는 기본 http다. 제어는 Virtual Control이다. `virtual_brix`를 보내지 않는 이전 요청은 기존 6-bin Mock 경로로 남아 있으므로, 12-bin 전체 통합 완료로 해석하면 안 된다.
- 실제 `src/simulator/` 구현과 DB 저장·조회 Repository 및 관제 API는 아직 없다. `compose.yaml`의 inference/backend는 실제 서비스이며 frontend/simulator만 placeholder다. FE 코드·Dockerfile·관제 API 클라이언트는 PR #18로 dev에 반영됐다. 실제 inference 코드는 `src/inference/`, OpenAPI는 `docs/contracts/inference-openapi.json`에 있다.
- 2026-09-26 당시 로컬 Backend 테스트 기록은 `tests/api` **98개 통과**다. 이는 DB·Simulator·Frontend·학원 서버 통합 시험이 아니다. 기존 [Backend 상태 문서](../reference/BE/backend-status.md)의 79개·6-bin 수치는 **BE-04 당시 기록**이다.

## 2. 돌아와서 시작할 순서

1. **브랜치와 계약 확인:** `feat/data`의 `BE-04 / 가상 당도 12-bin 배차 계약과 협업 인계` 커밋 및 [12-bin 상세 계약](12-bin-가상당도-배차-인계.md)을 읽는다. `dev` 포함 여부를 확인하고 자신의 Backend 변경과 충돌을 점검한다. `docs/wbs.md`의 BE-04 6-bin은 원래 완료 기준의 역사적 기록이므로 WBS 일정·코드를 임의로 다시 쓰지 않는다. 새 시연 정책은 12-bin 계약이 우선한다.
2. **BE-04 후속 12-bin 통합:** 실제 시연 모드에서는 `virtual_brix` 누락을 6-bin으로 흘려보내지 말고 재검사 처리한다. `src/api/services/bin_policy.py`의 12-bin 매핑을 운영 설정·DB와 연결한다. 13.9/14.0 경계, 12개 조합, 저신뢰·timeout·제어 거부를 테스트한다. 60:40 `commercial_grade`와 v3 출력은 배차 키가 아니다.
3. **BE-02/BE-05 DB 연결:** 기존 `bin_mappings`의 `(crop_type,cultivar,quality_grade)` unique 제약으로는 당도 2구간을 저장할 수 없다. **새 Alembic migration**으로 구간 키를 추가하고 12개 정상+재검사 1개 seed를 만든다. 검사·제어·오류 Repository, KST 밀리초 시각, 저장 실패 시 선별 지속, 이력·오늘 통계·필터·CSV를 구현한다. 검사 이력에는 가상 당도·출처·비실측 표시·구간·목적 bin을 남길 계약을 맞춘다.
4. **BE-06/BE-07 Simulator:** Git 제외 자료 `data/processed/realtime-apple-arrival-demo`를 배포 장비에 별도 전달받는다. `index.json`의 `default_playback=true`인 869개 12장 묶음을 500ms 간격으로 반복 재생하고, 각 `request.json`의 이미지 순서·각도 metadata를 유지한다. `demo-virtual-brix.csv`를 원래 묶음 ID로 조회하되 반복 요청마다 새 `inspection_id`를 쓴다. 1~11장 `partial_groups`는 기본 재생에서 제외한다. 사진 원본 그룹 ID·정답 파일은 Inference 입력으로 보내지 않는다. 시작·정지·위치 복구와 장애 토글, 정상 이미지 즉시 삭제·장애 이미지만 순환 보존도 담당 범위다.
5. **BE-08 이후 실제 연결:** 이미 구현된 `HttpInferenceClient`와 `POST /v1/predict` 연결을 실제 시연 사진으로 재검증하고 `inspection_id`, 이미지·metadata 순서, `used_frame_count`, 24MiB/1~12장, 500ms business deadline을 검증한다. Frontend 조회·12-bin 표시와 MLOps Compose/DB migration 배포를 연동한다. BE-09/10의 DB 장애, 동적 bin, 연속 요청·CSV 수용시험까지 마친 뒤에만 전체 통합 완료로 표시한다.

## 3. 다른 담당자와 바로 맞출 것

- **데이터·모델:** v2 모델 패키지와 SHA, 시연용 사진 약 13.7GB 및 `demo-virtual-brix.csv` 전달 위치, Inference HTTP 예시. 2026-09-29 기준 기본 869묶음은 14° 미만 381묶음·이상 488묶음이다. 기존 CSV의 구간 라벨은 새 기준으로 재생성한다.
- **MLOps:** 실제 Backend/Simulator 컨테이너 실행 명령·볼륨, 새 migration과 13개 bin seed 배포, 학원 서버에서의 통합 시험. 현재 Compose placeholder를 그대로 배포 완료로 보지 않는다.
- **Frontend:** 응답의 `virtual_brix`, `brix_is_measured=false`, `sweetness_band`, `target_bin_code` 표시와 12개 상품군 물량 집계. 주문·판매 데이터가 없으면 이를 실제 수요 예측 정확도로 부르지 않는다.

## 4. 빠른 재검증

Backend 의존성을 설치한 환경에서 `python -m pytest tests/api -q`와 `ruff check src/api tests/api`를 실행한다. 과거 기록은 98개 통과였지만 복귀 시 다시 검사한다. 더 자세한 과거 작업·계약 질문은 [Backend 상태 문서](../reference/BE/backend-status.md), [Backend 구현 명세](../reference/BE/backend-stack.md), [WBS](../../wbs.md), [12-bin 인계](12-bin-가상당도-배차-인계.md)를 따른다.



## 5. FE 관제 계약에 맞춘 우선 작업

[관제 API 인계](Frontend-관제-API-계약-인계.md)와 [OpenAPI](../../contracts/quality-operations.openapi.json)를 기준으로 `/v1/quality/*` adapter를 구현한다. 기존 `POST /v1/inspections`는 유지한다.

1. BE-05: 저장 Repository와 이력·기간 통계·CSV. FE snapshot에 맞춰 KST 누적·최근 결과·기간 합계를 제공한다.
2. BE-06/07: 실제 이미지 만료·삭제, Simulator 제어, 상태·오류, revision 충돌과 NEXT 한 건 소비.
3. 기존 응답의 코드·신뢰도 0~1을 화면 계약의 표시명·0~100에 매핑한다. 통계 제외·누락값은 null을 유지한다.
4. 실제 연결만 source=backend로 응답한다. 미구현 제어는 capabilities에서 비활성화한다. 참조 서버를 MySQL 구현으로 대체 표기하지 않는다.
5. FE 담당과 실제 저장 결과·필터·CSV·이미지 보존을 대조한 뒤 통합 완료를 판정한다.
