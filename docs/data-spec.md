# 데이터 및 테이블 명세 초안

상태: 서식 원본과 실제 다운로드 파일이 없어 아래는 설계 가정입니다. AI Hub 원본 필드명으로 확정된 명세가 아닙니다.

## AI Hub 데이터 확인
공식 소개에는 10품목(사과·감귤 포함), 특/상/보통 등급, 원시 60만 건에서 정제된 30만 건이 기재됩니다. 다운로드 권한, 샘플·원본의 파일 구조, 실제 품목별/등급별 건수는 직접 확인 TODO.

## 학습용 논리 데이터
| 필드 | 의미 | 상태 |
|---|---|---|
| sample_id | 내부 고유 식별자 | 가정 |
| image_path | 로컬 이미지 경로 | 가정 |
| crop_type | 품목(우선 사과) | 공식 품목 확인, 실제 필드 TODO |
| quality_grade | 특/상/보통 라벨 | 공식 등급 확인, 실제 필드 TODO |
| source_group | 동일 개체/촬영 묶음 | 존재 여부 TODO |
| split | train/validation/test | 분할 설계 TODO |

## 판정 이력 논리 테이블 (저장 방식 미정)
| 필드 | 의미 | 상태 |
|---|---|---|
| prediction_id | 판정 ID | 가정 |
| created_at | 판정 시각 | 가정 |
| crop_type | 품목 | 가정 |
| predicted_grade | 예측 등급 | 가정 |
| confidence | 모델 신뢰도 | 가정 |
| review_required | 검수 필요 여부 | 가정 |
| sorting_target | 시뮬레이션 선별 목적지 | 가정 |

원본 데이터는 data/raw에 보존하고 가공 결과만 data/processed에 저장합니다. 개인정보·라이선스 조건을 확인한 뒤 반입 정책을 정합니다.

출처: https://aihub.or.kr/aihubdata/data/view.do?aihubDataSe=data&dataSetSn=149&topMenu=103