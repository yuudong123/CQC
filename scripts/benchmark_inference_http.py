"""Measure one group's JPEG upload and Inference HTTP response on the target CPU."""

import argparse
import io
import json
import statistics
import time
import urllib.request
from pathlib import Path

from PIL import Image


def percentile(values, fraction):
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def multipart_payload():
    boundary = "cqc-benchmark-boundary"
    metadata = [dict(view_index=i, angle_direction="top" if i < 6 else "bottom",
                     verticality_angle=0, horizontality_angle=i * 30) for i in range(12)]
    image = Image.new("RGB", (224, 224))
    image.putdata([((x * 7 + y * 3) % 256, (x * 2 + y * 11) % 256,
                    (x * 13 + y * 5) % 256) for y in range(224) for x in range(224)])
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=85)
    encoded = buffer.getvalue()
    parts = []
    for name, value in (("inspection_id", "http-benchmark"),
                        ("metadata", json.dumps(metadata, separators=(",", ":")))):
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n".encode() + value.encode() + b"\r\n")
    for index in range(12):
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"images\"; filename=\"{index}.jpg\"\r\nContent-Type: image/jpeg\r\n\r\n".encode() + encoded + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), boundary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:18001/v1/predict")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--repeats", type=int, default=100)
    args = parser.parse_args()
    if args.warmup < 0 or args.repeats < 2 or args.output.exists():
        parser.error("warmup >= 0, repeats >= 2, and output must be a new file")
    body, boundary = multipart_payload()
    request = urllib.request.Request(args.url, data=body, method="POST", headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    elapsed, model = [], []
    started = time.perf_counter()
    for index in range(args.warmup + args.repeats):
        start = time.perf_counter()
        with urllib.request.urlopen(request, timeout=10) as response:
            result = json.load(response)
        duration = (time.perf_counter() - start) * 1000
        if result["used_frame_count"] != 12:
            raise RuntimeError("Unexpected frame count")
        if index == args.warmup:
            started = start
        if index >= args.warmup:
            elapsed.append(duration)
            model.append(result["inference_time_ms"])
    report = {
        "scope": "Windows host to standalone Docker Inference HTTP API; includes multipart upload, JPEG decoding, preprocessing, model forward and response",
        "input": "12 repeated deterministic synthetic 224x224 JPEG images; no validation or production images",
        "model_version": result["model_version"],
        "request_bytes": len(body),
        "warmup": args.warmup,
        "requests": args.repeats,
        "http_ms": {"mean": statistics.mean(elapsed), "max": max(elapsed), "p95": percentile(elapsed, 0.95)},
        "server_model_forward_ms": {"mean": statistics.mean(model), "max": max(model), "p95": percentile(model, 0.95)},
        "total_throughput_per_second": args.repeats / (time.perf_counter() - started),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
