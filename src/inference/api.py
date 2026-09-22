"""Optional FastAPI adapter around the framework-independent Predictor."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .predictor import Predictor
from .schemas import HealthResponse, PredictionResponse


MAX_REQUEST_BYTES = 24 * 1024 * 1024

try:
    from fastapi import FastAPI, File, Form, HTTPException, UploadFile
except ImportError:  # Optional runtime dependency.
    FastAPI = File = Form = HTTPException = UploadFile = None  # type: ignore[assignment]


def _validate_metadata(value: str, image_count: int) -> list[dict[str, Any]]:
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
            result = predictor.predict(payload).to_dict()
            result["inspection_id"] = inspection_id
            return result
        except (ValueError, OSError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    return app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CQC inference HTTP API")
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args(argv)
    try:
        import uvicorn
    except ImportError as exc:
        raise RuntimeError("uvicorn 실행 의존성을 설치해야 합니다") from exc
    uvicorn.run(create_app(Predictor(args.model_dir, device=args.device)), host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
