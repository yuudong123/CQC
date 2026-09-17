from __future__ import annotations

import unittest
from collections import Counter, defaultdict

from src.data.split_groups import GroupRecord, assign_groups, build_summary


def _groups() -> list[GroupRecord]:
    sizes = {
        ("fuji", "L"): 24,
        ("fuji", "M"): 24,
        ("fuji", "S"): 24,
        ("yanggwang", "L"): 24,
        ("yanggwang", "M"): 51,
        ("yanggwang", "S"): 32,
    }
    values: list[GroupRecord] = []
    group_index = 0
    for (cultivar, quality), count in sizes.items():
        for _ in range(count):
            group_index += 1
            values.append(
                GroupRecord(
                    group_no=str(600000000000 + group_index * 1000),
                    cultivar=cultivar,
                    quality_grade=quality,
                    original_split="train" if group_index <= 139 else "validation",
                    frames=40,
                )
            )
    return values


class SplitGroupsTest(unittest.TestCase):
    def test_assigns_exact_global_targets_without_group_overlap(self) -> None:
        records = assign_groups(_groups(), seed=42, folds=5)
        counts = Counter(record.split for record in records)
        self.assertEqual({"train": 125, "validation": 27, "test": 27}, dict(counts))
        self.assertEqual(179, len({record.group.group_no for record in records}))
        self.assertTrue(
            all(record.cv_fold is None for record in records if record.split == "test")
        )

    def test_is_deterministic_for_same_seed(self) -> None:
        first = assign_groups(_groups(), seed=42, folds=5)
        second = assign_groups(list(reversed(_groups())), seed=42, folds=5)
        first_map = {
            record.group.group_no: (record.split, record.cv_fold) for record in first
        }
        second_map = {
            record.group.group_no: (record.split, record.cv_fold) for record in second
        }
        self.assertEqual(first_map, second_map)

    def test_changes_assignment_for_different_seed(self) -> None:
        first = assign_groups(_groups(), seed=42, folds=5)
        second = assign_groups(_groups(), seed=43, folds=5)
        first_map = {
            record.group.group_no: (record.split, record.cv_fold) for record in first
        }
        second_map = {
            record.group.group_no: (record.split, record.cv_fold) for record in second
        }
        self.assertNotEqual(first_map, second_map)

    def test_each_development_stratum_covers_all_folds(self) -> None:
        records = assign_groups(_groups(), seed=42, folds=5)
        folds_by_stratum: dict[tuple[str, str], Counter[int]] = defaultdict(Counter)
        total_folds: Counter[int] = Counter()
        for record in records:
            if record.cv_fold is not None:
                folds_by_stratum[record.group.stratum][record.cv_fold] += 1
                total_folds[record.cv_fold] += 1
        self.assertTrue(
            all(set(counts) == set(range(5)) for counts in folds_by_stratum.values())
        )
        self.assertTrue(
            all(max(counts.values()) - min(counts.values()) <= 1 for counts in folds_by_stratum.values())
        )
        self.assertLessEqual(max(total_folds.values()) - min(total_folds.values()), 1)

    def test_summary_reports_zero_overlap(self) -> None:
        records = assign_groups(_groups(), seed=42, folds=5)
        summary = build_summary(records, seed=42, folds=5)
        self.assertEqual(0, summary["group_overlap"])
        self.assertEqual(0, summary["test_groups_with_cv_fold"])


if __name__ == "__main__":
    unittest.main()
