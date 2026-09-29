"""검증 입력으로 순차·동시 추론의 지연시간과 처리량을 비교한다."""

from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import torch

from src.data.multiview import MultiViewDataset, load_groups
from src.data.torch_dataset import TorchMultiViewDataset

from .benchmark import percentile, synchronize
from .evaluate import load_checkpoint
from .models import build_model
from .train import resolve_device, write_json


def main(argv: list[str] | None = None) -> int:
    """실행 인자를 읽고 다음 작업을 수행한다: 검증 입력으로 순차·동시 추론의 지연시간과 처리량을 비교한다."""
    parser = argparse.ArgumentParser(description="순차·병렬 추론시간 비교")
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=Path("data/processed/manifest.csv"))
    parser.add_argument("--splits", type=Path, default=Path("configs/splits/seed-42.csv"))
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--concurrency", type=int, nargs="+", default=(1, 2, 4))
    parser.add_argument("--repeats", type=int, default=50)
    parser.add_argument("--torch-threads", type=int, default=1)
    args = parser.parse_args(argv)
    if args.repeats <= 0 or args.torch_threads <= 0 or any(value <= 0 for value in args.concurrency):
        parser.error("repeats, torch-threads, concurrency는 1 이상이어야 합니다")
    torch.set_num_threads(args.torch_threads)
    device = resolve_device(args.device)
    checkpoint = load_checkpoint(args.checkpoint, device)
    config = checkpoint["config"]
    groups = load_groups(args.manifest, args.splits)
    source = MultiViewDataset(
        groups, args.raw_root, int(config["views"]), cv_fold=0, cv_role="validation"
    )
    dataset = TorchMultiViewDataset(source, training=False, image_size=int(config["image_size"]))
    model = build_model(str(config.get("model_kind", "joint")), pretrained=False).to(device)
    model.load_state_dict(checkpoint["model_state"])
    model.eval()
    item = dataset[0]
    images = item["images"].unsqueeze(0).to(device)
    mask = item["view_mask"].unsqueeze(0).to(device)

    def infer_once() -> float:
        """동시 실행에 사용할 모델 추론 한 번의 경과 시간을 측정한다."""
        started = time.perf_counter()
        with torch.inference_mode():
            model(images, mask)
        synchronize(device)
        return (time.perf_counter() - started) * 1000

    results = []
    try:
        for workers in args.concurrency:
            infer_once()
            wall_started = time.perf_counter()
            with ThreadPoolExecutor(max_workers=workers) as executor:
                timings = list(executor.map(lambda _: infer_once(), range(args.repeats)))
            wall_seconds = time.perf_counter() - wall_started
            results.append(
                {
                    "concurrency": workers,
                    "requests": args.repeats,
                    "mean_ms": statistics.mean(timings),
                    "max_ms": max(timings),
                    "p95_ms": percentile(timings, 0.95),
                    "throughput_per_second": args.repeats / wall_seconds,
                    "meets_500ms": percentile(timings, 0.95) <= 500,
                    "meets_2_per_second": args.repeats / wall_seconds >= 2,
                }
            )
    finally:
        source.close()
    report = {
        "checkpoint": str(args.checkpoint),
        "device": str(device),
        "cpu": platform.processor() or "unknown",
        "logical_cpu_count": os.cpu_count(),
        "platform": platform.platform(),
        "views": config["views"],
        "torch_threads": args.torch_threads,
        "results": results,
        "test_used": False,
    }
    write_json(args.output, report)
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
