"""Export per-group validation probabilities for confidence-policy analysis."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import torch
from torch.utils.data import DataLoader

from src.data.multiview import CULTIVAR_CLASSES, QUALITY_CLASSES, MultiViewDataset, load_groups
from src.data.torch_dataset import TorchMultiViewDataset

from .evaluate import load_checkpoint
from .models import build_model
from .train import resolve_device


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="검증 fold 그룹별 확률 내보내기")
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--cv-fold", type=int, choices=range(5), required=True)
    parser.add_argument("--manifest", type=Path, default=Path("data/processed/manifest.csv"))
    parser.add_argument("--splits", type=Path, default=Path("configs/splits/seed-42.csv"))
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    args = parser.parse_args(argv)
    device = resolve_device(args.device)
    checkpoint = load_checkpoint(args.checkpoint, device)
    config = checkpoint["config"]
    groups = load_groups(args.manifest, args.splits)
    source = MultiViewDataset(
        groups,
        args.raw_root,
        int(config["views"]),
        cv_fold=args.cv_fold,
        cv_role="validation",
    )
    loader = DataLoader(
        TorchMultiViewDataset(source, training=False, image_size=int(config["image_size"])),
        batch_size=1,
        shuffle=False,
        num_workers=0,
    )
    model = build_model(str(config.get("model_kind", "joint")), pretrained=False).to(device)
    model.load_state_dict(checkpoint["model_state"])
    model.eval()
    rows = []
    try:
        with torch.inference_mode():
            for batch in loader:
                output = model(batch["images"].to(device), batch["view_mask"].to(device))
                cultivar = output["cultivar_logits"].softmax(dim=1)[0].cpu()
                quality = output["quality_logits"].softmax(dim=1)[0].cpu()
                cultivar_prediction = int(cultivar.argmax())
                quality_prediction = int(quality.argmax())
                rows.append(
                    {
                        "group_no": batch["group_no"][0],
                        "fold": args.cv_fold,
                        "cultivar_target": CULTIVAR_CLASSES[int(batch["cultivar_target"][0])],
                        "cultivar_prediction": CULTIVAR_CLASSES[cultivar_prediction],
                        "cultivar_confidence": float(cultivar[cultivar_prediction]),
                        "quality_target": QUALITY_CLASSES[int(batch["quality_target"][0])],
                        "quality_prediction": QUALITY_CLASSES[quality_prediction],
                        "quality_confidence": float(quality[quality_prediction]),
                    }
                )
    finally:
        source.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"predictions={args.output} groups={len(rows)} test_used=False")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
