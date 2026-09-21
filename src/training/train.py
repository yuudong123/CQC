"""Command-line training entrypoint for the masked multi-view baseline."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path
from typing import Any

import torch
from torch.utils.data import DataLoader

from src.data.multiview import MultiViewDataset, SUPPORTED_VIEW_COUNTS, load_groups
from src.data.torch_dataset import TorchMultiViewDataset
from .engine import QUALITY_LOSS_KINDS, run_epoch, save_checkpoint
from .models import MODEL_KINDS, build_model


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="다각도 MobileNetV3 기준선 학습")
    parser.add_argument("--manifest", type=Path, default=Path("data/processed/manifest.csv"))
    parser.add_argument("--splits", type=Path, default=Path("configs/splits/seed-42.csv"))
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw"))
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--model-kind", choices=MODEL_KINDS, default="joint")
    parser.add_argument("--views", type=int, choices=SUPPORTED_VIEW_COUNTS, default=8)
    parser.add_argument("--cv-fold", type=int, default=0)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--dropout", type=float, default=0.2)
    parser.add_argument("--quality-loss", choices=QUALITY_LOSS_KINDS, default="cross_entropy")
    parser.add_argument("--focal-gamma", type=float, default=2.0)
    parser.add_argument("--ordinal-weight", type=float, default=0.25)
    parser.add_argument("--validation-scheme", choices=("cv", "source"), default="cv")
    parser.add_argument(
        "--view-sampling",
        choices=("fixed", "angle_balanced_random"),
        default="fixed",
    )
    parser.add_argument("--image-size", type=int, default=224)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--no-pretrained", action="store_true")
    args = parser.parse_args(argv)
    if args.epochs <= 0 or args.batch_size <= 0 or args.image_size <= 0:
        parser.error("epochs, batch-size, image-size는 1 이상이어야 합니다")
    if not 0 <= args.dropout < 1 or args.focal_gamma < 0 or args.ordinal_weight < 0:
        parser.error("dropout은 0~1 미만, focal-gamma와 ordinal-weight는 0 이상이어야 합니다")
    if args.workers != 0:
        parser.error("ZIP 핸들 안전성을 위해 현재 workers는 0만 지원합니다")
    if args.output_dir is None:
        suffix = f"fold-{args.cv_fold}" if args.validation_scheme == "cv" else "source"
        args.output_dir = Path("outputs/training") / f"{args.model_kind}-{args.views}view-{suffix}"
    return args


def set_reproducibility(seed: int) -> None:
    random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def resolve_device(requested: str) -> torch.device:
    if requested == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA를 요청했지만 사용할 수 없습니다")
    if requested == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return torch.device(requested)


def validation_score(metrics: dict[str, Any]) -> float:
    return (
        float(metrics["cultivar"]["macro_f1"])
        + float(metrics["quality"]["macro_f1"])
    ) / 2


def checkpoint_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def select_development_groups(
    groups: list[Any], *, validation_scheme: str, cv_fold: int
) -> tuple[list[Any], list[Any]]:
    development = [group for group in groups if group.split != "test"]
    if validation_scheme == "cv":
        return (
            [group for group in development if group.cv_fold != cv_fold],
            [group for group in development if group.cv_fold == cv_fold],
        )
    if validation_scheme == "source":
        return (
            [group for group in development if group.original_split == "train"],
            [group for group in development if group.original_split == "validation"],
        )
    raise ValueError(f"지원하지 않는 validation_scheme입니다: {validation_scheme}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    set_reproducibility(args.seed)
    device = resolve_device(args.device)
    groups = load_groups(args.manifest, args.splits)
    train_groups, validation_groups = select_development_groups(
        groups, validation_scheme=args.validation_scheme, cv_fold=args.cv_fold
    )
    train_source = MultiViewDataset(
        train_groups,
        args.raw_root,
        args.views,
        sampling=args.view_sampling,
        sampling_seed=args.seed,
    )
    validation_source = MultiViewDataset(validation_groups, args.raw_root, args.views)
    if not train_source.groups or not validation_source.groups:
        raise ValueError("선택한 CV fold의 학습 또는 검증 그룹이 비어 있습니다")

    config = {
        "manifest": str(args.manifest),
        "splits": str(args.splits),
        "raw_root": str(args.raw_root),
        "views": args.views,
        "model_kind": args.model_kind,
        "cv_fold": args.cv_fold,
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "learning_rate": args.learning_rate,
        "weight_decay": args.weight_decay,
        "dropout": args.dropout,
        "quality_loss": args.quality_loss,
        "focal_gamma": args.focal_gamma,
        "ordinal_weight": args.ordinal_weight,
        "validation_scheme": args.validation_scheme,
        "view_sampling": args.view_sampling,
        "image_size": args.image_size,
        "seed": args.seed,
        "workers": args.workers,
        "device": str(device),
        "pretrained": not args.no_pretrained,
        "train_groups": len(train_source),
        "validation_groups": len(validation_source),
        "test_used": False,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_json(args.output_dir / "config.json", config)

    generator = torch.Generator().manual_seed(args.seed)
    train_loader = DataLoader(
        TorchMultiViewDataset(train_source, training=True, image_size=args.image_size),
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=args.workers,
        pin_memory=device.type == "cuda",
        generator=generator,
    )
    validation_loader = DataLoader(
        TorchMultiViewDataset(validation_source, training=False, image_size=args.image_size),
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.workers,
        pin_memory=device.type == "cuda",
    )
    model = build_model(
        args.model_kind, pretrained=not args.no_pretrained, dropout=args.dropout
    ).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=args.learning_rate, weight_decay=args.weight_decay
    )
    history: list[dict[str, Any]] = []
    best_score = -1.0
    checkpoint_path = args.output_dir / "best.pt"
    try:
        for epoch in range(1, args.epochs + 1):
            train_source.set_epoch(epoch)
            loss_options = {
                "quality_loss_kind": args.quality_loss,
                "focal_gamma": args.focal_gamma,
                "ordinal_weight": args.ordinal_weight,
            }
            train_metrics = run_epoch(
                model, train_loader, device, optimizer=optimizer, **loss_options
            )
            validation_metrics = run_epoch(model, validation_loader, device, **loss_options)
            score = validation_score(validation_metrics)
            epoch_result = {
                "epoch": epoch,
                "train": train_metrics,
                "validation": validation_metrics,
                "validation_score": score,
            }
            history.append(epoch_result)
            write_json(args.output_dir / "history.json", history)
            if score > best_score:
                best_score = score
                save_checkpoint(
                    checkpoint_path,
                    model=model,
                    optimizer=optimizer,
                    epoch=epoch,
                    config=config,
                    metrics=validation_metrics,
                )
            print(
                f"epoch={epoch}/{args.epochs} train_loss={train_metrics['loss']:.4f} "
                f"validation_loss={validation_metrics['loss']:.4f} "
                f"validation_score={score:.4f}",
                flush=True,
            )
    finally:
        train_source.close()
        validation_source.close()

    summary = {
        "best_validation_score": best_score,
        "checkpoint": str(checkpoint_path),
        "checkpoint_sha256": checkpoint_sha256(checkpoint_path),
        "epochs_completed": len(history),
        "test_used": False,
    }
    write_json(args.output_dir / "summary.json", summary)
    print(
        f"completed epochs={len(history)} best_validation_score={best_score:.4f} "
        f"checkpoint={checkpoint_path}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
