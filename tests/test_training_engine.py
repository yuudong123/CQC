from __future__ import annotations

import unittest


try:
    import torch
    from src.training.engine import classification_metrics, confusion_matrix
except (ImportError, OSError):
    torch = None
    classification_metrics = None
    confusion_matrix = None


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


if __name__ == "__main__":
    unittest.main()
