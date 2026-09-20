from __future__ import annotations

import unittest

from src.training.report import aggregate_runs, recommendation


class TrainingReportTest(unittest.TestCase):
    def test_only_complete_five_fold_variant_is_recommended(self) -> None:
        runs = []
        for fold in range(5):
            runs.append(
                {
                    "model_kind": "joint",
                    "views": 8,
                    "fold": fold,
                    "score": 0.9 + fold * 0.01,
                    "cultivar_accuracy": 1.0,
                    "cultivar_macro_f1": 1.0,
                    "quality_accuracy": 0.9,
                    "quality_macro_f1": 0.9,
                }
            )
        runs.append(
            {
                "model_kind": "separate",
                "views": 4,
                "fold": 0,
                "score": 1.0,
                "cultivar_accuracy": 1.0,
                "cultivar_macro_f1": 1.0,
                "quality_accuracy": 1.0,
                "quality_macro_f1": 1.0,
            }
        )
        rows = aggregate_runs(runs)
        selected = recommendation(rows)
        self.assertIsNotNone(selected)
        self.assertEqual(selected["model_kind"], "joint")
        self.assertEqual(selected["views"], 8)
        self.assertFalse(selected["test_used"])


if __name__ == "__main__":
    unittest.main()
