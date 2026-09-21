from __future__ import annotations

import io
import unittest

import torch
from PIL import Image
from torch import nn

from src.data.torch_dataset import build_transform
from src.inference.predictor import Predictor


class _FixedModel(nn.Module):
    def forward(self, images: torch.Tensor, mask: torch.Tensor) -> dict[str, torch.Tensor]:
        self.last_shape = tuple(images.shape)
        self.last_mask = mask.detach().cpu().tolist()
        return {
            "cultivar_logits": torch.tensor([[1.0, 3.0]], device=images.device),
            "quality_logits": torch.tensor([[0.0, 2.0, 1.0]], device=images.device),
        }


def _png() -> bytes:
    stream = io.BytesIO()
    Image.new("RGB", (8, 8), (200, 10, 20)).save(stream, format="PNG")
    return stream.getvalue()


class PredictorTest(unittest.TestCase):
    def test_predicts_one_result_and_masks_missing_views(self) -> None:
        predictor = Predictor.__new__(Predictor)
        predictor.manifest = {
            "model_name": "test-model",
            "model_version": "test-v1",
            "preprocessing_version": "test-preprocess-v1",
        }
        predictor.device = torch.device("cpu")
        predictor.views = 4
        predictor.image_size = 32
        predictor.cultivar_classes = ("fuji", "yanggwang")
        predictor.quality_classes = ("L", "M", "S")
        predictor.transform = build_transform(training=False, image_size=32)
        predictor.model = _FixedModel()

        result = predictor.predict([_png(), _png()])

        self.assertEqual(result.predicted_cultivar, "yanggwang")
        self.assertEqual(result.predicted_grade, "M")
        self.assertEqual(result.crop_type, "apple")
        self.assertEqual(predictor.model.last_shape, (1, 4, 3, 32, 32))
        self.assertEqual(predictor.model.last_mask, [[True, True, False, False]])
        self.assertAlmostEqual(sum(result.cultivar_probabilities.values()), 1.0, places=6)
        self.assertAlmostEqual(sum(result.quality_probabilities.values()), 1.0, places=6)

    def test_rejects_empty_group(self) -> None:
        predictor = Predictor.__new__(Predictor)
        predictor.views = 4
        with self.assertRaises(ValueError):
            predictor._prepare([])


if __name__ == "__main__":
    unittest.main()
