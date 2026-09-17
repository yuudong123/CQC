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

    def test_defaults_to_eight_views_without_test_evaluation(self) -> None:
        args = parse_args([])
        self.assertEqual(args.views, 8)
        self.assertEqual(args.cv_fold, 0)
        self.assertEqual(args.model_kind, "joint")
        self.assertEqual(
            args.output_dir, Path("outputs/training/joint-8view-fold-0")
        )

    def test_checkpoint_hash_is_stable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoint.pt"
            path.write_bytes(b"cqc")
            self.assertEqual(
                checkpoint_sha256(path),
                "e55498bc9703b7dfac98202fa77a4a8e40ef0d2ea33fd5be08d3af588de40f7a",
            )


if __name__ == "__main__":
    unittest.main()
