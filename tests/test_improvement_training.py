from __future__ import annotations

import unittest
import json
import tempfile
from pathlib import Path

import torch

from src.data.multiview import GroupRecord
from src.training.engine import quality_loss
from src.training.improvement_experiments import VARIANTS, build_plan
from src.training.improvement_report import evaluate_variant, recommend
from src.training.train import select_development_groups


class ImprovementTrainingTest(unittest.TestCase):
    def test_quality_losses_are_finite_and_differentiable(self) -> None:
        for kind in ("cross_entropy", "focal", "ordinal", "focal_ordinal"):
            with self.subTest(kind=kind):
                logits = torch.tensor([[1.0, 0.0, -1.0]], requires_grad=True)
                loss = quality_loss(logits, torch.tensor([1]), kind=kind)
                self.assertTrue(torch.isfinite(loss))
                loss.backward()
                self.assertIsNotNone(logits.grad)

    def test_source_validation_excludes_test_and_uses_original_split(self) -> None:
        groups = [
            GroupRecord("a", "fuji", "L", "train", 0, (), "train"),
            GroupRecord("b", "fuji", "M", "validation", 1, (), "validation"),
            GroupRecord("c", "fuji", "S", "test", None, (), "validation"),
        ]
        train, validation = select_development_groups(
            groups, validation_scheme="source", cv_fold=0
        )
        self.assertEqual(["a"], [group.group_no for group in train])
        self.assertEqual(["b"], [group.group_no for group in validation])

    def test_plan_has_cv_and_source_runs_for_each_variant(self) -> None:
        plan = build_plan()
        self.assertEqual(len(plan), len(VARIANTS) * 6)
        for variant in VARIANTS:
            runs = [run for run in plan if run["variant"] == variant]
            self.assertEqual(sum(run["validation_scheme"] == "cv" for run in runs), 5)
            self.assertEqual(sum(run["validation_scheme"] == "source" for run in runs), 1)
            self.assertTrue(all("test" not in run["validation_scheme"] for run in runs))

    def test_report_selects_robust_common_epoch(self) -> None:
        def row(epoch: int, quality: float, cultivar: float, m_recall: float) -> dict:
            return {
                "epoch": epoch,
                "validation": {
                    "quality": {"macro_f1": quality, "recall": [1.0, m_recall, 1.0]},
                    "cultivar": {"macro_f1": cultivar},
                },
            }

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            variant = "ce_regularized"
            history = [row(1, 0.70, 0.96, 0.60), row(2, 0.82, 0.97, 0.80)]
            for fold in range(5):
                run = root / f"{variant}-cv-fold-{fold}"
                run.mkdir()
                (run / "history.json").write_text(json.dumps(history), encoding="utf-8")
            source = root / f"{variant}-source"
            source.mkdir()
            (source / "history.json").write_text(
                json.dumps([row(1, 0.68, 0.94, 0.55), row(2, 0.78, 0.95, 0.75)]),
                encoding="utf-8",
            )
            rows = evaluate_variant(root, variant)
            self.assertEqual(recommend(rows)["epoch"], 2)
            self.assertTrue(all(row["test_used"] is False for row in rows))


if __name__ == "__main__":
    unittest.main()
