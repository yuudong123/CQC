"""Optional FastAPI adapter around the framework-independent Predictor."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from .predictor import Predictor

try:
    from fastapi import FastAPI, File, HTTPException, UploadFile
except ImportError:  # Optional runtime dependency.
    FastAPI = File = HTTPException = UploadFile = None  # type: ignore[assignment]


def create_app(predictor: Predictor) -> Any:
    if FastAPI is None:
        raise RuntimeError("FastAPI 실행 의존성을 설치해야 합니다")

    app = FastAPI(title="CQC Inference API", version="1.0.0")

    @app.get("/health")
    def health() -> dict[str, Any]:
        return predictor.health()

    @app.post("/v1/predict")
    async def predict(images: list[UploadFile] = File(...)) -> dict[str, Any]:
        if not images:
            raise HTTPException(status_code=422, detail="images는 1장 이상 필요합니다")
        payload = []
        for image in images:
            if image.content_type not in {"image/png", "image/jpeg"}:
                raise HTTPException(status_code=415, detail="PNG 또는 JPEG만 지원합니다")
            payload.append(await image.read())
        try:
            return predictor.predict(payload).to_dict()
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
