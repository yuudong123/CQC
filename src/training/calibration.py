"""개발 5-fold OOF 예측으로 신뢰도를 보정하고 재검사 임계값 표를 만든다.

입력은 ``export_predictions``가 fold별로 만든 CSV(정답·예측·logits)다. Test 사과는 쓰지 않는다.

fit:
    1. 품종·품질 head마다 temperature T 하나를 NLL 최소화로 찾는다. 예측 등급은 바뀌지 않는다.
    2. 보정 전후 NLL·ECE·Brier·정확도·평균 신뢰도와 신뢰도 구간별 표(reliability)를 기록한다.
    3. 보정 후 신뢰도로 품종·품질 임계값 조합별 자동 처리율·재검사율·자동 처리 구간 정확도와
       등급 오류 유형(상위 등급→보통, 보통→상위 등급, 특↔보통)을 표로 만든다.
    4. ``--min-quality-accuracy``, ``--max-reinspection``을 주면 조건을 만족하는 조합 중 자동 처리율이
       가장 높은 것을 추천한다. 추천은 참고값이며 최종 임계값은 팀이 정한다.

apply:
    fit 결과의 temperature를 모델 패키지 manifest에 넣는다. 체크포인트(model.pt)와 SHA-256은 그대로다.

사용:
    python -m src.training.calibration fit --predictions outputs/v2-calibration/oof-fold-*.csv \\
        --output outputs/v2-calibration/calibration.json --table outputs/v2-calibration/threshold-table.csv
    python -m src.training.calibration apply --calibration outputs/v2-calibration/calibration.json \\
        --package models/cqc-apple-separate12-focal-v2-candidate --model-version <새 버전명>
"""

from __future__ import annotations

import argparse
import csv
import glob
import hashlib
import json
import math
import shutil
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as F

CULTIVAR_CLASSES = ("fuji", "yanggwang")
QUALITY_CLASSES = ("L", "M", "S")
ECE_BINS = 10
CULTIVAR_THRESHOLDS = (0.50, 0.60, 0.70, 0.80, 0.90)


@dataclass(frozen=True)
class OofRow:
    group_no: str
    fold: int
    cultivar_target: int
    quality_target: int
    cultivar_logits: tuple[float, ...]
    quality_logits: tuple[float, ...]


def read_predictions(paths: Iterable[Path]) -> list[OofRow]:
    """fold별 OOF CSV를 읽고 logits 열·중복 사과·클래스 이름을 검증한다."""
    rows: list[OofRow] = []
    seen: set[str] = set()
    for path in paths:
        with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
            for record in csv.DictReader(stream):
                try:
                    cultivar_logits = tuple(float(record[f"cultivar_logit_{c}"]) for c in CULTIVAR_CLASSES)
                    quality_logits = tuple(float(record[f"quality_logit_{c}"]) for c in QUALITY_CLASSES)
                except KeyError as exc:
                    raise ValueError(
                        f"{path}에 logits 열이 없습니다. 최신 export_predictions로 다시 내보내야 합니다"
                    ) from exc
                group_no = str(record["group_no"])
                if group_no in seen:
                    raise ValueError(f"같은 사과가 여러 fold에 있습니다: {group_no}")
                seen.add(group_no)
                rows.append(
                    OofRow(
                        group_no=group_no,
                        fold=int(record["fold"]),
                        cultivar_target=CULTIVAR_CLASSES.index(record["cultivar_target"]),
                        quality_target=QUALITY_CLASSES.index(record["quality_target"]),
                        cultivar_logits=cultivar_logits,
                        quality_logits=quality_logits,
                    )
                )
    if not rows:
        raise ValueError("OOF 예측이 비어 있습니다")
    return rows


def _nll(logits: torch.Tensor, targets: torch.Tensor, temperature: float) -> float:
    return float(F.cross_entropy(logits / temperature, targets))


def fit_temperature(logits: torch.Tensor, targets: torch.Tensor) -> float:
    """NLL을 최소화하는 temperature를 로그 격자 탐색 후 황금분할로 좁혀 찾는다."""
    logits = logits.double()
    grid = torch.logspace(math.log10(0.05), math.log10(20.0), steps=121, dtype=torch.float64)
    losses = [_nll(logits, targets, float(t)) for t in grid]
    best = min(range(len(grid)), key=losses.__getitem__)
    low = math.log(float(grid[max(best - 1, 0)]))
    high = math.log(float(grid[min(best + 1, len(grid) - 1)]))
    ratio = (math.sqrt(5) - 1) / 2
    for _ in range(60):
        a = high - ratio * (high - low)
        b = low + ratio * (high - low)
        if _nll(logits, targets, math.exp(a)) <= _nll(logits, targets, math.exp(b)):
            high = b
        else:
            low = a
    return math.exp((low + high) / 2)


def calibration_metrics(
    logits: torch.Tensor, targets: torch.Tensor, temperature: float, bins: int = ECE_BINS
) -> dict[str, Any]:
    """정확도·평균 신뢰도·NLL·Brier·ECE와 신뢰도 구간별 표를 계산한다."""
    probabilities = (logits.double() / temperature).softmax(dim=1)
    confidence, prediction = probabilities.max(dim=1)
    correct = prediction.eq(targets).double()
    one_hot = F.one_hot(targets, probabilities.shape[1]).double()
    table = []
    ece = 0.0
    edges = torch.linspace(0, 1, bins + 1, dtype=torch.float64)
    for index in range(bins):
        lower, upper = float(edges[index]), float(edges[index + 1])
        selected = (confidence > lower) & (confidence <= upper) if index else (confidence <= upper)
        count = int(selected.sum())
        if count:
            accuracy = float(correct[selected].mean())
            mean_confidence = float(confidence[selected].mean())
            ece += count / len(targets) * abs(accuracy - mean_confidence)
        else:
            accuracy = mean_confidence = None
        table.append(
            {"lower": round(lower, 3), "upper": round(upper, 3), "count": count,
             "accuracy": accuracy, "mean_confidence": mean_confidence}
        )
    return {
        "temperature": temperature,
        "samples": len(targets),
        "accuracy": float(correct.mean()),
        "mean_confidence": float(confidence.mean()),
        "nll": _nll(logits, targets, temperature),
        "brier": float(((probabilities - one_hot) ** 2).sum(dim=1).mean()),
        "ece": ece,
        "reliability": table,
    }


def _probabilities(rows: Sequence[OofRow], head: str, temperature: float) -> torch.Tensor:
    logits = torch.tensor([getattr(row, f"{head}_logits") for row in rows], dtype=torch.float64)
    return (logits / temperature).softmax(dim=1)


def threshold_table(
    rows: Sequence[OofRow],
    cultivar_temperature: float,
    quality_temperature: float,
    quality_thresholds: Sequence[float] | None = None,
    cultivar_thresholds: Sequence[float] = CULTIVAR_THRESHOLDS,
) -> list[dict[str, Any]]:
    """임계값 조합별 자동 처리율과 자동 처리 구간의 정확도·오류 유형을 계산한다."""
    if quality_thresholds is None:
        quality_thresholds = [round(0.34 + 0.01 * i, 2) for i in range(62)]
    cultivar_p = _probabilities(rows, "cultivar", cultivar_temperature)
    quality_p = _probabilities(rows, "quality", quality_temperature)
    cultivar_conf, cultivar_pred = cultivar_p.max(dim=1)
    quality_conf, quality_pred = quality_p.max(dim=1)
    cultivar_true = torch.tensor([row.cultivar_target for row in rows])
    quality_true = torch.tensor([row.quality_target for row in rows])
    total = len(rows)
    result = []
    for c_thr in cultivar_thresholds:
        for q_thr in quality_thresholds:
            accepted = (cultivar_conf >= c_thr) & (quality_conf >= q_thr)
            count = int(accepted.sum())
            qt, qp = quality_true[accepted], quality_pred[accepted]
            ct, cp = cultivar_true[accepted], cultivar_pred[accepted]
            s_index = QUALITY_CLASSES.index("S")
            l_index = QUALITY_CLASSES.index("L")
            result.append(
                {
                    "cultivar_threshold": c_thr,
                    "quality_threshold": q_thr,
                    "accepted": count,
                    "total": total,
                    "coverage": count / total,
                    "reinspection_rate": 1 - count / total,
                    "cultivar_accuracy": float((ct == cp).double().mean()) if count else None,
                    "quality_accuracy": float((qt == qp).double().mean()) if count else None,
                    "quality_macro_f1": _macro_f1(qt, qp, len(QUALITY_CLASSES)) if count else None,
                    "higher_to_normal": int(((qt != s_index) & (qp == s_index)).sum()),
                    "normal_to_higher": int(((qt == s_index) & (qp != s_index)).sum()),
                    "extreme_l_s_swap": int(
                        (((qt == l_index) & (qp == s_index)) | ((qt == s_index) & (qp == l_index))).sum()
                    ),
                    "quality_errors": int((qt != qp).sum()),
                    "cultivar_errors": int((ct != cp).sum()),
                }
            )
    return result


def _macro_f1(targets: torch.Tensor, predictions: torch.Tensor, classes: int) -> float:
    scores = []
    for index in range(classes):
        tp = int(((predictions == index) & (targets == index)).sum())
        fp = int(((predictions == index) & (targets != index)).sum())
        fn = int(((predictions != index) & (targets == index)).sum())
        denominator = 2 * tp + fp + fn
        scores.append(2 * tp / denominator if denominator else 0.0)
    return sum(scores) / classes


def recommend(
    table: Sequence[dict[str, Any]], *, min_quality_accuracy: float | None, max_reinspection: float | None
) -> dict[str, Any] | None:
    """조건을 만족하는 조합 중 자동 처리율이 가장 높고 임계값이 낮은 조합을 고른다."""
    if min_quality_accuracy is None and max_reinspection is None:
        return None
    eligible = [
        row for row in table
        if row["accepted"]
        and (min_quality_accuracy is None or row["quality_accuracy"] >= min_quality_accuracy)
        and (max_reinspection is None or row["reinspection_rate"] <= max_reinspection)
    ]
    if not eligible:
        return None
    return max(eligible, key=lambda row: (row["coverage"], -row["quality_threshold"], -row["cultivar_threshold"]))


def fit(
    rows: Sequence[OofRow],
    *,
    min_quality_accuracy: float | None = None,
    max_reinspection: float | None = None,
    sources: Sequence[str] = (),
) -> dict[str, Any]:
    """두 head의 temperature를 적합하고 보정 전후 지표·임계값 표·추천을 묶어 반환한다."""
    folds = sorted({row.fold for row in rows})
    report: dict[str, Any] = {
        "role": "development_oof_calibration",
        "test_used": False,
        "samples": len(rows),
        "folds": folds,
        "sources": list(sources),
        "heads": {},
    }
    temperatures = {}
    for head, classes in (("cultivar", CULTIVAR_CLASSES), ("quality", QUALITY_CLASSES)):
        logits = torch.tensor([getattr(row, f"{head}_logits") for row in rows], dtype=torch.float64)
        targets = torch.tensor([getattr(row, f"{head}_target") for row in rows])
        temperature = fit_temperature(logits, targets)
        temperatures[head] = temperature
        report["heads"][head] = {
            "classes": list(classes),
            "temperature": temperature,
            "before": calibration_metrics(logits, targets, 1.0),
            "after": calibration_metrics(logits, targets, temperature),
        }
    table = threshold_table(rows, temperatures["cultivar"], temperatures["quality"])
    report["threshold_table_rows"] = len(table)
    report["reference_at_current_thresholds"] = next(
        row for row in table if row["cultivar_threshold"] == 0.5 and row["quality_threshold"] == 0.5
    )
    report["recommendation"] = {
        "constraints": {"min_quality_accuracy": min_quality_accuracy, "max_reinspection": max_reinspection},
        "selection": recommend(
            table, min_quality_accuracy=min_quality_accuracy, max_reinspection=max_reinspection
        ),
        "note": "개발 OOF 기준 참고값. 최종 임계값은 팀이 정하고 Backend 설정에 반영한다.",
    }
    report["threshold_table"] = table
    return report


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def apply_to_package(
    calibration: dict[str, Any],
    package: Path,
    *,
    model_version: str,
    output_package: Path | None = None,
) -> Path:
    """temperature를 manifest에 기록한다. 출력 경로가 없으면 같은 폴더에 쓰고 원래 manifest를 백업한다."""
    manifest_path = package / "model.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    checkpoint = package / "model.pt"
    if _sha256(checkpoint) != manifest["checkpoint_sha256"]:
        raise ValueError("체크포인트 SHA-256이 manifest와 다릅니다")
    if calibration.get("test_used") is not False:
        raise ValueError("Test를 사용하지 않은 보정 결과만 적용할 수 있습니다")
    target = output_package or package
    if target != package:
        target.mkdir(parents=True, exist_ok=False)
        shutil.copy2(checkpoint, target / "model.pt")
    else:
        backup = package / "model.json.before-calibration"
        if not backup.exists():
            shutil.copy2(manifest_path, backup)
    manifest.update(
        {
            "model_version": model_version,
            "cultivar_temperature": calibration["heads"]["cultivar"]["temperature"],
            "quality_temperature": calibration["heads"]["quality"]["temperature"],
            "threshold_status": "calibrated_dev_oof",
            "calibration_source": {
                "samples": calibration["samples"],
                "folds": calibration["folds"],
                "quality_ece_before": calibration["heads"]["quality"]["before"]["ece"],
                "quality_ece_after": calibration["heads"]["quality"]["after"]["ece"],
                "test_used": False,
            },
        }
    )
    (target / "model.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def _write_table(path: Path, table: Sequence[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(table[0]))
        writer.writeheader()
        writer.writerows(table)


def main(argv: list[str] | None = None) -> int:
    """fit 또는 apply 하위 명령을 실행한다."""
    parser = argparse.ArgumentParser(description="개발 OOF 기반 신뢰도 보정·임계값 표")
    commands = parser.add_subparsers(dest="command", required=True)
    fit_parser = commands.add_parser("fit")
    fit_parser.add_argument("--predictions", nargs="+", required=True)
    fit_parser.add_argument("--output", type=Path, required=True)
    fit_parser.add_argument("--table", type=Path)
    fit_parser.add_argument("--min-quality-accuracy", type=float)
    fit_parser.add_argument("--max-reinspection", type=float)
    apply_parser = commands.add_parser("apply")
    apply_parser.add_argument("--calibration", type=Path, required=True)
    apply_parser.add_argument("--package", type=Path, required=True)
    apply_parser.add_argument("--model-version", required=True)
    apply_parser.add_argument("--output-package", type=Path)
    args = parser.parse_args(argv)

    if args.command == "fit":
        paths = sorted({Path(p) for pattern in args.predictions for p in (glob.glob(pattern) or [pattern])})
        rows = read_predictions(paths)
        report = fit(
            rows,
            min_quality_accuracy=args.min_quality_accuracy,
            max_reinspection=args.max_reinspection,
            sources=[str(p) for p in paths],
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if args.table:
            _write_table(args.table, report["threshold_table"])
        quality = report["heads"]["quality"]
        print(
            f"calibration={args.output} samples={report['samples']} "
            f"quality_T={quality['temperature']:.3f} "
            f"quality_ECE={quality['before']['ece']:.3f}->{quality['after']['ece']:.3f} test_used=False"
        )
        return 0

    calibration = json.loads(args.calibration.read_text(encoding="utf-8"))
    target = apply_to_package(
        calibration, args.package, model_version=args.model_version, output_package=args.output_package
    )
    print(f"package={target} model_version={args.model_version} threshold_status=calibrated_dev_oof")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
