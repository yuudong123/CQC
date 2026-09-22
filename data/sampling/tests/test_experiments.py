from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from data.sampling.experiments import build_plan, plan_from_v2_report


class SamplingExperimentsTest(unittest.TestCase):
    def test_builds_five_cv_and_one_source_run(self) -> None:
        plan = build_plan("focal_regularized", 14)
        self.assertEqual(len(plan), 6)
        self.assertEqual(sum(run["validation_scheme"] == "cv" for run in plan), 5)
        self.assertEqual(sum(run["validation_scheme"] == "source" for run in plan), 1)
        self.assertTrue(
            all(run["view_sampling"] == "angle_balanced_random" for run in plan)
        )
        self.assertTrue(all(run["epochs"] == 14 for run in plan))

    def test_uses_only_test_free_v2_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            path.write_text(
                json.dumps(
                    {
                        "selection": {
                            "variant": "ordinal_regularized",
                            "epoch": 18,
                            "test_used": False,
                        },
                        "test_used": False,
                    }
                ),
                encoding="utf-8",
            )
            plan = plan_from_v2_report(path)
            self.assertEqual(plan[0]["variant"], "ordinal_regularized")
            self.assertEqual(plan[0]["epochs"], 18)

            path.write_text(
                json.dumps(
                    {
                        "selection": {
                            "variant": "ordinal_regularized",
                            "epoch": 18,
                            "test_used": True,
                        },
                        "test_used": True,
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "Test"):
                plan_from_v2_report(path)


if __name__ == "__main__":
    unittest.main()
