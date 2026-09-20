from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import torch

from src.inference.predictor import Predictor
from src.training.models import build_model


class ModelPackageTest(unittest.TestCase):
    def _package(self, root: Path) -> Path:
        model = build_model("joint", pretrained=False)
        model_path = root / "model.pt"
        torch.save({"model_state": model.state_dict()}, model_path)
        digest = hashlib.sha256(model_path.read_bytes()).hexdigest()
        (root / "model.json").write_text(
            json.dumps(
                {
                    "model_name": "mobilenet_v3_small_multiview",
                    "model_version": "test-v1",
                    "model_kind": "joint",
                    "views": 4,
                    "image_size": 32,
                    "cultivar_classes": ["fuji", "yanggwang"],
                    "quality_classes": ["L", "M", "S"],
                    "preprocessing_version": "rgb-resize-imagenet-v1",
                    "checkpoint_sha256": digest,
                }
            ),
            encoding="utf-8",
        )
        return model_path

    def test_loads_valid_package(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._package(root)
            predictor = Predictor(root, device="cpu")
            self.assertEqual(predictor.health()["status"], "ready")
            self.assertEqual(predictor.health()["model_version"], "test-v1")

    def test_rejects_checkpoint_checksum_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model_path = self._package(root)
            with model_path.open("ab") as stream:
                stream.write(b"tampered")
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                Predictor(root, device="cpu")


if __name__ == "__main__":
    unittest.main()
