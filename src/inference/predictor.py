"""모델 패키지의 무결성을 확인하고 사과 한 개의 사진 묶음을 추론한다.

manifest의 선택 필드 ``quality_temperature``·``cultivar_temperature``(기본 1.0)가 있으면 logits를
temperature로 나눈 뒤 softmax한다. 예측 등급은 바뀌지 않고 신뢰도 값만 보정된다. 값은
``src.training.calibration``이 개발 5-fold OOF 예측으로 구한다.

실제 시연 사진(1000×1000 PNG 12장)은 PNG 해제가 모델 계산보다 오래 걸리므로, 사진별 해제·크기
변환을 작은 스레드 풀에서 병렬로 한다. 사진마다 같은 변환을 독립적으로 적용하므로 결과 텐서는
순차 처리와 비트 단위로 같다.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
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
    used_frame_count: int

    def to_dict(self) -> dict[str, Any]:
        """예측 결과를 응답에 사용할 사전 형태로 변환한다."""
        return asdict(self)


class Predictor:
    def __init__(self, package_dir: Path, *, device: str = "auto", decode_workers: int = 0) -> None:
        """``decode_workers``는 사진 해제 스레드 수다. 0이면 CPU 수와 view 수 중 작은 값, 1이면 순차 처리."""
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
        if decode_workers < 0:
            raise ValueError("decode_workers는 0 이상이어야 합니다")
        self.decode_workers = decode_workers or max(1, min(self.views, os.cpu_count() or 1))
        self.cultivar_temperature = _temperature(self.manifest, "cultivar_temperature")
        self.quality_temperature = _temperature(self.manifest, "quality_temperature")
        checkpoint = torch.load(checkpoint_path, map_location=self.device, weights_only=False)
        self.model = build_model(
            str(self.manifest["model_kind"]), pretrained=False
        ).to(self.device)
        self.model.load_state_dict(checkpoint["model_state"])
        self.model.eval()

    def _prepare(self, image_bytes: Sequence[bytes]) -> tuple[torch.Tensor, torch.Tensor]:
        """업로드한 사진을 공통 크기·정규화로 바꾸고 부족한 입력의 마스크를 만든다."""
        if not image_bytes:
            raise ValueError("이미지는 1장 이상 필요합니다")
        selected = list(image_bytes)
        if len(selected) > self.views:
            selected = [selected[index] for index in evenly_spaced_indices(len(selected), self.views)]
        pool = self._decode_pool() if len(selected) > 1 else None
        tensors = list(pool.map(self._decode, selected)) if pool else [self._decode(v) for v in selected]
        mask = [True] * len(tensors)
        while len(tensors) < self.views:
            tensors.append(torch.zeros(3, self.image_size, self.image_size))
            mask.append(False)
        return (
            torch.stack(tensors).unsqueeze(0).to(self.device),
            torch.tensor(mask, dtype=torch.bool).unsqueeze(0).to(self.device),
        )

    def _decode(self, value: bytes) -> torch.Tensor:
        with Image.open(BytesIO(value)) as image:
            return self.transform(image.convert("RGB"))

    def _decode_pool(self) -> ThreadPoolExecutor | None:
        """해제용 스레드 풀을 처음 쓸 때 만든다. 작업자가 1이면 풀 없이 순차 처리한다."""
        workers = getattr(self, "decode_workers", 1)
        if workers <= 1:
            return None
        pool = getattr(self, "_pool", None)
        if pool is None:
            with _POOL_LOCK:
                pool = getattr(self, "_pool", None)
                if pool is None:
                    pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="cqc-decode")
                    self._pool = pool
        return pool

    def predict(self, image_bytes: Sequence[bytes]) -> Prediction:
        """사진 묶음을 예측한다. 응답 계약의 ``inference_time_ms``는 모델 계산 시간만 담는다."""
        return self.predict_timed(image_bytes)[0]

    def predict_timed(self, image_bytes: Sequence[bytes]) -> tuple[Prediction, dict[str, float]]:
        """예측 결과와 함께 디코딩·전처리(``decode``)와 모델 계산(``model``) 시간을 ms로 돌려준다."""
        prepare_started = time.perf_counter()
        images, mask = self._prepare(image_bytes)
        decode_ms = (time.perf_counter() - prepare_started) * 1000
        if self.device.type == "cuda":
            torch.cuda.synchronize(self.device)
        started = time.perf_counter()
        with torch.inference_mode():
            output = self.model(images, mask)
            cultivar = (
                output["cultivar_logits"] / getattr(self, "cultivar_temperature", 1.0)
            ).softmax(dim=1)[0].cpu()
            quality = (
                output["quality_logits"] / getattr(self, "quality_temperature", 1.0)
            ).softmax(dim=1)[0].cpu()
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
            used_frame_count=int(mask.sum().item()),
        ), {"decode": decode_ms, "model": elapsed_ms}

    def health(self) -> dict[str, Any]:
        return {
            "status": "ready",
            "model_loaded": True,
            "model_name": self.manifest["model_name"],
            "model_version": self.manifest["model_version"],
            "device": str(self.device),
            "views": self.views,
            "approval_status": str(self.manifest.get("approval_status", "unknown")),
            "threshold_status": str(self.manifest.get("threshold_status", "unknown")),
            "checkpoint_sha256": str(self.manifest.get("checkpoint_sha256", "")),
            "quality_temperature": self.quality_temperature,
            "cultivar_temperature": self.cultivar_temperature,
            "decode_workers": getattr(self, "decode_workers", 1),
        }


_POOL_LOCK = threading.Lock()


def _temperature(manifest: dict[str, Any], key: str) -> float:
    """manifest의 temperature를 읽고 없으면 1.0을 쓴다. 0 이하·비정상 값은 거부한다."""
    value = float(manifest.get(key, 1.0))
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{key}는 0보다 큰 유한한 값이어야 합니다")
    return value
