from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.data.multiview import GroupRecord
from src.training.final_fit import development_groups, parse_args, select_final_epochs


class FinalFitTest(unittest.TestCase):
    def test_selects_best_common_epoch_instead_of_median_fold_peak(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            best_epochs = [3, 1, 3, 1, 3]
            for fold, best_epoch in enumerate(best_epochs):
                run = root / f"separate-12view-fold-{fold}"
                run.mkdir()
                history = [
                    {"epoch": 1, "validation_score": 0.9 if best_epoch == 1 else 0.2},
                    {"epoch": 2, "validation_score": 0.8},
                    {"epoch": 3, "validation_score": 0.9 if best_epoch == 3 else 0.2},
                ]
                (run / "history.json").write_text(json.dumps(history), encoding="utf-8")
            epochs, collected = select_final_epochs(root, "separate", 12)
            self.assertEqual(collected, best_epochs)
            self.assertEqual(epochs, 2)

    def test_development_groups_exclude_test(self) -> None:
        groups = [
            GroupRecord("a", "fuji", "L", "train", 0, ()),
            GroupRecord("b", "fuji", "L", "validation", 1, ()),
            GroupRecord("c", "fuji", "L", "test", None, ()),
        ]
        self.assertEqual(["a", "b"], [group.group_no for group in development_groups(groups)])

    def test_defaults_prepare_only(self) -> None:
        args = parse_args([])
        self.assertFalse(args.execute)
        self.assertEqual(args.model_kind, "separate")
        self.assertEqual(args.views, 12)
        self.assertEqual(args.output_dir, Path("outputs/final-training/separate-12view"))


if __name__ == "__main__":
    unittest.main()
