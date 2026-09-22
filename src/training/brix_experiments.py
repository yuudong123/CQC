"""Prepare a development-only 12-view baseline versus virtual-Brix experiment."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from .improvement_experiments import VARIANTS


MODEL_KINDS = ("separate", "separate_brix")


def build_plan(
    *,
    epochs: int = 25,
    batch_size: int = 2,
    variants: tuple[str, ...] = tuple(VARIANTS),
    model_kinds: tuple[str, ...] = MODEL_KINDS,
    root: Path = Path("outputs/training-brix-v1"),
) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for model_kind in model_kinds:
        for variant in variants:
            settings = VARIANTS[variant]
            for validation_scheme, folds in (("cv", range(5)), ("source", range(1))):
                for fold in folds:
                    suffix = f"cv-fold-{fold}" if validation_scheme == "cv" else "source"
                    runs.append(
                        {
                            "model_kind": model_kind,
                            "variant": variant,
                            "validation_scheme": validation_scheme,
                            "cv_fold": fold,
                            "views": 12,
                            "epochs": epochs,
                            "batch_size": batch_size,
                            "output_dir": str(root / model_kind / f"{variant}-{suffix}"),
                            "test_used": False,
                            **settings,
                        }
                    )
    return runs


def command_for(run: dict[str, Any], device: str, virtual_brix: Path) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "src.training.train",
        "--model-kind",
        str(run["model_kind"]),
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
    if run["model_kind"] == "separate_brix":
        command.extend(("--virtual-brix", str(virtual_brix)))
    return command


def run_is_complete(run: dict[str, Any]) -> bool:
    summary_path = Path(str(run["output_dir"])) / "summary.json"
    if not summary_path.is_file():
        return False
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        return int(summary.get("epochs_completed", 0)) >= int(run["epochs"])
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="대표 12장 가상 당도 A/B 실험 계획")
    parser.add_argument(
        "--virtual-brix",
        type=Path,
        default=Path("data/processed/virtual-brix.csv"),
    )
    parser.add_argument("--root", type=Path, default=Path("outputs/training-brix-v1"))
    parser.add_argument("--output", type=Path, default=Path("outputs/training-brix-v1-plan.json"))
    parser.add_argument("--epochs", type=int, default=25)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--variants", nargs="+", choices=tuple(VARIANTS), default=list(VARIANTS))
    parser.add_argument("--models", nargs="+", choices=MODEL_KINDS, default=list(MODEL_KINDS))
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--rerun-completed", action="store_true")
    args = parser.parse_args(argv)
    plan = build_plan(
        epochs=args.epochs,
        batch_size=args.batch_size,
        variants=tuple(args.variants),
        model_kinds=tuple(args.models),
        root=args.root,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"plan={args.output} runs={len(plan)} views=12 execute={args.execute}")
    if not args.execute:
        return 0
    if "separate_brix" in args.models and not args.virtual_brix.is_file():
        parser.error(f"가상 당도 CSV가 없습니다: {args.virtual_brix}")
    for index, run in enumerate(plan, 1):
        if not args.rerun_completed and run_is_complete(run):
            print(f"run={index}/{len(plan)} status=skip_completed output={run['output_dir']}", flush=True)
            continue
        print(
            f"run={index}/{len(plan)} model={run['model_kind']} "
            f"variant={run['variant']} scheme={run['validation_scheme']}",
            flush=True,
        )
        subprocess.run(command_for(run, args.device, args.virtual_brix), check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
