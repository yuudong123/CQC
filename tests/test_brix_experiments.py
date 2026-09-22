from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from src.training.brix_experiments import build_plan, command_for, run_is_complete


class BrixExperimentsTest(unittest.TestCase):
    def test_default_plan_is_fixed_to_twelve_views_and_excludes_test(self) -> None:
        plan = build_plan()
        self.assertEqual(len(plan), 48)
        self.assertEqual({run["views"] for run in plan}, {12})
        self.assertEqual({run["validation_scheme"] for run in plan}, {"cv", "source"})
        self.assertTrue(all(run["test_used"] is False for run in plan))

    def test_only_fusion_command_receives_virtual_brix(self) -> None:
        plan = build_plan(
            variants=("ce_regularized",),
            model_kinds=("separate", "separate_brix"),
        )
        baseline = next(run for run in plan if run["model_kind"] == "separate")
        fusion = next(run for run in plan if run["model_kind"] == "separate_brix")
        brix_path = Path("data/processed/virtual-brix.csv")
        baseline_command = command_for(baseline, "cuda", brix_path)
        fusion_command = command_for(fusion, "cuda", brix_path)
        self.assertEqual(baseline_command[0], sys.executable)
        self.assertNotIn("--virtual-brix", baseline_command)
        self.assertIn("--virtual-brix", fusion_command)
        self.assertEqual(fusion_command[fusion_command.index("--views") + 1], "12")

    def test_completed_run_can_be_skipped_safely(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run = build_plan(
                epochs=3,
                variants=("ce_regularized",),
                model_kinds=("separate",),
                root=Path(directory),
            )[0]
            output = Path(run["output_dir"])
            output.mkdir(parents=True)
            (output / "summary.json").write_text(
                json.dumps({"epochs_completed": 3}),
                encoding="utf-8",
            )
            self.assertTrue(run_is_complete(run))


if __name__ == "__main__":
    unittest.main()
