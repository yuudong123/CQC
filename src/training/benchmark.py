"""Measure checkpoint inference latency on validation groups without using test."""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

import torch

from src.data.multiview import MultiViewDataset, load_groups
from src.data.torch_dataset import TorchMultiViewDataset

from .evaluate import load_checkpoint
from .models import build_model
from .train import resolve_device, write_json


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * fraction)))
    return ordered[index]


def synchronize(device: torch.device) -> None:
    if device.type == "cuda":
        torch.cuda.synchronize(device)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="검증 그룹 추론시간 측정")
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=Path("data/processed/manifest.csv"))
    parser.add_argument("--splits", type=Path, default=Path("configs/splits/seed-42.csv"))
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--repeats", type=int, default=50)
    args = parser.parse_args(argv)
    if args.warmup < 0 or args.repeats <= 0:
        parser.error("warmup은 0 이상, repeats는 1 이상이어야 합니다")

    device = resolve_device(args.device)
    checkpoint = load_checkpoint(args.checkpoint, device)
    config = checkpoint["config"]
    groups = load_groups(args.manifest, args.splits)
    source = MultiViewDataset(
        groups, args.raw_root, int(config["views"]), cv_fold=0, cv_role="validation"
    )
    dataset = TorchMultiViewDataset(
        source, training=False, image_size=int(config["image_size"])
    )
    model = build_model(
        str(config.get("model_kind", "joint")), pretrained=False
    ).to(device)
    model.load_state_dict(checkpoint["model_state"])
    model.eval()
    item = dataset[0]
    images = item["images"].unsqueeze(0).to(device)
    mask = item["view_mask"].unsqueeze(0).to(device)
    try:
        with torch.inference_mode():
            for _ in range(args.warmup):
                model(images, mask)
            synchronize(device)
            timings = []
            for _ in range(args.repeats):
                started = time.perf_counter()
                model(images, mask)
                synchronize(device)
                timings.append((time.perf_counter() - started) * 1000)
    finally:
        source.close()
    result = {
        "checkpoint": str(args.checkpoint),
        "device": str(device),
        "views": config["views"],
        "repeats": args.repeats,
        "mean_ms": statistics.mean(timings),
        "max_ms": max(timings),
        "p95_ms": percentile(timings, 0.95),
        "test_used": False,
    }
    write_json(args.output, result)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
