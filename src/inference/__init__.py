"""체크포인트를 불러와 사과 다각도 사진을 예측하는 추론 서비스다.

한 사과의 이미지 묶음에 품종·품질 결과를 하나씩 반환한다. bin·재검사·DB 정책은 Backend가 맡는다.
모델 패키지 로딩 성공은 품질 승인이 아니다. 현재 서비스 패키지는 v2 후보
(``unverified_candidate``, 신뢰도 미보정)다.

API (``api.py``):
    GET  /health       모델 로딩·버전·장치 상태
    POST /v1/predict   ``inspection_id``, 이미지별 각도 ``metadata`` JSON, ``images`` PNG/JPEG
                       1~12장·합계 24MiB. 12장보다 적으면 마스크 패딩, 초과는 413.
                       응답: 같은 ``inspection_id``, ``used_frame_count``, 품종·품질 확률과
                       예측·신뢰도, 모델 forward 시간(``inference_time_ms``), 모델명·버전.

실행:
    python -m src.inference.api --model-dir models/<패키지> --device cpu --port 8001
    python -m src.inference.export_openapi   # docs/contracts/inference-openapi.json 생성

컨테이너는 ``Dockerfile.inference``로 만들고 패키지를 ``/app/models/approved``에 넣는다. 이 경로명은
배포 인터페이스이며 승인 상태를 뜻하지 않는다. 단독 시험은 루트 ``compose.inference.yaml``,
시험 기록은 ``docs/wbs/[DM-07] 추론 모듈·HTTP API.md``를 따른다.
"""
