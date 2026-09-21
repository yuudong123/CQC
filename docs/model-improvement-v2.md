# CQC 품질 모델 v2 개선안

## 1. 목적과 범위

`cqc-apple-separate12-v1.0.0`은 최종 Test에서 품종 Macro F1 1.0000, 품질 Macro F1 0.7778을 기록했다. 품질 승인 기준 0.90을 충족하지 못했으므로 다음 버전은 품질 등급의 강건성을 우선 개선한다.

이 문서는 기존 WBS를 변경하지 않는다. 기존 Test 27그룹도 모델·epoch·손실·임계값 선택에 다시 사용하지 않는다.

## 2. 실패 분석

### Test 실패 형태

- 품질 오분류 6건은 모두 실제 `M(상)` 등급이다.
- `M→L` 4건, `M→S` 2건이다.
- 6건 중 4건은 잘못된 예측의 신뢰도가 0.96 이상이다.
- 따라서 신뢰도 임계값 조정만으로는 해결할 수 없다.

### 클래스 불균형은 주원인이 아니다

Test를 제외한 개발 데이터 152그룹의 품질 분포는 `L=41`, `M=63`, `S=48`이다. 실패한 M이 가장 많은 클래스이므로 단순 역빈도 가중치는 M의 영향력을 오히려 낮출 수 있어 이번 개선안에서 제외한다.

### 최종 epoch 선택 오류

v1은 fold별 최고 epoch `20·15·16·19·20`의 중앙값 19를 최종 학습 epoch로 사용했다. 하지만 같은 epoch끼리 비교하면 다음과 같다.

| 공통 epoch | 5-fold 품질 Macro F1 평균 | M Recall 평균 | 두 과제 평균 점수 |
|---:|---:|---:|---:|
| 14 | 0.8251 | 0.8128 | 0.9060 |
| 18 | 0.7984 | 0.8885 | 0.8927 |
| 19 | 0.6735 | 0.7385 | 0.8303 |
| 20 | 0.8616 | 0.8526 | 0.9243 |

서로 다른 fold의 최고 시점을 중앙값으로 합치는 방식은 공통 epoch의 일반화 성능을 보장하지 않았다. fold별 최고 체크포인트를 사후 선택한 CV 0.9809도 작은 validation 세트에서 낙관적으로 추정됐을 가능성이 있다.

### 과적합 가능성

- 개발 그룹은 152개뿐인데 `separate` 모델은 품종·품질용 MobileNetV3 인코더를 각각 학습한다.
- 기존 learning rate `1e-3`, dropout `0.2`, weight decay `1e-4`에서 epoch별 성능 변동이 컸다.
- 다음 실험은 낮은 learning rate와 더 강한 dropout·weight decay를 공통 적용한다.

## 3. 개선 내용

### 데이터 누수 방지

- 기존 Test 27그룹은 모든 v2 실험에서 제외한다.
- 152개 개발 그룹만 5-fold Group CV에 사용한다.
- AI Hub 원본 `Training` 118그룹으로 학습하고 원본 `Validation` 34그룹으로 검증하는 source holdout을 추가한다.
- 기존 Test 결과는 실패 원인 보고에만 사용하고 후보 순위 계산에는 넣지 않는다.

### 학습 안정화

- learning rate: `3e-4`
- dropout: `0.4`
- weight decay: `5e-4`
- 최대 epoch: `25`
- 품종·품질 구조와 12장 입력은 고정하여 손실·정규화 효과만 비교한다.

### 품질 손실 후보

| variant | 품질 손실 | 목적 |
|---|---|---|
| `ce_regularized` | Cross Entropy | 정규화 강화 효과 기준선 |
| `focal_regularized` | Focal Loss, gamma 2.0 | 어렵고 확신이 낮은 경계 표본 집중 |
| `ordinal_regularized` | CE + 순서형 기대값 MSE 0.25 | L-M-S 거리와 중간 등급 경계 반영 |
| `focal_ordinal_regularized` | Focal + 순서형 MSE | 어려운 표본과 등급 순서를 함께 반영 |

L·M·S는 순서가 있으므로 순서형 보조 손실은 `L→S` 같은 먼 오류를 더 크게 벌점 처리한다.

## 4. 실험과 선정 기준

각 variant마다 5-fold CV 5회와 source holdout 1회를 실행하여 총 24회다.

후보 epoch는 fold별 최고값 중앙값이 아니라 모든 fold에 공통으로 존재하는 같은 epoch끼리 비교한다. 다음 조건으로 자동 선정한다.

1. CV 품종 Macro F1 평균 0.95 이상
2. source holdout 품종 Macro F1 0.90 이상
3. `min(CV 품질 최저 fold, source 품질 Macro F1)` 최대화
4. 동률이면 CV 품질 평균, M Recall 최저 fold, 더 이른 epoch 순서

이 방식은 평균이 높아도 한 fold나 원본 Validation에서 무너지는 후보를 제외한다.

## 5. 준비된 파일

- `configs/training-v2-plan.json`: 24회 고정 실행 계획
- `src/training/improvement_experiments.py`: 계획 생성·명시적 실행
- `src/training/improvement_report.py`: Test 미사용 강건성 비교·후보 선정
- `src/training/engine.py`: CE·Focal·순서형·Focal+순서형 손실
- `src/training/train.py`: dropout·손실·source holdout 설정
- `src/training/final_fit.py`: 공통 epoch 평균 점수 기반 최종 epoch 선택

## 6. 실행 전 상태

계획 생성만 완료했으며 v2 학습은 시작하지 않았다. `--execute`를 명시해야만 실제 학습한다.

```powershell
D:\Study\CQC\.venv\Scripts\python.exe -m src.training.improvement_experiments `
  --output outputs\training-v2-plan.json `
  --device cuda `
  --execute
```

기존 RTX 4070 실측을 기준으로 순차 실행은 약 9~12시간으로 예상한다. 학습 완료 후 `src.training.improvement_report`로 후보와 공통 epoch를 선정하되 기존 Test는 다시 평가하지 않는다.

## 7. 다음 승인 조건

v2의 개발 데이터 비교가 좋아도 기존 Test 점수를 새 버전 승인값으로 재사용하지 않는다. 최종 승인을 위해서는 기존 179그룹과 독립된 신규 사과 그룹을 확보하여 새 holdout을 만들어야 한다.
