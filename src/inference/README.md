# 추론 서비스

승인된 모델 패키지를 읽어 한 사과의 다각도 이미지 그룹에 품종·품질 결과를 각각 하나씩 반환한다. bin, 재검사, DB 정책은 포함하지 않는다.

## API

- `GET /health`: 모델 로딩·버전·장치 상태
- `POST /v1/predict`: `images` 이름의 PNG/JPEG multipart 파일 1장 이상

응답에는 품종·품질별 확률, 예측 클래스, 두 신뢰도, 순수 모델 추론시간, 모델명과 버전이 포함된다. 요청 이미지는 승인 모델 입력 장수인 12장 이하, 합계 24MiB까지 허용한다. 12장보다 적으면 마스크 패딩하며, 초과 입력은 HTTP 413으로 거부한다.

실제 모델 패키지와 서비스 통합 검증은 학습 결과 확인 및 모델 승인 후 진행한다.

컨테이너는 `Dockerfile.inference`로 만들며 승인 모델 디렉터리를 `/app/models/approved`에 읽기 전용 마운트한다. CPU용 PyTorch 설치 방식과 모델 볼륨 경로는 MLOps Compose에서 최종 고정한다.

`python -m src.inference.export_openapi`로 백엔드·프론트 공유용 OpenAPI JSON을 생성한다.
