# [DM-09] 최종 Test 1회·모델 카드

## 목적

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

운영 기본값은 동시 처리 1이다. 목표 i7-4790 장비가 없어 위 값은 예비 결과이며 NFR-07 승인값이 아니다.

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
