from __future__ import annotations

import unittest

from src.training.model_card import failure_cases, render_card


class ModelCardTest(unittest.TestCase):
    def test_card_lists_failed_group(self) -> None:
        manifest = {
            "model_name": "cqc",
            "model_version": "v1",
            "checkpoint_sha256": "abc",
            "model_kind": "joint",
            "views": 8,
            "image_size": 224,
            "preprocessing_version": "p1",
        }
        test_result = {
            "test_used": True,
            "test": {
                "samples": 1,
                "cultivar": {"accuracy": 1.0, "macro_f1": 1.0},
                "quality": {"accuracy": 0.0, "macro_f1": 0.0},
                "predictions": [
                    {
                        "group_no": "g1",
                        "cultivar_target_index": 0,
                        "cultivar_prediction_index": 0,
                        "quality_target_index": 0,
                        "quality_prediction_index": 1,
                    }
                ],
            },
        }
        self.assertEqual(len(failure_cases(test_result)), 1)
        card = render_card(
            manifest,
            {"recommendation": {"status": "provisional"}},
            test_result,
            {"selection": {"cultivar_threshold": 0.8}},
            {"results": []},
        )
        self.assertIn("g1", card)
        self.assertIn("최종 Test 사용: 1회", card)


if __name__ == "__main__":
    unittest.main()
