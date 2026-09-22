# 가상 당도(SSC, °Brix) 생성·모델 연동 계획

## 1. 결론

현재 AI Hub 데이터에는 사과별 실측 당도 정답이 없다. 따라서 RGB 이미지에서 만든 값은 **실측 당도**나 **당도 예측값**이 아니라 발표용 **가상 당도(`virtual_brix`)**로 명시한다.

가상 값을 데이터셋에 한 번 생성해 고정하고 품질 분류 실험에 추가하는 것은 가능하다. 다만 가상 당도 역시 같은 이미지에서 계산되므로 새로운 센서 정보가 생기는 것은 아니다. 이 값을 사용해 품질 성능이 올라도 실제 당도 측정 능력이 검증된 것으로 해석하지 않는다.

## 2. 조사 근거와 해석

| 근거 | 결과 | 이 프로젝트의 해석 |
|---|---|---|
| Ku, Kim, Jeong (2019), 부사 420개 | 과피 적색도 `a*`와 SSC 상관 `r=0.626` | 중간 정도 양의 상관이다. `r`을 62.6% 설명력으로 읽으면 안 되며 단순 환산 `R²`는 약 0.392다. |
| Kim (2022), 동일 지역 사과 RGB·HSV·Lab 분석 | 평균 Lab 색상과 당도 `r=0.342`, 복합 색상 `R²=0.3627`, 9개 색상 공간 `R²=0.3668` | 일반 RGB 촬영에서 색만으로 당도를 설명하는 힘은 제한적이다. |
| Kim et al. (2023), 국내 품종 실측 | 양광 `13.37±0.65 °Brix`, 부사 `14.24±0.67 °Brix` | 품종별 분포를 가상 값의 범위 점검에만 사용한다. 정답 품종을 생성 입력으로 쓰면 누수가 생길 수 있다. |
| 국내 주산지 부사 3년 조사 | 평균 `14.81 °Brix`, 표준편차 `1.78 °Brix` | 재배지·연도에 따른 분산이 커 단일 고정값이 부적절하다. |
| Wang et al. (2025), 과점과 HSI | 과점 영역이 분광 SSC 모델의 강건성과 정확도에 영향을 줌, 사과 예측 `R²=0.808` | 과점은 분광 신호에 영향을 주지만 “과점이 많을수록 당도가 높다”는 증거는 아니다. RGB 생성식에서는 약한 보조·불확실성 특징으로만 사용한다. |
| 사과·배 러셋 표면 연구 | 러셋은 거칠고 갈색인 표면 장애이며 표면 거칠기가 약 2.5배 증가 | “거칠수록 달다”는 일반 규칙으로 사용하지 않는다. 거칠기·광택은 촬영과 표면 상태에 민감한 보조 특징이다. |
| Hyperspectral bi-layer SSC 연구 | 예측 상관 `r=0.9560`, RMSEP `0.2528` | RGB 성능 근거가 아니다. 실제 비파괴 당도화를 원하면 NIR/HSI 또는 실측 굴절계 라벨이 필요하다. |

따라서 문서와 발표에서는 **“색상과 당도 사이에 조건부 상관이 보고되었으며, 부사 연구에서 `r=0.626`이 관찰됐다”**고 표현한다. **“외관이 당도를 60% 결정한다”**, **“현재 분류모델이 당도를 판정한다”**고 표현하지 않는다.

## 3. MVP 가상 당도 생성기

### 3.1 입력 단위

- `1 apple = 1 group_no`
- train/validation/test 분할을 먼저 고정한 후 그룹별 값 생성
- 특징 표준화 계수는 Test를 제외한 개발 세트에서만 계산하고 Test에는 그대로 적용
- 동일 사과의 대표 12장 전체에서 특징을 집계
- 정답 품종, 정답 품질 등급, split 이름은 생성식 입력에서 제외

### 3.2 RGB 특징

1. 사과 마스크 내부 CIELAB `a*`, `b*`의 평균·표준편차
2. 붉은 영역 비율과 뷰 사이 붉은색 균일도
3. 하이라이트 면적 비율과 국소 명암 분산을 이용한 광택·거칠기 대리값
4. 과점 후보 개수를 사과 마스크 면적으로 정규화한 값
5. 뷰 사이 특징 편차와 유효 뷰 수

색상 특징을 주 신호로 사용한다. 광택·거칠기·과점은 양의 당도 규칙으로 고정하지 않고 작은 가중치 또는 불확실성 증가에만 사용한다.

### 3.3 생성 방식

학습 정답이 없으므로 신경망 생성기를 학습하지 않는다. 재현 가능한 확률식이 더 정직하고 검증 가능하다.

```text
visual_score = 표준화된 색상·균일도 특징의 가중합
z_brix = r_target × visual_score + sqrt(1-r_target²) × seeded_noise
virtual_brix = clip(mu + sigma × z_brix, 9.0, 18.0)
```

- 기본 `r_target=0.34`: 일반 RGB 연구의 관찰값을 보수적으로 사용
- 민감도 실험: `r_target=0.00`, `0.34`, `0.63`
- `mu=14.0`, `sigma=1.5`: 국내 부사·양광 실측 범위를 포괄하는 초기값
- 범위: `9.0~18.0 °Brix`, 저장 정밀도 `0.1 °Brix`
- 잡음 seed: `SHA-256(group_no + generator_version)`에서 생성하여 매번 동일한 값 보장
- 생성기 버전과 특징값을 함께 저장하여 재생성 가능하게 유지

`r_target=0.63`은 부사 단일 품종의 적색도 연구를 흉내 내는 상한 시나리오일 뿐 전체 데이터의 사실값으로 사용하지 않는다.

## 4. 데이터 필드

`data/processed/virtual-brix.csv`를 별도 생성하고 기존 원본 매니페스트는 변경하지 않는다.

| 필드 | 의미 |
|---|---|
| `group_no` | 사과 그룹 키 |
| `virtual_brix` | 생성된 가상 °Brix |
| `brix_source` | 항상 `simulated_rgb_proxy` |
| `brix_generator_version` | 생성 규칙 버전 |
| `brix_target_correlation` | 사용한 `r_target` |
| `brix_uncertainty` | 뷰 편차·마스크 품질 기반 불확실성 |
| `feature_*` | 색상·균일도·광택·과점 대리 특징 |

API와 화면에는 `virtual_brix`, `brix_source`, `brix_is_measured=false`를 함께 노출한다.

## 5. 분류모델 변경

### 5.1 비교 모델

- A: 기존 이미지 전용 품종·품질 분류모델
- B: 이미지 그룹 특징에 `virtual_brix`와 불확실성을 이어 붙이는 late-fusion 모델
- C: 이미지 모델에 가상 Brix 회귀 보조 헤드를 추가한 멀티태스크 모델

발표용 기본안은 B다. 가상 센서값을 명시적으로 입력받으므로 “촬영 후 가상 당도 측정 → 품질 판정” 흐름을 설명하기 쉽다. A와 B를 같은 그룹 분할에서 비교하되 B의 성능 향상은 실제 당도 측정 성능으로 주장하지 않는다. C는 생성값을 다시 예측하는 순환 학습이라 우선순위가 낮다.

### 5.2 누수 방지

- 품질 등급을 이용해 가상 Brix를 생성하지 않는다.
- 정답 품종을 생성식 입력으로 사용하지 않는다.
- `group_no`는 seed와 조인 키로만 사용하고 모델 입력에 넣지 않는다.
- 가상 Brix가 포함된 상태에서도 기존 group 단위 split을 유지한다.
- 최종 Test는 생성식·가중치·임계값 결정에 사용하지 않는다.

## 6. 실제 당도 모델로 전환하는 조건

실제 당도 예측을 주장하려면 같은 사과에 대해 다각도 이미지와 굴절당도계 측정값을 쌍으로 수집해야 한다.

1. 부사·양광, 농가·수확일·저장조건을 나누어 최소 수백 개 사과 수집
2. 사과별 대표 주스의 °Brix를 교정된 굴절당도계로 측정
3. 사과 단위로 train/validation/test 분할
4. 이미지 특징 또는 Vis/NIR 스펙트럼으로 회귀모델 학습
5. Test에서 MAE, RMSE, `R²`, bias와 품종별 오차 공개
6. RGB-only와 NIR/HSI 또는 실제 센서 결합 모델 비교

실측 라벨이 확보되면 `virtual_brix`는 폐기하고 `measured_brix`를 정답으로 사용하는 별도 회귀 헤드 또는 센서 융합 모델로 교체한다.

## 7. 출처

- Ku, K. H., Kim, H. J., & Jeong, M. C. (2019). *Relationship between quality characteristics and skin color of ‘Fuji’ Apples*. Journal of Food Measurement and Characterization, 13, 1935–1946. https://doi.org/10.1007/s11694-019-00112-9
- 김선종 (2022). *선형회귀를 이용한 사과의 색상과 당도 분석*. 문화기술의 융합, 8(1), 201–207. https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART002808457
- Kim, K. et al. (2023). *Relationships between sensory properties and metabolomic profiles of different apple cultivars*. Food Chemistry: X, 18, 100641. https://doi.org/10.1016/j.fochx.2023.100641
- *주산지 후지 사과의 내·외부 품질 특성*. https://www.kci.go.kr/kciportal/landing/article.kci?arti_id=ART000995089
- Wang, Z. et al. (2025). *Exploring the impact of lenticels on the detection of soluble solids content in apples and pears using hyperspectral imaging and one-dimensional convolutional neural networks*. Food Research International, 115960. https://doi.org/10.1016/j.foodres.2025.115960
- *Non-Invasive Examination of Plant Surfaces by Opto-Electronic Means—Using Russet as a Prime Example*. https://pmc.ncbi.nlm.nih.gov/articles/PMC4850966/
- *A bi-layer model for nondestructive prediction of soluble solids content in apple based on reflectance spectra and peel pigments*. https://doi.org/10.1016/j.foodchem.2017.07.106
