"""시연 묶음을 현재 모델로 일괄 추론해 신뢰도 분포·재검사 비율·실제 사진 지연시간을 집계한다.

시연 묶음은 원본 사과의 남은 사진이라 **독립 평가 데이터가 아니다**. 이 도구의 목적은 성능 승인이
아니라 (1) 실제 시연 입력에서 재검사 bin으로 얼마나 빠지는지, (2) 실제 PNG 12장의 디코딩·추론
시간이 500ms 예산에 들어오는지를 시연 전에 확인하는 것이다. 개발 사과(v2가 학습한 사과)와
Test 사과(가중치가 학습하지 않은 사과)에서 나온 묶음을 나눠 집계한다.

모드:
    local  모델 패키지를 직접 읽는다. 디코딩(``decode_ms``)·모델(``model_ms``) 시간을 나눠 잰다.
    http   실행 중인 Inference API에 multipart로 보낸다. 왕복 시간과 ``Server-Timing`` 헤더를 기록한다.

사용:
    python scripts/evaluate_demo_bundles.py --mode local \\
        --model-dir models/cqc-apple-separate12-focal-v2-candidate --output-dir outputs/demo-dry-run
    python scripts/evaluate_demo_bundles.py --mode http --url http://127.0.0.1:8001/v1/predict \\
        --output-dir outputs/demo-dry-run-http --limit 100
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import statistics
import sys
import time
import urllib.request
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_DEMO = Path("data/processed/realtime-apple-arrival-demo")
DEFAULT_SPLITS = Path("configs/splits/seed-42.csv")


def percentile(values: list[float], fraction: float) -> float | None:
    """정렬한 값의 선형 보간 분위수. 값이 없으면 None."""
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def load_split_roles(path: Path) -> dict[str, str]:
    """사과 group_no를 ``dev``(학습·검증) 또는 ``test``로 분류한다."""
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return {row["group_no"]: ("test" if row["split"] == "test" else "dev") for row in csv.DictReader(stream)}


def select_bundles(
    demo_root: Path, roles: dict[str, str], role: str, limit: int | None, seed: int, index_path: Path | None = None
) -> list[dict[str, Any]]:
    """기본 재생 목록(12장 묶음)에서 역할별로 고르고, limit이 있으면 무작위 추출한다.

    ``index_path``를 주면 ``demo_root/index.json`` 대신 그 목록(일부 묶음만 담은 사본 등)을 쓴다.
    """
    index = json.loads((index_path or demo_root / "index.json").read_text(encoding="utf-8"))
    bundles = [b for b in index if b.get("default_playback")]
    for bundle in bundles:
        bundle["role"] = roles.get(str(bundle["source_group_id"]), "unknown")
    if role != "all":
        bundles = [b for b in bundles if b["role"] == role]
    if limit is not None and limit < len(bundles):
        bundles = random.Random(seed).sample(bundles, limit)
    return sorted(bundles, key=lambda b: b["inspection_id"])


def read_bundle(demo_root: Path, bundle: dict[str, Any]) -> tuple[list[bytes], list[dict[str, Any]], dict[str, Any]]:
    folder = demo_root / bundle["path"]
    request = json.loads((folder / "request.json").read_text(encoding="utf-8"))
    expected = json.loads((folder / "expected.json").read_text(encoding="utf-8"))
    images = [(folder / name).read_bytes() for name in request["images"]]
    return images, request["metadata"], expected


def _multipart(inspection_id: str, metadata: list[dict[str, Any]], images: list[bytes]) -> tuple[bytes, str]:
    boundary = f"cqc-{uuid.uuid4().hex}"
    parts = []
    for name, value in (("inspection_id", inspection_id), ("metadata", json.dumps(metadata))):
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'.encode() + value.encode() + b"\r\n"
        )
    for index, content in enumerate(images):
        media = "image/png" if content.startswith(b"\x89PNG") else "image/jpeg"
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="images"; filename="view-{index}"\r\n'
            f"Content-Type: {media}\r\n\r\n".encode() + content + b"\r\n"
        )
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), boundary


def _parse_server_timing(value: str | None) -> dict[str, float]:
    result: dict[str, float] = {}
    for item in (value or "").split(","):
        name, _, rest = item.strip().partition(";dur=")
        if name and rest:
            try:
                result[name] = float(rest)
            except ValueError:
                continue
    return result


class LocalRunner:
    def __init__(self, model_dir: Path, device: str, decode_workers: int) -> None:
        from src.inference.predictor import Predictor

        self.predictor = Predictor(model_dir, device=device, decode_workers=decode_workers)
        self.model_version = str(self.predictor.manifest["model_version"])

    def __call__(self, bundle_id: str, metadata: list[dict[str, Any]], images: list[bytes]) -> tuple[dict[str, Any], dict[str, float]]:
        started = time.perf_counter()
        prediction, timings = self.predictor.predict_timed(images)
        timings = dict(timings, total=(time.perf_counter() - started) * 1000)
        return prediction.to_dict(), timings


class HttpRunner:
    def __init__(self, url: str, timeout: float) -> None:
        self.url, self.timeout, self.model_version = url, timeout, "unknown"

    def __call__(self, bundle_id: str, metadata: list[dict[str, Any]], images: list[bytes]) -> tuple[dict[str, Any], dict[str, float]]:
        body, boundary = _multipart(f"dry-run-{bundle_id}-{uuid.uuid4().hex[:8]}", metadata, images)
        request = urllib.request.Request(
            self.url, data=body, method="POST", headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
        )
        started = time.perf_counter()
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            result = json.load(response)
            header = response.headers.get("Server-Timing")
        timings = {f"server_{k}": v for k, v in _parse_server_timing(header).items()}
        timings["round_trip"] = (time.perf_counter() - started) * 1000
        timings.setdefault("server_model", float(result.get("inference_time_ms", 0.0)))
        self.model_version = str(result.get("model_version", self.model_version))
        return result, timings


def summarize(rows: list[dict[str, Any]], thresholds: list[tuple[float, float]], latency_key: str, budget_ms: float) -> dict[str, Any]:
    """역할별 정확도·신뢰도·재검사 비율과 지연 분위수를 계산한다."""
    def block(subset: list[dict[str, Any]]) -> dict[str, Any]:
        if not subset:
            return {"bundles": 0}
        quality_conf = [r["quality_confidence"] for r in subset]
        latency = [r[latency_key] for r in subset if r.get(latency_key) is not None]
        return {
            "bundles": len(subset),
            "source_apples": len({r["source_group_id"] for r in subset}),
            "cultivar_accuracy": sum(r["cultivar_correct"] for r in subset) / len(subset),
            "quality_accuracy": sum(r["quality_correct"] for r in subset) / len(subset),
            "quality_confidence": {
                "mean": statistics.mean(quality_conf),
                "median": statistics.median(quality_conf),
                "min": min(quality_conf),
                "p10": percentile(quality_conf, 0.10),
            },
            "cultivar_confidence_min": min(r["cultivar_confidence"] for r in subset),
            "reinspection_rate": {
                f"cultivar>={c:.2f},quality>={q:.2f}": sum(
                    1 for r in subset if r["cultivar_confidence"] < c or r["quality_confidence"] < q
                ) / len(subset)
                for c, q in thresholds
            },
            "latency_ms": {
                "key": latency_key,
                "mean": statistics.mean(latency) if latency else None,
                "p50": percentile(latency, 0.5),
                "p95": percentile(latency, 0.95),
                "max": max(latency) if latency else None,
                f"over_{int(budget_ms)}ms": sum(1 for v in latency if v > budget_ms),
            },
        }

    return {
        "all": block(rows),
        "dev_apples": block([r for r in rows if r["role"] == "dev"]),
        "test_apples": block([r for r in rows if r["role"] == "test"]),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="시연 묶음 드라이런: 신뢰도·재검사 비율·실사진 지연")
    parser.add_argument("--mode", choices=("local", "http"), default="local")
    parser.add_argument("--model-dir", type=Path)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="cpu")
    parser.add_argument("--decode-workers", type=int, default=0, help="local 모드 사진 해제 스레드 수 (0=자동, 1=순차)")
    parser.add_argument("--url", default="http://127.0.0.1:8001/v1/predict")
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--demo-root", type=Path, default=DEFAULT_DEMO)
    parser.add_argument("--index", type=Path, help="묶음 목록 JSON. 기본은 <demo-root>/index.json")
    parser.add_argument("--splits", type=Path, default=DEFAULT_SPLITS)
    parser.add_argument("--role", choices=("all", "dev", "test"), default="all")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--threshold", action="append", default=[], metavar="CULTIVAR,QUALITY",
                        help="재검사 비율을 볼 임계값 조합. 여러 번 지정 가능. 기본 0.5,0.5")
    parser.add_argument("--budget-ms", type=float, default=500.0)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.mode == "local" and args.model_dir is None:
        parser.error("local 모드에는 --model-dir가 필요합니다")
    thresholds = [tuple(float(x) for x in t.split(",")) for t in args.threshold] or [(0.5, 0.5)]

    roles = load_split_roles(args.splits)
    bundles = select_bundles(args.demo_root, roles, args.role, args.limit, args.seed, args.index)
    if not bundles:
        parser.error("선택된 묶음이 없습니다")
    runner = LocalRunner(args.model_dir, args.device, args.decode_workers) if args.mode == "local" else HttpRunner(args.url, args.timeout)

    warm_images, warm_metadata, _ = read_bundle(args.demo_root, bundles[0])
    for _ in range(max(args.warmup, 0)):
        runner("warmup", warm_metadata, warm_images)

    rows = []
    for number, bundle in enumerate(bundles, start=1):
        images, metadata, expected = read_bundle(args.demo_root, bundle)
        result, timings = runner(bundle["inspection_id"], metadata, images)
        row = {
            "bundle_id": bundle["inspection_id"],
            "source_group_id": bundle["source_group_id"],
            "role": bundle["role"],
            "expected_cultivar": expected["cultivar"],
            "expected_grade": expected["quality_grade"],
            "predicted_cultivar": result["predicted_cultivar"],
            "predicted_grade": result["predicted_grade"],
            "cultivar_confidence": float(result["cultivar_confidence"]),
            "quality_confidence": float(result["quality_confidence"]),
            "cultivar_correct": result["predicted_cultivar"] == expected["cultivar"],
            "quality_correct": result["predicted_grade"] == expected["quality_grade"],
            "used_frame_count": result["used_frame_count"],
            "upload_bytes": sum(len(image) for image in images),
            **{f"{name}_ms": round(value, 3) for name, value in timings.items()},
        }
        rows.append(row)
        if number % 25 == 0:
            print(f"{number}/{len(bundles)}", flush=True)

    latency_key = "total_ms" if args.mode == "local" else "round_trip_ms"
    report = {
        "role": "demo_dry_run_not_independent_evaluation",
        "mode": args.mode,
        "decode_workers": getattr(getattr(runner, "predictor", None), "decode_workers", None),
        "model_version": runner.model_version,
        "bundles": len(rows),
        "selection": {"role": args.role, "limit": args.limit, "seed": args.seed, "index": str(args.index or "")},
        "thresholds": [list(t) for t in thresholds],
        "summary": summarize(rows, thresholds, latency_key, args.budget_ms),
        "mean_upload_mib": statistics.mean(r["upload_bytes"] for r in rows) / 2**20,
        "note": "시연 묶음은 같은 실제 사과의 다른 사진이다. dev_apples는 모델이 학습한 사과이므로 정확도를 성능으로 인용하지 않는다.",
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with (args.output_dir / "bundles.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (args.output_dir / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    overall = report["summary"]["all"]
    print(
        f"bundles={len(rows)} quality_acc={overall['quality_accuracy']:.3f} "
        f"quality_conf_median={overall['quality_confidence']['median']:.3f} "
        f"reinspection={next(iter(overall['reinspection_rate'].values())):.3f} "
        f"latency_p95={overall['latency_ms']['p95']:.1f}ms output={args.output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
