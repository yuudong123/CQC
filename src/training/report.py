"""Build comparison tables and charts from completed experiment folders."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from .summarize import best_epoch


RUN_PATTERN = re.compile(r"^(joint|separate)-(4|8|12|16|40)view-fold-([0-4])$")


def collect_runs(root: Path) -> list[dict[str, Any]]:
    runs = []
    for directory in sorted(root.iterdir() if root.exists() else ()):
        match = RUN_PATTERN.fullmatch(directory.name)
        history_path = directory / "history.json"
        summary_path = directory / "summary.json"
        if not match or not history_path.exists() or not summary_path.exists():
            continue
        best = best_epoch(history_path)
        validation = best["validation"]
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        runs.append(
            {
                "model_kind": match.group(1),
                "views": int(match.group(2)),
                "fold": int(match.group(3)),
                "best_epoch": best["epoch"],
                "score": best["validation_score"],
                "cultivar_accuracy": validation["cultivar"]["accuracy"],
                "cultivar_macro_f1": validation["cultivar"]["macro_f1"],
                "quality_accuracy": validation["quality"]["accuracy"],
                "quality_macro_f1": validation["quality"]["macro_f1"],
                "checkpoint": summary["checkpoint"],
                "checkpoint_sha256": summary["checkpoint_sha256"],
            }
        )
    return runs


def aggregate_runs(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    import statistics

    grouped: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for run in runs:
        grouped[(run["model_kind"], run["views"])].append(run)
    rows = []
    metric_keys = (
        "score",
        "cultivar_accuracy",
        "cultivar_macro_f1",
        "quality_accuracy",
        "quality_macro_f1",
    )
    for (model_kind, views), folds in sorted(grouped.items()):
        row: dict[str, Any] = {
            "model_kind": model_kind,
            "views": views,
            "completed_folds": len(folds),
            "complete": len(folds) == 5,
        }
        for key in metric_keys:
            values = [float(fold[key]) for fold in folds]
            row[f"{key}_mean"] = statistics.mean(values)
            row[f"{key}_stdev"] = statistics.stdev(values) if len(values) > 1 else 0.0
        rows.append(row)
    return rows


def recommendation(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    complete = [row for row in rows if row["complete"]]
    if not complete:
        return None
    best = max(
        complete,
        key=lambda row: (
            row["score_mean"],
            row["quality_macro_f1_mean"],
            -row["views"],
            row["model_kind"] == "joint",
        ),
    )
    return {
        "status": "provisional",
        "reason": "5-fold 정확도 기준 임시 후보이며 CPU 지연시간 비교 후 확정",
        "model_kind": best["model_kind"],
        "views": best["views"],
        "score_mean": best["score_mean"],
        "score_stdev": best["score_stdev"],
        "test_used": False,
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_chart(path: Path, rows: list[dict[str, Any]]) -> None:
    import matplotlib.pyplot as plt

    complete = [row for row in rows if row["complete"]]
    labels = [f"{row['model_kind']}\n{row['views']} views" for row in complete]
    values = [row["score_mean"] for row in complete]
    errors = [row["score_stdev"] for row in complete]
    path.parent.mkdir(parents=True, exist_ok=True)
    figure, axis = plt.subplots(figsize=(10, 5))
    axis.bar(labels, values, yerr=errors, capsize=4, color="#4C78A8")
    axis.set_ylim(0, 1)
    axis.set_ylabel("Mean Macro F1")
    axis.set_title("Model and view-count comparison (5-fold CV)")
    axis.grid(axis="y", alpha=0.25)
    figure.tight_layout()
    figure.savefig(path, dpi=160)
    plt.close(figure)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="전체 학습 결과 비교 보고서 생성")
    parser.add_argument("--root", type=Path, default=Path("outputs/training"))
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/comparison"))
    parser.add_argument("--chart", action="store_true")
    args = parser.parse_args(argv)
    runs = collect_runs(args.root)
    rows = aggregate_runs(runs)
    result = {
        "completed_runs": len(runs),
        "expected_runs": 50,
        "experiments": rows,
        "recommendation": recommendation(rows),
        "test_used": False,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "comparison.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_csv(args.output_dir / "comparison.csv", rows)
    if args.chart:
        write_chart(args.output_dir / "comparison.png", rows)
    print(f"runs={len(runs)}/50 report={args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
