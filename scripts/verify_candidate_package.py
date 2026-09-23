"""Verify package integrity and API wiring, not model quality or network latency."""

from __future__ import annotations

import argparse
import json
from io import BytesIO
from pathlib import Path

import torch
from fastapi.testclient import TestClient
from PIL import Image

from src.inference.api import create_app
from src.inference.predictor import Predictor


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Existing verification report must not be overwritten")
    torch.set_num_threads(1)
    predictor = Predictor(args.package, device="cpu")
    buffer = BytesIO()
    Image.new("RGB", (224, 224), (160, 40, 30)).save(buffer, format="PNG")
    metadata = [dict(view_index=i, angle_direction="top" if i < 6 else "bottom",
                     verticality_angle=45, horizontality_angle=(i % 6) * 60)
                for i in range(12)]
    with TestClient(create_app(predictor)) as client:
        health = client.get("/health")
        response = client.post("/v1/predict", data={
            "inspection_id": "candidate-smoke-12", "metadata": json.dumps(metadata),
        }, files=[("images", (f"{i}.png", buffer.getvalue(), "image/png")) for i in range(12)])
    if health.status_code != 200 or response.status_code != 200:
        raise RuntimeError(f"API verification failed: {health.text}, {response.text}")
    prediction = response.json()
    if prediction["inspection_id"] != "candidate-smoke-12" or prediction["used_frame_count"] != 12:
        raise RuntimeError("Inspection ID or frame count mismatch")
    report = {
        "scope": "synthetic_image_inprocess_api_smoke_only",
        "quality_evaluated": False, "production_approved": False,
        "target_cpu_verified": False, "test_used": False,
        "checkpoint_sha256": predictor.manifest["checkpoint_sha256"],
        "health": health.json(), "prediction": prediction,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
