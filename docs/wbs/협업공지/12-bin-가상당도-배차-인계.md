# Backend·MLOps 인계: 시연용 12-bin 배차

2026-09-26 사용자 결정. WBS 작업명·기간은 바꾸지 않고 시연 정책만 6개 정상 bin에서 12개로 확장한다. 실제 당도 측정·새 모델 학습은 하지 않는다.

## 결정된 정책

- v2는 **품종(fuji/yanggwang)과 외관 등급(L/M/S)**을 예측한다. 가상 당도는 별도 시연 생성값(`virtual_brix`, `brix_is_measured=false`)이다.
- 정상 판정에 한해 `virtual_brix < 12.0`은 `less_sweet`, `>= 12.0`은 `sweet`으로 분류한다. 12.0은 `sweet`에 속한다. 이는 프로젝트 시연 경계이며 실제 단맛 보증이 아니다.
- 품종 2 × 외관 3 × 당도 2 = 정상 12 bin. 저신뢰·시간 초과·시스템 오류·가상 당도 누락은 기존 재검사 bin 1개로 보낸다. 가상 당도 9~18 범위를 벗어나거나 NaN/무한대이면 입력 오류로 거부한다.
- 기존 외관 60%·가상 당도 40%의 `commercial_grade`는 별도 종합등급 실험/표시 값이다. **12-bin 배차에는 사용하지 않는다.** 원래 외관 등급과 당도 구간을 각각 유지해야 12개 조합이 성립한다.
- bin별 입고량 집계는 수요 분석 화면에 사용할 수 있다. 주문·판매 데이터 없는 상태에서 이를 실제 수요 예측 정확도로 부르지 않는다.
- 현재 시연용 기본 869묶음을 12° 기준으로 재생하면 12° 미만은 43묶음이다. 원본 사과 기준으로는 128개 중 6개뿐이며, `fuji/M/less_sweet`과 `yanggwang/S/less_sweet`의 시연 원본 사과는 0개다. **12개 목적지는 정의되지만 기본 데이터만 재생해서는 12개가 모두 채워지지 않는다.** 12° 경계는 사용자와 합의한 시연값으로 유지한다.

| 품종 | 외관 | 12 미만 | 12 이상 |
|---|---|---|---|
| fuji | L | `DEMO_BIN_01` | `DEMO_BIN_02` |
| fuji | M | `DEMO_BIN_03` | `DEMO_BIN_04` |
| fuji | S | `DEMO_BIN_05` | `DEMO_BIN_06` |
| yanggwang | L | `DEMO_BIN_07` | `DEMO_BIN_08` |
| yanggwang | M | `DEMO_BIN_09` | `DEMO_BIN_10` |
| yanggwang | S | `DEMO_BIN_11` | `DEMO_BIN_12` |

코드와 경계 테스트: `src/api/services/bin_policy.py`의 `determine_demo_target_bin`, `tests/api/test_bin_policy.py`. Backend `POST /v1/inspections`는 시연용 multipart 필드 `virtual_brix`를 받으면 12-bin 경로를 사용하고 응답에 `virtual_brix`, `brix_is_measured=false`, `sweetness_band`, `target_bin_code`를 반환한다. **기존 Mock 요청에 이 필드가 없으면 과거 6-bin 경로로 동작한다.** 이 하위 호환 동작은 시연 배포 완료 상태가 아니며, Simulator·DB·Frontend·실제 Inference 연결은 별도 작업이다.

## Backend 담당 작업

1. Simulator의 시연용 12장 묶음 입력과 가상 당도 출처를 연결한다. `data/processed/realtime-apple-arrival-demo`는 Git 제외 자료다. 원본 `group_no`나 정답 라벨은 모델 입력으로 보내지 않는다. `demo-virtual-brix.csv`에서 조회한 9~18 범위의 값을 현재 Backend 검사 요청의 `virtual_brix` multipart form 필드로 전달한다. 계약 변경을 Simulator·Frontend·OpenAPI와 동기화한다.
   - 자료 폴더의 `demo-virtual-brix.csv`는 `demo_bundle_id`로 `index.json`의 `inspection_id` 예시와 결합한다. 반복 검사에서는 새 `inspection_id`를 발급하되 당도 조회에는 원래 묶음 ID를 사용한다. 996개 묶음의 값을 모두 포함하며 기본 869개 중 12° 미만은 43개다. 이 파일은 `scripts/build_demo_bin_brix.py`로 생성·검증한다.
2. 현재 HTTP 시연 경로는 12-bin으로 연결했으나, **가상 당도 누락 시 기존 6-bin Mock 경로가 남아 있다.** 실제 시연 모드에서는 누락을 재검사로 바꾸고, 응답·DB의 `virtual_brix`, 출처, `brix_is_measured=false`, 당도 구간, `target_bin_code` 저장을 연동한다. 이미지는 Inference에 보내되 가상 당도는 배차 정책에서 사용한다.
3. 기존 `bin_mappings`의 `(crop_type, cultivar, quality_grade)` 유일 제약은 같은 외관의 당도 2개 bin을 담을 수 없다. 기존 마이그레이션을 고치지 말고 **새 마이그레이션**으로 sweetness 구간을 키에 추가하고 12개 정상+재검사 1개 seed를 준비한다.
4. 가상 제어 거부 시 재검사 대체·시간 초과 후 확정 bin 불변·저신뢰 분기는 기존 정책을 유지한다. 12조합 및 11.9/12.0 경계 통합 테스트를 추가한다.

## Frontend·MLOps 담당 작업

- Frontend: 12개 정상 목적지와 재검사 1개를 표시하고, 가상 당도/구간을 `실측 아님`으로 표기한다. 12개 상품군 물량 집계를 수요 분석용으로 보여준다.
- MLOps: Git에서 제외된 시연용 사진 묶음과 가상 당도 자료를 서비스에 공급하고, DB 신규 마이그레이션·13개 bin seed를 배포한다. 자료 배치 전에는 12-bin 통합 시험 완료로 표시하지 않는다.
