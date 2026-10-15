# CQC 테이블·데이터 명세서

## 1. 문서 범위

이 문서는 학습 데이터, 가공 데이터, 모델 출력과 MySQL 저장 요구사항을 정의한다. 실제 AI Hub 파일의 정확한 필드명과 MySQL 물리 구조는 담당자의 확인 문서에서 확정한다.

| 영역 | 담당 | 현재 상태 |
|---|---|---|
| AI Hub 원본·라벨 분석 | 조현재 | ZIP·JSON 필드와 라벨 매핑 확인 완료 |
| 가공 데이터와 분할 | 조현재 | 논리 필드 정의 완료 |
| 모델 출력 계약 | 조현재·홍준희 | `/v1/predict` 요청·응답과 OpenAPI 확정 |
| MySQL 물리 설계 | 홍준희 | 별도 DB 설계 문서 TODO |
| 이력·통계 화면 요구 | 강성민·홍준희 | 조회 차원 정의 완료 |

## 2. 데이터 출처

- 데이터셋: AI Hub 농산물 품질(QC) 이미지
- 형식: PNG 이미지와 라벨·메타데이터
- 공식 전체 규모: 정제 데이터 30만 건
- 공식 품목: 무, 배추, 양파, 마늘, 양배추, 감, 사과, 배, 감귤, 감자
- 공식 품질 등급: 특, 상, 보통
- 현재 프로젝트 보유 범위: 사과 이미지
- MVP: 사과 품종 2종
- 두 번째 품목: M5 결정 전까지 미정

### 2.1 로컬 보유 데이터 확인 결과

- 위치: `data/raw/068.농산물 품질(QC) 이미지/01.데이터/`
- 제공 분할: `1.Training`, `2.Validation`
- 품종: 부사(`fuji`), 양광(`yanggwang`)
- 품질: `L=특`, `M=상`, `S=보통`
- Training: 이미지·JSON 21,896쌍, `group_no` 139개
- Validation: 이미지·JSON 3,128쌍, `group_no` 40개
- 전체: 이미지·JSON 25,024쌍
- 별도 Test 폴더: 없음
- 이미지 ZIP 12개와 라벨 ZIP 12개를 조합별로 대조한 결과 파일명 짝 누락 0건

각 `group_no`에는 동일 사과를 여러 각도에서 촬영한 이미지가 묶여 있으며 다수 그룹은 184장이다. 학습·평가·추론의 기본 단위는 개별 이미지가 아니라 `group_no`로 식별한 사과 한 개다.

JSON의 `no`는 4,532개 값이 중복되고 `(group_no, img_no)`도 5,072개 조합이 중복된다. 따라서 두 필드는 샘플 고유키로 사용하지 않는다. 이미지와 라벨은 같은 조합 ZIP 안에서 **확장자를 제외한 파일명**을 대소문자 무시 기준으로 연결하고, 내부 `sample_id`는 `원본 분할:품종:품질:파일명 stem`으로 만든다. JSON의 `identifier`는 일부 값이 실제 ZIP 멤버 경로와 다르므로 연결 키로 사용하지 않는다.

### 2.2 다각도 프레임 가용성

| 구분 | 전체 그룹 | 40장 이상 | 40장 미만 |
|---|---:|---:|---:|
| Training | 139 | 138 | 1 |
| Validation | 40 | 37 | 3 |
| 합계 | 179 | 175 | 4 |

40장 미만 그룹의 장수는 8, 16, 21, 30장이다. 원본 PNG는 1000×1000이며 평균 파일 크기는 약 1.17MB다. 40장을 비압축 RGB로 디코딩하면 사과당 약 114.4MB다. 초당 사과 2개를 모두 40장으로 처리하면 초당 약 228.9MB의 디코딩 이미지가 생성되므로 CPU 추론·메모리 복사·HTTP 전달 비용을 함께 시험해야 한다.

출처: <https://aihub.or.kr/aihubdata/data/view.do?aihubDataSe=data&dataSetSn=149&topMenu=103>

## 3. 원본 데이터 보존 규칙

- 다운로드한 원본은 `data/raw/`에 저장하고 직접 수정하지 않는다.
- 원본 이미지와 라벨은 Git에 커밋하지 않는다.
- 원본 파일의 상대 경로와 해시를 기록하여 누락·중복을 검사한다.
- 정제·변환한 파일은 `data/processed/`에 저장한다.
- 제외한 샘플은 삭제 이유와 함께 별도 목록으로 남긴다.
- 데이터 이용조건과 배포 가능 범위를 확인한 뒤 팀 외부 공유 여부를 결정한다.

## 4. AI Hub 원본 라벨 후보

전체 JSON 25,024개를 읽어 확인한 실제 매핑이다. JSON은 UTF-8이며 BOM 유무를 허용한다.

| 논리 항목 | 공식 설명 | 필수 여부 | 프로젝트 사용 | 실제 매핑 |
|---|---|---|---|---|
| sample_id | 내부 샘플 키 | Y | 프레임 고유 식별 | 원본 분할·ZIP명·멤버 파일명으로 생성 |
| group_id | 동일 사과 묶음 | Y | 그룹 분할·추론 단위 | `group_no` 정수, 문자열로 정규화 |
| identifier | 제공 파일명 | Y | 원본 추적 보조 | `identifier` 문자열, 연결 키로 사용 금지 |
| image_size | 압축 전 이미지 바이트 | Y | 파일 검사 | 이미지 ZIP 멤버의 `file_size` |
| image_crc32 | ZIP 멤버 CRC32 | Y | 빠른 무결성 확인 | 이미지 ZIP 멤버의 `CRC` |
| resolution | 픽셀 수 | Y | 품질 검사 | `resolution` 정수 |
| date | 취득 일시 | Y | 그룹·편향 분석 후보 | `date` 문자열 |
| species_id | 품종 코드 | Y | 품종 검증 | `catecode`: 부사 `060103`, 양광 `060114` |
| crop_type | 품목 | Y | 품목 필터 | `cate1`: `사과` |
| cultivar | 품종 | Y | 품종 정답 | `cate2`: `부사`, `양광` |
| quality_grade | 품질 등급 | Y | 품질 정답 | `cate3`: `특`, `상`, `보통` |
| captured_side | 촬영면 | Y | 그룹·성능 분석 | `angle_direction`: `top`, `bottom` |
| vertical_angle | 수직 촬영각도 | Y | 대표 프레임 선택 | `verticality_angle` 정수 |
| horizontal_angle | 수평 촬영각도 | Y | 대표 프레임 선택 | `horizontality_angle` 정수 |
| height | 품목 높이 | Y | 메타데이터 분석 후보 | `height` 숫자 문자열 |
| width | 품목 너비 | Y | 메타데이터 분석 후보 | `width` 숫자 문자열 |
| weight | 품목 무게 | Y | 메타데이터 분석 후보 | `weight` 숫자 문자열 |
| box_coordinates | 객체 좌표 | Y | 객체 영역 확인 후보 | `bndbox.{xmin,ymin,xmax,ymax}` 정수 |

JSON 스키마는 두 종류다. 18,156개는 기본 촬영 필드만 있고, 6,868개는 `camera_model`과 `camera_software`가 추가된다. `f_stop`, `exposure_time`, `iso`, `focal_length`, `full_aperture`, `white_balance`는 문자열과 숫자 타입이 섞여 있으므로 모델 입력에 바로 사용하지 않고 별도 정규화 후 사용한다. `no`와 `img_no`도 정수·문자열이 섞여 있어 문자열로 정규화한다.

## 5. 가공 데이터 매니페스트

아래는 학습 파이프라인에서 사용할 논리 필드다. 저장 형식은 구현 전에 조현재가 확정한다.

| 필드 | 의미 | 형식 후보 | 필수 | 생성 규칙 |
|---|---|---|---|---|
| sample_id | 내부 샘플 고유값 | 문자열 | Y | `원본 분할:품종:품질:파일명 stem` |
| source_image_archive | 이미지 ZIP 상대 경로 | 문자열 | Y | `data/raw/` 기준 상대 경로 |
| source_image_member | 이미지 ZIP 멤버명 | 문자열 | Y | 라벨 멤버와 같은 stem |
| processed_image_path | 가공 이미지 상대 경로 | 문자열 | 조건부 | 별도 파일을 만들 때 기록 |
| source_label_archive | 라벨 ZIP 상대 경로 | 문자열 | Y | `data/raw/` 기준 상대 경로 |
| source_label_member | 라벨 ZIP 멤버명 | 문자열 | Y | 원본 JSON 추적용 |
| source_crc32 | 원본 이미지 ZIP CRC32 | 문자열 | Y | 빠른 무결성 확인, 중복 판정에는 별도 해시 사용 |
| crop_type | 품목 | 범주 | Y | 현재 `apple`, 확장 시 한 품목 추가 |
| cultivar | 품종 | 범주 | Y | `fuji=부사`, `yanggwang=양광` |
| quality_grade | 품질 등급 | 범주 | Y | `L=특`, `M=상`, `S=보통` |
| source_group_id | 동일 개체·촬영 묶음 | 문자열 | Y | JSON `group_no` |
| captured_side | 촬영면 | 범주 | 조건부 | 실제 라벨 존재 시 유지 |
| vertical_angle | 수직 촬영각도 | 수치·범주 | 조건부 | 실제 단위 확인 후 확정 |
| horizontal_angle | 수평 촬영각도 | 수치·범주 | 조건부 | 실제 단위 확인 후 확정 |
| image_width | 이미지 너비 | 정수 | Y | 이미지에서 읽음 |
| image_height | 이미지 높이 | 정수 | Y | 이미지에서 읽음 |
| split | 데이터 분할 | 범주 | Y | train·validation·test |
| exclusion_reason | 제외 이유 | 문자열 | 조건부 | 제외 샘플만 기록 |

## 6. 데이터 분할 규칙

1. 원본 Training과 Validation을 합친다.
2. JSON의 `group_no`를 `source_group_id`로 사용하고 그룹 단위로만 분할한다.
3. 품종 2종과 품질 3단계의 조합을 층화하여 train 70%, validation 15%, test 15%로 나눈다.
4. 동일 개체의 여러 촬영각도 이미지는 반드시 같은 split에 배치한다.
5. 시험 세트는 모델·입력 장수·결합 방식·임계값 선택에 사용하지 않는다.
6. 분할 seed와 생성 설정을 기록한다.
7. 품종·품질 Macro F1은 그룹 단위 교차검증으로 변동성도 기록한다.
8. 최종 분할 전 조합별 그룹 수를 확인하고 70/15/15 층화가 불안정하면 비율을 재검토한다.

### 6.1 seed 42 확정 분할

- Train 125그룹, Validation 27그룹, Test 27그룹
- 실제 그룹 비율: 69.8324% / 15.0838% / 15.0838%
- 최종 Test를 제외한 152그룹의 5-Fold 크기: 31 / 31 / 30 / 30 / 30
- 모든 품종×품질 조합이 각 fold에 포함되며 조합별 fold 크기 차이는 최대 1개
- Train·Validation·Test의 `group_no` 교차 0건
- 분할 파일: `configs/splits/seed-42.csv`
- 요약 파일: `configs/splits/seed-42-summary.json`
- 상세 검토: [DM-03 그룹 층화 분할·교차검증](<../../[DM-03] 그룹 층화 분할·교차검증.md>)

## 7. 가상 당도 파생 데이터

원본 매니페스트와 AI Hub 라벨은 수정하지 않는다. 동일 사과의 `group_no` 단위로 한 번 생성한 결과를 `data/processed/virtual-brix.csv`에 별도 저장하고 분할 파일과 조인한다.

| 필드 | 의미 |
|---|---|
| `group_no` | 동일 사과 그룹 식별자 |
| `virtual_brix` | 시연용 가상 당도(°Brix), 0.1 단위 |
| `brix_uncertainty` | 가상값의 상대 불확실성 |
| `brix_source` | 고정값 `simulated_rgb_proxy` |
| `brix_is_measured` | 고정값 `false` |
| `brix_generator_version` | 생성 규칙·계수 버전 |
| `feature_version` | 색상·균일도 특징 버전 |

생성기는 정답 품종·품질 라벨을 입력으로 사용하지 않는다. `group_no`는 조인과 고정 난수 시드에만 사용하며, 학습 입력에는 포함하지 않는다. 생성식과 민감도 분석은 [`virtual-brix-plan.md`](<virtual-brix-plan.md>)를 따른다.

## 8. 데이터 품질 검사

| 검사 ID | 검사 | 실패 처리 | 결과 기록 |
|---|---|---|---|
| DQ-01 | 이미지 파일 존재 | 제외 | 누락 목록 |
| DQ-02 | 이미지 디코딩 가능 | 제외 | 손상 파일 목록 |
| DQ-03 | 라벨 파일 존재 | 제외 | 라벨 누락 목록 |
| DQ-04 | 품목이 허용 범위인지 확인 | 제외 또는 보류 | 알 수 없는 품목 목록 |
| DQ-05 | 품종이 선택한 2종인지 확인 | 보류 | 품종별 건수 |
| DQ-06 | 품질 등급이 특·상·보통인지 확인 | 제외 또는 매핑 수정 | 알 수 없는 등급 목록 |
| DQ-07 | 파일 해시 중복 검사 | 한 건 유지 또는 그룹화 | 완전 중복 목록 |
| DQ-08 | 동일 개체 split 교차 검사 | 분할 재생성 | 누수 검사 결과 |
| DQ-09 | 품종·등급별 분포 검사 | 분할 또는 학습 전략 검토 | 분포표 |

### 8.1 2026-09-17 전체 검사 결과

- 이미지·JSON 25,024쌍의 파일명 연결 성공, 누락 0건
- 전체 PNG 청크 CRC와 ZIP 멤버 CRC 검사 성공, 손상 0건
- PNG IHDR과 JSON의 1000×1000 해상도 불일치 0건
- ZIP명과 `catecode`·`cate1`·`cate2`·`cate3` 불일치 0건
- SHA-256 완전 중복 이미지 5쌍·10장을 후보로 기록하고 자동 삭제하지 않음
- 179그룹 중 175그룹은 40장 이상, 4그룹은 각각 8·16·21·30장

실행 결과와 중복 식별자는 [DM-02 그룹 EDA·품질 검사](<../../[DM-02] 그룹 EDA·품질 검사.md>)에 기록한다.

## 9. 모델 입력·출력 계약

### 9.1 입력

- 검사 단위: `1 inspection = 사과 1개 = group_no 1개`
- Simulator 기본 시연 전송: `data/processed/realtime-apple-arrival-demo/index.json`의 `default_playback=true`인 사전 구성 12장 묶음. `partial_groups`는 누락 뷰 시연 전용
- 전송 형식: Base64가 아닌 `multipart/form-data`
- 지원 입력 장수 실험: 4·8·12·16·40장
- 대표 프레임 선정 기준(자료 생성 단계): `angle_direction → horizontality_angle → verticality_angle → sample_id` 순 정렬 후 전체 범위에서 첫·마지막 프레임을 포함하는 균등 인덱스. 기본 시연 실행 중에는 이미 구성된 묶음을 재선택하지 않음
- 부족 뷰: 보유 프레임 뒤를 패딩하고 `view_mask=False` 적용
- 지원 이미지 형식: PNG, JPEG
- 최대 요청 크기: multipart 이미지 합계 24MiB
- 색상 공간·리사이즈·정규화: RGB, 모델 패키지의 `image_size`, ImageNet mean/std
- 정답 품종은 모델 입력으로 전달하지 않고 모델이 이미지에서 예측한다.

전체 179그룹 검증에서 4·8장은 패딩이 없고, 12·16장은 8장 그룹 하나만 각각 4·8슬롯을 패딩한다. 40장은 8·16·21·30장 그룹 네 개에 총 85슬롯을 패딩한다. 상세 결과는 [DM-04 다각도 로더·누락 뷰 마스킹](<../../[DM-04] 다각도 로더·누락 뷰 마스킹.md>)와 `configs/view-selection-summary.json`에 기록한다.

### 9.2 출력 논리 필드

| 필드 | 의미 | 필수 |
|---|---|---|
| inspection_id | 요청과 동일한 공통 검사 식별값 | Y |
| crop_type | 판정 품목 | Y |
| cultivar_probabilities | `fuji`·`yanggwang` 라벨을 key로 가진 확률 객체 | Y |
| predicted_cultivar | 최대 확률의 품종 | Y |
| cultivar_confidence | 품종 예측 신뢰도 | Y |
| quality_probabilities | `L`·`M`·`S` 라벨을 key로 가진 확률 객체 | Y |
| predicted_grade | 최대 확률의 품질 등급 | Y |
| quality_confidence | 품질 예측 신뢰도 | Y |
| inference_time_ms | 그룹 추론시간 | Y |
| model_name | 모델 구조 식별 | Y |
| model_version | 모델 버전 | Y |
| preprocessing_version | 전처리 버전 | Y |
| used_frame_count | 실제 모델이 사용한 프레임 수 | Y |
| virtual_brix | 시연용 가상 당도(°Brix) | Y |
| brix_uncertainty | 가상값의 상대 불확실성 | Y |
| brix_source | `simulated_rgb_proxy` | Y |
| brix_is_measured | 항상 `false` | Y |
| brix_generator_version | 생성 규칙 버전 | Y |

클래스 코드와 순서는 모델 산출물에 고정하고 백엔드에서 임의로 재정렬하지 않는다.

- 품종 순서: `fuji`, `yanggwang`
- 품질 순서: `L`, `M`, `S`

## 10. MySQL 저장 요구사항

MySQL 사용 목적은 정해진 순환 보존 범위 안에서 검사 이력을 저장하고 웹의 이력·통계·분석 조회를 지원하는 것이다. 아래 내용은 논리 요구사항이며 물리 스키마가 아니다.

### 10.1 검사 단위 저장 항목

| 논리 항목 | 목적 | 필수 |
|---|---|---|
| inspection_id | 전체 처리 흐름에서 공유하는 검사 식별값 | Y |
| created_at | Asia/Seoul 기준 밀리초 단위 검사 시각 | Y |
| crop_type | 품목별 조회 | Y |
| predicted_cultivar | 예측 품종과 품종별 조회 | Y |
| source_reference | 입력 파일 추적용 식별값 | Y |
| predicted_grade | 등급별 조회·통계 | Y |
| cultivar_confidence | 품종 저신뢰 분석 | Y |
| quality_confidence | 품질 저신뢰 분석 | Y |
| applied_cultivar_threshold | 검사에 적용한 품종 confidence threshold | Y |
| applied_quality_threshold | 검사에 적용한 품질 confidence threshold | Y |
| review_required | 검수 대상 조회 | Y |
| sorting_target | 선별 결과 확인 | Y |
| model_version | 모델별 결과 추적 | Y |
| inference_time_ms | 실제 추론시간과 CPU 성능 분석 | Y |
| model_name | 모델 구조 비교와 운영 추적 | Y |
| preprocessing_version | 전처리 설정 추적 | Y |
| used_frame_count | 실제 사용 프레임 수 추적 | Y |
| virtual_brix | 시연용 가상 당도 표시·조회 | Y |
| brix_uncertainty | 가상값 신뢰도 해석 | Y |
| brix_source | 실측값과 가상값 구분 | Y |
| brix_is_measured | 비실측 여부 표시 | Y |
| brix_generator_version | 생성 규칙 추적 | Y |
| inspection_status | 검사 판정과 처리 흐름 상태 | Y |
| control_status | Virtual Control 처리 상태 | Y |
| persistence_status | DB 저장 결과 상태 | Y |
| error_code | 실패 원인 분석 | 조건부 |
| deadline_exceeded | Backend의 Inference 요청 전송부터 응답 전체 수신까지 500ms 초과 여부 | Y |
| late_result_received_at | 시간 초과 후 결과 도착 시각 | 조건부 |
| late_cultivar | 시간 초과 후 도착한 품종 진단 결과 | 조건부 |
| late_grade | 시간 초과 후 도착한 품질 진단 결과 | 조건부 |
| exclude_from_normal_stats | 정상 품종·품질 통계 제외 여부 | Y |

정상 이미지는 추론 직후 메모리에서도 제거하며 MySQL에 이미지나 경로를 저장하지 않는다. 장애가 발생한 이미지만 별도 파일 저장소에 임시 보관하고 DB에는 장애 이미지 참조와 상태만 저장한다. 관리자가 수동 삭제할 수 있다. 장애 이미지는 최대 100개를 유지하고, 101번째 파일을 저장할 때 가장 오래된 파일부터 자동 삭제한다.

### 10.2 웹 조회 차원

- 검사 기간
- 품목
- 품종
- 예측 등급
- 수동 검수 여부
- 선별 목적지
- 모델 버전
- 검사·제어·저장 상태
- 오류 유형
- 오판 의심 유형

### 10.3 기본 집계 요구

- 전체 검사 건수
- 등급별 건수와 비율
- 품목·품종별 검사 건수
- 저신뢰·수동 검수 건수와 비율
- 기간별 검사 추이
- 평균 처리 시간
- 오류 유형별 건수

시간 초과 또는 시스템 오류인 건은 품종·품질 분포에서 제외한다. 저신뢰 건은 두 제외 조건이 아니면 품종·품질 분포에 포함한다. 모든 건은 전체 검사량에 포함하고, 재검사율은 `재검사 건수 ÷ 전체 검사 건수`로 계산한다. 이후 도착한 추론 결과는 진단 필드에 저장하고 확정된 bin과 정상 통계를 변경하지 않는다.

### 10.4 이력 보존과 내보내기

- 검사 이력은 상한에 도달하기 전까지 누적한다.
- 검사 이력의 건수 상한 86,400건에 도달하면 생성 시각이 오래된 8,640건을 삭제한다.
- 삭제 후 77,760건부터 다시 누적하므로 초당 사과 그룹 2개 기준 보존 범위는 약 10.8~12시간이다.
- CSV는 관리 화면의 필터 조건을 그대로 적용한다.
- CSV에는 별도의 행 수 제한을 두지 않고 현재 보존 중인 필터 결과 전체를 내보낸다.
- CSV에는 이미지가 포함되지 않으며 검사 결과, 신뢰도, 성능, 오류, 모델 버전과 오판 의심 정보를 포함한다.

실제 테이블, 컬럼, 데이터 타입, 기본키·외래키, 인덱스, 집계 방식, 보존·삭제 정책, 마이그레이션은 홍준희가 별도 DB 설계 문서에서 확정한다.

## 11. 데이터 보안과 운영

- MySQL 접속 정보는 환경 변수 또는 비밀 관리 방식으로 주입한다.
- 실제 비밀번호를 Git에 커밋하지 않는다.
- 개발·시험 데이터 초기화 절차를 문서화한다.
- 마이그레이션은 새 환경에서 순서대로 재실행할 수 있어야 한다.
- MySQL 볼륨과 마이그레이션 복구 절차를 문서화하되, 검사 이력은 확정된 순환 정책을 따른다.

## 12. 담당과 미결정 사항

| 항목 | 담당 | 상태 |
|---|---|---|
| AI Hub 실제 필드 매핑 | 조현재 | 전체 JSON 25,024개 확인 완료 |
| 사과 품종명 2종 | 조현재 | 부사(`fuji`)·양광(`yanggwang`) 확정 |
| 분할 파일 형식 | 조현재 | `configs/splits/seed-42.csv` 확정 |
| 모델 클래스 코드·순서 | 조현재·홍준희 | 품종 `fuji`, `yanggwang`; 품질 `L`, `M`, `S` 확정 |
| MySQL 물리 스키마 | 홍준희 | 별도 문서 TODO |
| 마이그레이션 도구 | 홍준희·홍유나 | TODO |
| 통계 API 응답 형식 | 홍준희·강성민 | TODO |
| 지원 이미지 형식·파일/요청 크기·허용 프레임 수 | 조현재·홍준희 | PNG/JPEG, 1~12장, multipart 합계 24MiB 확정 |
| 상태 Enum·오류 코드·세부 OpenAPI Schema | 홍준희·관련 담당자 | TODO |
| late result 비동기 수신 방식 | 홍준희 | Backend 구현 설계에서 결정 |
| 장애 이미지 저장 한도·자동 삭제 기준 | 홍준희 | 최대 100개, 오래된 파일부터 삭제 확정 |
| bin 코드·품종·품질 매핑 | 홍준희 | DB 설계 문서에서 결정 |
| 보존·삭제 정책 | 홍준희·전체 | 86,400건 도달 시 오래된 8,640건 삭제 확정 |
