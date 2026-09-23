"""Prepare angle-balanced random-sampling runs from the selected v2 variant."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from src.training.improvement_experiments import VARIANTS


def build_plan(
    variant: str,
    epoch: int,
    *,
    batch_size: int = 2,
) -> list[dict[str, Any]]:
    if variant not in VARIANTS:
        raise ValueError(f"지원하지 않는 v2 variant입니다: {variant}")
    if epoch <= 0:
        raise ValueError("epoch는 1 이상이어야 합니다")
    settings = VARIANTS[variant]
    runs = []
    for fold in range(5):
        runs.append(
            {
                "variant": variant,
                "validation_scheme": "cv",
                "cv_fold": fold,
                "epochs": epoch,
                "batch_size": batch_size,
                "view_sampling": "angle_balanced_random",
                "output_dir": str(
                    Path("outputs/training-sampling") / f"{variant}-cv-fold-{fold}"
                ),
                **settings,
            }
        )
    runs.append(
        {
            "variant": variant,
            "validation_scheme": "source",
            "cv_fold": 0,
            "epochs": epoch,
            "batch_size": batch_size,
            "view_sampling": "angle_balanced_random",
            "output_dir": str(Path("outputs/training-sampling") / f"{variant}-source"),
            **settings,
        }
    )
    return runs


def plan_from_v2_report(report_path: Path, *, batch_size: int = 2) -> list[dict[str, Any]]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    selection = report.get("selection")
    if not isinstance(selection, dict):
        raise ValueError("v2 보고서에 selection이 없습니다")
    if report.get("test_used") is not False or selection.get("test_used") is not False:
        raise ValueError("Test를 사용한 v2 보고서는 샘플링 실험 계획에 사용할 수 없습니다")
    return build_plan(
        str(selection["variant"]), int(selection["epoch"]), batch_size=batch_size
    )


def command_for(run: dict[str, Any], device: str) -> list[str]:
    return [
        sys.executable,
        "-m",
        "src.training.train",
        "--model-kind",
        "separate",
        "--views",
        "12",
        "--view-sampling",
        "angle_balanced_random",
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="각도 균형 랜덤 12장 후속 실험")
    parser.add_argument(
        "--v2-report", type=Path, default=Path("outputs/training-v2-report.json")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("outputs/training-sampling-plan.json")
    )
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--variant", choices=tuple(VARIANTS))
    parser.add_argument("--epoch", type=int)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if (args.variant is None) != (args.epoch is None):
        parser.error("--variant와 --epoch는 함께 지정해야 합니다")
    plan = (
        build_plan(args.variant, args.epoch, batch_size=args.batch_size)
        if args.variant is not None else
        plan_from_v2_report(args.v2_report, batch_size=args.batch_size)
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"plan={args.output} runs={len(plan)} execute={args.execute}")
    if not args.execute:
        return 0
    for index, run in enumerate(plan, 1):
        print(
            f"run={index}/{len(plan)} variant={run['variant']} "
            f"scheme={run['validation_scheme']}",
            flush=True,
        )
        subprocess.run(command_for(run, args.device), check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
