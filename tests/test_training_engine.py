from __future__ import annotations

import unittest


try:
    import torch
    from src.training.engine import classification_metrics, confusion_matrix, run_epoch
except (ImportError, OSError):
    torch = None
    classification_metrics = None
    confusion_matrix = None
    run_epoch = None


@unittest.skipIf(torch is None, "PyTorch 실행 환경이 없습니다")
class TrainingEngineTest(unittest.TestCase):
    def test_confusion_matrix_uses_target_rows(self) -> None:
        result = confusion_matrix(torch.tensor([0, 0, 1, 2]), torch.tensor([0, 1, 1, 0]), 3)
        self.assertEqual([[1, 1, 0], [0, 1, 0], [1, 0, 0]], result.tolist())

    def test_metrics_include_macro_f1_and_class_values(self) -> None:
        matrix = torch.tensor([[2, 0], [1, 1]])
        result = classification_metrics(matrix)
        self.assertAlmostEqual(0.75, result["accuracy"])
        self.assertEqual(2, len(result["precision"]))
        self.assertEqual([[2, 0], [1, 1]], result["confusion_matrix"])

    def test_evaluation_can_include_group_predictions(self) -> None:
        class FixedModel(torch.nn.Module):
            def forward(self, images, view_mask):
                return {
                    "cultivar_logits": torch.tensor([[2.0, 1.0]]),
                    "quality_logits": torch.tensor([[0.0, 3.0, 1.0]]),
                }

        batch = {
            "group_no": ["apple-1"],
            "images": torch.zeros(1, 1, 3, 4, 4),
            "view_mask": torch.tensor([[True]]),
            "cultivar_target": torch.tensor([0]),
            "quality_target": torch.tensor([1]),
        }
        result = run_epoch(
            FixedModel(), [batch], torch.device("cpu"), include_predictions=True
        )
        self.assertEqual(result["predictions"][0]["group_no"], "apple-1")
        self.assertEqual(result["predictions"][0]["cultivar_prediction_index"], 0)
        self.assertEqual(result["predictions"][0]["quality_prediction_index"], 1)


if __name__ == "__main__":
    unittest.main()
