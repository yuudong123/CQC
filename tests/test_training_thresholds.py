from __future__ import annotations

import unittest

from src.training.thresholds import evaluate_thresholds, select_thresholds


class TrainingThresholdsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.rows = [
            {"cultivar_target": "fuji", "cultivar_prediction": "fuji", "cultivar_confidence": 0.9, "quality_target": "L", "quality_prediction": "L", "quality_confidence": 0.9},
            {"cultivar_target": "fuji", "cultivar_prediction": "fuji", "cultivar_confidence": 0.8, "quality_target": "M", "quality_prediction": "S", "quality_confidence": 0.6},
            {"cultivar_target": "yanggwang", "cultivar_prediction": "yanggwang", "cultivar_confidence": 0.95, "quality_target": "S", "quality_prediction": "S", "quality_confidence": 0.95},
        ]

    def test_threshold_metrics_report_coverage(self) -> None:
        result = evaluate_thresholds(self.rows, 0.85, 0.85)
        self.assertEqual(result["accepted"], 2)
        self.assertAlmostEqual(result["coverage"], 2 / 3)
        self.assertEqual(result["quality_accuracy"], 1.0)

    def test_selection_maximizes_eligible_coverage(self) -> None:
        result = select_thresholds(
            self.rows, min_cultivar_accuracy=1.0, min_quality_accuracy=1.0
        )
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result["coverage"], 2 / 3)


if __name__ == "__main__":
    unittest.main()
