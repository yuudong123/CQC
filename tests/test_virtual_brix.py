from __future__ import annotations

import csv
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from PIL import Image

from src.data.virtual_brix import (
    RGBProxyFeatures,
    build_virtual_brix_rows,
    extract_rgb_proxy,
    load_virtual_brix,
    write_virtual_brix,
)


def image_bytes(color: tuple[int, int, int]) -> bytes:
    stream = BytesIO()
    Image.new("RGB", (32, 32), color).save(stream, format="PNG")
    return stream.getvalue()


class VirtualBrixTest(unittest.TestCase):
    def test_red_image_has_stronger_redness_than_green(self) -> None:
        self.assertGreater(extract_rgb_proxy(image_bytes((210, 40, 30))).redness, extract_rgb_proxy(image_bytes((40, 180, 50))).redness)

    def test_generation_is_deterministic_and_bounded(self) -> None:
        features = {
            "a": (RGBProxyFeatures(0.1, 0.2, 0.8, 0.03, 0.02), 0.01, 12),
            "b": (RGBProxyFeatures(0.3, 0.8, 0.9, 0.04, 0.03), 0.02, 12),
        }
        first = build_virtual_brix_rows(features)
        second = build_virtual_brix_rows(features)
        self.assertEqual(first, second)
        self.assertTrue(all(9.0 <= float(row["virtual_brix"]) <= 18.0 for row in first))
        self.assertTrue(all(row["brix_is_measured"] == "false" for row in first))

    def test_round_trip_rejects_measured_source(self) -> None:
        features = {"a": (RGBProxyFeatures(0.1, 0.2, 0.8, 0.03, 0.02), 0.01, 12)}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "brix.csv"
            rows = build_virtual_brix_rows(features)
            write_virtual_brix(path, rows)
            self.assertEqual(set(load_virtual_brix(path)), {"a"})
            with path.open("r", encoding="utf-8-sig", newline="") as stream:
                loaded = list(csv.DictReader(stream))
            loaded[0]["brix_is_measured"] = "true"
            write_virtual_brix(path, loaded)
            with self.assertRaises(ValueError):
                load_virtual_brix(path)

    def test_loader_rejects_out_of_range_values(self) -> None:
        features = {"a": (RGBProxyFeatures(0.1, 0.2, 0.8, 0.03, 0.02), 0.01, 12)}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "brix.csv"
            rows = build_virtual_brix_rows(features)
            rows[0]["virtual_brix"] = "99.0"
            write_virtual_brix(path, rows)
            with self.assertRaises(ValueError):
                load_virtual_brix(path)


if __name__ == "__main__":
    unittest.main()
