from __future__ import annotations

import unittest

from src.training.experiments import build_plan


class TrainingExperimentsTest(unittest.TestCase):
    def test_complete_matrix_contains_fifty_runs(self) -> None:
        plan = build_plan()
        self.assertEqual(len(plan), 50)
        self.assertEqual(
            {(run["model_kind"], run["views"], run["cv_fold"]) for run in plan},
            {
                (model, views, fold)
                for model in ("joint", "separate")
                for views in (4, 8, 12, 16, 40)
                for fold in range(5)
            },
        )

    def test_forty_views_uses_batch_one(self) -> None:
        plan = build_plan(views=(40,), folds=(0,), model_kinds=("joint",))
        self.assertEqual(plan[0]["batch_size"], 1)
