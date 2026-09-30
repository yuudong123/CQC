"""패키지 검증, 사진 전처리와 예측 결과 구성을 확인한다."""

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
        """사진과 유효 마스크를 받아 품종·품질 예측 점수를 계산한다."""
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

    def _predictor(self, **temperatures: float) -> Predictor:
        predictor = Predictor.__new__(Predictor)
        predictor.manifest = {
            "model_name": "test-model",
            "model_version": "test-v1",
            "preprocessing_version": "test-preprocess-v1",
            "approval_status": "unverified_candidate",
            "threshold_status": "calibrated_dev_oof",
            "checkpoint_sha256": "abc",
        }
        predictor.device = torch.device("cpu")
        predictor.views = 4
        predictor.image_size = 32
        predictor.cultivar_classes = ("fuji", "yanggwang")
        predictor.quality_classes = ("L", "M", "S")
        predictor.transform = build_transform(training=False, image_size=32)
        predictor.model = _FixedModel()
        predictor.cultivar_temperature = temperatures.get("cultivar", 1.0)
        predictor.quality_temperature = temperatures.get("quality", 1.0)
        return predictor

    def test_temperature_changes_confidence_but_not_prediction(self) -> None:
        base = self._predictor().predict([_png()])
        sharp = self._predictor(quality=0.5, cultivar=0.5).predict([_png()])
        soft = self._predictor(quality=2.0, cultivar=2.0).predict([_png()])
        self.assertEqual(base.predicted_grade, sharp.predicted_grade)
        self.assertEqual(base.predicted_grade, soft.predicted_grade)
        self.assertEqual(base.predicted_cultivar, soft.predicted_cultivar)
        self.assertGreater(sharp.quality_confidence, base.quality_confidence)
        self.assertLess(soft.quality_confidence, base.quality_confidence)

    def test_predict_timed_reports_decode_and_model(self) -> None:
        prediction, timings = self._predictor().predict_timed([_png(), _png()])
        self.assertEqual(set(timings), {"decode", "model"})
        self.assertEqual(prediction.inference_time_ms, timings["model"])
        self.assertTrue(all(value >= 0 for value in timings.values()))

    def test_health_reports_approval_and_calibration(self) -> None:
        health = self._predictor(quality=0.8).health()
        self.assertEqual(health["approval_status"], "unverified_candidate")
        self.assertEqual(health["threshold_status"], "calibrated_dev_oof")
        self.assertEqual(health["quality_temperature"], 0.8)

    def test_manifest_temperature_validation(self) -> None:
        from src.inference.predictor import _temperature

        self.assertEqual(_temperature({}, "quality_temperature"), 1.0)
        self.assertEqual(_temperature({"quality_temperature": 0.7}, "quality_temperature"), 0.7)
        for bad in (0, -1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                _temperature({"quality_temperature": bad}, "quality_temperature")

    def test_parallel_decode_matches_sequential_and_keeps_order(self) -> None:
        generator = torch.Generator().manual_seed(0)
        images = []
        for _ in range(6):
            pixels = torch.randint(0, 256, (40, 40, 3), generator=generator, dtype=torch.uint8).numpy()
            stream = io.BytesIO()
            Image.fromarray(pixels).save(stream, format="PNG")
            images.append(stream.getvalue())
        sequential = self._predictor()
        sequential.views = 6
        sequential.decode_workers = 1
        parallel = self._predictor()
        parallel.views = 6
        parallel.decode_workers = 4
        expected, _ = sequential._prepare(images)
        actual, _ = parallel._prepare(images)
        self.assertTrue(torch.equal(expected, actual))
        self.assertIsNotNone(parallel._pool)
        self.assertEqual(parallel.health()["decode_workers"], 4)

    def test_rejects_empty_group(self) -> None:
        predictor = Predictor.__new__(Predictor)
        predictor.views = 4
        with self.assertRaises(ValueError):
            predictor._prepare([])


if __name__ == "__main__":
    unittest.main()
