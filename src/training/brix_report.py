"""Compare 12-view image-only and virtual-Brix late-fusion development results."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .brix_experiments import MODEL_KINDS
from .improvement_experiments import VARIANTS
from .improvement_report import evaluate_variant, recommend


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="대표 12장 가상 당도 A/B 결과 비교")
    parser.add_argument("--root", type=Path, default=Path("outputs/training-brix-v1"))
    parser.add_argument("--output", type=Path, default=Path("outputs/training-brix-v1-report.json"))
    args = parser.parse_args(argv)

    candidates: dict[str, list[dict[str, Any]]] = {}
    selections: dict[str, dict[str, Any] | None] = {}
    for model_kind in MODEL_KINDS:
        rows = [
            {**row, "model_kind": model_kind, "views": 12}
            for variant in VARIANTS
            for row in evaluate_variant(args.root / model_kind, variant)
        ]
        candidates[model_kind] = rows
        selections[model_kind] = recommend(rows)

    baseline = selections["separate"]
    fusion = selections["separate_brix"]
    comparison = None
    if baseline is not None and fusion is not None:
        comparison = {
            "baseline_robust_quality_score": baseline["robust_quality_score"],
            "fusion_robust_quality_score": fusion["robust_quality_score"],
            "fusion_delta": fusion["robust_quality_score"] - baseline["robust_quality_score"],
            "recommended_model_kind": (
                "separate_brix"
                if fusion["robust_quality_score"] > baseline["robust_quality_score"]
                else "separate"
            ),
            "interpretation": "demo_rgb_proxy_only_not_measured_brix",
        }
    result = {
        "views": 12,
        "selections": selections,
        "comparison": comparison,
        "candidates": candidates,
        "brix_source": "simulated_rgb_proxy",
        "brix_is_measured": False,
        "test_used": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"report={args.output} comparison={comparison is not None}")
    return 0 if comparison is not None else 2


if __name__ == "__main__":
    raise SystemExit(main())
