"""Create the reproducible group-level holdout split and 5-fold CV assignment."""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path


SPLIT_RATIOS = {"train": 0.70, "validation": 0.15, "test": 0.15}
SPLIT_ORDER = tuple(SPLIT_RATIOS)


class SplitValidationError(ValueError):
    """Raised when a group split cannot satisfy the data contract."""


@dataclass(frozen=True)
class GroupRecord:
    group_no: str
    cultivar: str
    quality_grade: str
    original_split: str
    frames: int

    @property
    def stratum(self) -> tuple[str, str]:
        return self.cultivar, self.quality_grade


@dataclass(frozen=True)
class SplitRecord:
    group: GroupRecord
    split: str
    cv_fold: int | None


def load_groups(manifest_path: Path) -> list[GroupRecord]:
    """Collapse the frame manifest into one validated row per group_no."""

    groups: dict[str, dict[str, object]] = {}
    with manifest_path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {
            "source_group_id",
            "cultivar",
            "quality_grade",
            "original_split",
        }
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise SplitValidationError(f"매니페스트 필드가 누락되었습니다: {sorted(missing)}")

        for row in reader:
            group_no = row["source_group_id"]
            target = (row["cultivar"], row["quality_grade"], row["original_split"])
            if group_no not in groups:
                groups[group_no] = {"target": target, "frames": 0}
            elif groups[group_no]["target"] != target:
                raise SplitValidationError(
                    f"한 group_no에 서로 다른 라벨 또는 원본 분할이 있습니다: {group_no}"
                )
            groups[group_no]["frames"] = int(groups[group_no]["frames"]) + 1

    if not groups:
        raise SplitValidationError("매니페스트에 그룹이 없습니다")

    return [
        GroupRecord(
            group_no=group_no,
            cultivar=str(value["target"][0]),
            quality_grade=str(value["target"][1]),
            original_split=str(value["target"][2]),
            frames=int(value["frames"]),
        )
        for group_no, value in sorted(groups.items())
    ]


def _largest_remainder_targets(total: int) -> dict[str, int]:
    raw = {split: total * ratio for split, ratio in SPLIT_RATIOS.items()}
    targets = {split: math.floor(value) for split, value in raw.items()}
    remaining = total - sum(targets.values())
    ranked = sorted(
        SPLIT_ORDER,
        key=lambda split: (raw[split] - targets[split], -SPLIT_ORDER.index(split)),
        reverse=True,
    )
    for split in ranked[:remaining]:
        targets[split] += 1
    return targets


def _allocate_stratum_counts(
    stratum_sizes: dict[tuple[str, str], int], seed: int
) -> dict[tuple[str, str], dict[str, int]]:
    """Allocate exact global totals while keeping every stratum near 70/15/15."""

    total = sum(stratum_sizes.values())
    global_targets = _largest_remainder_targets(total)
    allocation: dict[tuple[str, str], dict[str, int]] = {}
    fractional: dict[tuple[tuple[str, str], str], float] = {}
    row_remaining: dict[tuple[str, str], int] = {}

    for stratum, size in sorted(stratum_sizes.items()):
        allocation[stratum] = {}
        for split, ratio in SPLIT_RATIOS.items():
            raw = size * ratio
            allocation[stratum][split] = math.floor(raw)
            fractional[(stratum, split)] = raw - math.floor(raw)
        row_remaining[stratum] = size - sum(allocation[stratum].values())

    column_remaining = {
        split: global_targets[split]
        - sum(counts[split] for counts in allocation.values())
        for split in SPLIT_ORDER
    }
    extra_used: set[tuple[tuple[str, str], str]] = set()
    tie_rng = random.Random(f"{seed}:allocation")
    tie_break = {
        (stratum, split): tie_rng.random()
        for stratum in sorted(stratum_sizes)
        for split in SPLIT_ORDER
    }

    while sum(row_remaining.values()):
        candidates = [
            (fractional[(stratum, split)], tie_break[(stratum, split)], stratum, split)
            for stratum in sorted(stratum_sizes)
            for split in SPLIT_ORDER
            if row_remaining[stratum] > 0
            and column_remaining[split] > 0
            and (stratum, split) not in extra_used
        ]
        if not candidates:
            raise SplitValidationError(
                f"층화 할당에 실패했습니다: rows={row_remaining}, columns={column_remaining}"
            )
        _, _, stratum, split = max(candidates)
        allocation[stratum][split] += 1
        row_remaining[stratum] -= 1
        column_remaining[split] -= 1
        extra_used.add((stratum, split))

    if any(column_remaining.values()):
        raise SplitValidationError(f"전역 분할 목표를 채우지 못했습니다: {column_remaining}")
    return allocation


def _allocate_fold_counts(
    development_sizes: dict[tuple[str, str], int], folds: int, seed: int
) -> dict[tuple[str, str], dict[int, int]]:
    """Balance CV fold totals while keeping every stratum within one group."""

    total = sum(development_sizes.values())
    base_target, target_remainder = divmod(total, folds)
    global_targets = {
        fold: base_target + (1 if fold < target_remainder else 0)
        for fold in range(folds)
    }
    allocation: dict[tuple[str, str], dict[int, int]] = {}
    row_remaining: dict[tuple[str, str], int] = {}
    fractional: dict[tuple[str, str], float] = {}
    for stratum, size in sorted(development_sizes.items()):
        base, remainder = divmod(size, folds)
        allocation[stratum] = {fold: base for fold in range(folds)}
        row_remaining[stratum] = remainder
        fractional[stratum] = size / folds - base

    column_remaining = {
        fold: global_targets[fold]
        - sum(counts[fold] for counts in allocation.values())
        for fold in range(folds)
    }
    extra_used: set[tuple[tuple[str, str], int]] = set()
    tie_rng = random.Random(f"{seed}:cv-allocation")
    tie_break = {
        (stratum, fold): tie_rng.random()
        for stratum in sorted(development_sizes)
        for fold in range(folds)
    }
    while sum(row_remaining.values()):
        candidates = [
            (fractional[stratum], tie_break[(stratum, fold)], stratum, fold)
            for stratum in sorted(development_sizes)
            for fold in range(folds)
            if row_remaining[stratum] > 0
            and column_remaining[fold] > 0
            and (stratum, fold) not in extra_used
        ]
        if not candidates:
            raise SplitValidationError(
                f"CV fold 균형화에 실패했습니다: rows={row_remaining}, "
                f"columns={column_remaining}"
            )
        _, _, stratum, fold = max(candidates)
        allocation[stratum][fold] += 1
        row_remaining[stratum] -= 1
        column_remaining[fold] -= 1
        extra_used.add((stratum, fold))

    if any(column_remaining.values()):
        raise SplitValidationError(f"CV fold 목표를 채우지 못했습니다: {column_remaining}")
    return allocation


def assign_groups(groups: list[GroupRecord], seed: int = 42, folds: int = 5) -> list[SplitRecord]:
    """Assign holdout split and CV fold without ever splitting a group."""

    if folds < 2:
        raise SplitValidationError("folds는 2 이상이어야 합니다")
    by_stratum: dict[tuple[str, str], list[GroupRecord]] = defaultdict(list)
    for group in groups:
        by_stratum[group.stratum].append(group)

    if any(len(values) < 3 for values in by_stratum.values()):
        small = {stratum: len(values) for stratum, values in by_stratum.items() if len(values) < 3}
        raise SplitValidationError(f"3-way 층화에 필요한 그룹이 부족합니다: {small}")

    allocation = _allocate_stratum_counts(
        {stratum: len(values) for stratum, values in by_stratum.items()}, seed
    )
    split_by_group: dict[str, str] = {}
    for stratum, values in sorted(by_stratum.items()):
        ordered = sorted(values, key=lambda group: group.group_no)
        random.Random(f"{seed}:{stratum[0]}:{stratum[1]}:holdout").shuffle(ordered)
        offset = 0
        for split in SPLIT_ORDER:
            count = allocation[stratum][split]
            for group in ordered[offset : offset + count]:
                split_by_group[group.group_no] = split
            offset += count

    development_by_stratum = {
        stratum: [group for group in values if split_by_group[group.group_no] != "test"]
        for stratum, values in by_stratum.items()
    }
    fold_allocation = _allocate_fold_counts(
        {stratum: len(values) for stratum, values in development_by_stratum.items()},
        folds,
        seed,
    )
    fold_by_group: dict[str, int] = {}
    for stratum, values in sorted(development_by_stratum.items()):
        development = sorted(
            values,
            key=lambda group: group.group_no,
        )
        if len(development) < folds:
            raise SplitValidationError(
                f"{stratum}의 Train·Validation 그룹이 {folds}-Fold에 부족합니다"
            )
        random.Random(f"{seed}:{stratum[0]}:{stratum[1]}:cv").shuffle(development)
        offset = 0
        for fold in range(folds):
            count = fold_allocation[stratum][fold]
            for group in development[offset : offset + count]:
                fold_by_group[group.group_no] = fold
            offset += count

    records = [
        SplitRecord(
            group=group,
            split=split_by_group[group.group_no],
            cv_fold=fold_by_group.get(group.group_no),
        )
        for group in sorted(groups, key=lambda value: value.group_no)
    ]
    validate_assignments(records, folds)
    return records


def validate_assignments(records: list[SplitRecord], folds: int = 5) -> None:
    group_ids = [record.group.group_no for record in records]
    if len(group_ids) != len(set(group_ids)):
        raise SplitValidationError("group_no가 여러 분할 행에 중복되었습니다")
    for record in records:
        if record.split == "test" and record.cv_fold is not None:
            raise SplitValidationError("최종 Test 그룹에 CV fold가 할당되었습니다")
        if record.split != "test" and record.cv_fold not in range(folds):
            raise SplitValidationError("Train·Validation 그룹의 CV fold가 올바르지 않습니다")


def build_summary(records: list[SplitRecord], seed: int, folds: int) -> dict:
    split_counts = Counter(record.split for record in records)
    split_frames = Counter()
    stratum_counts: dict[str, Counter[str]] = defaultdict(Counter)
    fold_counts: dict[str, Counter[int]] = defaultdict(Counter)
    fold_totals: Counter[int] = Counter()
    original_to_new: dict[str, Counter[str]] = defaultdict(Counter)
    for record in records:
        split_frames[record.split] += record.group.frames
        stratum = f"{record.group.cultivar}:{record.group.quality_grade}"
        stratum_counts[stratum][record.split] += 1
        original_to_new[record.group.original_split][record.split] += 1
        if record.cv_fold is not None:
            fold_counts[stratum][record.cv_fold] += 1
            fold_totals[record.cv_fold] += 1

    total = len(records)
    return {
        "seed": seed,
        "ratios": SPLIT_RATIOS,
        "folds": folds,
        "groups": total,
        "split_groups": dict(split_counts),
        "split_group_ratios": {
            split: round(split_counts[split] / total, 6) for split in SPLIT_ORDER
        },
        "split_frames": dict(split_frames),
        "stratum_groups": {
            stratum: dict(counts) for stratum, counts in sorted(stratum_counts.items())
        },
        "cv_fold_groups": {
            stratum: {str(fold): count for fold, count in sorted(counts.items())}
            for stratum, counts in sorted(fold_counts.items())
        },
        "cv_fold_totals": {
            str(fold): fold_totals[fold] for fold in range(folds)
        },
        "original_to_new_groups": {
            original: dict(counts) for original, counts in sorted(original_to_new.items())
        },
        "group_overlap": 0,
        "test_groups_with_cv_fold": 0,
    }


def write_outputs(
    records: list[SplitRecord], summary: dict, split_path: Path, summary_path: Path
) -> None:
    split_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with split_path.open("w", encoding="utf-8-sig", newline="") as stream:
        fieldnames = (
            "group_no",
            "cultivar",
            "quality_grade",
            "frames",
            "original_split",
            "split",
            "cv_fold",
        )
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "group_no": record.group.group_no,
                    "cultivar": record.group.cultivar,
                    "quality_grade": record.group.quality_grade,
                    "frames": record.group.frames,
                    "original_split": record.group.original_split,
                    "split": record.split,
                    "cv_fold": "" if record.cv_fold is None else record.cv_fold,
                }
            )
    with summary_path.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(summary, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="group_no 기준 데이터 분할 생성")
    parser.add_argument(
        "--manifest", type=Path, default=Path("data/processed/manifest.csv")
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument(
        "--output", type=Path, default=Path("configs/splits/seed-42.csv")
    )
    parser.add_argument(
        "--summary", type=Path, default=Path("configs/splits/seed-42-summary.json")
    )
    args = parser.parse_args(argv)
    groups = load_groups(args.manifest)
    records = assign_groups(groups, seed=args.seed, folds=args.folds)
    summary = build_summary(records, seed=args.seed, folds=args.folds)
    write_outputs(records, summary, args.output, args.summary)
    print(
        f"split={args.output} groups={len(records)} "
        f"counts={summary['split_groups']} summary={args.summary}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
