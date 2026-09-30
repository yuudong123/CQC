"""시연 묶음 드라이런 도구의 선택·집계·헤더 해석을 확인한다."""

from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts import evaluate_demo_bundles as tool


def _row(role: str, cultivar_conf: float, quality_conf: float, correct: bool, total_ms: float) -> dict:
    return {
        "source_group_id": f"{role}-{quality_conf}",
        "role": role,
        "cultivar_correct": True,
        "quality_correct": correct,
        "cultivar_confidence": cultivar_conf,
        "quality_confidence": quality_conf,
        "total_ms": total_ms,
    }


class DemoDryRunTest(unittest.TestCase):
    def test_percentile_interpolates(self) -> None:
        self.assertIsNone(tool.percentile([], 0.5))
        self.assertEqual(tool.percentile([1.0, 3.0], 0.5), 2.0)
        self.assertEqual(tool.percentile([5.0, 1.0, 3.0], 1.0), 5.0)

    def test_select_uses_custom_index_and_roles(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            splits = root / "splits.csv"
            with splits.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=["group_no", "split"])
                writer.writeheader()
                writer.writerows([{"group_no": "a", "split": "test"}, {"group_no": "b", "split": "train"}])
            full = [
                {"inspection_id": "demo-b-000", "path": "groups/b", "source_group_id": "b", "default_playback": True},
                {"inspection_id": "demo-a-000", "path": "groups/a", "source_group_id": "a", "default_playback": True},
                {"inspection_id": "demo-a-001", "path": "groups/a1", "source_group_id": "a", "default_playback": False},
            ]
            (root / "index.json").write_text(json.dumps(full), encoding="utf-8")
            subset = root / "subset.json"
            subset.write_text(json.dumps(full[1:]), encoding="utf-8")
            roles = tool.load_split_roles(splits)

            everything = tool.select_bundles(root, roles, "all", None, 0)
            self.assertEqual([b["inspection_id"] for b in everything], ["demo-a-000", "demo-b-000"])
            self.assertEqual({b["role"] for b in everything}, {"test", "dev"})
            only_subset = tool.select_bundles(root, roles, "all", None, 0, subset)
            self.assertEqual([b["inspection_id"] for b in only_subset], ["demo-a-000"])
            self.assertEqual(tool.select_bundles(root, roles, "dev", None, 0, subset), [])

    def test_summary_counts_reinspection_when_either_confidence_is_low(self) -> None:
        rows = [
            _row("test", 0.9, 0.45, False, 300.0),
            _row("test", 0.4, 0.90, True, 600.0),
            _row("dev", 0.9, 0.90, True, 200.0),
        ]
        summary = tool.summarize(rows, [(0.5, 0.5)], "total_ms", 500.0)
        rate = summary["all"]["reinspection_rate"]["cultivar>=0.50,quality>=0.50"]
        self.assertAlmostEqual(rate, 2 / 3)
        self.assertEqual(summary["test_apples"]["bundles"], 2)
        self.assertEqual(summary["all"]["latency_ms"]["over_500ms"], 1)
        self.assertAlmostEqual(summary["test_apples"]["quality_accuracy"], 0.5)

    def test_parses_server_timing_header(self) -> None:
        parsed = tool._parse_server_timing("decode;dur=12.5, model;dur=80, total;dur=bad")
        self.assertEqual(parsed, {"decode": 12.5, "model": 80.0})
        self.assertEqual(tool._parse_server_timing(None), {})


if __name__ == "__main__":
    unittest.main()
