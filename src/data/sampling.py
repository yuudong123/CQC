"""Angle-balanced view sampling for training-time multi-view augmentation."""

from __future__ import annotations

import hashlib
import random
from collections import defaultdict
from collections.abc import Sequence

from .multiview import FrameRecord, MultiViewValidationError, SelectedViews


def _stable_rng(*, seed: int, epoch: int, group_no: str) -> random.Random:
    payload = f"{seed}:{epoch}:{group_no}".encode("utf-8")
    digest = hashlib.sha256(payload).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def _allocate_slots(counts: dict[str, int], target: int) -> dict[str, int]:
    """Allocate slots as evenly as possible across available camera directions."""

    directions = sorted(direction for direction, count in counts.items() if count > 0)
    if not directions:
        raise MultiViewValidationError("빈 프레임 그룹은 선택할 수 없습니다")
    allocation = {direction: 0 for direction in directions}
    remaining = min(target, sum(counts.values()))
    while remaining:
        candidates = [
            direction
            for direction in directions
            if allocation[direction] < counts[direction]
        ]
        if not candidates:
            break
        direction = min(candidates, key=lambda value: (allocation[value], value))
        allocation[direction] += 1
        remaining -= 1
    return allocation


def _sample_spread(
    frames: Sequence[FrameRecord], count: int, rng: random.Random
) -> list[FrameRecord]:
    """Choose one random frame from each contiguous angular sector."""

    ordered = sorted(
        frames,
        key=lambda frame: (
            frame.horizontality_angle % 360,
            frame.verticality_angle % 360,
            frame.sample_id,
        ),
    )
    if count >= len(ordered):
        return ordered
    selected = []
    size = len(ordered)
    for sector in range(count):
        start = sector * size // count
        end = (sector + 1) * size // count
        selected.append(ordered[rng.randrange(start, end)])
    return selected


def select_angle_balanced_random_views(
    frames: Sequence[FrameRecord],
    target: int,
    *,
    seed: int,
    epoch: int,
    group_no: str,
) -> SelectedViews:
    """Randomly sample views while covering camera directions and angular sectors."""

    if target <= 0:
        raise MultiViewValidationError("target은 1 이상이어야 합니다")
    if epoch < 0:
        raise MultiViewValidationError("epoch는 0 이상이어야 합니다")
    if not frames:
        raise MultiViewValidationError("빈 프레임 그룹은 선택할 수 없습니다")
    if any(frame.group_no != group_no for frame in frames):
        raise MultiViewValidationError("서로 다른 group_no의 프레임을 함께 샘플링할 수 없습니다")

    by_direction: dict[str, list[FrameRecord]] = defaultdict(list)
    for frame in frames:
        if frame.angle_direction not in {"top", "bottom"}:
            raise MultiViewValidationError(
                f"지원하지 않는 angle_direction입니다: {frame.angle_direction!r}"
            )
        by_direction[frame.angle_direction].append(frame)

    allocation = _allocate_slots(
        {direction: len(values) for direction, values in by_direction.items()}, target
    )
    rng = _stable_rng(seed=seed, epoch=epoch, group_no=group_no)
    selected = []
    for direction in sorted(allocation):
        selected.extend(_sample_spread(by_direction[direction], allocation[direction], rng))
    selected.sort(key=lambda frame: frame.view_key)
    padding = target - len(selected)
    return SelectedViews(
        tuple(selected) + (None,) * padding,
        (True,) * len(selected) + (False,) * padding,
    )
