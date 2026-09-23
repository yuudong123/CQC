"""Portable, model-only CPU acceptance for the packaged v2 checkpoint."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import torch

from src.training.benchmark import percentile
from src.training.models import build_model


def cpu_name() -> str:
    if Path('/proc/cpuinfo').is_file():
        for line in Path('/proc/cpuinfo').read_text(errors='replace').splitlines():
            if line.lower().startswith('model name'):
                return line.partition(':')[2].strip()
    return platform.processor() or 'unknown'


def physical_memory_bytes() -> int:
    if Path('/proc/meminfo').is_file():
        for line in Path('/proc/meminfo').read_text(errors='replace').splitlines():
            if line.startswith('MemTotal:'):
                return int(line.split()[1]) * 1024
    if os.name == 'nt':
        import ctypes

        class MemoryStatus(ctypes.Structure):
            _fields_ = [('length', ctypes.c_ulong), ('memory_load', ctypes.c_ulong),
                        ('total_physical', ctypes.c_ulonglong), ('available_physical', ctypes.c_ulonglong),
                        ('total_page_file', ctypes.c_ulonglong), ('available_page_file', ctypes.c_ulonglong),
                        ('total_virtual', ctypes.c_ulonglong), ('available_virtual', ctypes.c_ulonglong),
                        ('available_extended_virtual', ctypes.c_ulonglong)]

        status = MemoryStatus()
        status.length = ctypes.sizeof(status)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            raise OSError('GlobalMemoryStatusEx failed')
        return status.total_physical
    raise RuntimeError('Cannot identify physical memory on this host')


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def measured(values: list[float]) -> dict[str, float]:
    return dict(mean_ms=statistics.mean(values), max_ms=max(values), p95_ms=percentile(values, 0.95))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--warmup', type=int, default=10)
    parser.add_argument('--repeats', type=int, default=100)
    parser.add_argument('--smoke', action='store_true', help='Allow other CPUs for a dry run; never approve')
    args = parser.parse_args()
    if args.output.exists() or args.warmup < 0 or args.repeats < 2:
        parser.error('Output must be new, warmup >= 0 and repeats >= 2')

    detected_cpu = cpu_name()
    memory_gib = physical_memory_bytes() / 1024**3
    cpu_match = re.search(r'i7[-\s]*4790\b', detected_cpu, re.IGNORECASE) is not None
    ram_match = memory_gib >= 15.0
    if not args.smoke and (not cpu_match or not ram_match):
        parser.error(f'Target must be i7-4790 / at least 15 GiB RAM; detected {detected_cpu}, {memory_gib:.2f} GiB')

    manifest_path = args.package_dir / 'model.json'
    model_path = args.package_dir / 'model.pt'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    actual_sha = sha256(model_path)
    if actual_sha != manifest['checkpoint_sha256']:
        raise ValueError('Package checksum differs from model.json')
    if manifest['model_kind'] != 'separate' or manifest['views'] != 12 or manifest['image_size'] != 224:
        raise ValueError('This acceptance is for separate, 12-view, 224px v2 only')

    torch.set_num_threads(1)
    checkpoint = torch.load(model_path, map_location='cpu', weights_only=False)
    config = checkpoint['config']
    if config['model_kind'] != manifest['model_kind'] or config['views'] != manifest['views']:
        raise ValueError('Package and checkpoint model configuration differ')
    model = build_model('separate', pretrained=False).cpu().eval()
    model.load_state_dict(checkpoint['model_state'])
    generator = torch.Generator().manual_seed(42)
    images = torch.randn((1, 12, 3, 224, 224), generator=generator)
    mask = torch.ones((1, 12), dtype=torch.bool)

    def infer() -> float:
        started = time.perf_counter()
        with torch.inference_mode():
            model(images, mask)
        return (time.perf_counter() - started) * 1000

    for _ in range(args.warmup):
        infer()
    latency = measured([infer() for _ in range(args.repeats)])
    concurrency = []
    for workers in (1, 2, 4):
        infer()
        started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=workers) as pool:
            timings = list(pool.map(lambda _: infer(), range(args.repeats)))
        throughput = args.repeats / (time.perf_counter() - started)
        concurrency.append(dict(workers=workers, requests=args.repeats,
                                throughput_per_second=throughput, **measured(timings)))

    one = concurrency[0]
    performance_passed = (latency['p95_ms'] <= 500 and one['p95_ms'] <= 500
                          and one['throughput_per_second'] >= 2)
    result = dict(
        evaluation_role='model_only_cpu_acceptance',
        target_cpu='Intel Core i7-4790', detected_cpu=detected_cpu,
        physical_memory_gib=round(memory_gib, 2), cpu_verified=cpu_match,
        memory_verified=ram_match, smoke=args.smoke,
        model_version=manifest['model_version'], checkpoint_sha256=actual_sha,
        package_status=manifest.get('approval_status'),
        input='deterministic_synthetic_tensor_after_preprocessing',
        input_shape=[1, 12, 3, 224, 224], test_used=False,
        torch_threads=1, warmup=args.warmup, repeats=args.repeats,
        latency=latency, concurrency=concurrency,
        criteria=dict(p95_ms_max=500, throughput_per_second_min=2),
        performance_passed=performance_passed,
        accepted=bool(cpu_match and ram_match and not args.smoke and performance_passed),
        limitation='Model forward only; excludes image decoding, HTTP transfer, Docker queueing and Backend time',
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'acceptance={args.output} accepted={result["accepted"]} '
          f'latency_p95_ms={latency["p95_ms"]:.2f} throughput={one["throughput_per_second"]:.2f}', flush=True)
    return 0 if result['accepted'] or args.smoke else 2


if __name__ == '__main__':
    raise SystemExit(main())
