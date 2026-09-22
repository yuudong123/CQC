from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.training.train import checkpoint_sha256, parse_args, validation_score


class TrainingCliTest(unittest.TestCase):
    def test_validation_score_averages_both_tasks(self) -> None:
        metrics = {
            "cultivar": {"macro_f1": 0.8},
            "quality": {"macro_f1": 0.4},
        }
        self.assertAlmostEqual(validation_score(metrics), 0.6)

    def test_defaults_to_twelve_views_without_test_evaluation(self) -> None:
        args = parse_args([])
        self.assertEqual(args.views, 12)
        self.assertEqual(args.cv_fold, 0)
        self.assertEqual(args.model_kind, "joint")
        self.assertEqual(
            args.output_dir, Path("outputs/training/joint-12view-fold-0")
        )

    def test_checkpoint_hash_is_stable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoint.pt"
            path.write_bytes(b"cqc")
            self.assertEqual(
                checkpoint_sha256(path),
                "e55498bc9703b7dfac98202fa77a4a8e40ef0d2ea33fd5be08d3af588de40f7a",
            )

    def test_brix_model_requires_csv(self) -> None:
        with self.assertRaises(SystemExit):
            parse_args(["--model-kind", "separate_brix"])
        args = parse_args(["--model-kind", "separate_brix", "--virtual-brix", "data/processed/virtual-brix.csv"])
        self.assertEqual(args.model_kind, "separate_brix")

    def test_brix_comparison_is_fixed_to_twelve_views(self) -> None:
        with self.assertRaises(SystemExit):
            parse_args(
                [
                    "--model-kind",
                    "separate_brix",
                    "--virtual-brix",
                    "brix.csv",
                    "--views",
                    "4",
                ]
            )

    def test_baseline_rejects_brix_input(self) -> None:
        with self.assertRaises(SystemExit):
            parse_args(["--model-kind", "separate", "--virtual-brix", "brix.csv"])


if __name__ == "__main__":
    unittest.main()
