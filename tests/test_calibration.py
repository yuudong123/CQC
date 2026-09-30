"""개발 OOF 기반 temperature 보정·임계값 표·패키지 반영을 확인한다."""

from __future__ import annotations

import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import torch

from src.training import calibration
from src.training.calibration import OofRow


def _synthetic_rows(count: int, scale: float, seed: int = 0) -> list[OofRow]:
    """정답은 ``true_logits``의 확률로 뽑고, 모델 출력은 그 logits에 ``scale``을 곱해 과신·과소 확신을 만든다."""
    generator = torch.Generator().manual_seed(seed)
    rows = []
    for index in range(count):
        cultivar_true = torch.randn(2, generator=generator) * 2
        quality_true = torch.randn(3, generator=generator) * 2
        cultivar_target = int(torch.multinomial(cultivar_true.softmax(0), 1, generator=generator))
        quality_target = int(torch.multinomial(quality_true.softmax(0), 1, generator=generator))
        rows.append(
            OofRow(
                group_no=f"g{index}",
                fold=index % 5,
                cultivar_target=cultivar_target,
                quality_target=quality_target,
                cultivar_logits=tuple(float(v) for v in cultivar_true * scale),
                quality_logits=tuple(float(v) for v in quality_true * scale),
            )
        )
    return rows


def _write_csv(path: Path, rows: list[OofRow]) -> None:
    fields = ["group_no", "fold", "cultivar_target", "quality_target"]
    fields += [f"cultivar_logit_{c}" for c in calibration.CULTIVAR_CLASSES]
    fields += [f"quality_logit_{c}" for c in calibration.QUALITY_CLASSES]
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            record = {
                "group_no": row.group_no,
                "fold": row.fold,
                "cultivar_target": calibration.CULTIVAR_CLASSES[row.cultivar_target],
                "quality_target": calibration.QUALITY_CLASSES[row.quality_target],
            }
            record.update(zip(fields[4:6], row.cultivar_logits))
            record.update(zip(fields[6:], row.quality_logits))
            writer.writerow(record)


class TemperatureTest(unittest.TestCase):
    def test_recovers_under_and_over_confidence(self) -> None:
        for scale in (0.5, 2.0):
            rows = _synthetic_rows(4000, scale)
            logits = torch.tensor([row.quality_logits for row in rows])
            targets = torch.tensor([row.quality_target for row in rows])
            temperature = calibration.fit_temperature(logits, targets)
            self.assertAlmostEqual(temperature, scale, delta=0.15 * scale)
            before = calibration.calibration_metrics(logits, targets, 1.0)
            after = calibration.calibration_metrics(logits, targets, temperature)
            self.assertLess(after["ece"], before["ece"])
            self.assertLessEqual(after["nll"], before["nll"] + 1e-9)
            self.assertEqual(after["accuracy"], before["accuracy"])

    def test_reliability_bins_cover_all_samples(self) -> None:
        rows = _synthetic_rows(300, 1.0)
        logits = torch.tensor([row.quality_logits for row in rows])
        targets = torch.tensor([row.quality_target for row in rows])
        metrics = calibration.calibration_metrics(logits, targets, 1.0)
        self.assertEqual(sum(b["count"] for b in metrics["reliability"]), 300)


class ThresholdTableTest(unittest.TestCase):
    def test_coverage_decreases_with_threshold_and_counts_error_types(self) -> None:
        rows = _synthetic_rows(500, 1.0, seed=3)
        table = calibration.threshold_table(rows, 1.0, 1.0, quality_thresholds=[0.4, 0.6, 0.8], cultivar_thresholds=[0.5])
        coverages = [row["coverage"] for row in table]
        self.assertEqual(coverages, sorted(coverages, reverse=True))
        first = table[0]
        self.assertEqual(first["accepted"] + round(first["reinspection_rate"] * first["total"]), first["total"])
        self.assertLessEqual(first["extreme_l_s_swap"], first["higher_to_normal"] + first["normal_to_higher"])

    def test_recommendation_respects_constraints(self) -> None:
        table = [
            {"accepted": 90, "coverage": 0.9, "reinspection_rate": 0.1, "quality_accuracy": 0.90, "quality_threshold": 0.5, "cultivar_threshold": 0.5},
            {"accepted": 80, "coverage": 0.8, "reinspection_rate": 0.2, "quality_accuracy": 0.95, "quality_threshold": 0.6, "cultivar_threshold": 0.5},
            {"accepted": 50, "coverage": 0.5, "reinspection_rate": 0.5, "quality_accuracy": 0.99, "quality_threshold": 0.8, "cultivar_threshold": 0.5},
        ]
        chosen = calibration.recommend(table, min_quality_accuracy=0.94, max_reinspection=0.3)
        self.assertEqual(chosen["quality_threshold"], 0.6)
        self.assertIsNone(calibration.recommend(table, min_quality_accuracy=0.999, max_reinspection=0.3))
        self.assertIsNone(calibration.recommend(table, min_quality_accuracy=None, max_reinspection=None))

    def test_reference_uses_uncalibrated_confidence(self) -> None:
        # 과소 확신 모델에서 보정 후 0.50/0.50과 현재 운영(보정 전 0.50/0.50)의 자동 처리 수가 달라야 한다.
        rows = _synthetic_rows(500, 0.4, seed=5)
        report = calibration.fit(rows)
        reference = report["reference_at_current_thresholds"]
        uncalibrated = calibration.threshold_table(rows, 1.0, 1.0, quality_thresholds=[0.5], cultivar_thresholds=[0.5])[0]
        calibrated = next(
            row for row in report["threshold_table"]
            if row["cultivar_threshold"] == 0.5 and row["quality_threshold"] == 0.5
        )
        self.assertEqual(reference["temperature"], 1.0)
        self.assertEqual(reference["accepted"], uncalibrated["accepted"])
        self.assertLess(reference["accepted"], calibrated["accepted"])


class FileFlowTest(unittest.TestCase):
    def test_cli_fit_and_apply_keep_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = _synthetic_rows(200, 0.6, seed=5)
            for fold in range(5):
                _write_csv(root / f"oof-fold-{fold}.csv", [r for r in rows if r.fold == fold])
            output = root / "calibration.json"
            code = calibration.main(
                ["fit", "--predictions", str(root / "oof-fold-*.csv"), "--output", str(output),
                 "--table", str(root / "table.csv"), "--min-quality-accuracy", "0.5"]
            )
            self.assertEqual(code, 0)
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertFalse(report["test_used"])
            self.assertEqual(report["samples"], 200)
            self.assertEqual(report["folds"], [0, 1, 2, 3, 4])
            self.assertTrue((root / "table.csv").exists())

            package = root / "package"
            package.mkdir()
            (package / "model.pt").write_bytes(b"weights")
            sha = hashlib.sha256(b"weights").hexdigest()
            (package / "model.json").write_text(
                json.dumps({"model_version": "v2", "checkpoint_sha256": sha, "threshold_status": "not_calibrated"}),
                encoding="utf-8",
            )
            calibration.main(
                ["apply", "--calibration", str(output), "--package", str(package), "--model-version", "v2-cal"]
            )
            manifest = json.loads((package / "model.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["model_version"], "v2-cal")
            self.assertEqual(manifest["checkpoint_sha256"], sha)
            self.assertEqual(manifest["threshold_status"], "calibrated_dev_oof")
            self.assertGreater(manifest["quality_temperature"], 0)
            self.assertTrue((package / "model.json.before-calibration").exists())

    def test_rejects_duplicate_group_and_missing_logits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = _synthetic_rows(4, 1.0)
            _write_csv(root / "a.csv", rows)
            _write_csv(root / "b.csv", rows[:1])
            with self.assertRaises(ValueError):
                calibration.read_predictions([root / "a.csv", root / "b.csv"])
            (root / "old.csv").write_text("group_no,fold,cultivar_target,quality_target\ng1,0,fuji,L\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                calibration.read_predictions([root / "old.csv"])


if __name__ == "__main__":
    unittest.main()
