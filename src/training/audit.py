"""Audit all expected experiment artifacts before model comparison."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from .experiments import build_plan


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit_run(directory: Path, expected: dict[str, Any]) -> dict[str, Any]:
    errors = []
    required = {
        "config": directory / "config.json",
        "history": directory / "history.json",
        "summary": directory / "summary.json",
        "checkpoint": directory / "best.pt",
    }
    missing = [name for name, path in required.items() if not path.exists()]
    if missing:
        return {"directory": str(directory), "complete": False, "errors": [f"누락: {', '.join(missing)}"]}
    try:
        config = json.loads(required["config"].read_text(encoding="utf-8"))
        history = json.loads(required["history"].read_text(encoding="utf-8"))
        summary = json.loads(required["summary"].read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return {"directory": str(directory), "complete": False, "errors": [f"JSON 읽기 실패: {exc}"]}
    for key in ("model_kind", "views", "cv_fold", "epochs"):
        if config.get(key) != expected[key]:
            errors.append(f"config {key}: expected={expected[key]!r}, actual={config.get(key)!r}")
    if len(history) != expected["epochs"]:
        errors.append(f"history epoch 수: expected={expected['epochs']}, actual={len(history)}")
    if summary.get("epochs_completed") != expected["epochs"]:
        errors.append(
            f"summary epoch 수: expected={expected['epochs']}, actual={summary.get('epochs_completed')}"
        )
    actual_hash = sha256(required["checkpoint"])
    if summary.get("checkpoint_sha256") != actual_hash:
        errors.append("체크포인트 SHA-256 불일치")
    if summary.get("test_used") is not False:
        errors.append("CV 학습 summary의 test_used가 false가 아닙니다")
    return {"directory": str(directory), "complete": not errors, "errors": errors}


def audit_all(root: Path, *, epochs: int = 20, batch_size: int = 2) -> dict[str, Any]:
    plan = build_plan(epochs=epochs, batch_size=batch_size)
    results = []
    for expected in plan:
        directory = root / Path(expected["output_dir"]).name
        results.append(audit_run(directory, expected))
    complete = sum(result["complete"] for result in results)
    return {
        "expected_runs": len(results),
        "complete_runs": complete,
        "all_complete": complete == len(results),
        "failed_runs": [result for result in results if not result["complete"]],
        "test_used": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="전체 학습 산출물 무결성 검사")
    parser.add_argument("--root", type=Path, default=Path("outputs/training"))
    parser.add_argument("--output", type=Path, default=Path("outputs/training-audit.json"))
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=2)
    args = parser.parse_args(argv)
    result = audit_all(args.root, epochs=args.epochs, batch_size=args.batch_size)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"complete={result['complete_runs']}/{result['expected_runs']} audit={args.output}")
    return 0 if result["all_complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
