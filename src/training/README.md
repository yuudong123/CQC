# 학습 코드 안내

학습·비교·평가 코드는 이 폴더에 모아 둔다. 데이터 로더와 공통 모델 본체는 각각 `src/data`, `src/models`의 기존 구현을 가져와 사용한다.

## 파일

| 파일 | 역할 |
|---|---|
| `train.py` | 4·8·12·16·40장, joint·separate 모델의 단일 fold 학습 |
| `engine.py` | 학습·평가 epoch, Accuracy·Macro F1·혼동행렬, 체크포인트 저장 |
| `models.py` | 공유 인코더 joint 모델과 과제별 독립 인코더 separate 모델 생성 |
| `experiments.py` | 2개 모델 × 5개 입력 장수 × 5-fold, 총 50개 비교 계획 생성 |
| `summarize.py` | 완료된 fold의 최고 epoch와 평균·표준편차 집계 |
| `benchmark.py` | Test를 사용하지 않는 CPU·GPU 평균·최대·p95 추론시간 측정 |
| `benchmark_concurrency.py` | 순차·병렬 처리의 p95·처리량과 500ms·초당 2건 충족 여부 비교 |
| `evaluate.py` | 최종 선정 체크포인트의 고정 Test 1회 평가 |
| `report.py` | 전체 50개 결과 비교표·차트와 정확도 기준 임시 후보 생성 |
| `package_model.py` | 승인 체크포인트와 불변 메타데이터·SHA-256 패키징 |
| `export_predictions.py` | validation fold 그룹별 확률·정답 CSV 생성 |
| `thresholds.py` | 품종·품질 신뢰도 기준 후보 탐색 |

## 안전 장치

- `python -m src.training.experiments`는 계획 JSON만 만들며 학습하지 않는다.
- 전체 학습은 `--execute`를 명시한 경우에만 시작한다.
- 최종 Test 평가는 `--confirm-final-test RUN_FINAL_TEST_ONCE`가 없으면 거부한다.
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
