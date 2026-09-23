"""Real loopback HTTP smoke test with optional unmodified Backend response schema."""
from __future__ import annotations

import argparse
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

import httpx
from PIL import Image


def backend_response_type(root: Path):
    package = root / "src/api"
    spec = importlib.util.spec_from_file_location(
        "cqc_backend_snapshot", package / "__init__.py",
        submodule_search_locations=[str(package)],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    from cqc_backend_snapshot.schemas.inference import InferenceResponse
    return InferenceResponse


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--backend-root", type=Path)
    parser.add_argument("--backend-revision")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Use a new report path; previous evidence is preserved")
    schema = backend_response_type(args.backend_root) if args.backend_root else None
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = dict(os.environ, OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
    command = [sys.executable, "-m", "src.inference.api", "--model-dir",
               str(args.package.resolve()), "--device", "cpu", "--host", "127.0.0.1", "--port", str(port)]
    results = []
    with tempfile.TemporaryFile(mode="w+b") as log:
        process = subprocess.Popen(command, env=env, stdout=log, stderr=log,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=10, trust_env=False) as client:
                deadline = time.monotonic() + 60
                while True:
                    if process.poll() is not None:
                        raise RuntimeError("Inference server exited during startup")
                    try:
                        health = client.get("/health")
                        if health.status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    if time.monotonic() >= deadline:
                        raise TimeoutError("Inference startup exceeded 60 seconds")
                    time.sleep(0.2)
                image = io.BytesIO()
                Image.new("RGB", (224, 224), (160, 40, 30)).save(image, format="PNG")
                for name, count, mime, payload, mismatch, expected in [
                    ("twelve_frames", 12, "image/png", image.getvalue(), False, 200),
                    ("masked_eight_frames", 8, "image/png", image.getvalue(), False, 200),
                    ("too_many_frames", 13, "image/png", image.getvalue(), False, 413),
                    ("metadata_mismatch", 12, "image/png", image.getvalue(), True, 422),
                    ("unsupported_type", 1, "text/plain", b"bad", False, 415),
                    ("corrupt_image", 1, "image/png", b"bad", False, 422),
                ]:
                    metadata = [dict(view_index=i, angle_direction="top", verticality_angle=45,
                                     horizontality_angle=(i % 6) * 60) for i in range(count)]
                    started = time.perf_counter()
                    response = client.post("/v1/predict", data={"inspection_id": name,
                        "metadata": json.dumps(metadata[:-1] if mismatch else metadata)},
                        files=[("images", (f"{i}.png", payload, mime)) for i in range(count)])
                    elapsed = (time.perf_counter() - started) * 1000
                    if response.status_code != expected:
                        raise RuntimeError(f"{name}: {response.status_code}: {response.text}")
                    if expected == 200:
                        body = response.json()
                        if body["inspection_id"] != name or body["used_frame_count"] != count:
                            raise RuntimeError(f"{name}: response identity mismatch")
                        if schema:
                            schema.model_validate(body)
                    results.append(dict(case=name, status=response.status_code, round_trip_ms=elapsed))
            report = dict(scope="loopback_http_synthetic_images", health=health.json(), cases=results,
                          backend_schema_validated=schema is not None,
                          backend_revision=args.backend_revision, backend_orchestration_verified=False,
                          quality_evaluated=False, target_cpu_verified=False, production_approved=False)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(report))
        except Exception:
            log.seek(0)
            print(log.read().decode("utf-8", errors="replace"), file=sys.stderr)
            raise
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)


if __name__ == "__main__":
    main()
