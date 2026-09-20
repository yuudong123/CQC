"""Framework layer for loading a packaged model and predicting one apple group."""

from __future__ import annotations

import json
import hashlib
import time
from dataclasses import asdict, dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Sequence

import torch
from PIL import Image

from src.data.multiview import evenly_spaced_indices
from src.data.torch_dataset import build_transform
from src.training.models import build_model


@dataclass(frozen=True)
class Prediction:
    crop_type: str
    predicted_cultivar: str
    cultivar_confidence: float
    cultivar_probabilities: dict[str, float]
    predicted_grade: str
    quality_confidence: float
    quality_probabilities: dict[str, float]
    inference_time_ms: float
    model_name: str
    model_version: str
    preprocessing_version: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Predictor:
    def __init__(self, package_dir: Path, *, device: str = "auto") -> None:
        manifest_path = package_dir / "model.json"
        checkpoint_path = package_dir / "model.pt"
        self.manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        required = {
            "model_name", "model_version", "model_kind", "views", "image_size",
            "cultivar_classes", "quality_classes", "preprocessing_version",
            "checkpoint_sha256",
        }
        missing = required - set(self.manifest)
        if missing:
            raise ValueError(f"모델 manifest 필드 누락: {sorted(missing)}")
        digest = hashlib.sha256(checkpoint_path.read_bytes()).hexdigest()
        if digest != self.manifest["checkpoint_sha256"]:
            raise ValueError("체크포인트 SHA-256이 모델 manifest와 다릅니다")
        if device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA를 요청했지만 사용할 수 없습니다")
        self.device = torch.device(
            "cuda" if device == "auto" and torch.cuda.is_available() else
            "cpu" if device == "auto" else device
        )
        self.views = int(self.manifest["views"])
        self.image_size = int(self.manifest["image_size"])
        self.cultivar_classes = tuple(self.manifest["cultivar_classes"])
        self.quality_classes = tuple(self.manifest["quality_classes"])
        self.transform = build_transform(training=False, image_size=self.image_size)
        checkpoint = torch.load(checkpoint_path, map_location=self.device, weights_only=False)
        self.model = build_model(
            str(self.manifest["model_kind"]), pretrained=False
        ).to(self.device)
        self.model.load_state_dict(checkpoint["model_state"])
        self.model.eval()

    def _prepare(self, image_bytes: Sequence[bytes]) -> tuple[torch.Tensor, torch.Tensor]:
        if not image_bytes:
            raise ValueError("이미지는 1장 이상 필요합니다")
        selected = list(image_bytes)
        if len(selected) > self.views:
            selected = [selected[index] for index in evenly_spaced_indices(len(selected), self.views)]
        tensors = []
        for value in selected:
            with Image.open(BytesIO(value)) as image:
                tensors.append(self.transform(image.convert("RGB")))
        mask = [True] * len(tensors)
        while len(tensors) < self.views:
            tensors.append(torch.zeros(3, self.image_size, self.image_size))
            mask.append(False)
        return (
            torch.stack(tensors).unsqueeze(0).to(self.device),
            torch.tensor(mask, dtype=torch.bool).unsqueeze(0).to(self.device),
        )

    def predict(self, image_bytes: Sequence[bytes]) -> Prediction:
        images, mask = self._prepare(image_bytes)
        if self.device.type == "cuda":
            torch.cuda.synchronize(self.device)
        started = time.perf_counter()
        with torch.inference_mode():
            output = self.model(images, mask)
            cultivar = output["cultivar_logits"].softmax(dim=1)[0].cpu()
            quality = output["quality_logits"].softmax(dim=1)[0].cpu()
        if self.device.type == "cuda":
            torch.cuda.synchronize(self.device)
        elapsed_ms = (time.perf_counter() - started) * 1000
        cultivar_index = int(cultivar.argmax())
        quality_index = int(quality.argmax())
        return Prediction(
            crop_type="apple",
            predicted_cultivar=self.cultivar_classes[cultivar_index],
            cultivar_confidence=float(cultivar[cultivar_index]),
            cultivar_probabilities=dict(zip(self.cultivar_classes, map(float, cultivar))),
            predicted_grade=self.quality_classes[quality_index],
            quality_confidence=float(quality[quality_index]),
            quality_probabilities=dict(zip(self.quality_classes, map(float, quality))),
            inference_time_ms=elapsed_ms,
            model_name=str(self.manifest["model_name"]),
            model_version=str(self.manifest["model_version"]),
            preprocessing_version=str(self.manifest["preprocessing_version"]),
        )

    def health(self) -> dict[str, Any]:
        return {
            "status": "ready",
            "model_loaded": True,
            "model_name": self.manifest["model_name"],
            "model_version": self.manifest["model_version"],
            "device": str(self.device),
            "views": self.views,
        }
