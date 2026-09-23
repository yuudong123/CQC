# 추론 서비스

모델 패키지를 읽어 한 사과의 다각도 이미지 그룹에 품종·품질 결과를 각각 하나씩 반환한다. 패키지 로딩 성공은 품질 승인이 아니다. bin, 재검사, DB 정책은 포함하지 않는다.

## API

- `GET /health`: 모델 로딩·버전·장치 상태
- `POST /v1/predict`: `inspection_id`, 이미지별 각도 `metadata` JSON, `images` 이름의 PNG/JPEG multipart 파일 1장 이상

응답에는 요청과 동일한 `inspection_id`, 실제 사용한 `used_frame_count`, 품종·품질별 확률, 예측 클래스, 두 신뢰도, 순수 모델 추론시간, 모델명과 버전이 포함된다. 모델 목표 입력은 12장이며 요청은 1~12장, 합계 24MiB까지 허용한다. 12장보다 적으면 마스크 패딩하며, 초과 입력은 HTTP 413으로 거부한다.

현재 v1 패키지는 서비스 통합 검증에 사용할 수 있지만 품질 승인 모델은 아니다. 운영 배포는 품질 기준을 통과한 새 버전에서 진행한다.

컨테이너는 `Dockerfile.inference`로 만들며 배포 슬롯 `/app/models/approved`를 읽기 전용으로 사용한다. 이 경로명은 배포 인터페이스이며, 현재 v1 패키지의 품질 승인 상태를 의미하지 않는다. CPU용 PyTorch 설치 방식과 모델 볼륨 경로는 MLOps Compose에서 최종 고정한다.

`python -m src.inference.export_openapi`로 백엔드·프론트 공유용 OpenAPI JSON을 생성한다.

독립 컨테이너 시험 설정은 루트 `compose.inference.yaml`, 실행·교체·복구 및 실제 HTTP 계약 시험 기록은 `docs/wbs/[DM-07] 추론 모듈·HTTP API.md`를 따른다. 팀 공용 Compose에는 자동 적용하지 않는다.
