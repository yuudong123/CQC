from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from src.data.manifest import (
    CULTIVARS,
    QUALITY_GRADES,
    DatasetValidationError,
    build_manifest,
)


def _label(cultivar: str, quality: str, group_no: int, img_no: int) -> dict:
    return {
        "group_no": group_no,
        "no": group_no + img_no,
        "img_no": img_no,
        "catecode": CULTIVARS[cultivar]["catecode"],
        "cate1": "사과",
        "cate2": CULTIVARS[cultivar]["ko"],
        "cate3": QUALITY_GRADES[quality],
        "width": "8.0",
        "height": "7.0",
        "weight": "250",
        "identifier": f"{img_no}.png",
        "format": "png",
        "img_height": 1000,
        "img_width": 1000,
        "angle_direction": "top",
        "verticality_angle": 0,
        "horizontality_angle": 45,
        "bndbox": {"xmin": 0, "ymin": 0, "xmax": 1000, "ymax": 1000},
    }


class ManifestTest(unittest.TestCase):
    def _make_dataset(self, root: Path, *, mismatched_label: bool = False) -> None:
        group = 601000000000
        for split_dir in ("1.Training", "2.Validation"):
            image_dir = root / split_dir / "원천데이터_230921_add"
            label_dir = root / split_dir / "라벨링데이터_230921_add"
            image_dir.mkdir(parents=True, exist_ok=True)
            label_dir.mkdir(parents=True, exist_ok=True)
            for cultivar in CULTIVARS:
                for quality in QUALITY_GRADES:
                    group += 1000
                    archive = f"Apple_{cultivar}_{quality}.zip"
                    stem = f"apple_{cultivar}_{quality}_1-1"
                    with ZipFile(image_dir / archive, "w") as image_zip:
                        image_zip.writestr(f"{stem}.PNG", b"fake-png")
                    value = _label(cultivar, quality, group, 1)
                    if mismatched_label and split_dir == "1.Training" and cultivar == "fuji" and quality == "L":
                        value["cate3"] = "보통"
                    with ZipFile(label_dir / archive, "w") as label_zip:
                        label_zip.writestr(
                            f"{stem}.json",
                            json.dumps(value, ensure_ascii=False).encode("utf-8"),
                        )

    def test_builds_manifest_for_all_archive_pairs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._make_dataset(root)
            rows, summary = build_manifest(root)

        self.assertEqual(12, len(rows))
        self.assertEqual(12, summary["dataset"]["archive_pairs"])
        self.assertEqual(12, summary["dataset"]["groups"])
        self.assertEqual("fuji", rows[0]["cultivar"])
        self.assertRegex(rows[0]["image_crc32"], r"^[0-9a-f]{8}$")

    def test_rejects_label_that_conflicts_with_archive_name(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._make_dataset(root, mismatched_label=True)
            with self.assertRaises(DatasetValidationError):
                build_manifest(root)

    def test_rejects_unpaired_image_member(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._make_dataset(root)
            archive = (
                root
                / "1.Training"
                / "원천데이터_230921_add"
                / "Apple_fuji_L.zip"
            )
            with ZipFile(archive, "a") as image_zip:
                image_zip.writestr("unpaired.png", b"fake-png")
            with self.assertRaises(DatasetValidationError):
                build_manifest(root)


if __name__ == "__main__":
    unittest.main()
