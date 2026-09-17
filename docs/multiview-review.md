# DM-04 다각도 로더 리뷰

- 작업일: 2026-09-17
- 작업 브랜치: `feat/data`
- 지원 입력 장수: 4·8·12·16·40장
- 검사 단위: `group_no` 하나

## 선택 규칙

1. 그룹 프레임을 `angle_direction → horizontality_angle → verticality_angle → sample_id` 순으로 정렬한다.
2. 첫 프레임과 마지막 프레임을 포함하도록 전체 순서에서 균등 간격 인덱스를 선택한다.
3. 그룹 프레임이 목표 장수보다 적으면 보유 프레임을 전부 사용한다.
4. 부족한 위치는 오른쪽에 `None`으로 채우고 `view_mask=False`를 반환한다.
5. 동일 입력과 설정에서는 매니페스트 행 순서와 무관하게 같은 프레임을 선택한다.

선택과 마스킹은 학습·검증·Test·서비스 추론에서 같은 함수를 사용한다.

## 전체 그룹 검증 결과

| 목표 장수 | 전체 그룹 | 패딩 그룹 | 패딩 슬롯 | 실제 프레임 분포 |
|---:|---:|---:|---:|---|
| 4 | 179 | 0 | 0 | 4장 × 179그룹 |
| 8 | 179 | 0 | 0 | 8장 × 179그룹 |
| 12 | 179 | 1 | 4 | 8장 × 1, 12장 × 178 |
| 16 | 179 | 1 | 8 | 8장 × 1, 16장 × 178 |
| 40 | 179 | 4 | 85 | 8·16·21·30장 각 1, 40장 × 175 |

40장 설정의 부족 슬롯은 `32 + 24 + 19 + 10 = 85`개다.

## 로더 반환값

`MultiViewDataset[index]`는 사과 하나에 대해 다음 값을 반환한다.

- `group_no`
- `cultivar`, `cultivar_index`
- `quality_grade`, `quality_index`
- `split`, `cv_fold`
- `images`: ZIP에서 지연 로딩한 이미지 bytes 또는 패딩 `None`
- `view_mask`: 실제 이미지 여부
- `angles`: 각 프레임의 방향·수직각·수평각
- `sample_ids`: 원본 프레임 추적 ID

이미지 디코딩과 텐서 변환은 최종 학습 프레임워크를 정하는 DM-05에서 연결한다. 프레임 선택·마스크 계약은 프레임워크와 무관하게 유지한다.

## Test 누수 방지

- 고정 분할 로딩은 `split=train|validation|test`로 선택한다.
- 5-Fold CV는 고정 Train·Validation 152그룹만 사용한다.
- `cv_role=train`은 선택한 fold를 제외한다.
- `cv_role=validation`은 선택한 fold만 사용한다.
- 최종 Test 그룹은 어떤 CV 역할에도 포함하지 않는다.
- `split` 필터와 `cv_role`은 동시에 사용할 수 없게 차단했다.

## 실행과 리뷰 파일

```powershell
python -m src.data.multiview --smoke-load
```

1. `src/data/multiview.py`
   - 프레임 정렬·선택·마스크와 ZIP 지연 로더
2. `tests/test_multiview.py`
   - 균등 선택, 짧은 그룹, 순서 독립성과 Test 누수 방지 테스트
3. `configs/view-selection-summary.json`
   - 179그룹 × 5개 입력 장수의 실제 패딩 결과
4. `configs/splits/seed-42.csv`
   - 로더가 사용하는 고정 그룹 분할과 CV fold

## 다음 단계

- DM-05에서 이미지 디코더·리사이즈·정규화·증강을 연결한다.
- 공유 특징 추출기와 그룹 결합 계층의 첫 기준선을 만든다.
- 품종·품질 멀티태스크 출력과 분리 모델 비교 기반을 준비한다.
