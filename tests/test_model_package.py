from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import torch

from src.inference.predictor import Predictor
from src.training.models import build_model
from src.training.package_model import load_threshold_selection, main


class ModelPackageTest(unittest.TestCase):
    def test_candidate_without_calibrated_thresholds(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checkpoint = root / "checkpoint.pt"
            checkpoint.write_bytes(b"test checkpoint")
            args = ["--checkpoint", str(checkpoint), "--version", "candidate-test",
                    "--model-kind", "separate", "--views", "12",
                    "--output-root", str(root / "packages")]
            self.assertEqual(main(args), 0)
            manifest = json.loads((root / "packages/candidate-test/model.json").read_text())
            self.assertEqual(manifest["approval_status"], "unverified_candidate")
            self.assertEqual(manifest["threshold_status"], "not_calibrated")
            self.assertNotIn("quality_threshold", manifest)
            self.assertEqual(manifest["checkpoint_sha256"], hashlib.sha256(checkpoint.read_bytes()).hexdigest())
            with self.assertRaises(SystemExit):
                main(args)

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

    def test_loads_packaged_thresholds(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "thresholds.json"
            path.write_text(
                json.dumps(
                    {
                        "selection": {
                            "cultivar_threshold": 0.5,
                            "quality_threshold": 0.6,
                        }
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                load_threshold_selection(path),
                {"cultivar_threshold": 0.5, "quality_threshold": 0.6},
            )


if __name__ == "__main__":
    unittest.main()
