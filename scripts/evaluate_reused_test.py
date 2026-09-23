"""Descriptive regression check on the already used 27-group Test split.

This output is never an independent final approval or a model-selection score.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import torch
from torch.utils.data import DataLoader

from src.data.multiview import MultiViewDataset, load_groups
from src.data.torch_dataset import TorchMultiViewDataset
from src.data.virtual_brix import load_virtual_brix
from src.training.engine import run_epoch
from src.training.evaluate import load_checkpoint
from src.training.models import build_model
from src.training.train import resolve_device, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--manifest", type=Path, default=Path("data/processed/manifest.csv"))
    parser.add_argument("--splits", type=Path, default=Path("configs/splits/seed-42.csv"))
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw"))
    parser.add_argument("--virtual-brix", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"기존 평가 파일을 덮어쓰지 않습니다: {args.output}")
    device = resolve_device(args.device)
    checkpoint = load_checkpoint(args.checkpoint, device)
    config = checkpoint["config"]
    if (config["model_kind"] == "separate_brix") != (args.virtual_brix is not None):
        parser.error("separate_brix requires --virtual-brix; image-only models must omit it")
    virtual_brix = load_virtual_brix(args.virtual_brix) if args.virtual_brix else None
    source = MultiViewDataset(
        load_groups(args.manifest, args.splits), args.raw_root,
        int(config["views"]), split="test",
    )
    loader = DataLoader(
        TorchMultiViewDataset(source, training=False, image_size=int(config["image_size"]), virtual_brix=virtual_brix),
        batch_size=2, shuffle=False, num_workers=0,
    )
    model = build_model(str(config["model_kind"]), pretrained=False).to(device)
    model.load_state_dict(checkpoint["model_state"])
    try:
        metrics = run_epoch(model, loader, device, include_predictions=True)
    finally:
        source.close()
    write_json(args.output, {
        "evaluation_role": "reused_test_regression_diagnostic",
        "independent_final_approval": False,
        "may_select_model_or_epoch": False,
        "prior_test_usage": "v1 final evaluation and failure analysis",
        "checkpoint": str(args.checkpoint),
        "checkpoint_epoch": checkpoint["epoch"],
        "virtual_brix": str(args.virtual_brix) if args.virtual_brix else None,
        "brix_is_measured": False if args.virtual_brix else None,
        "config": config,
        "test": metrics,
    })
    print(f"regression_result={args.output} samples={metrics['samples']} "
          f"quality_macro_f1={metrics['quality']['macro_f1']:.6f}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
