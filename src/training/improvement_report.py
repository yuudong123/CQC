"""Select a robust v2 variant from development-only CV and source holdout histories."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any

from .improvement_experiments import VARIANTS


def read_history(path: Path) -> list[dict[str, Any]]:
    history = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(history, list) or not history:
        raise ValueError(f"잘못된 history입니다: {path}")
    return history


def evaluate_variant(root: Path, variant: str) -> list[dict[str, Any]]:
    cv_histories = [
        read_history(root / f"{variant}-cv-fold-{fold}" / "history.json")
        for fold in range(5)
    ]
    source_history = read_history(root / f"{variant}-source" / "history.json")
    common_epochs = set.intersection(
        *[{int(row["epoch"]) for row in history} for history in [*cv_histories, source_history]]
    )
    rows = []
    for epoch in sorted(common_epochs):
        cv = [next(row for row in history if int(row["epoch"]) == epoch) for history in cv_histories]
        source = next(row for row in source_history if int(row["epoch"]) == epoch)
        quality_values = [float(row["validation"]["quality"]["macro_f1"]) for row in cv]
        cultivar_values = [float(row["validation"]["cultivar"]["macro_f1"]) for row in cv]
        m_recalls = [float(row["validation"]["quality"]["recall"][1]) for row in cv]
        source_quality = float(source["validation"]["quality"]["macro_f1"])
        source_cultivar = float(source["validation"]["cultivar"]["macro_f1"])
        rows.append(
            {
                "variant": variant,
                "epoch": epoch,
                "cv_quality_macro_f1_mean": statistics.mean(quality_values),
                "cv_quality_macro_f1_stdev": statistics.stdev(quality_values),
                "cv_quality_macro_f1_worst": min(quality_values),
                "cv_cultivar_macro_f1_mean": statistics.mean(cultivar_values),
                "cv_m_recall_mean": statistics.mean(m_recalls),
                "cv_m_recall_worst": min(m_recalls),
                "source_quality_macro_f1": source_quality,
                "source_cultivar_macro_f1": source_cultivar,
                "robust_quality_score": min(min(quality_values), source_quality),
                "test_used": False,
            }
        )
    return rows


def recommend(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    eligible = [
        row
        for row in rows
        if row["cv_cultivar_macro_f1_mean"] >= 0.95
        and row["source_cultivar_macro_f1"] >= 0.90
    ]
    if not eligible:
        return None
    return max(
        eligible,
        key=lambda row: (
            row["robust_quality_score"],
            row["cv_quality_macro_f1_mean"],
            row["cv_m_recall_worst"],
            -row["epoch"],
        ),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="v2 개발 데이터 강건성 비교")
    parser.add_argument("--root", type=Path, default=Path("outputs/training-v2"))
    parser.add_argument("--output", type=Path, default=Path("outputs/training-v2-report.json"))
    args = parser.parse_args(argv)
    rows = [row for variant in VARIANTS for row in evaluate_variant(args.root, variant)]
    result = {"selection": recommend(rows), "candidates": rows, "test_used": False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"report={args.output} selection={result['selection'] is not None}")
    return 0 if result["selection"] is not None else 2


if __name__ == "__main__":
    raise SystemExit(main())
