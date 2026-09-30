"""추론기를 HTTP 상태 확인·예측 API로 제공하는 FastAPI 연결 계층이다.

- ``GET /health``: 모델 로딩·버전·장치, 승인·보정 상태.
- ``POST /v1/predict``: ``inspection_id``, 사진별 각도 ``metadata`` JSON, ``images`` 이름의 PNG/JPEG
  multipart 파일 1~12장(합계 24MiB). 12장보다 적으면 마스크로 패딩하고 초과하면 413.
- 응답은 같은 ``inspection_id``, 사용한 장수, 품종·품질 확률·예측·신뢰도, 모델 계산 시간, 모델명·버전.
  단계별 시간은 ``Server-Timing`` 헤더로 준다.
- bin·재검사·DB 정책은 Backend 책임이다. 패키지 로딩 성공은 품질 승인이 아니다.
- 컨테이너는 ``Dockerfile.inference``, 모델 슬롯은 읽기 전용 ``/app/models/approved``.
  공유 OpenAPI JSON은 ``python -m src.inference.export_openapi``로 만든다.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

from .predictor import Predictor
from .schemas import HealthResponse, PredictionResponse


MAX_REQUEST_BYTES = 24 * 1024 * 1024

try:
    from fastapi import FastAPI, File, Form, HTTPException, Response, UploadFile
    from fastapi.concurrency import run_in_threadpool
except ImportError:  # HTTP 서버 기능을 사용할 때 필요한 선택 의존성이다.
    # 의존성이 없는 환경에서도 모듈을 읽게 한다. 아래 표기는 자료형 검사기 지시문이다.
    FastAPI = File = Form = HTTPException = Response = UploadFile = None  # type: ignore[assignment]
    run_in_threadpool = None  # type: ignore[assignment]


def _timed_predict(predictor: Any, payload: list[bytes]) -> tuple[Any, dict[str, float]]:
    """``predict_timed``가 있으면 단계별 시간도 받고, 없으면 모델 시간만 쓴다."""
    timed = getattr(predictor, "predict_timed", None)
    if timed is not None:
        return timed(payload)
    prediction = predictor.predict(payload)
    return prediction, {"model": float(prediction.inference_time_ms)}


def _server_timing(timings: dict[str, float], total_ms: float) -> str:
    """단계별 시간을 표준 ``Server-Timing`` 헤더 값으로 만든다. 응답 본문 계약은 바꾸지 않는다."""
    parts = [f"{name};dur={value:.2f}" for name, value in timings.items()]
    parts.append(f"total;dur={total_ms:.2f}")
    return ", ".join(parts)


def _validate_metadata(value: str, image_count: int) -> list[dict[str, Any]]:
    """사진 수와 각도 메타데이터의 길이·인덱스·필드를 확인한다."""
    try:
        metadata = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError("metadata는 JSON 배열이어야 합니다") from exc
    if not isinstance(metadata, list) or len(metadata) != image_count:
        raise ValueError("metadata 항목 수는 images 수와 같아야 합니다")
    required = {
        "view_index",
        "angle_direction",
        "verticality_angle",
        "horizontality_angle",
    }
    for index, item in enumerate(metadata):
        if not isinstance(item, dict) or not required.issubset(item):
            raise ValueError(f"metadata[{index}] 필수 필드가 누락되었습니다")
        if item["view_index"] != index:
            raise ValueError("metadata의 view_index는 images 순서와 일치해야 합니다")
        if item["angle_direction"] not in {"top", "bottom"}:
            raise ValueError("angle_direction은 top 또는 bottom이어야 합니다")
        if not isinstance(item["verticality_angle"], int) or not isinstance(
            item["horizontality_angle"], int
        ):
            raise ValueError("촬영 각도는 정수여야 합니다")
    return metadata


def create_app(predictor: Predictor) -> Any:
    """주입받은 추론기를 상태 확인·예측 HTTP 경로에 연결한다."""
    if FastAPI is None:
        raise RuntimeError("FastAPI 실행 의존성을 설치해야 합니다")

    app = FastAPI(title="CQC Inference API", version="1.0.0")
    predictor_views = getattr(predictor, "views", None)
    max_files = int(predictor_views if predictor_views is not None else predictor.health()["views"])

    @app.get("/health", response_model=HealthResponse)
    def health() -> dict[str, Any]:
        return predictor.health()

    @app.post(
        "/v1/predict",
        response_model=PredictionResponse,
        responses={
            415: {"description": "PNG/JPEG 외 형식"},
            413: {"description": "파일 수 또는 전체 요청 크기 초과"},
            422: {"description": "빈 요청, 손상 이미지 또는 디코딩 실패"},
            500: {"description": "예상하지 못한 추론 오류"},
        },
    )
    async def predict(
        response: Response,
        inspection_id: str = Form(..., min_length=1),
        metadata: str = Form(...),
        images: list[UploadFile] = File(...),
    ) -> dict[str, Any]:
        if not images:
            raise HTTPException(status_code=422, detail="images는 1장 이상 필요합니다")
        if len(images) > max_files:
            raise HTTPException(
                status_code=413, detail=f"images는 최대 {max_files}장까지 허용합니다"
            )
        try:
            _validate_metadata(metadata, len(images))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        payload = []
        total_bytes = 0
        for image in images:
            if image.content_type not in {"image/png", "image/jpeg"}:
                raise HTTPException(status_code=415, detail="PNG 또는 JPEG만 지원합니다")
            value = await image.read()
            total_bytes += len(value)
            if total_bytes > MAX_REQUEST_BYTES:
                raise HTTPException(status_code=413, detail="전체 이미지는 최대 24MiB입니다")
            payload.append(value)
        try:
            # CPU를 쓰는 추론을 스레드풀에서 실행해 그동안 /health 등 다른 요청이 막히지 않게 한다.
            started = time.perf_counter()
            prediction, timings = await run_in_threadpool(_timed_predict, predictor, payload)
            response.headers["Server-Timing"] = _server_timing(
                timings, (time.perf_counter() - started) * 1000
            )
            result = prediction.to_dict()
            result["inspection_id"] = inspection_id
            return result
        except (ValueError, OSError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    return app


def main(argv: list[str] | None = None) -> int:
    """실행 인자를 읽고 다음 작업을 수행한다: 추론기를 HTTP 상태 확인·예측 API로 제공하는 FastAPI 연결 계층이다."""
    parser = argparse.ArgumentParser(description="CQC inference HTTP API")
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument(
        "--decode-workers", type=int, default=int(os.environ.get("INFERENCE_DECODE_WORKERS", "0")),
        help="사진 해제 스레드 수. 0이면 CPU 수 기준 자동, 1이면 순차 (환경변수 INFERENCE_DECODE_WORKERS)",
    )
    args = parser.parse_args(argv)
    try:
        import uvicorn
    except ImportError as exc:
        raise RuntimeError("uvicorn 실행 의존성을 설치해야 합니다") from exc
    uvicorn.run(create_app(Predictor(args.model_dir, device=args.device, decode_workers=args.decode_workers)), host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
