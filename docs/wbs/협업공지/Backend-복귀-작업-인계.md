# Backend 복귀 시 바로 읽을 작업 인계

기준: 2026-09-26 `feat/data`에서 코드·WBS·Compose를 확인한 스냅샷. Backend 담당자가 돌아오면 **현재 브랜치·PR·파일 상태를 먼저 재확인**하고 아래 미완료 항목부터 이어간다. 이 문서는 기존 WBS 코드나 완료 기록을 고치지 않는다.

## 1. 지금 구현된 것과 구현되지 않은 것

- `src/api/`에는 BE-01~BE-04 범위의 FastAPI `POST /v1/inspections`, `/health`, Mock Inference/Virtual Control, 신뢰도·500ms timeout·late-result 정책이 있다. `src/api/db/`에는 ORM과 **초기** Alembic migration이 있지만 검사 결과를 실제 MySQL에 저장하는 Repository는 없다.
- 2026-09-26 추가: 검사 multipart의 선택 필드 `virtual_brix`(9~18)를 받으면 품종 2종 × v2 외관 L/M/S × 12°Brix 미만/이상의 **정상 12 bin**으로 배차하고 응답에 `virtual_brix`, `brix_is_measured=false`, `sweetness_band`를 담는다. 경계값 12.0은 `sweet`이다. 저신뢰·timeout은 재검사 bin으로 간다.
- 이 경로도 여전히 **Mock Inference·Mock Control** 위에서 동작한다. `virtual_brix`를 보내지 않는 이전 요청은 기존 6-bin Mock 경로로 남아 있으므로, 12-bin 전체 통합 완료로 해석하면 안 된다.
- `src/simulator/`와 BE-05~BE-10 구현·WBS 결과 문서는 아직 없다. `compose.yaml`의 기본 inference/backend/frontend/simulator 서비스는 Alpine placeholder다. 실제 inference 코드는 `src/inference/`, OpenAPI는 `docs/contracts/inference-openapi.json`에 있다.
- 이번 수정의 로컬 Backend 테스트는 `tests/api` **98개 통과**다. 이는 DB·Simulator·Frontend·학원 서버 통합 시험이 아니다. 기존 [Backend 상태 문서](../reference/BE/backend-status.md)의 79개·6-bin 수치는 **BE-04 당시 기록**이다.

## 2. 돌아와서 시작할 순서

1. **브랜치와 계약 확인:** `feat/data`의 `BE-04 / 가상 당도 12-bin 배차 계약과 협업 인계` 커밋 및 [12-bin 상세 계약](12-bin-가상당도-배차-인계.md)을 읽는다. `dev` 포함 여부를 확인하고 자신의 Backend 변경과 충돌을 점검한다. `docs/wbs.md`의 BE-04 6-bin은 원래 완료 기준의 역사적 기록이므로 WBS 일정·코드를 임의로 다시 쓰지 않는다. 새 시연 정책은 12-bin 계약이 우선한다.
2. **BE-04 후속 12-bin 통합:** 실제 시연 모드에서는 `virtual_brix` 누락을 6-bin으로 흘려보내지 말고 재검사 처리한다. `src/api/services/bin_policy.py`의 12-bin 매핑을 운영 설정·DB와 연결한다. 11.9/12.0 경계, 12개 조합, 저신뢰·timeout·제어 거부를 테스트한다. 60:40 `commercial_grade`와 v3 출력은 배차 키가 아니다.
3. **BE-02/BE-05 DB 연결:** 기존 `bin_mappings`의 `(crop_type,cultivar,quality_grade)` unique 제약으로는 당도 2구간을 저장할 수 없다. **새 Alembic migration**으로 구간 키를 추가하고 12개 정상+재검사 1개 seed를 만든다. 검사·제어·오류 Repository, KST 밀리초 시각, 저장 실패 시 선별 지속, 이력·오늘 통계·필터·CSV를 구현한다. 검사 이력에는 가상 당도·출처·비실측 표시·구간·목적 bin을 남길 계약을 맞춘다.
4. **BE-06/BE-07 Simulator:** Git 제외 자료 `data/processed/realtime-apple-arrival-demo`를 배포 장비에 별도 전달받는다. `index.json`의 `default_playback=true`인 869개 12장 묶음을 500ms 간격으로 반복 재생하고, 각 `request.json`의 이미지 순서·각도 metadata를 유지한다. `demo-virtual-brix.csv`를 원래 묶음 ID로 조회하되 반복 요청마다 새 `inspection_id`를 쓴다. 1~11장 `partial_groups`는 기본 재생에서 제외한다. 사진 원본 그룹 ID·정답 파일은 Inference 입력으로 보내지 않는다. 시작·정지·위치 복구와 장애 토글, 정상 이미지 즉시 삭제·장애 이미지만 순환 보존도 담당 범위다.
5. **BE-08 이후 실제 연결:** `MockInferenceClient`를 `src/inference/`의 `POST /v1/predict`와 연결하고 `inspection_id`, 이미지·metadata 순서, `used_frame_count`, 24MiB/1~12장, 500ms business deadline을 검증한다. Frontend 조회·12-bin 표시와 MLOps Compose/DB migration 배포를 연동한다. BE-09/10의 DB 장애, 동적 bin, 연속 요청·CSV 수용시험까지 마친 뒤에만 전체 통합 완료로 표시한다.

## 3. 다른 담당자와 바로 맞출 것

- **데이터·모델:** v2 모델 패키지와 SHA, 시연용 사진 약 13.7GB 및 `demo-virtual-brix.csv` 전달 위치, Inference HTTP 예시. 가상 당도는 실측이 아니며 기본 869묶음 중 12° 미만은 43묶음이다. 기본 데이터에서 12개 bin 중 2개 조합은 비어 있으므로 모든 bin이 실제 채워졌다고 시연하지 않는다.
- **MLOps:** 실제 Backend/Simulator 컨테이너 실행 명령·볼륨, 새 migration과 13개 bin seed 배포, 학원 서버에서의 통합 시험. 현재 Compose placeholder를 그대로 배포 완료로 보지 않는다.
- **Frontend:** 응답의 `virtual_brix`, `brix_is_measured=false`, `sweetness_band`, `target_bin_code` 표시와 12개 상품군 물량 집계. 주문·판매 데이터가 없으면 이를 실제 수요 예측 정확도로 부르지 않는다.

## 4. 빠른 재검증

Backend 의존성을 설치한 환경에서 `python -m pytest tests/api -q`와 `ruff check src/api tests/api`를 실행한다. 현재 스냅샷은 98개 통과였지만 복귀 시 다시 검사한다. 더 자세한 과거 작업·계약 질문은 [Backend 상태 문서](../reference/BE/backend-status.md), [Backend 구현 명세](../reference/BE/backend-stack.md), [WBS](../../wbs.md), [12-bin 인계](12-bin-가상당도-배차-인계.md)를 따른다.

이 문서를 GPT가 읽고 인지했다면 지워도 됩니다.
