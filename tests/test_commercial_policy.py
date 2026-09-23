import unittest

from src.inference.commercial_policy import assess_commercial_grade, assess_prediction


class CommercialPolicyTests(unittest.TestCase):
    def test_grade_matrix(self):
        for appearance, expected in {"L": "LMSS", "M": "MMSS", "S": "SSSS"}.items():
            for brix, grade in zip((14, 12, 10, 9), expected):
                with self.subTest(appearance=appearance, brix=brix):
                    result = assess_commercial_grade(appearance, brix)
                    self.assertEqual(result["commercial_grade"], grade)
                    self.assertFalse(result["brix_is_measured"])

    def test_boundaries(self):
        for brix, expected in ((9.9, "S"), (10, "S"), (11.999, "S"), (12, "M"), (13.999, "M"), (14, "L"), (18, "L")):
            self.assertEqual(assess_commercial_grade("L", brix)["commercial_grade"], expected)
        self.assertEqual(assess_commercial_grade("L", 12)["score"], 88)
        self.assertTrue(assess_commercial_grade("L", 9.9)["low_brix"])

    def test_holds_and_missing(self):
        for options in ({"review_required": True}, {"severe_defect": True}):
            result = assess_commercial_grade("L", 18, **options)
            self.assertTrue(result["review_required"])
            self.assertIsNone(result["commercial_grade"])
        self.assertIsNone(assess_commercial_grade("L", None)["score"])

    def test_invalid_inputs(self):
        for brix in (True, "14", float("nan"), float("inf"), 8.9, 18.1):
            with self.assertRaises(ValueError):
                assess_commercial_grade("L", brix)
        with self.assertRaises(ValueError):
            assess_commercial_grade("unknown", 14)

    def test_names_and_nonmutating_adapter(self):
        prediction = {"predicted_grade": "L", "inspection_id": "demo-1"}
        result = assess_prediction(prediction, 12, labels={"L": "A", "M": "B", "S": "C"})
        self.assertEqual(result["commercial_assessment"]["commercial_grade_label"], "B")
        self.assertEqual(prediction, {"predicted_grade": "L", "inspection_id": "demo-1"})
        self.assertEqual(result["inference"], prediction)


if __name__ == "__main__":
    unittest.main()
