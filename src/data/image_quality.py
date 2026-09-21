"""Run a full, streaming integrity check for every PNG in the source ZIPs."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import zlib
from collections import defaultdict
from pathlib import Path, PurePosixPath
from typing import BinaryIO
from zipfile import BadZipFile, ZipFile

from .manifest import DatasetValidationError, discover_archive_pairs


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class PngValidationError(ValueError):
    """Raised when a PNG stream has an invalid structure or chunk checksum."""


def _read_exact(stream: BinaryIO, size: int, hasher: object) -> bytes:
    value = stream.read(size)
    if len(value) != size:
        raise PngValidationError(f"예상 {size}바이트 중 {len(value)}바이트만 읽었습니다")
    hasher.update(value)
    return value


def validate_png_stream(stream: BinaryIO) -> tuple[str, int, int]:
    """Validate all PNG chunks and return SHA-256 plus IHDR dimensions."""

    hasher = hashlib.sha256()
    signature = _read_exact(stream, len(PNG_SIGNATURE), hasher)
    if signature != PNG_SIGNATURE:
        raise PngValidationError("PNG 시그니처가 올바르지 않습니다")

    width = height = None
    saw_iend = False
    chunk_index = 0
    while not saw_iend:
        length_bytes = _read_exact(stream, 4, hasher)
        length = struct.unpack(">I", length_bytes)[0]
        chunk_type = _read_exact(stream, 4, hasher)
        crc = zlib.crc32(chunk_type)

        if chunk_index == 0 and (chunk_type != b"IHDR" or length != 13):
            raise PngValidationError("첫 PNG 청크가 올바른 IHDR이 아닙니다")

        remaining = length
        ihdr = bytearray()
        while remaining:
            block = _read_exact(stream, min(1024 * 1024, remaining), hasher)
            crc = zlib.crc32(block, crc)
            if chunk_type == b"IHDR":
                ihdr.extend(block)
            remaining -= len(block)

        expected_crc_bytes = _read_exact(stream, 4, hasher)
        expected_crc = struct.unpack(">I", expected_crc_bytes)[0]
        if (crc & 0xFFFFFFFF) != expected_crc:
            name = chunk_type.decode("ascii", errors="replace")
            raise PngValidationError(f"{name} 청크 CRC가 일치하지 않습니다")

        if chunk_type == b"IHDR":
            width, height = struct.unpack(">II", ihdr[:8])
            if width <= 0 or height <= 0:
                raise PngValidationError("IHDR 해상도가 올바르지 않습니다")
        elif chunk_type == b"IEND":
            if length != 0:
                raise PngValidationError("IEND 청크 길이가 0이 아닙니다")
            saw_iend = True
        chunk_index += 1

    trailing = stream.read(1)
    if trailing:
        raise PngValidationError("IEND 뒤에 불필요한 데이터가 있습니다")
    if width is None or height is None:
        raise PngValidationError("IHDR 청크가 없습니다")
    return hasher.hexdigest(), width, height


def scan_images(raw_root: Path) -> dict:
    """Read every source image fully and collect corrupt and duplicate files."""

    raw_root = raw_root.resolve()
    pairs = discover_archive_pairs(raw_root)
    errors: list[dict[str, str]] = []
    hashes: dict[str, list[str]] = defaultdict(list)
    checked = 0
    archive_results: list[dict[str, object]] = []

    for pair in pairs:
        archive_checked = 0
        archive_errors = 0
        try:
            with ZipFile(pair.image_archive) as archive:
                infos = sorted(
                    (
                        info
                        for info in archive.infolist()
                        if not info.is_dir()
                        and PurePosixPath(info.filename).suffix.casefold() == ".png"
                    ),
                    key=lambda info: info.filename.casefold(),
                )
                for info in infos:
                    sample_id = (
                        f"{pair.key.split}:{pair.key.cultivar}:{pair.key.quality}:"
                        f"{PurePosixPath(info.filename).stem.casefold()}"
                    )
                    try:
                        with archive.open(info) as stream:
                            sha256, _, _ = validate_png_stream(stream)
                        hashes[sha256].append(sample_id)
                    except (BadZipFile, OSError, PngValidationError) as exc:
                        archive_errors += 1
                        errors.append(
                            {
                                "sample_id": sample_id,
                                "archive": pair.image_archive.relative_to(raw_root).as_posix(),
                                "member": info.filename,
                                "error": str(exc),
                            }
                        )
                    checked += 1
                    archive_checked += 1
        except BadZipFile as exc:
            archive_errors += 1
            errors.append(
                {
                    "sample_id": "",
                    "archive": pair.image_archive.relative_to(raw_root).as_posix(),
                    "member": "",
                    "error": str(exc),
                }
            )
        archive_results.append(
            {
                "split": pair.key.split,
                "cultivar": pair.key.cultivar,
                "quality_grade": pair.key.quality,
                "checked_images": archive_checked,
                "errors": archive_errors,
            }
        )
        print(
            f"checked {pair.key.split}/{pair.key.cultivar}/{pair.key.quality}: "
            f"{archive_checked} images, {archive_errors} errors",
            flush=True,
        )

    duplicate_groups = [
        {"sha256": sha256, "sample_ids": samples}
        for sha256, samples in sorted(hashes.items())
        if len(samples) > 1
    ]
    return {
        "check": "full PNG chunk CRC, ZIP member CRC, and SHA-256",
        "checked_images": checked,
        "valid_images": checked - len(errors),
        "corrupt_images": len(errors),
        "errors": errors,
        "duplicate_sha256_groups": len(duplicate_groups),
        "duplicate_sha256_images": sum(
            len(group["sample_ids"]) for group in duplicate_groups
        ),
        "duplicates": duplicate_groups,
        "archives": archive_results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="전체 원본 PNG 무결성 검사")
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/image-quality-report.json"),
    )
    args = parser.parse_args(argv)
    try:
        report = scan_images(args.raw_root)
    except DatasetValidationError as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(
        f"report={args.output} checked={report['checked_images']} "
        f"corrupt={report['corrupt_images']} "
        f"duplicate_groups={report['duplicate_sha256_groups']}"
    )
    return 1 if report["corrupt_images"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
