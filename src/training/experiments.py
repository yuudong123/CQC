"""Prepare or explicitly launch the complete DM-06 comparison matrix."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from src.data.multiview import SUPPORTED_VIEW_COUNTS

from .models import MODEL_KINDS


def build_plan(
    *,
    views: tuple[int, ...] = SUPPORTED_VIEW_COUNTS,
    folds: tuple[int, ...] = tuple(range(5)),
    model_kinds: tuple[str, ...] = MODEL_KINDS,
    epochs: int = 20,
    batch_size: int = 2,
) -> list[dict[str, Any]]:
    return [
        {
            "model_kind": model_kind,
            "views": view_count,
            "cv_fold": fold,
            "epochs": epochs,
            "batch_size": 1 if view_count == 40 else batch_size,
            "output_dir": str(
                Path("outputs/training")
                / f"{model_kind}-{view_count}view-fold-{fold}"
            ),
        }
        for model_kind in model_kinds
        for view_count in views
        for fold in folds
    ]


def command_for(run: dict[str, Any], device: str) -> list[str]:
    return [
        sys.executable,
        "-m",
        "src.training.train",
        "--model-kind",
        str(run["model_kind"]),
        "--views",
        str(run["views"]),
        "--cv-fold",
        str(run["cv_fold"]),
        "--epochs",
        str(run["epochs"]),
        "--batch-size",
        str(run["batch_size"]),
        "--device",
        device,
        "--output-dir",
        str(run["output_dir"]),
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="학습 비교 실험 계획 생성")
    parser.add_argument("--output", type=Path, default=Path("outputs/training-plan.json"))
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="명시한 경우에만 계획의 학습을 실제 실행합니다",
    )
    args = parser.parse_args(argv)
    plan = build_plan(epochs=args.epochs, batch_size=args.batch_size)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"plan={args.output} runs={len(plan)} execute={args.execute}")
    if not args.execute:
        return 0
    for index, run in enumerate(plan, 1):
        print(f"run={index}/{len(plan)} {run}", flush=True)
        subprocess.run(command_for(run, args.device), check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
