"""Build a frame-level manifest directly from the AI Hub ZIP archives.

The source archives are intentionally not extracted. Image and JSON members are
paired by their case-insensitive member stem because the JSON ``identifier``
field is not a stable archive path and ``no``/``img_no`` are not unique.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable
from zipfile import BadZipFile, ZipFile, ZipInfo


ARCHIVE_PATTERN = re.compile(
    r"Apple_(?P<cultivar>fuji|yanggwang)_(?P<quality>[LMS])\.zip",
    re.IGNORECASE,
)

CULTIVARS = {
    "fuji": {"ko": "부사", "catecode": "060103"},
    "yanggwang": {"ko": "양광", "catecode": "060114"},
}

QUALITY_GRADES = {
    "L": "특",
    "M": "상",
    "S": "보통",
}

REQUIRED_FIELDS = {
    "group_no",
    "no",
    "img_no",
    "catecode",
    "cate1",
    "cate2",
    "cate3",
    "identifier",
    "format",
    "img_height",
    "img_width",
    "angle_direction",
    "verticality_angle",
    "horizontality_angle",
    "bndbox",
}

MANIFEST_FIELDS = (
    "sample_id",
    "original_split",
    "crop_type",
    "cultivar",
    "cultivar_ko",
    "quality_grade",
    "quality_grade_ko",
    "source_group_id",
    "source_no",
    "source_img_no",
    "angle_direction",
    "verticality_angle",
    "horizontality_angle",
    "image_width",
    "image_height",
    "object_width",
    "object_height",
    "object_weight",
    "schema_variant",
    "image_archive",
    "image_member",
    "image_crc32",
    "image_size_bytes",
    "label_archive",
    "label_member",
)


class DatasetValidationError(ValueError):
    """Raised when the local dataset violates the agreed archive contract."""


@dataclass(frozen=True, order=True)
class ArchiveKey:
    split: str
    cultivar: str
    quality: str


@dataclass(frozen=True)
class ArchivePair:
    key: ArchiveKey
    image_archive: Path
    label_archive: Path


def _relative_posix(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _member_stem(name: str) -> str:
    return PurePosixPath(name).stem.casefold()


def _index_members(
    infos: Iterable[ZipInfo], *, suffixes: set[str], archive: Path
) -> dict[str, ZipInfo]:
    indexed: dict[str, ZipInfo] = {}
    for info in infos:
        if info.is_dir() or PurePosixPath(info.filename).suffix.casefold() not in suffixes:
            continue
        stem = _member_stem(info.filename)
        if stem in indexed:
            raise DatasetValidationError(
                f"ZIP 내부 파일명이 대소문자 무시 기준으로 중복됩니다: "
                f"{archive} ({indexed[stem].filename}, {info.filename})"
            )
        indexed[stem] = info
    return indexed


def _split_from_path(path: Path) -> str:
    if "1.Training" in path.parts:
        return "train"
    if "2.Validation" in path.parts:
        return "validation"
    raise DatasetValidationError(f"Training/Validation 구분을 찾을 수 없습니다: {path}")


def discover_archive_pairs(raw_root: Path) -> list[ArchivePair]:
    """Find and pair the 12 image/label archive combinations."""

    found: dict[ArchiveKey, dict[str, Path]] = defaultdict(dict)
    for path in raw_root.rglob("*.zip"):
        match = ARCHIVE_PATTERN.fullmatch(path.name)
        if match is None:
            continue
        parent_text = str(path.parent)
        if "원천데이터" in parent_text:
            kind = "image"
        elif "라벨링데이터" in parent_text:
            kind = "label"
        else:
            continue

        key = ArchiveKey(
            split=_split_from_path(path),
            cultivar=match.group("cultivar").lower(),
            quality=match.group("quality").upper(),
        )
        if kind in found[key]:
            raise DatasetValidationError(f"중복 {kind} ZIP 조합입니다: {key}")
        found[key][kind] = path

    expected = {
        ArchiveKey(split, cultivar, quality)
        for split in ("train", "validation")
        for cultivar in CULTIVARS
        for quality in QUALITY_GRADES
    }
    missing = sorted(expected - set(found))
    extra = sorted(set(found) - expected)
    incomplete = sorted(key for key, value in found.items() if set(value) != {"image", "label"})
    if missing or extra or incomplete:
        raise DatasetValidationError(
            f"ZIP 구성이 올바르지 않습니다. missing={missing}, extra={extra}, "
            f"incomplete={incomplete}"
        )

    return [
        ArchivePair(key, found[key]["image"], found[key]["label"])
        for key in sorted(expected)
    ]


def _load_label(label_zip: ZipFile, info: ZipInfo) -> dict[str, Any]:
    try:
        value = json.loads(label_zip.read(info).decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DatasetValidationError(
            f"JSON을 UTF-8로 읽을 수 없습니다: {label_zip.filename}!{info.filename}"
        ) from exc
    if not isinstance(value, dict):
        raise DatasetValidationError(
            f"JSON 최상위 값이 객체가 아닙니다: {label_zip.filename}!{info.filename}"
        )
    return value


def _validate_label(label: dict[str, Any], pair: ArchivePair, member: str) -> None:
    missing = sorted(REQUIRED_FIELDS - set(label))
    if missing:
        raise DatasetValidationError(f"필수 JSON 필드 누락: {member} ({missing})")

    expected_cultivar = CULTIVARS[pair.key.cultivar]
    expected_quality = QUALITY_GRADES[pair.key.quality]
    expected_values = {
        "cate1": "사과",
        "cate2": expected_cultivar["ko"],
        "cate3": expected_quality,
        "catecode": expected_cultivar["catecode"],
    }
    mismatches = {
        field: {"expected": expected, "actual": label.get(field)}
        for field, expected in expected_values.items()
        if label.get(field) != expected
    }
    if mismatches:
        raise DatasetValidationError(f"ZIP명과 라벨 값 불일치: {member} ({mismatches})")

    if label["angle_direction"] not in {"top", "bottom"}:
        raise DatasetValidationError(
            f"알 수 없는 angle_direction: {member} ({label['angle_direction']!r})"
        )


def _schema_variant(label: dict[str, Any]) -> str:
    return "camera_metadata" if "camera_model" in label else "legacy_metadata"


def _row(
    *,
    pair: ArchivePair,
    raw_root: Path,
    label_info: ZipInfo,
    image_info: ZipInfo,
    label: dict[str, Any],
) -> dict[str, Any]:
    member_stem = _member_stem(label_info.filename)
    sample_id = f"{pair.key.split}:{pair.key.cultivar}:{pair.key.quality}:{member_stem}"
    return {
        "sample_id": sample_id,
        "original_split": pair.key.split,
        "crop_type": "apple",
        "cultivar": pair.key.cultivar,
        "cultivar_ko": CULTIVARS[pair.key.cultivar]["ko"],
        "quality_grade": pair.key.quality,
        "quality_grade_ko": QUALITY_GRADES[pair.key.quality],
        "source_group_id": str(label["group_no"]),
        "source_no": str(label["no"]),
        "source_img_no": str(label["img_no"]),
        "angle_direction": label["angle_direction"],
        "verticality_angle": label["verticality_angle"],
        "horizontality_angle": label["horizontality_angle"],
        "image_width": label["img_width"],
        "image_height": label["img_height"],
        "object_width": label.get("width", ""),
        "object_height": label.get("height", ""),
        "object_weight": label.get("weight", ""),
        "schema_variant": _schema_variant(label),
        "image_archive": _relative_posix(pair.image_archive, raw_root),
        "image_member": image_info.filename,
        "image_crc32": f"{image_info.CRC:08x}",
        "image_size_bytes": image_info.file_size,
        "label_archive": _relative_posix(pair.label_archive, raw_root),
        "label_member": label_info.filename,
    }


def _type_name(value: Any) -> str:
    return type(value).__name__


def build_manifest(raw_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Validate every JSON member and return manifest rows plus a summary."""

    raw_root = raw_root.resolve()
    pairs = discover_archive_pairs(raw_root)
    rows: list[dict[str, Any]] = []
    archive_summaries: list[dict[str, Any]] = []
    field_types: dict[str, Counter[str]] = defaultdict(Counter)
    schema_variants: Counter[str] = Counter()
    group_sizes: Counter[str] = Counter()
    source_no_counts: Counter[str] = Counter()
    group_img_counts: Counter[tuple[str, str]] = Counter()
    angle_values: dict[str, set[Any]] = defaultdict(set)

    for pair in pairs:
        try:
            with ZipFile(pair.image_archive) as image_zip, ZipFile(pair.label_archive) as label_zip:
                images = _index_members(
                    image_zip.infolist(),
                    suffixes={".png", ".jpg", ".jpeg"},
                    archive=pair.image_archive,
                )
                labels = _index_members(
                    label_zip.infolist(), suffixes={".json"}, archive=pair.label_archive
                )
                label_only = sorted(set(labels) - set(images))
                image_only = sorted(set(images) - set(labels))
                if label_only or image_only:
                    raise DatasetValidationError(
                        f"이미지/라벨 파일명 짝이 맞지 않습니다: {pair.key}; "
                        f"label_only={label_only[:5]}, image_only={image_only[:5]}"
                    )

                archive_groups: Counter[str] = Counter()
                start = len(rows)
                for stem in sorted(labels):
                    label_info = labels[stem]
                    label = _load_label(label_zip, label_info)
                    _validate_label(label, pair, label_info.filename)
                    for field, value in label.items():
                        field_types[field][_type_name(value)] += 1
                    for field in (
                        "angle_direction",
                        "verticality_angle",
                        "horizontality_angle",
                    ):
                        angle_values[field].add(label[field])

                    group_id = str(label["group_no"])
                    img_no = str(label["img_no"])
                    archive_groups[group_id] += 1
                    group_sizes[group_id] += 1
                    source_no_counts[str(label["no"])] += 1
                    group_img_counts[(group_id, img_no)] += 1
                    schema_variants[_schema_variant(label)] += 1
                    rows.append(
                        _row(
                            pair=pair,
                            raw_root=raw_root,
                            label_info=label_info,
                            image_info=images[stem],
                            label=label,
                        )
                    )

                archive_summaries.append(
                    {
                        "split": pair.key.split,
                        "cultivar": pair.key.cultivar,
                        "quality_grade": pair.key.quality,
                        "frames": len(rows) - start,
                        "groups": len(archive_groups),
                        "group_size_distribution": {
                            str(size): count
                            for size, count in sorted(Counter(archive_groups.values()).items())
                        },
                    }
                )
        except BadZipFile as exc:
            raise DatasetValidationError(f"손상된 ZIP입니다: {exc}") from exc

    duplicate_sample_ids = [
        sample_id for sample_id, count in Counter(row["sample_id"] for row in rows).items() if count > 1
    ]
    if duplicate_sample_ids:
        raise DatasetValidationError(f"sample_id가 중복됩니다: {duplicate_sample_ids[:5]}")

    group_size_distribution = Counter(group_sizes.values())
    summary = {
        "contract": {
            "crop_type": "apple",
            "cultivars": CULTIVARS,
            "quality_grades": QUALITY_GRADES,
            "pairing_key": "case-insensitive ZIP member stem",
            "group_key": "group_no",
            "text_encoding": "utf-8-sig",
        },
        "dataset": {
            "archive_pairs": len(pairs),
            "frames": len(rows),
            "groups": len(group_sizes),
            "groups_at_least_40_frames": sum(
                count for size, count in group_size_distribution.items() if size >= 40
            ),
            "groups_below_40_frames": sum(
                count for size, count in group_size_distribution.items() if size < 40
            ),
            "group_size_distribution": {
                str(size): count for size, count in sorted(group_size_distribution.items())
            },
            "schema_variants": dict(sorted(schema_variants.items())),
            "duplicate_source_no_keys": sum(1 for count in source_no_counts.values() if count > 1),
            "duplicate_group_img_no_keys": sum(
                1 for count in group_img_counts.values() if count > 1
            ),
        },
        "angles": {
            field: sorted(values, key=lambda value: (str(type(value)), str(value)))
            for field, values in sorted(angle_values.items())
        },
        "field_types": {
            field: dict(sorted(type_counts.items()))
            for field, type_counts in sorted(field_types.items())
        },
        "archives": archive_summaries,
    }
    return rows, summary


def write_outputs(
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
    manifest_path: Path,
    summary_path: Path,
) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    with summary_path.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(summary, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AI Hub 사과 ZIP 매니페스트 생성")
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw"))
    parser.add_argument(
        "--manifest", type=Path, default=Path("data/processed/manifest.csv")
    )
    parser.add_argument(
        "--summary", type=Path, default=Path("data/processed/manifest-summary.json")
    )
    args = parser.parse_args(argv)
    rows, summary = build_manifest(args.raw_root)
    write_outputs(rows, summary, args.manifest, args.summary)
    print(
        f"manifest={args.manifest} frames={len(rows)} "
        f"groups={summary['dataset']['groups']} summary={args.summary}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
