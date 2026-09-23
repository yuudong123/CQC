# 학습 코드 안내

## 가상 당도 시연 실험

가상 당도는 RGB 이미지에서 생성한 시연값이며 실측값이 아니다. 원본 매니페스트는 수정하지 않는다.

```powershell
python -m src.data.virtual_brix
python -m src.training.brix_experiments
```

두 명령은 각각 가상 당도 CSV와 실행 전 48개 비교 계획만 만든다. 학습은 시작하지 않는다. 계획은 `separate`와 `separate_brix`에 대해 동일한 4개 손실 설정 × (5-fold CV + 원본 source holdout)를 구성하며 입력은 모두 대표 12장이다.

계획을 확인한 뒤 실제 학습과 결과 비교는 다음처럼 실행한다.

```powershell
python -m src.training.brix_experiments --device cuda --execute
python -m src.training.brix_report
```

중단 후 같은 명령을 다시 실행하면 `summary.json` 기준 완료된 run은 건너뛴다. 처음부터 다시 돌릴 때만 `--rerun-completed`를 붙인다.

비교 기준선은 같은 분할·설정의 `separate` 결과다. Test는 모델 선택에 사용하지 않는다. 결합 모델의 개선을 실제 당도 측정 성능으로 해석하지 않는다.

AI Hub `전북 장수 사과 당도 품질 데이터`는 RGB 이미지와 착즙/NIR 당도 필드를 가진 별도 후보지만, 현재 저장소에는 원본 파일이 없다. 따라서 이번 코드는 그 데이터로 실제 Brix 회귀를 학습하는 코드가 아니라 현재 데이터의 RGB 프록시 결합 실험이다.

학습·비교·평가 코드는 이 폴더에 모아 둔다. 데이터 로더와 공통 모델 본체는 각각 `src/data`, `src/models`의 기존 구현을 가져와 사용한다.

## 파일

| 파일 | 역할 |
|---|---|
| `train.py` | 4·8·12·16·40장, joint·separate·가상 당도 late-fusion 모델의 단일 fold 학습 |
| `engine.py` | 학습·평가 epoch, Accuracy·Macro F1·혼동행렬, 체크포인트 저장 |
| `models.py` | 공유 인코더 joint 모델과 과제별 독립 인코더 separate 모델 생성 |
| `brix_experiments.py` | 대표 12장 이미지 단독·가상 당도 late-fusion 개발 실험 48개 계획·실행 |
| `brix_report.py` | 동일 epoch의 CV 최저점·source holdout으로 두 모델 비교 |
| `experiments.py` | 2개 모델 × 5개 입력 장수 × 5-fold, 총 50개 비교 계획 생성 |
| `audit.py` | 50개 실험의 파일 누락·epoch 수·설정·체크포인트 SHA-256 검사 |
| `summarize.py` | 완료된 fold의 최고 epoch와 평균·표준편차 집계 |
| `benchmark.py` | Test를 사용하지 않는 CPU·GPU 평균·최대·p95 추론시간 측정 |
| `benchmark_concurrency.py` | 순차·병렬 처리의 p95·처리량과 500ms·초당 2건 충족 여부 비교 |
| `evaluate.py` | 최종 선정 체크포인트의 고정 Test 1회 평가 |
| `model_card.py` | 패키지·CV·Test·임계값·CPU 측정 산출물로 최종 모델 카드 생성 |
| `report.py` | 전체 50개 결과 비교표·차트와 정확도 기준 임시 후보 생성 |
| `package_model.py` | 승인 체크포인트와 클래스·전처리·신뢰도 기준·SHA-256 패키징 |
| `export_predictions.py` | validation fold 그룹별 확률·정답 CSV 생성 |
| `thresholds.py` | 품종·품질 신뢰도 기준 후보 탐색 |
| `final_fit.py` | 공통 epoch의 CV 평균 점수로 시점을 정해 Test 제외 전체 개발 데이터를 최종 학습 |
| `run_final_fit.ps1` | 원격 Windows 예약 작업에서 최종 학습을 실행하고 로그 분리 저장 |
| `improvement_experiments.py` | 품질 v2 손실·정규화 4종의 5-fold·source holdout 24회 계획 |
| `improvement_report.py` | 공통 epoch의 CV 최저 fold·source holdout을 함께 비교해 강건 후보 선정 |
| `run_improvement_v2.ps1` | 원격 Windows 예약 작업에서 v2 24회 실험을 실행하고 로그 저장 |
| `run_i7_4790_acceptance.ps1` | 목표 CPU·RAM을 확인한 뒤 지연시간·처리량 수용시험 실행 |
| `acceptance_cpu.py` | 학원 Linux Jenkins의 Docker에서 v2 패키지 해시·CPU·RAM 확인 후 합성 입력 모델 단독 수용시험 |
| `../../data/sampling/experiments.py` | v2 미달 시 선정 설정을 유지하고 각도 균형 랜덤 12장으로 6회 후속 비교 |

## 안전 장치

- `python -m src.training.experiments`는 계획 JSON만 만들며 학습하지 않는다.
- 전체 학습은 `--execute`를 명시한 경우에만 시작한다.
- 최종 Test 평가는 `--confirm-final-test RUN_FINAL_TEST_ONCE`가 없으면 거부한다.
- 최종 Test를 시도하면 체크포인트 옆에 잠금 표식을 남기고 같은 체크포인트의 재실행을 거부한다.
- `final_fit.py`는 기본적으로 계획만 만들며 `--execute`를 명시해야 학습한다.
- 최종 학습 epoch는 모든 fold의 같은 epoch끼리 평균한 validation score가 가장 높은 시점으로 결정한다. fold별 최고 epoch 중앙값은 사용하지 않는다.
- 품질 v2 실험도 기본적으로 JSON 계획만 만들며 `--execute`를 명시해야 시작한다.
- 품질 v2 선택에는 고정 Test를 사용하지 않고 5-fold와 AI Hub 원본 Validation 홀드아웃만 사용한다.
- 40장 입력은 기본 batch size를 1로 낮춘다.
- 모든 학습 산출물은 Git 제외 경로인 `outputs/training/` 아래에 저장한다.

## 준비된 비교 범위

- 모델: `joint`, `separate`
- 입력 장수: `4`, `8`, `12`, `16`, `40`
- 교차검증: fold `0`~`4`
- 기본 epoch: `20`
- 기본 seed: `42`
- 기본 입력 해상도: `224×224`

실제 학습은 실행 전 사용자 확인을 받은 뒤 진행한다.
