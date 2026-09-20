# [DM-07] 추론 모듈·HTTP API

## 목적

승인된 다각도 모델을 HTTP로 제공하고 품종·품질 확률과 신뢰도, 모델 버전을 백엔드에 전달한다.

## 구현 완료

- `src/inference/predictor.py`: 모델 패키지 로딩, 동일 전처리, 마스크 패딩, 확률·신뢰도 반환
- `src/inference/api.py`: `/health`, `/v1/predict` FastAPI 어댑터
- `src/inference/README.md`: 입력·응답과 책임 범위
- PNG/JPEG multipart 입력만 허용하고 빈 그룹을 거부한다.
- 입력 장수 초과 시 전달 순서 전체에서 균등 선택하고 부족하면 0 텐서와 마스크로 패딩한다.
- bin, 재검사, DB 정책은 포함하지 않는다.

## 남은 검증

- 승인 모델 패키지 실제 로딩
- 실제 이미지 HTTP 통합시험
- CPU 처리시간과 500ms 제한 확인
- 백엔드와 오류 코드·최대 요청 크기 확정
