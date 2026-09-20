"""Search independent cultivar and quality confidence thresholds."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def evaluate_thresholds(
    rows: list[dict[str, Any]], cultivar_threshold: float, quality_threshold: float
) -> dict[str, Any]:
    accepted = [
        row
        for row in rows
        if float(row["cultivar_confidence"]) >= cultivar_threshold
        and float(row["quality_confidence"]) >= quality_threshold
    ]
    total = len(rows)
    count = len(accepted)
    return {
        "cultivar_threshold": cultivar_threshold,
        "quality_threshold": quality_threshold,
        "accepted": count,
        "total": total,
        "coverage": count / total if total else 0.0,
        "cultivar_accuracy": sum(
            row["cultivar_target"] == row["cultivar_prediction"] for row in accepted
        ) / count if count else 0.0,
        "quality_accuracy": sum(
            row["quality_target"] == row["quality_prediction"] for row in accepted
        ) / count if count else 0.0,
    }


def select_thresholds(
    rows: list[dict[str, Any]], *, min_cultivar_accuracy: float, min_quality_accuracy: float
) -> dict[str, Any] | None:
    candidates = []
    for cultivar_percent in range(50, 100):
        for quality_percent in range(50, 100):
            result = evaluate_thresholds(
                rows, cultivar_percent / 100, quality_percent / 100
            )
            if (
                result["accepted"] > 0
                and result["cultivar_accuracy"] >= min_cultivar_accuracy
                and result["quality_accuracy"] >= min_quality_accuracy
            ):
                candidates.append(result)
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda value: (
            value["coverage"],
            -value["cultivar_threshold"],
            -value["quality_threshold"],
        ),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="두 신뢰도 기준 후보 탐색")
    parser.add_argument("predictions", nargs="+", type=Path)
    parser.add_argument("--min-cultivar-accuracy", type=float, required=True)
    parser.add_argument("--min-quality-accuracy", type=float, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    rows = []
    for path in args.predictions:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            rows.extend(csv.DictReader(stream))
    selected = select_thresholds(
        rows,
        min_cultivar_accuracy=args.min_cultivar_accuracy,
        min_quality_accuracy=args.min_quality_accuracy,
    )
    result = {
        "selection": selected,
        "requirements": {
            "min_cultivar_accuracy": args.min_cultivar_accuracy,
            "min_quality_accuracy": args.min_quality_accuracy,
        },
        "validation_groups": len(rows),
        "test_used": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"thresholds={args.output} selected={selected is not None}")
    return 0 if selected is not None else 2


if __name__ == "__main__":
    raise SystemExit(main())
