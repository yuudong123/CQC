"""Prepare the CQC v2 quality-improvement experiment matrix without using Test."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


VARIANTS: dict[str, dict[str, Any]] = {
    "ce_regularized": {
        "quality_loss": "cross_entropy",
        "dropout": 0.4,
        "learning_rate": 3e-4,
        "weight_decay": 5e-4,
    },
    "focal_regularized": {
        "quality_loss": "focal",
        "dropout": 0.4,
        "learning_rate": 3e-4,
        "weight_decay": 5e-4,
        "focal_gamma": 2.0,
    },
    "ordinal_regularized": {
        "quality_loss": "ordinal",
        "dropout": 0.4,
        "learning_rate": 3e-4,
        "weight_decay": 5e-4,
        "ordinal_weight": 0.25,
    },
    "focal_ordinal_regularized": {
        "quality_loss": "focal_ordinal",
        "dropout": 0.4,
        "learning_rate": 3e-4,
        "weight_decay": 5e-4,
        "focal_gamma": 2.0,
        "ordinal_weight": 0.25,
    },
}


def build_plan(*, epochs: int = 25, batch_size: int = 2) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for variant, settings in VARIANTS.items():
        for fold in range(5):
            runs.append(
                {
                    "variant": variant,
                    "validation_scheme": "cv",
                    "cv_fold": fold,
                    "epochs": epochs,
                    "batch_size": batch_size,
                    "output_dir": str(Path("outputs/training-v2") / f"{variant}-cv-fold-{fold}"),
                    **settings,
                }
            )
        runs.append(
            {
                "variant": variant,
                "validation_scheme": "source",
                "cv_fold": 0,
                "epochs": epochs,
                "batch_size": batch_size,
                "output_dir": str(Path("outputs/training-v2") / f"{variant}-source"),
                **settings,
            }
        )
    return runs


def command_for(run: dict[str, Any], device: str) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "src.training.train",
        "--model-kind",
        "separate",
        "--views",
        "12",
        "--validation-scheme",
        str(run["validation_scheme"]),
        "--cv-fold",
        str(run["cv_fold"]),
        "--epochs",
        str(run["epochs"]),
        "--batch-size",
        str(run["batch_size"]),
        "--quality-loss",
        str(run["quality_loss"]),
        "--dropout",
        str(run["dropout"]),
        "--learning-rate",
        str(run["learning_rate"]),
        "--weight-decay",
        str(run["weight_decay"]),
        "--focal-gamma",
        str(run.get("focal_gamma", 2.0)),
        "--ordinal-weight",
        str(run.get("ordinal_weight", 0.25)),
        "--device",
        device,
        "--output-dir",
        str(run["output_dir"]),
    ]
    return command


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="v2 품질 개선 실험 계획")
    parser.add_argument("--output", type=Path, default=Path("outputs/training-v2-plan.json"))
    parser.add_argument("--epochs", type=int, default=25)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    plan = build_plan(epochs=args.epochs, batch_size=args.batch_size)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"plan={args.output} runs={len(plan)} execute={args.execute}")
    if not args.execute:
        return 0
    for index, run in enumerate(plan, 1):
        print(f"run={index}/{len(plan)} variant={run['variant']} scheme={run['validation_scheme']}", flush=True)
        subprocess.run(command_for(run, args.device), check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
