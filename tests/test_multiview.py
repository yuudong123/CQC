from __future__ import annotations

import unittest
from pathlib import Path

from src.data.multiview import (
    FrameRecord,
    GroupRecord,
    MultiViewDataset,
    evenly_spaced_indices,
    select_views,
)


def _frames(count: int) -> list[FrameRecord]:
    return [
        FrameRecord(
            sample_id=f"sample-{index:03d}",
            group_no="group-1",
            cultivar="fuji",
            quality_grade="L",
            angle_direction="top" if index < count // 2 else "bottom",
            verticality_angle=(index * 15) % 360,
            horizontality_angle=(index // 24) * 45,
            image_archive="images.zip",
            image_member=f"{index}.png",
        )
        for index in range(count)
    ]


class MultiViewTest(unittest.TestCase):
    def test_even_indices_cover_both_ends(self) -> None:
        self.assertEqual((0, 3, 6, 9), evenly_spaced_indices(10, 4))

    def test_selects_requested_count_without_padding(self) -> None:
        selected = select_views(_frames(184), 40)
        self.assertEqual(40, len(selected.frames))
        self.assertEqual(40, sum(selected.mask))
        self.assertEqual(40, len(set(frame.sample_id for frame in selected.real_frames)))

    def test_pads_short_groups_and_returns_mask(self) -> None:
        for available, missing in ((8, 32), (16, 24), (21, 19), (30, 10)):
            with self.subTest(available=available):
                selected = select_views(_frames(available), 40)
                self.assertEqual(40, len(selected.frames))
                self.assertEqual(available, sum(selected.mask))
                self.assertEqual(missing, selected.mask.count(False))
                self.assertTrue(all(selected.mask[:available]))
                self.assertTrue(all(not value for value in selected.mask[available:]))

    def test_selection_is_independent_of_manifest_row_order(self) -> None:
        frames = _frames(40)
        first = select_views(frames, 12)
        second = select_views(list(reversed(frames)), 12)
        self.assertEqual(
            [frame.sample_id for frame in first.real_frames],
            [frame.sample_id for frame in second.real_frames],
        )

    def test_cv_filter_never_includes_final_test(self) -> None:
        frame = _frames(8)[0]
        groups = [
            GroupRecord("train-group", "fuji", "L", "train", 0, (frame,)),
            GroupRecord("validation-group", "fuji", "L", "validation", 1, (frame,)),
            GroupRecord("test-group", "fuji", "L", "test", None, (frame,)),
        ]
        dataset = MultiViewDataset(
            groups,
            raw_root=Path("."),
            target_views=4,
            cv_fold=0,
            cv_role="train",
        )
        self.assertEqual(["validation-group"], [group.group_no for group in dataset.groups])


if __name__ == "__main__":
    unittest.main()
