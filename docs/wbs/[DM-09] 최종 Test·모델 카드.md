# [DM-09] 최종 Test 1회·모델 카드

## 2026-09-23 후속 요청: 종합등급 v3 신규 모델 학습

### 기존 Test 진단 및 5-fold 후속 실행

- `outputs/training-commercial-v3`는 25/25 epoch 완료. 최고 source Validation 체크포인트는 epoch 17이며 합성 종합등급 Macro F1은 0.623793, 품종 Macro F1은 1.000000이다.
- 해당 체크포인트의 기존 Test 27그룹 합성 종합등급 Macro F1은 **0.715670**, 정확도 20/27, 품종 Macro F1은 1.000000이다. 혼동행렬(L/M/S)은 `[[3,1,0],[2,10,2],[1,1,7]]`이다. [평가 원본](results/commercial-v3-reused-test-diagnostic.json).
- 같은 27그룹·같은 합성 종합등급 정답에 v2 외관 예측 + 정확한 60:40 정책을 적용한 비교는 Macro F1 **1.000000**, 정확도 27/27이다. [규칙 비교 원본](results/commercial-v2-rule-reused-test.json).
- 두 방법은 Test 사과와 합성 정답은 같지만 학습 사과 수가 다르다(v2 외관 최종 모델 152그룹, v3 source 모델 118그룹). 따라서 이 Test 표의 차이를 순수한 구조 차이로 해석하지 않는다.
- 위 Test는 이미 사용한 27그룹의 회귀 진단이다. v3 epoch·설정 변경이나 독립 승인 판단에 사용하지 않는다.
- 5-fold Group CV는 집 PC `outputs/training-commercial-v3-cv`에서 5회 순차 실행 중이다. 각 fold의 학습/검증 사과는 분리하고 공통 epoch 17에서 품종·합성 종합등급 Macro F1을 집계한다. 완료 전에는 평균 결과가 없다.

앞선 v2+규칙만 유지 방침 이후, 사용자 지시로 **종합등급 자체를 출력하는 신규 모델**을 학습한다. 이전 가상 당도 결합 실험(외관 정답 예측)과 다르다. v2는 보존한다.

- 코드: `src/training/train_commercial_v3.py`. 사진 12장(224 RGB)과 기존 가상 당도·불확실성을 입력한다.
- 품종 정답은 유지하고 품질 헤드 정답만 원본 외관 정답 + 가상 당도의 승인된 60:40 정책으로 생성한다. 원본 매니페스트·라벨은 변경하지 않는다.
- 정답 의미는 `simulated_commercial_grade`, 모델 후보 버전은 `commercial-v3-candidate`. 신경망은 규칙을 근사하므로 규칙과 항상 일치하는 것은 아니다. 평가 점수는 실측 품질 정확도가 아닌 합성 정책 정답과의 일치도다.
- Test 제외 후 source 분할: 학습 118개(L16/M61/S41), 검증 34개(L6/M15/S13). Test 27개와 시연용 사진 폴더는 학습에 사용하지 않는다.
- MobileNetV3 Small 분리 인코더·가상 당도 결합, 고정 12장, 25 epoch, batch 2, Focal gamma 2, dropout 0.4, AdamW lr 0.0003·weight decay 0.0005, seed 42, workers 0. 기존 학습 전처리를 유지한다.
- 집컴 `D:\Study\CQC\outputs\training-commercial-v3`: 설정·개발 정답·history·best.pt·last.pt·완료 summary. 표준 로그는 같은 outputs의 `training-commercial-v3.stdout.log`, 오류 로그는 `.stderr.log`다.
- 집컴의 독립 프로세스로 실행하며 노트북 SSH 종료와 분리한다. 집컴 종료 시에는 멈추며 자동 재개 기능은 없다.
- 로컬 정책 테스트 5개 통과, 원격 실행 전 분할·클래스 분포·입력 파일 해시 점검 완료. 기존 v2의 API·패키지·승인 상태는 변경하지 않는다.

## 2026-09-23: v2 유지 및 시연용 종합 판정

- 추가 학습 없이 v2 외관 결과에 `demo-commercial-v1` 정책을 적용한다. 모델·체크포인트·승인 메타데이터는 변경하지 않았다.
- `src/inference/commercial_policy.py`: 외관 60%·가상 당도 40%, 최소 등급 조건 및 검수 보류. 이름 변경 가능.
- 외관 `predicted_grade`와 종합 `commercial_grade`를 분리하며 실측 당도·공식 상품 등급으로 표시하지 않는다.
- 정책표·사용법·근거는 [가상 당도 계획](reference/DM/virtual-brix-plan.md)의 최신 확정 절을 따른다.
- `tests/test_commercial_policy.py`: 전체 등급 조합, 경계값, 잘못된 값, 검수 보류, 이름 변경 및 기존 응답 보존 검증.
- 로컬 어댑터 구현 범위이며 HTTP·DB·Frontend·Simulator 연결은 미적용이다. 재학습하지 않는다.

## 목적

### 2026-09-23 가상 당도 결합 모델의 기존 Test 진단

- 사용자 요청으로 기존 완료 모델을 먼저 평가했으며 신규 학습은 시작하지 않았다.
- 대상: `training-brix-v1/separate_brix/focal_ordinal_regularized-source/best.pt`. 25 epoch 학습 완료, source Validation이 선택한 저장 체크포인트는 **epoch 8**이다. 공통 epoch 비교 보고서의 epoch 11 모델이나 전체 개발 세트 최종 학습본과는 다르다.
- 입력: 고정 12장 + 기존 가상 당도 CSV. 학습 118그룹·검증 34그룹, 기존 Test 27그룹은 학습에서 제외됐다.
- 결과: 품종 Macro F1 1.000000, 외관 품질 Macro F1 0.926740, 품질 정확도 25/27(92.59%). 보통(S) 2개를 상(M)으로 오분류했다.
- 결과 파일: [결합 모델 기존 Test 진단](results/brix-source-reused-test-20260923.json).
- 기존 Test 반복 사용에 따른 참고 진단이며 독립 최종 승인이나 Test 기반 후보 선택에 사용하지 않는다. v2 최종 모델은 152그룹 학습이므로 동등 학습 조건 비교가 아니다.
- 이 모델은 가상 당도를 입력받아 **기존 외관 등급**을 예측한다. 당도 측정 모델이나 60:40 종합 상품성 정책을 학습한 모델이 아니다.
- `scripts/evaluate_reused_test.py`에 결합 모델용 `--virtual-brix` 입력 검증·데이터 연결을 추가했다.

Test를 보지 않고 확정한 모델 구조·입력 장수·epoch·신뢰도 기준으로 최종 학습한 뒤, 고정 Test 27그룹을 한 번만 평가하고 승인 여부와 한계를 기록한다.

## 시험 전 확정값

- 모델: 품종·품질 분리 MobileNetV3 Small (`separate`)
- 입력: 동일 사과 대표 12장, 224×224 RGB
- 최종 학습: Test 제외 152그룹, 19 epoch
- 신뢰도 기준: 품종 0.50, 품질 0.50
- 승인 기준: 품종·품질 Macro F1 각각 0.90 이상
- 모델 버전: `cqc-apple-separate12-v1.0.0`

19 epoch는 5-fold 최고 epoch `20·15·16·19·20`의 중앙값으로 정했다. 최종 학습 설정과 기준은 Test를 열기 전에 고정했다.

## 최종 학습 결과

- 학습 그룹: 152
- 완료 epoch: 19/19
- Test 사용: 없음
- 체크포인트 SHA-256: `7c2d68a9f56f6e00555bb5e79db5bd0881caa6e742ae5d04469525a89e8183a2`
- 실행 방식: 집 PC Windows 예약 작업 `CQCFinalFit`

## 최종 Test 1회 결과

| 과제 | Accuracy | Macro F1 | 승인 기준 | 결과 |
|---|---:|---:|---:|---|
| 품종 | 1.0000 | 1.0000 | 0.90 | 통과 |
| 품질 | 0.7778 | 0.7778 | 0.90 | 실패 |

품종 혼동행렬은 `[[10, 0], [0, 17]]`, 품질 혼동행렬은 `[[7, 0, 0], [4, 6, 2], [0, 0, 8]]`이다. 품질 클래스 순서는 `L, M, S`다.

Test 실행 시 체크포인트 옆에 잠금 표식을 생성했다. 같은 체크포인트는 출력 경로를 바꿔도 다시 평가할 수 없다.

## 실패 사례

오분류 6건은 모두 실제 `M(상)` 등급이다.

| group_no | 실제 | 예측 | 예측 신뢰도 |
|---|---|---|---:|
| 601032003000 | M | S | 0.9655 |
| 601032016000 | M | L | 0.9770 |
| 601142004000 | M | L | 0.6681 |
| 601142010000 | M | L | 0.6981 |
| 601142014000 | M | L | 0.9858 |
| 601142064000 | M | S | 0.9703 |

높은 신뢰도의 오분류가 있어 0.50 임계값을 올리는 것만으로 해결할 수 없다. 이번 Test 결과를 보고 모델이나 임계값을 다시 선택하면 Test 누수가 되므로 재학습·재평가는 진행하지 않는다.

## 패키지·서비스 검증

- 모델 파일과 manifest SHA-256 일치 확인
- manifest에 클래스 순서, 전처리, 12장 입력, 두 신뢰도 기준 포함
- 실제 validation 그룹 12장, 14,253,186바이트 multipart 요청 성공
- `GET /health`: HTTP 200, 모델 버전·CPU·12장 입력 확인
- `POST /v1/predict`: HTTP 200, 품종·품질 확률과 신뢰도 반환
- 해당 단일 CPU 호출의 모델 추론시간: 45.8ms

## CPU 예비 측정

i7-14700F, PyTorch thread 1, 100회 결과다.

| 동시 처리 | p95 | 처리량/초 | 500ms | 초당 2건 |
|---:|---:|---:|---|---|
| 1 | 113.6ms | 9.31 | 충족 | 충족 |
| 2 | 151.2ms | 14.46 | 충족 | 충족 |
| 4 | 182.1ms | 23.41 | 충족 | 충족 |

운영 기본값은 동시 처리 1이다. 목표 i7-4790은 학원 Jenkins 서버에 있으나 아직 해당 장비에서 실행한 기록이 없어 위 값은 예비 결과이며 NFR-07 승인값이 아니다.

## 결론

DM-09의 최종 학습, Test 1회, 실패 분석, 모델 카드와 패키지 기능 검증은 완료했다. 그러나 품질 Macro F1이 사전 승인 기준에 미달하므로 이 버전을 최종 승인 모델로 표시하거나 운영 배포하면 안 된다.

다음 모델 개선에는 Test와 독립된 신규 사과 그룹을 새로운 holdout으로 확보해야 한다. 기존 27개 Test 결과는 이번 버전의 최종 보고 근거로만 보존한다.

## 산출물

- `docs/wbs/reference/DM/model-card.md`
- `docs/wbs/results/final-test-result.json`
- `docs/wbs/results/final-concurrency-i7-14700F.json`
- `docs/wbs/results/thresholds-separate-12view.json`
- `docs/wbs/results/model-comparison.json`
- `docs/wbs/results/model-manifest.json`

모델 바이너리는 Git에 넣지 않고 집 PC의 `D:\Study\CQC\models\cqc-apple-separate12-v1.0.0`에 보관한다.


## 2026-09-23: 후속 최종 학습 준비·실행 기록

- DM-06 개발 비교에서 정한 separate·12장·focal·4 epoch를 사용한다.
- dropout 0.4, learning rate 0.0003, weight decay 0.0005, 개발 152그룹이다.
- `final_fit.py`에 명시적 epoch·품질 손실·dropout 전달을 추가했고 관련 테스트 20개 통과를 확인했다.
- 원격 `outputs/final-training-brix-v1/separate-12view-focal-e4` 학습은 2026-09-23 08:53에 4/4 epoch 완료했다. 로그·summary·체크포인트 존재를 확인했다.
- 완료 산출물 요약·패키지 manifest·동작 검증 결과를 `docs/wbs/results/candidate-v2-*.json`으로 수집했다.
- 남은 승인 조건: 신규 독립 holdout, 새 모델 신뢰도 기준 검증, i7-4790 성능시험. 기존 27그룹 평가를 새 독립 Test로 표시하지 않는다.

## 후속 후보 모델 카드 및 인계 정보

| 항목 | 확인 결과 |
|---|---|
| 버전 | `cqc-apple-separate12-focal-v2-candidate` |
| 상태 | 미승인 후보, 운영 배포 금지 |
| 구조 | separate MobileNetV3 Small, 12장, 224×224 RGB |
| 학습 | 개발 152그룹, focal, 4 epoch, dropout 0.4 |
| 당도 입력 | 사용하지 않음. 가상 당도는 실측 당도가 아님 |
| SHA-256 | `b254206e4091732a49c5db02c12e5fb6dc3d996dbce694c2e82d442a2ba8753a` |
| 독립 Test F1 | 미측정. 학습 종료나 API 성공으로 추정하지 않음 |
| 신뢰도 기준 | 미보정. 이전 모델 임계값을 새 검증값으로 재사용하지 않음 |
| 패키지 | 집 PC `D:\Study\CQC\models\cqc-apple-separate12-focal-v2-candidate` |

기존 v1 모델 카드와 패키지는 보존한다. 개발 비교 결과는 DM-06에 기록되어 있으며 새 최종 체크포인트의 독립 평가 결과가 아니다.

### 기능 검증

- SHA-256 검증 후 CPU 모델 로딩 성공.
- 합성 PNG 12장으로 FastAPI TestClient의 `/health`, `/v1/predict` 성공.
- `inspection_id` 왕복, `used_frame_count=12`, 품종·품질 확률 응답 확인.
- 집 PC의 구버전 `api.py`, `schemas.py`, `predictor.py`를 로컬의 기존 최신 계약 코드로 동기화했다. 최초 실패는 구버전 응답 필드 누락이었으며 동기화 후 통과했다.
- 이 검증은 프로세스 내부 API 시험이다. 실제 네트워크·Backend 통합·실사과 정확도·목표 CPU 성능을 검증한 것이 아니다.
- 로컬 패키징·최종 학습 설정·추론 API·predictor 관련 테스트 16개 통과.

재현 명령(프로젝트 루트, 검증 보고서는 새 경로 사용):

```powershell
python -m scripts.verify_candidate_package --package models/cqc-apple-separate12-focal-v2-candidate --output outputs/candidate-v2-smoke.json
```

백엔드 담당자는 후보 버전을 명시해 연동 시험에 사용할 수 있다. 입력 계약은 기존 대표 12장·inspection_id·metadata를 유지한다. 서버 상시 실행·운영 모델 교체는 이번 작업에서 하지 않았다.

## 2026-09-23: v2 후보의 기존 Test 회귀 진단

- 체크포인트: `cqc-apple-separate12-focal-v2-candidate`, SHA-256 `b254206e4091732a49c5db02c12e5fb6dc3d996dbce694c2e82d442a2ba8753a`.
- 기존 v1 분석에 사용했던 동일 Test 27그룹에 대해 v2 예측을 한 번 더 계산했다. 품종·품질 Macro F1 모두 **1.0000**, 품질 혼동행렬 L/M/S 순서 `[[7,0,0],[0,12,0],[0,0,8]]`이었다.
- 원본 결과: `docs/wbs/results/candidate-v2-reused-test-regression.json`. 이전 v1 품질 0.7778과 비교하는 **회귀 진단**이다. v1 Test 실패가 개선 방향에 영향을 주었으므로 독립 최종 승인 결과가 아니며, 이 점수로 다음 모델·epoch·임계값을 선택하지 않는다.
- 개발 비교의 source holdout 품질 F1 약 0.793과 차이가 크다. 표본·분할 차이, 원본 출처별 난이도, 반복 사용 편향을 별도로 분석해야 한다. 현 단계에서는 27/27을 실제 운영 정확도로 일반화하지 않는다.
- 신규 독립 그룹 확보와 목표 i7-4790 시험은 여전히 미완료다.

### 프로젝트 적용 판단 (2026-09-23)

사용자와 평가 범위를 재정리하여 v2를 프로젝트 적용 기준 모델로 유지한다. 신규 데이터를 얻기 어려운 프로젝트 조건에서, 기존 Test 27그룹의 전후 비교 개선은 유효한 성과로 보고한다. 신규 독립 데이터 확보를 시연·통합의 필수 선행 조건으로 두지 않는다. 다만 기존 Test 반복 사용과 source 검증 품질 F1 약 0.793을 함께 공개하며, 외부 환경에서 품질 100% 또는 운영 일반화 검증 완료로 표현하지 않는다. 추가 증강 학습은 사용자 요청으로 중단했고, 선택적인 후속 계획은 DM-06에 기록했다. 기존 패키지의 `unverified_candidate` 표기는 독립 승인 여부를 나타내므로 이번 문서 판단만으로 바이너리·manifest를 바꾸지 않았다.
