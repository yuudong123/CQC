# 시연용 12-bin 배차 정책

2026-09-26 사용자 결정. WBS 작업명·기간은 바꾸지 않고 시연 정책만 6개 정상 bin에서 12개로 확장한다. 실제 당도 측정·새 모델 학습은 하지 않는다.

## 결정된 정책

- v2는 **품종(fuji/yanggwang)과 외관 등급(L/M/S)**을 예측한다. 가상 당도는 별도 시연 생성값(`virtual_brix`, `brix_is_measured=false`)이다.
- 정상 판정에 한해 `virtual_brix < 14.0`은 `less_sweet`, `>= 14.0`은 `sweet`으로 분류한다. 14.0은 `sweet`에 속한다. 이는 프로젝트 시연 경계이며 실제 단맛 보증이 아니다.
- 품종 2 × 외관 3 × 당도 2 = 정상 12 bin. 저신뢰·시간 초과·시스템 오류·가상 당도 누락은 기존 재검사 bin 1개로 보낸다. 가상 당도 9~18 범위를 벗어나거나 NaN/무한대이면 입력 오류로 거부한다.
- 기존 외관 60%·가상 당도 40%의 `commercial_grade`는 별도 종합등급 실험/표시 값이다. **12-bin 배차에는 사용하지 않는다.** 원래 외관 등급과 당도 구간을 각각 유지해야 12개 조합이 성립한다.
- bin별 입고량 집계는 수요 분석 화면에 사용할 수 있다. 주문·판매 데이터 없는 상태에서 이를 실제 수요 예측 정확도로 부르지 않는다.
- 2026-09-29 사용자 결정으로 구간 경계를 14°Brix로 변경했다. 전체 179개 사과는 미만 87개·이상 92개, 기본 869묶음은 미만 381개·이상 488개다. 전체 996묶음은 미만 434개·이상 562개다. 생성된 가상 당도 값과 기존 60:40 종합등급 기준은 유지한다.

| 품종 | 외관 | 14 미만 | 14 이상 |
|---|---|---|---|
| fuji | L | `DEMO_BIN_01` | `DEMO_BIN_02` |
| fuji | M | `DEMO_BIN_03` | `DEMO_BIN_04` |
| fuji | S | `DEMO_BIN_05` | `DEMO_BIN_06` |
| yanggwang | L | `DEMO_BIN_07` | `DEMO_BIN_08` |
| yanggwang | M | `DEMO_BIN_09` | `DEMO_BIN_10` |
| yanggwang | S | `DEMO_BIN_11` | `DEMO_BIN_12` |

코드와 경계 테스트: `src/api/services/bin_policy.py`(상수·매핑), `src/api/services/inspections.py`의 `_classify_sweetness`, `tests/api/test_bin_policy.py`. Backend `POST /v1/inspections`는 multipart 필드 `virtual_brix`로 구간을 정하고 응답에 `virtual_brix`, `brix_is_measured=false`, `sweetness_band`, `target_bin_code`를 반환한다. `virtual_brix`가 없으면 재검사로 분기한다.

구현 결과(DB `bin_mappings` 조회, 당도 누락 재검사, 13개 seed)와 남은 연동은 [BE-05](../BE-05.md), [ALL-03](../ALL-03.md)을 따른다.
