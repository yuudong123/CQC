from __future__ import annotations

import unittest

from src.data.multiview import FrameRecord
from src.data.sampling import select_angle_balanced_random_views


def frames(count_per_direction: int = 24) -> list[FrameRecord]:
    result = []
    for direction in ("top", "bottom"):
        for index in range(count_per_direction):
            result.append(
                FrameRecord(
                    sample_id=f"{direction}-{index:02d}",
                    group_no="apple-1",
                    cultivar="fuji",
                    quality_grade="M",
                    angle_direction=direction,
                    verticality_angle=(index % 3) * 15,
                    horizontality_angle=index * 15,
                    image_archive="images.zip",
                    image_member=f"{direction}-{index}.png",
                )
            )
    return result


class AngleBalancedSamplingTest(unittest.TestCase):
    def test_balances_top_and_bottom(self) -> None:
        selected = select_angle_balanced_random_views(
            frames(), 12, seed=42, epoch=1, group_no="apple-1"
        )
        directions = [frame.angle_direction for frame in selected.real_frames]
        self.assertEqual(directions.count("top"), 6)
        self.assertEqual(directions.count("bottom"), 6)

    def test_is_reproducible_for_same_epoch(self) -> None:
        first = select_angle_balanced_random_views(
            frames(), 12, seed=42, epoch=3, group_no="apple-1"
        )
        second = select_angle_balanced_random_views(
            list(reversed(frames())), 12, seed=42, epoch=3, group_no="apple-1"
        )
        self.assertEqual(
            [frame.sample_id for frame in first.real_frames],
            [frame.sample_id for frame in second.real_frames],
        )

    def test_changes_subset_between_epochs(self) -> None:
        first = select_angle_balanced_random_views(
            frames(), 12, seed=42, epoch=1, group_no="apple-1"
        )
        second = select_angle_balanced_random_views(
            frames(), 12, seed=42, epoch=2, group_no="apple-1"
        )
        self.assertNotEqual(
            [frame.sample_id for frame in first.real_frames],
            [frame.sample_id for frame in second.real_frames],
        )

    def test_pads_short_group_without_duplication(self) -> None:
        selected = select_angle_balanced_random_views(
            frames(4), 12, seed=42, epoch=1, group_no="apple-1"
        )
        self.assertEqual(sum(selected.mask), 8)
        self.assertEqual(len({frame.sample_id for frame in selected.real_frames}), 8)
        self.assertEqual(selected.mask[-4:], (False,) * 4)


if __name__ == "__main__":
    unittest.main()
