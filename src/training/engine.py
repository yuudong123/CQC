"""Reusable multi-task training loop and dependency-free classification metrics."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import torch
from torch import Tensor, nn


def confusion_matrix(targets: Tensor, predictions: Tensor, classes: int) -> Tensor:
    targets = targets.detach().to(dtype=torch.long, device="cpu")
    predictions = predictions.detach().to(dtype=torch.long, device="cpu")
    if targets.shape != predictions.shape:
        raise ValueError("targets와 predictions 크기가 다릅니다")
    if classes <= 1:
        raise ValueError("classes는 2 이상이어야 합니다")
    if torch.any(targets < 0) or torch.any(targets >= classes):
        raise ValueError("targets에 클래스 범위 밖 값이 있습니다")
    if torch.any(predictions < 0) or torch.any(predictions >= classes):
        raise ValueError("predictions에 클래스 범위 밖 값이 있습니다")
    indices = targets * classes + predictions
    return torch.bincount(indices, minlength=classes * classes).reshape(classes, classes)


def classification_metrics(matrix: Tensor) -> dict[str, Any]:
    matrix = matrix.to(dtype=torch.float64, device="cpu")
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError("혼동행렬은 정사각 행렬이어야 합니다")
    true_positive = matrix.diag()
    precision_denominator = matrix.sum(dim=0)
    recall_denominator = matrix.sum(dim=1)
    precision = torch.where(precision_denominator > 0, true_positive / precision_denominator, 0)
    recall = torch.where(recall_denominator > 0, true_positive / recall_denominator, 0)
    f1_denominator = precision + recall
    f1 = torch.where(f1_denominator > 0, 2 * precision * recall / f1_denominator, 0)
    total = matrix.sum()
    accuracy = (true_positive.sum() / total).item() if total > 0 else 0.0
    return {
        "accuracy": accuracy,
        "macro_f1": f1.mean().item(),
        "precision": precision.tolist(),
        "recall": recall.tolist(),
        "f1": f1.tolist(),
        "confusion_matrix": matrix.to(dtype=torch.long).tolist(),
    }


def _move(batch: Mapping[str, Any], key: str, device: torch.device) -> Tensor:
    value = batch[key]
    if not isinstance(value, Tensor):
        raise TypeError(f"{key}는 Tensor여야 합니다")
    return value.to(device, non_blocking=True)


def run_epoch(
    model: nn.Module,
    batches: Iterable[Mapping[str, Any]],
    device: torch.device,
    *,
    optimizer: torch.optim.Optimizer | None = None,
    cultivar_loss_weight: float = 1.0,
    quality_loss_weight: float = 1.0,
    include_predictions: bool = False,
) -> dict[str, Any]:
    training = optimizer is not None
    model.train(training)
    criterion = nn.CrossEntropyLoss()
    total_loss = 0.0
    samples = 0
    cultivar_targets: list[Tensor] = []
    cultivar_predictions: list[Tensor] = []
    quality_targets: list[Tensor] = []
    quality_predictions: list[Tensor] = []
    prediction_records: list[dict[str, Any]] = []

    for batch in batches:
        images = _move(batch, "images", device)
        view_mask = _move(batch, "view_mask", device)
        cultivar_target = _move(batch, "cultivar_target", device)
        quality_target = _move(batch, "quality_target", device)
        if training:
            optimizer.zero_grad(set_to_none=True)
        with torch.set_grad_enabled(training):
            output = model(images, view_mask)
            cultivar_loss = criterion(output["cultivar_logits"], cultivar_target)
            quality_loss = criterion(output["quality_logits"], quality_target)
            loss = cultivar_loss_weight * cultivar_loss + quality_loss_weight * quality_loss
            if training:
                loss.backward()
                optimizer.step()
        batch_size = cultivar_target.shape[0]
        total_loss += loss.detach().item() * batch_size
        samples += batch_size
        cultivar_targets.append(cultivar_target.detach().cpu())
        quality_targets.append(quality_target.detach().cpu())
        cultivar_predictions.append(output["cultivar_logits"].argmax(dim=1).detach().cpu())
        quality_predictions.append(output["quality_logits"].argmax(dim=1).detach().cpu())
        if include_predictions:
            group_numbers = batch.get("group_no")
            if not isinstance(group_numbers, (list, tuple)) or len(group_numbers) != batch_size:
                raise TypeError("예측 기록 시 group_no 문자열 목록이 필요합니다")
            cultivar_probabilities = output["cultivar_logits"].softmax(dim=1).detach().cpu()
            quality_probabilities = output["quality_logits"].softmax(dim=1).detach().cpu()
            for index, group_no in enumerate(group_numbers):
                prediction_records.append(
                    {
                        "group_no": str(group_no),
                        "cultivar_target_index": int(cultivar_target[index]),
                        "cultivar_prediction_index": int(cultivar_probabilities[index].argmax()),
                        "cultivar_probabilities": cultivar_probabilities[index].tolist(),
                        "quality_target_index": int(quality_target[index]),
                        "quality_prediction_index": int(quality_probabilities[index].argmax()),
                        "quality_probabilities": quality_probabilities[index].tolist(),
                    }
                )

    if samples == 0:
        raise ValueError("빈 DataLoader는 평가할 수 없습니다")
    cultivar_matrix = confusion_matrix(torch.cat(cultivar_targets), torch.cat(cultivar_predictions), 2)
    quality_matrix = confusion_matrix(torch.cat(quality_targets), torch.cat(quality_predictions), 3)
    result = {
        "loss": total_loss / samples,
        "samples": samples,
        "cultivar": classification_metrics(cultivar_matrix),
        "quality": classification_metrics(quality_matrix),
    }
    if include_predictions:
        result["predictions"] = prediction_records
    return result


def save_checkpoint(
    path: Path,
    *,
    model: nn.Module,
    optimizer: torch.optim.Optimizer,
    epoch: int,
    config: Mapping[str, Any],
    metrics: Mapping[str, Any],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "epoch": epoch,
            "model_state": model.state_dict(),
            "optimizer_state": optimizer.state_dict(),
            "config": dict(config),
            "metrics": dict(metrics),
        },
        path,
    )
