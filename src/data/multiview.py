"""사과 단위로 여러 사진을 묶고 재현 가능한 순서로 입력 사진을 선택한다."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence
from zipfile import ZipFile


SUPPORTED_VIEW_COUNTS = (4, 8, 12, 16, 40)
CULTIVAR_CLASSES = ("fuji", "yanggwang")
QUALITY_CLASSES = ("L", "M", "S")


class MultiViewValidationError(ValueError):
    """매니페스트·분할·선택 사진이 입력 규칙을 위반하면 발생한다."""


@dataclass(frozen=True)
class FrameRecord:
    sample_id: str
    group_no: str
    cultivar: str
    quality_grade: str
    angle_direction: str
    verticality_angle: int
    horizontality_angle: int
    image_archive: str
    image_member: str
    original_split: str = ""

    @property
    def view_key(self) -> tuple[int, int, int, str]:
        """촬영 방향·각도로 사진의 안정적인 정렬 순서를 만든다."""
        direction_order = {"top": 0, "bottom": 1}
        if self.angle_direction not in direction_order:
            raise MultiViewValidationError(
                f"지원하지 않는 angle_direction입니다: {self.angle_direction!r}"
            )
        return (
            direction_order[self.angle_direction],
            self.horizontality_angle % 360,
            self.verticality_angle % 360,
            self.sample_id,
        )


@dataclass(frozen=True)
class GroupAssignment:
    group_no: str
    split: str
    cv_fold: int | None


@dataclass(frozen=True)
class GroupRecord:
    group_no: str
    cultivar: str
    quality_grade: str
    split: str
    cv_fold: int | None
    frames: tuple[FrameRecord, ...]
    original_split: str = ""


@dataclass(frozen=True)
class SelectedViews:
    frames: tuple[FrameRecord | None, ...]
    mask: tuple[bool, ...]

    @property
    def real_frames(self) -> tuple[FrameRecord, ...]:
        """패딩을 제외하고 실제 선택된 사진만 반환한다."""
        return tuple(frame for frame in self.frames if frame is not None)


def evenly_spaced_indices(size: int, target: int) -> tuple[int, ...]:
    """정렬된 전체 구간을 고르게 덮는 중복 없는 인덱스를 반환한다."""

    if size <= 0:
        raise MultiViewValidationError("빈 프레임 그룹은 선택할 수 없습니다")
    if target <= 0:
        raise MultiViewValidationError("target은 1 이상이어야 합니다")
    if target > size:
        raise MultiViewValidationError("target이 프레임 수보다 큽니다")
    if target == 1:
        return (size // 2,)
    indices = tuple(round(index * (size - 1) / (target - 1)) for index in range(target))
    if len(set(indices)) != target:
        raise MultiViewValidationError(
            f"균등 선택 인덱스가 중복되었습니다: size={size}, target={target}, {indices}"
        )
    return indices


def select_views(frames: Sequence[FrameRecord], target: int) -> SelectedViews:
    """사진을 고르게 선택하고 부족한 자리는 오른쪽에 패딩과 마스크로 표시한다."""

    if target not in SUPPORTED_VIEW_COUNTS:
        raise MultiViewValidationError(
            f"지원하지 않는 입력 장수입니다: {target}; {SUPPORTED_VIEW_COUNTS} 중 선택"
        )
    ordered = tuple(sorted(frames, key=lambda frame: frame.view_key))
    if not ordered:
        raise MultiViewValidationError("빈 프레임 그룹은 선택할 수 없습니다")

    if len(ordered) >= target:
        selected = tuple(ordered[index] for index in evenly_spaced_indices(len(ordered), target))
        return SelectedViews(selected, (True,) * target)

    padding = target - len(ordered)
    return SelectedViews(
        ordered + (None,) * padding,
        (True,) * len(ordered) + (False,) * padding,
    )


def load_assignments(split_path: Path) -> dict[str, GroupAssignment]:
    """고정 분할 CSV에서 사과별 분할·교차검증 번호를 읽는다."""
    assignments: dict[str, GroupAssignment] = {}
    with split_path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"group_no", "split", "cv_fold"}
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise MultiViewValidationError(f"분할 파일 필드 누락: {sorted(missing)}")
        for row in reader:
            group_no = row["group_no"]
            if group_no in assignments:
                raise MultiViewValidationError(f"분할 파일 group_no 중복: {group_no}")
            fold_text = row["cv_fold"].strip()
            assignments[group_no] = GroupAssignment(
                group_no=group_no,
                split=row["split"],
                cv_fold=None if not fold_text else int(fold_text),
            )
    return assignments


def load_groups(manifest_path: Path, split_path: Path) -> list[GroupRecord]:
    """사진별 매니페스트에 사과 단위의 고정 분할 정보를 연결한다."""

    assignments = load_assignments(split_path)
    frames_by_group: dict[str, list[FrameRecord]] = defaultdict(list)
    targets: dict[str, tuple[str, str]] = {}
    original_splits: dict[str, str] = {}
    sample_ids: set[str] = set()
    with manifest_path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {
            "sample_id",
            "original_split",
            "source_group_id",
            "cultivar",
            "quality_grade",
            "angle_direction",
            "verticality_angle",
            "horizontality_angle",
            "image_archive",
            "image_member",
        }
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise MultiViewValidationError(f"매니페스트 필드 누락: {sorted(missing)}")

        for row in reader:
            sample_id = row["sample_id"]
            if sample_id in sample_ids:
                raise MultiViewValidationError(f"sample_id 중복: {sample_id}")
            sample_ids.add(sample_id)
            group_no = row["source_group_id"]
            target = (row["cultivar"], row["quality_grade"])
            if group_no in targets and targets[group_no] != target:
                raise MultiViewValidationError(f"그룹 라벨 불일치: {group_no}")
            targets[group_no] = target
            original_split = row["original_split"].strip().lower()
            if original_split not in {"train", "validation"}:
                raise MultiViewValidationError(
                    f"지원하지 않는 original_split입니다: {original_split!r}"
                )
            if group_no in original_splits and original_splits[group_no] != original_split:
                raise MultiViewValidationError(f"그룹 original_split 불일치: {group_no}")
            original_splits[group_no] = original_split
            frames_by_group[group_no].append(
                FrameRecord(
                    sample_id=sample_id,
                    group_no=group_no,
                    cultivar=target[0],
                    quality_grade=target[1],
                    angle_direction=row["angle_direction"],
                    verticality_angle=int(row["verticality_angle"]),
                    horizontality_angle=int(row["horizontality_angle"]),
                    image_archive=row["image_archive"],
                    image_member=row["image_member"],
                    original_split=original_split,
                )
            )

    missing_assignments = sorted(set(frames_by_group) - set(assignments))
    missing_groups = sorted(set(assignments) - set(frames_by_group))
    if missing_assignments or missing_groups:
        raise MultiViewValidationError(
            f"매니페스트와 분할 파일 그룹 불일치: "
            f"분할 누락={missing_assignments[:5]}, 매니페스트 누락={missing_groups[:5]}"
        )

    return [
        GroupRecord(
            group_no=group_no,
            cultivar=targets[group_no][0],
            quality_grade=targets[group_no][1],
            split=assignments[group_no].split,
            cv_fold=assignments[group_no].cv_fold,
            frames=tuple(frames_by_group[group_no]),
            original_split=original_splits[group_no],
        )
        for group_no in sorted(frames_by_group)
    ]


class MultiViewDataset:
    """항목 하나가 사과 하나이며, 필요한 사진 바이트만 ZIP에서 그때 읽는다."""

    def __init__(
        self,
        groups: Iterable[GroupRecord],
        raw_root: Path,
        target_views: int,
        *,
        split: str | None = None,
        cv_fold: int | None = None,
        cv_role: str | None = None,
        sampling: str = "fixed",
        sampling_seed: int = 42,
    ) -> None:
        if cv_role not in {None, "train", "validation"}:
            raise MultiViewValidationError("cv_role은 train 또는 validation이어야 합니다")
        if cv_role is not None and cv_fold is None:
            raise MultiViewValidationError("cv_role 사용 시 cv_fold가 필요합니다")
        if cv_role is not None and split is not None:
            raise MultiViewValidationError("CV 사용 시 고정 split 필터를 함께 사용할 수 없습니다")
        if target_views not in SUPPORTED_VIEW_COUNTS:
            raise MultiViewValidationError(
                f"지원하지 않는 입력 장수입니다: {target_views}; {SUPPORTED_VIEW_COUNTS} 중 선택"
            )
        if sampling not in {"fixed", "angle_balanced_random"}:
            raise MultiViewValidationError(f"지원하지 않는 sampling입니다: {sampling!r}")
        selected_groups = []
        for group in groups:
            if split is not None and group.split != split:
                continue
            if cv_role is not None and group.split == "test":
                continue
            if cv_role == "train" and group.cv_fold == cv_fold:
                continue
            if cv_role == "validation" and group.cv_fold != cv_fold:
                continue
            selected_groups.append(group)
        self.groups = tuple(selected_groups)
        self.raw_root = raw_root.resolve()
        self.target_views = target_views
        self.sampling = sampling
        self.sampling_seed = sampling_seed
        self.epoch = 0
        self._archives: dict[str, ZipFile] = {}

    def set_epoch(self, epoch: int) -> None:
        """무작위 사진 선택에 사용할 현재 학습 회차를 갱신한다."""
        if epoch < 0:
            raise MultiViewValidationError("epoch는 0 이상이어야 합니다")
        self.epoch = epoch

    def __len__(self) -> int:
        return len(self.groups)

    def __getitem__(self, index: int) -> dict[str, Any]:
        group = self.groups[index]
        if self.sampling == "angle_balanced_random":
            from data.sampling import select_angle_balanced_random_views

            selected = select_angle_balanced_random_views(
                group.frames,
                self.target_views,
                seed=self.sampling_seed,
                epoch=self.epoch,
                group_no=group.group_no,
            )
        else:
            selected = select_views(group.frames, self.target_views)
        images: list[bytes | None] = []
        angles: list[dict[str, int | str] | None] = []
        sample_ids: list[str | None] = []
        for frame in selected.frames:
            if frame is None:
                images.append(None)
                angles.append(None)
                sample_ids.append(None)
                continue
            archive = self._archives.get(frame.image_archive)
            if archive is None:
                archive_path = (self.raw_root / Path(frame.image_archive)).resolve()
                if self.raw_root not in archive_path.parents:
                    raise MultiViewValidationError(
                        f"원본 루트 밖의 ZIP 경로입니다: {frame.image_archive}"
                    )
                archive = ZipFile(archive_path)
                self._archives[frame.image_archive] = archive
            images.append(archive.read(frame.image_member))
            angles.append(
                {
                    "angle_direction": frame.angle_direction,
                    "verticality_angle": frame.verticality_angle,
                    "horizontality_angle": frame.horizontality_angle,
                }
            )
            sample_ids.append(frame.sample_id)
        return {
            "group_no": group.group_no,
            "cultivar": group.cultivar,
            "cultivar_index": CULTIVAR_CLASSES.index(group.cultivar),
            "quality_grade": group.quality_grade,
            "quality_index": QUALITY_CLASSES.index(group.quality_grade),
            "split": group.split,
            "cv_fold": group.cv_fold,
            "images": tuple(images),
            "view_mask": selected.mask,
            "angles": tuple(angles),
            "sample_ids": tuple(sample_ids),
        }

    def close(self) -> None:
        """열어 둔 ZIP 파일을 닫아 파일 핸들을 반환한다."""
        for archive in self._archives.values():
            archive.close()
        self._archives.clear()

    def __enter__(self) -> "MultiViewDataset":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def build_selection_summary(groups: Sequence[GroupRecord]) -> dict[str, Any]:
    """사진 수별 실제 입력·패딩 수량과 사과 그룹 통계를 집계한다."""
    targets: dict[str, Any] = {}
    for target in SUPPORTED_VIEW_COUNTS:
        padded_groups = 0
        padding_slots = 0
        selected_counts: Counter[int] = Counter()
        for group in groups:
            selected = select_views(group.frames, target)
            real_count = sum(selected.mask)
            selected_counts[real_count] += 1
            if real_count < target:
                padded_groups += 1
                padding_slots += target - real_count
        targets[str(target)] = {
            "groups": len(groups),
            "padded_groups": padded_groups,
            "padding_slots": padding_slots,
            "real_frame_count_distribution": {
                str(count): groups_count
                for count, groups_count in sorted(selected_counts.items())
            },
        }
    return {
        "algorithm": (
            "angle_direction, horizontality_angle, verticality_angle, sample_id 순으로 "
            "정렬 후 전체 범위에서 균등 인덱스 선택; 부족분은 오른쪽 padding"
        ),
        "supported_view_counts": list(SUPPORTED_VIEW_COUNTS),
        "groups": len(groups),
        "targets": targets,
    }


def main(argv: list[str] | None = None) -> int:
    """실행 인자를 읽고 다음 작업을 수행한다: 사과 단위로 여러 사진을 묶고 재현 가능한 순서로 입력 사진을 선택한다."""
    parser = argparse.ArgumentParser(description="다각도 그룹 선택·마스킹 검증")
    parser.add_argument(
        "--manifest", type=Path, default=Path("data/processed/manifest.csv")
    )
    parser.add_argument(
        "--splits", type=Path, default=Path("configs/splits/seed-42.csv")
    )
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("configs/view-selection-summary.json"),
    )
    parser.add_argument("--smoke-load", action="store_true")
    args = parser.parse_args(argv)
    groups = load_groups(args.manifest, args.splits)
    summary = build_selection_summary(groups)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(summary, stream, ensure_ascii=False, indent=2)
        stream.write("\n")

    if args.smoke_load:
        for target in SUPPORTED_VIEW_COUNTS:
            with MultiViewDataset(groups, args.raw_root, target) as dataset:
                item = dataset[0]
                if len(item["images"]) != target or len(item["view_mask"]) != target:
                    raise MultiViewValidationError(f"{target}장 smoke load 실패")
    print(
        f"groups={len(groups)} targets={SUPPORTED_VIEW_COUNTS} "
        f"summary={args.output} smoke_load={args.smoke_load}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
