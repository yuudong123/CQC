# [DM-07] 추론 모듈·HTTP API

## 목적

승인된 다각도 모델을 HTTP로 제공하고 품종·품질 확률과 신뢰도, 모델 버전을 백엔드에 전달한다.

## 구현 완료

- `src/inference/predictor.py`: 모델 패키지 로딩, 동일 전처리, 마스크 패딩, 확률·신뢰도 반환
- `src/inference/api.py`: `/health`, `/v1/predict` FastAPI 어댑터
- `src/inference/README.md`: 입력·응답과 책임 범위
- 가짜 예측기를 사용한 `/health`, multipart 반복 이미지, 415 오류 HTTP 계약 테스트 완료
- PNG/JPEG multipart 입력만 허용하고 빈 그룹을 거부한다.
- 입력 장수 초과 시 전달 순서 전체에서 균등 선택하고 부족하면 0 텐서와 마스크로 패딩한다.
- bin, 재검사, DB 정책은 포함하지 않는다.

## 실제 패키지 검증

- `cqc-apple-separate12-v1.0.0` 패키지 체크섬 검증과 CPU 로딩 성공
- validation 그룹의 실제 PNG 12장을 multipart로 보내 `/health`, `/v1/predict` HTTP 200 확인
- 단일 호출 모델 추론시간 45.8ms
- 최대 12파일·24MiB를 넘으면 HTTP 413 반환
- PNG/JPEG 외 형식은 HTTP 415, 빈 요청·손상 이미지는 HTTP 422

목표 i7-4790의 500ms 수용시험만 남는다. 최종 Test 품질 Macro F1이 승인 기준에 미달했으므로 현재 패키지는 기능 검증용이며 승인 모델이 아니다.
