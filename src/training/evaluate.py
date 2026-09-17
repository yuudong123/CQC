"""Evaluate a selected checkpoint; final test requires an explicit confirmation token."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import torch
from torch.utils.data import DataLoader

from src.data.multiview import MultiViewDataset, load_groups
from src.data.torch_dataset import TorchMultiViewDataset

from .engine import run_epoch
from .models import build_model
from .train import resolve_device, write_json


FINAL_TEST_CONFIRMATION = "RUN_FINAL_TEST_ONCE"


def load_checkpoint(path: Path, device: torch.device) -> dict[str, Any]:
    checkpoint = torch.load(path, map_location=device, weights_only=False)
    required = {"model_state", "config", "epoch", "metrics"}
    missing = required - set(checkpoint)
    if missing:
        raise ValueError(f"체크포인트 필드 누락: {sorted(missing)}")
    return checkpoint


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="선정 모델 평가")
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=Path("data/processed/manifest.csv"))
    parser.add_argument("--splits", type=Path, default=Path("configs/splits/seed-42.csv"))
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--confirm-final-test", default="")
    args = parser.parse_args(argv)
    if args.confirm_final_test != FINAL_TEST_CONFIRMATION:
        parser.error(
            "최종 Test 평가는 모델 선정 후 확인 문자열 "
            f"{FINAL_TEST_CONFIRMATION!r}가 있어야 실행됩니다"
        )

    device = resolve_device(args.device)
    checkpoint = load_checkpoint(args.checkpoint, device)
    config = checkpoint["config"]
    groups = load_groups(args.manifest, args.splits)
    source = MultiViewDataset(
        groups, args.raw_root, int(config["views"]), split="test"
    )
    dataset = TorchMultiViewDataset(
        source, training=False, image_size=int(config["image_size"])
    )
    loader = DataLoader(dataset, batch_size=args.batch_size, shuffle=False, num_workers=0)
    model = build_model(
        str(config.get("model_kind", "joint")), pretrained=False
    ).to(device)
    model.load_state_dict(checkpoint["model_state"])
    try:
        metrics = run_epoch(model, loader, device)
    finally:
        source.close()
    result = {
        "checkpoint": str(args.checkpoint),
        "checkpoint_epoch": checkpoint["epoch"],
        "config": config,
        "test": metrics,
        "test_used": True,
    }
    write_json(args.output, result)
    print(f"test_result={args.output} samples={metrics['samples']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
