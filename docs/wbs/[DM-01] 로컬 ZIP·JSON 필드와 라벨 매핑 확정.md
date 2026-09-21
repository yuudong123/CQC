# [DM-01] 로컬 ZIP·JSON 필드와 라벨 매핑 확정

## 1. 작업 목적

AI Hub 사과 데이터의 실제 ZIP·JSON 구조를 코드로 확인하고, 이후 EDA·분할·학습·추론에서 공통으로 사용할 라벨과 샘플 식별 규칙을 확정하는 작업이다.

기획 문서에 적힌 필드 후보만 믿고 구현하면 실제 파일명이나 타입 차이 때문에 데이터가 잘못 연결될 수 있다. 따라서 원본 ZIP을 직접 읽어 모든 JSON을 검사하고 재현 가능한 프레임 매니페스트를 생성하도록 했다.

## 2. 확인한 원본 데이터

| 항목 | 결과 |
|---|---:|
| 이미지 ZIP | 12개 |
| 라벨 ZIP | 12개 |
| 이미지·JSON 쌍 | 25,024개 |
| Training | 21,896개·139그룹 |
| Validation | 3,128개·40그룹 |
| 전체 `group_no` | 179개 |

확정한 라벨은 다음과 같다.

| 구분 | 코드 | 의미 | 실제 JSON |
|---|---|---|---|
| 품목 | `apple` | 사과 | `cate1=사과` |
| 품종 | `fuji` | 부사 | `cate2=부사`, `catecode=060103` |
| 품종 | `yanggwang` | 양광 | `cate2=양광`, `catecode=060114` |
| 품질 | `L` | 특 | `cate3=특` |
| 품질 | `M` | 상 | `cate3=상` |
| 품질 | `S` | 보통 | `cate3=보통` |

동일 사과의 다각도 프레임 묶음은 JSON의 `group_no`로 식별한다. 촬영 방향과 각도는 `angle_direction`, `verticality_angle`, `horizontality_angle`을 사용한다.

## 3. 구현 내용

`src/data/manifest.py`에 다음 기능을 구현했다.

1. `Training/Validation × 부사/양광 × L/M/S`의 12개 조합을 찾는다.
2. 각 조합의 이미지 ZIP과 라벨 ZIP을 연결한다.
3. 전체 JSON을 UTF-8로 읽고 필수 필드를 검증한다.
4. ZIP명과 `catecode`·`cate1`·`cate2`·`cate3`가 일치하는지 확인한다.
5. 이미지와 JSON 멤버를 확장자를 제외한 파일명 stem으로 연결한다.
6. PNG 헤더 해상도와 JSON의 `img_width`·`img_height`를 비교한다.
7. 프레임 단위 CSV와 데이터 구조 요약 JSON을 생성한다.

실행 명령:

```powershell
python -m src.data.manifest
```

생성 결과:

- `data/processed/manifest.csv`
- `data/processed/manifest-summary.json`

두 파일은 원본에서 재생성할 수 있는 산출물이므로 Git에서 제외한다.

## 4. 주요 설계 결정과 이유

### ZIP을 풀지 않고 직접 읽는다

원본 ZIP 전체 크기가 약 27.9GB이므로 압축을 풀면 저장공간을 추가로 사용하고 원본·가공 파일의 경계도 흐려진다. 매니페스트에는 ZIP 상대 경로와 내부 멤버명을 기록하고, 실제 이미지가 필요할 때만 해당 멤버를 읽게 했다.

### `no`와 `img_no`를 고유키로 사용하지 않는다

- `no` 중복 값: 4,532개
- `(group_no, img_no)` 중복 조합: 5,072개
- 두 필드는 정수와 문자열 타입도 섞여 있다.

따라서 내부 `sample_id`는 `원본 분할:품종:품질:파일명 stem` 형식으로 생성한다.

### JSON `identifier`로 이미지를 연결하지 않는다

일부 `identifier`에는 실제 ZIP 멤버명과 다른 한글 경로가 들어 있다. 이미지·라벨 연결은 같은 조합 ZIP의 파일명 stem을 대소문자 무시 기준으로 수행한다.

### 클래스 순서를 코드로 고정한다

- 품종: `fuji`, `yanggwang`
- 품질: `L`, `M`, `S`

Backend가 모델 클래스 순서를 추정하지 않도록 이후 모델 산출물과 Inference 응답에도 이 매핑을 명시한다.

## 5. 수정·생성 파일

- `src/data/manifest.py`: ZIP 탐색, JSON 검증과 매니페스트 생성
- `tests/test_manifest.py`: ZIP 조합·라벨·파일 짝·해상도 오류 테스트
- `docs/data-spec.md`: 실제 필드와 라벨 매핑 반영
- `docs/model-stack.md`: 데이터 생성 명령과 현재 상태

관련 커밋:

- `07c66ae 데이터 매니페스트 생성 기반 구축`

## 6. 다른 파트에 전달할 계약

- 한 번의 검사 단위는 `group_no` 하나인 사과 한 개다.
- 정답 품종·품질이나 `group_no`는 모델 입력 특징으로 사용하지 않는다.
- Inference는 품종과 품질을 모두 예측한다.
- 품종 확률 키는 `fuji`, `yanggwang`이다.
- 품질 확률 키는 `L`, `M`, `S`다.
- 원본 데이터 위치나 파일명 규칙을 Backend와 Frontend가 직접 해석하지 않는다.

## 7. 검증 결과

- 12개 이미지 ZIP과 12개 라벨 ZIP 조합 확인
- 이미지·라벨 파일명 짝 누락 0건
- ZIP명과 JSON 라벨 불일치 0건
- PNG·JSON 해상도 불일치 0건
- 매니페스트 25,024행 생성
- 그룹 179개 확인

## 8. 발표용 요약

“AI Hub 설명서만 사용하지 않고 실제 ZIP 24개와 JSON 25,024개를 전수 검사했습니다. 중복되는 원본 번호 대신 ZIP 멤버 파일명으로 안정적인 샘플 ID를 만들고, 동일 사과의 다각도 이미지는 `group_no`로 묶는 데이터 계약을 확정했습니다.”
