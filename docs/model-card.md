# CQC 모델 카드

## 식별 정보

- 모델명: `mobilenet_v3_small_multiview`
- 모델 버전: `cqc-apple-separate12-v1.0.0`
- 체크포인트 SHA-256: `7c2d68a9f56f6e00555bb5e79db5bd0881caa6e742ae5d04469525a89e8183a2`
- 모델 구조: `separate`
- 입력 장수: 12
- 입력 크기: 224×224 RGB

## 클래스 계약

- 품종: `fuji, yanggwang`
- 품질: `L, M, S`
- 전처리 버전: `rgb-resize-imagenet-v1`

## 평가 결과

- 5-fold 추천 상태: `provisional`
- 최종 Test 표본: 27그룹
- 품종 Accuracy: 1.0000
- 품종 Macro F1: 1.0000
- 품질 Accuracy: 0.7778
- 품질 Macro F1: 0.7778
- 실패 그룹 수: 6
- 실패 그룹 예시: 601032003000, 601032016000, 601142004000, 601142010000, 601142014000, 601142064000
- 최종 Test 사용: 1회
- 승인 기준: 품종·품질 Macro F1 각각 0.90 이상
- 모델 품질 승인: 실패

## 운영 설정

- 신뢰도 기준: `{"cultivar_threshold": 0.5, "quality_threshold": 0.5, "accepted": 150, "total": 152, "coverage": 0.9868421052631579, "cultivar_accuracy": 0.9866666666666667, "quality_accuracy": 0.98}`
- 측정 CPU: `Intel64 Family 6 Model 183 Stepping 1, GenuineIntel`
- 논리 CPU 수: `28`
- 목표 i7-4790 수용시험: 미완료
- inference는 예측만 담당하며 bin·재검사·DB 정책은 백엔드가 담당한다.

| 동시 처리 | p95 | 처리량/초 | 500ms | 초당 2건 |
|---:|---:|---:|---|---|
| 1 | 113.6ms | 9.31 | True | True |
| 2 | 151.2ms | 14.46 | True | True |
| 4 | 182.1ms | 23.41 | True | True |

## 한계

- 사과 부사·양광과 L/M/S 품질 외 입력은 보장하지 않는다.
- 촬영 환경과 품목 변화에 대한 일반화는 검증되지 않았다.
- 중복 해시 이미지 5쌍은 원본에서 제거하지 않았다.
- 목표 장비가 아닌 CPU 측정은 i7-4790 성능 승인 근거로 사용하지 않는다.
