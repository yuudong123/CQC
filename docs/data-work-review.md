# 조현재 데이터 작업 리뷰 안내

- 작업일: 2026-09-17
- 작업 범위: DM-01 로컬 ZIP·JSON 계약, DM-02 그룹 EDA·품질 검사
- 작업 브랜치: `feat/data`
- 커밋·푸시 상태: 현재 DM-02 변경은 로컬 미커밋

## 1. DM-01에서 한 일

### 데이터 계약 확정

- 원본 이미지 ZIP 12개와 라벨 ZIP 12개를 `원본 분할 × 품종 × 품질` 조합으로 연결했다.
- 품종은 부사(`fuji`, `catecode=060103`)와 양광(`yanggwang`, `catecode=060114`)으로 확정했다.
- 품질은 `L=특`, `M=상`, `S=보통`으로 확정했다.
- 동일 사과 식별자는 JSON의 `group_no`로 확정했다.
- 각도 필드는 `angle_direction`, `verticality_angle`, `horizontality_angle`로 확정했다.
- JSON의 `no`와 `(group_no, img_no)`는 중복되므로 고유키로 사용하지 않게 했다.
- JSON의 `identifier`도 실제 ZIP 멤버명과 다른 값이 있어 이미지 연결 키에서 제외했다.
- 이미지와 JSON은 같은 조합 ZIP 안의 파일명 stem을 대소문자 무시 기준으로 연결한다.

### 매니페스트 생성기

다음 명령으로 원본 ZIP을 풀지 않고 전체 매니페스트와 요약을 만든다.

```powershell
python -m src.data.manifest
```

생성 결과:

- `data/processed/manifest.csv`: 25,024개 프레임의 원본 ZIP·멤버·라벨·각도·그룹 정보
- `data/processed/manifest-summary.json`: 그룹 크기, 스키마 타입, 필드 타입과 중복 후보 요약

## 2. DM-02에서 한 일

### 그룹 EDA 결과

| 품종 | 품질 | 그룹 | 프레임 |
|---|---|---:|---:|
| 부사 | 특 | 24 | 4,170 |
| 부사 | 상 | 24 | 4,170 |
| 부사 | 보통 | 24 | 4,172 |
| 양광 | 특 | 24 | 4,170 |
| 양광 | 상 | 51 | 4,013 |
| 양광 | 보통 | 32 | 4,329 |
| 합계 |  | 179 | 25,024 |

- 원본 Training: 139그룹, 21,896프레임
- 원본 Validation: 40그룹, 3,128프레임
- 40장 이상: 175그룹
- 40장 미만: 4그룹

| `group_no` | 원본 분할 | 품종 | 품질 | 프레임 |
|---|---|---|---|---:|
| `601143027000` | Validation | 양광 | 보통 | 8 |
| `601142038000` | Training | 양광 | 상 | 16 |
| `601142063000` | Validation | 양광 | 상 | 21 |
| `601143037000` | Validation | 양광 | 보통 | 30 |

이 네 그룹은 삭제하지 않고 대표 프레임 균등 선택과 누락 뷰 마스킹 대상으로 유지한다.

### 무결성 검사 결과

다음 명령은 모든 이미지 데이터를 끝까지 읽으며 PNG 청크 CRC, ZIP 멤버 CRC와 SHA-256을 검사한다.

```powershell
python -m src.data.image_quality
```

- 전체 검사: 25,024장
- 정상: 25,024장
- 손상: 0장
- 이미지·라벨 파일명 짝 누락: 0건
- PNG와 JSON 해상도 불일치: 0건
- SHA-256 완전 중복: 5쌍, 10장

완전 중복 5쌍은 같은 `group_no` 안의 인접 프레임이지만 서로 다른 각도 라벨을 가진다. 자동 삭제하지 않고 DM-02 중복 후보로 보존한다.

| 그룹 | 중복 파일 stem | 각도 차이 |
|---|---|---|
| `601032003000` | `apple_fuji_M_3-27`, `apple_fuji_M_3-28` | 수직 30° / 45° |
| `601143003000` | `apple_yanggwang_S_3-41`, `apple_yanggwang_S_3-42` | 수직 240° / 255° |
| `601143003000` | `apple_yanggwang_S_3-45`, `apple_yanggwang_S_3-46` | 수직 300° / 315° |
| `601143004000` | `apple_yanggwang_S_4-85`, `apple_yanggwang_S_4-86` | 수직 180° / 195° |
| `601032026000` | `apple_fuji_M_26-140`, `apple_fuji_M_26-141` | 수직 285° / 300° |

## 3. 리뷰할 파일

권장 순서는 다음과 같다.

1. `docs/data-work-review.md`
   - DM-01·DM-02 결과와 남은 판단 사항을 빠르게 확인한다.
2. `docs/data-spec.md`
   - 확정된 JSON 필드, 라벨 매핑, 매니페스트 계약을 확인한다.
3. `src/data/manifest.py`
   - ZIP 탐색, 이미지·라벨 연결, 라벨 검증, 매니페스트 생성 로직을 리뷰한다.
4. `src/data/image_quality.py`
   - 전체 PNG·ZIP CRC와 SHA-256 검사 로직을 리뷰한다.
5. `tests/test_manifest.py`, `tests/test_image_quality.py`
   - 계약 위반, 누락 파일, 해상도 불일치와 PNG 손상을 거부하는 테스트를 확인한다.
6. `data/processed/manifest-summary.json`
   - 실제 전체 데이터의 그룹·스키마·필드 타입 통계를 확인한다.
7. `data/processed/image-quality-report.json`
   - 손상 목록과 SHA-256 중복 5쌍의 정확한 식별자를 확인한다.

`data/processed/` 결과는 원본 경로를 포함하는 생성물이므로 Git에 올리지 않는다. 같은 원본 ZIP에서 위 명령으로 재생성한다.

## 4. 리뷰 시 결정할 사항

- SHA-256 완전 중복 5쌍에서 한 장씩 제외할지, 각도 라벨 오류 사례로 별도 보관할지 결정
- DM-03 분할 전에 6개 품종×품질 조합의 그룹 수 차이를 그대로 층화할지 확인
- 40장 미만 4그룹의 누락 뷰 마스크 표현 형식 확정
- 원본 Training·Validation은 합친 뒤 seed 42의 70/15/15 그룹 분할로 다시 생성
