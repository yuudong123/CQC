"""Aggregate completed cross-validation histories without running training."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any


def best_epoch(history_path: Path) -> dict[str, Any]:
    history = json.loads(history_path.read_text(encoding="utf-8"))
    if not history:
        raise ValueError(f"빈 학습 이력입니다: {history_path}")
    return max(history, key=lambda row: row["validation_score"])


def aggregate(run_dirs: list[Path]) -> dict[str, Any]:
    folds = []
    for fold, directory in enumerate(run_dirs):
        best = best_epoch(directory / "history.json")
        validation = best["validation"]
        folds.append(
            {
                "fold": fold,
                "epoch": best["epoch"],
                "score": best["validation_score"],
                "cultivar_accuracy": validation["cultivar"]["accuracy"],
                "cultivar_macro_f1": validation["cultivar"]["macro_f1"],
                "quality_accuracy": validation["quality"]["accuracy"],
                "quality_macro_f1": validation["quality"]["macro_f1"],
            }
        )
    keys = (
        "score",
        "cultivar_accuracy",
        "cultivar_macro_f1",
        "quality_accuracy",
        "quality_macro_f1",
    )
    summary = {
        key: {
            "mean": statistics.mean(row[key] for row in folds),
            "stdev": statistics.stdev(row[key] for row in folds)
            if len(folds) > 1
            else 0.0,
        }
        for key in keys
    }
    return {"folds": folds, "aggregate": summary, "test_used": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="5-fold 학습 결과 집계")
    parser.add_argument("run_dirs", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = aggregate(args.run_dirs)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"summary={args.output} folds={len(args.run_dirs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
