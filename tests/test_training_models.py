from __future__ import annotations

import unittest

import torch

from src.training.models import SeparateTaskBaseline, SeparateTaskBrixFusion, build_model


class TrainingModelsTest(unittest.TestCase):
    def test_separate_model_returns_both_tasks(self) -> None:
        model = SeparateTaskBaseline(pretrained=False).eval()
        images = torch.randn(1, 2, 3, 32, 32)
        mask = torch.tensor([[True, True]])
        with torch.no_grad():
            output = model(images, mask)
        self.assertEqual(tuple(output["cultivar_logits"].shape), (1, 2))
        self.assertEqual(tuple(output["quality_logits"].shape), (1, 3))

    def test_factory_rejects_unknown_kind(self) -> None:
        with self.assertRaises(ValueError):
            build_model("unknown", pretrained=False)

    def test_brix_fusion_requires_and_uses_proxy_fields(self) -> None:
        model = SeparateTaskBrixFusion(pretrained=False).eval()
        images = torch.randn(2, 2, 3, 32, 32)
        mask = torch.ones(2, 2, dtype=torch.bool)
        with self.assertRaises(ValueError):
            model(images, mask)
        with torch.no_grad():
            output = model(images, mask, torch.tensor([13.0, 15.0]), torch.tensor([0.4, 0.6]))
        self.assertEqual(tuple(output["quality_logits"].shape), (2, 3))
