"""Prepare and explicitly run a final fit without touching the held-out Test split."""

from __future__ import annotations

import argparse
import json
import random
import statistics
from pathlib import Path
from typing import Any, Iterable

import torch
from torch.utils.data import DataLoader

from src.data.multiview import GroupRecord, MultiViewDataset, SUPPORTED_VIEW_COUNTS, load_groups
from src.data.torch_dataset import TorchMultiViewDataset

from .engine import run_epoch, save_checkpoint
from .models import MODEL_KINDS, build_model
from .train import checkpoint_sha256, resolve_device, write_json


DEFAULT_FOLDS = tuple(range(5))


def best_epoch_from_history(path: Path) -> int:
    history = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(history, list) or not history:
        raise ValueError(f"비어 있거나 잘못된 history입니다: {path}")
    try:
        best = max(history, key=lambda row: float(row["validation_score"]))
        epoch = int(best["epoch"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"epoch 또는 validation_score가 잘못되었습니다: {path}") from error
    if epoch <= 0:
        raise ValueError(f"best epoch는 1 이상이어야 합니다: {path}")
    return epoch


def select_final_epochs(
    training_root: Path,
    model_kind: str,
    views: int,
    folds: Iterable[int] = DEFAULT_FOLDS,
) -> tuple[int, list[int]]:
    best_epochs = [
        best_epoch_from_history(
            training_root / f"{model_kind}-{views}view-fold-{fold}" / "history.json"
        )
        for fold in folds
    ]
    if not best_epochs:
        raise ValueError("fold가 하나 이상 필요합니다")
    return int(statistics.median(best_epochs)), best_epochs


def development_groups(groups: Iterable[GroupRecord]) -> list[GroupRecord]:
    return [group for group in groups if group.split != "test"]


def set_reproducibility(seed: int) -> None:
    random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test 제외 전체 개발 데이터 최종 학습")
    parser.add_argument("--manifest", type=Path, default=Path("data/processed/manifest.csv"))
    parser.add_argument("--splits", type=Path, default=Path("configs/splits/seed-42.csv"))
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw"))
    parser.add_argument("--training-root", type=Path, default=Path("outputs/training"))
    parser.add_argument("--plan-output", type=Path, default=Path("outputs/final-fit-plan.json"))
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--model-kind", choices=MODEL_KINDS, default="separate")
    parser.add_argument("--views", type=int, choices=SUPPORTED_VIEW_COUNTS, default=12)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--image-size", type=int, default=224)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--no-pretrained", action="store_true")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="명시한 경우에만 Test 제외 전체 개발 데이터 학습을 실행합니다",
    )
    args = parser.parse_args(argv)
    if args.batch_size <= 0 or args.image_size <= 0:
        parser.error("batch-size와 image-size는 1 이상이어야 합니다")
    if args.workers != 0:
        parser.error("ZIP 핸들 안전성을 위해 현재 workers는 0만 지원합니다")
    if args.output_dir is None:
        args.output_dir = Path("outputs/final-training") / f"{args.model_kind}-{args.views}view"
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    epochs, fold_best_epochs = select_final_epochs(
        args.training_root, args.model_kind, args.views
    )
    plan = {
        "model_kind": args.model_kind,
        "views": args.views,
        "epoch_selection": "median_of_cv_best_epochs",
        "fold_best_epochs": fold_best_epochs,
        "epochs": epochs,
        "data_scope": "all_non_test_groups",
        "test_used": False,
        "output_dir": str(args.output_dir),
    }
    write_json(args.plan_output, plan)
    print(
        f"plan={args.plan_output} model={args.model_kind}/{args.views}view "
        f"fold_best_epochs={fold_best_epochs} epochs={epochs} execute={args.execute}"
    )
    if not args.execute:
        return 0
    if args.output_dir.exists():
        raise FileExistsError(f"기존 최종 학습 폴더를 덮어쓰지 않습니다: {args.output_dir}")

    set_reproducibility(args.seed)
    device = resolve_device(args.device)
    groups = development_groups(load_groups(args.manifest, args.splits))
    source = MultiViewDataset(groups, args.raw_root, args.views)
    if not source.groups:
        raise ValueError("Test 제외 개발 그룹이 비어 있습니다")

    config: dict[str, Any] = {
        **plan,
        "manifest": str(args.manifest),
        "splits": str(args.splits),
        "raw_root": str(args.raw_root),
        "batch_size": args.batch_size,
        "learning_rate": args.learning_rate,
        "weight_decay": args.weight_decay,
        "image_size": args.image_size,
        "seed": args.seed,
        "workers": args.workers,
        "device": str(device),
        "pretrained": not args.no_pretrained,
        "train_groups": len(source),
    }
    args.output_dir.mkdir(parents=True)
    write_json(args.output_dir / "config.json", config)
    generator = torch.Generator().manual_seed(args.seed)
    loader = DataLoader(
        TorchMultiViewDataset(source, training=True, image_size=args.image_size),
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=args.workers,
        pin_memory=device.type == "cuda",
        generator=generator,
    )
    model = build_model(args.model_kind, pretrained=not args.no_pretrained).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=args.learning_rate, weight_decay=args.weight_decay
    )
    history: list[dict[str, Any]] = []
    checkpoint_path = args.output_dir / "final.pt"
    try:
        for epoch in range(1, epochs + 1):
            train_metrics = run_epoch(model, loader, device, optimizer=optimizer)
            history.append({"epoch": epoch, "train": train_metrics})
            write_json(args.output_dir / "history.json", history)
            print(
                f"epoch={epoch}/{epochs} train_loss={train_metrics['loss']:.4f}",
                flush=True,
            )
        save_checkpoint(
            checkpoint_path,
            model=model,
            optimizer=optimizer,
            epoch=epochs,
            config=config,
            metrics=history[-1]["train"],
        )
    finally:
        source.close()

    summary = {
        "checkpoint": str(checkpoint_path),
        "checkpoint_sha256": checkpoint_sha256(checkpoint_path),
        "epochs_completed": len(history),
        "train_groups": len(groups),
        "test_used": False,
    }
    write_json(args.output_dir / "summary.json", summary)
    print(f"completed epochs={len(history)} checkpoint={checkpoint_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
