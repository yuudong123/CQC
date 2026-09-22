"""Generate deterministic demo-only virtual Brix values from RGB apple views."""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from random import Random
from typing import Iterable

import torch
import torch.nn.functional as F
from PIL import Image
from torchvision.transforms.functional import pil_to_tensor

from .multiview import GroupRecord, load_groups, select_views


GENERATOR_VERSION = "virtual-brix-rgb-v1"
FEATURE_VERSION = "rgb-proxy-v1"
FIELDNAMES = (
    "group_no",
    "virtual_brix",
    "brix_uncertainty",
    "brix_source",
    "brix_is_measured",
    "brix_generator_version",
    "brix_target_correlation",
    "feature_version",
    "feature_redness",
    "feature_red_coverage",
    "feature_color_uniformity",
    "feature_texture",
    "feature_lenticel_proxy",
    "valid_view_count",
)


@dataclass(frozen=True)
class RGBProxyFeatures:
    redness: float
    red_coverage: float
    color_uniformity: float
    texture: float
    lenticel_proxy: float


def _apple_mask(rgb: torch.Tensor) -> torch.Tensor:
    maximum = rgb.max(dim=0).values
    minimum = rgb.min(dim=0).values
    saturation = (maximum - minimum) / maximum.clamp_min(1e-6)
    brightness = rgb.mean(dim=0)
    mask = (saturation > 0.10) & (brightness < 0.96)
    if mask.float().mean() < 0.03:
        mask = brightness < 0.94
    if mask.float().mean() < 0.03:
        mask = torch.ones_like(brightness, dtype=torch.bool)
    return mask


def extract_rgb_proxy(image_bytes: bytes) -> RGBProxyFeatures:
    """Extract transparent RGB proxies; none of them is a measured sugar value."""

    with Image.open(BytesIO(image_bytes)) as image:
        image = image.convert("RGB").resize((128, 128))
        rgb = pil_to_tensor(image).to(dtype=torch.float32) / 255.0
    mask = _apple_mask(rgb)
    red_signal = (rgb[0] - (rgb[1] + rgb[2]) / 2).clamp(-1, 1)
    values = red_signal[mask]
    redness = float(values.mean())
    red_coverage = float((values > 0.08).float().mean())
    color_uniformity = float((1.0 - values.std(unbiased=False)).clamp(0, 1))

    luminance = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]
    dx = (luminance[:, 1:] - luminance[:, :-1]).abs()
    dy = (luminance[1:, :] - luminance[:-1, :]).abs()
    texture = float((dx.mean() + dy.mean()) / 2)
    local_mean = F.avg_pool2d(luminance[None, None], 5, stride=1, padding=2)[0, 0]
    local_contrast = (luminance - local_mean).abs()
    lenticel_proxy = float(((local_contrast > 0.10) & mask).float().sum() / mask.float().sum())
    return RGBProxyFeatures(redness, red_coverage, color_uniformity, texture, lenticel_proxy)


def aggregate_features(features: Iterable[RGBProxyFeatures]) -> tuple[RGBProxyFeatures, float, int]:
    items = tuple(features)
    if not items:
        raise ValueError("특징을 집계할 이미지가 없습니다")
    names = RGBProxyFeatures.__dataclass_fields__
    columns = {name: torch.tensor([getattr(item, name) for item in items]) for name in names}
    aggregate = RGBProxyFeatures(**{name: float(values.mean()) for name, values in columns.items()})
    view_variation = float(
        torch.stack((columns["redness"].std(unbiased=False), columns["red_coverage"].std(unbiased=False))).mean()
    )
    return aggregate, view_variation, len(items)


def _standardize(values: list[float], fit_indices: list[int]) -> list[float]:
    tensor = torch.tensor(values, dtype=torch.float64)
    fit = tensor[fit_indices]
    std = fit.std(unbiased=False)
    if std <= 1e-12:
        return [0.0] * len(values)
    return ((tensor - fit.mean()) / std).tolist()


def _seeded_normal(group_no: str, version: str) -> float:
    digest = hashlib.sha256(f"{group_no}:{version}".encode("utf-8")).digest()
    return Random(int.from_bytes(digest[:8], "big")).gauss(0.0, 1.0)


def build_virtual_brix_rows(
    group_features: dict[str, tuple[RGBProxyFeatures, float, int]],
    *,
    target_correlation: float = 0.34,
    mean_brix: float = 14.0,
    std_brix: float = 1.5,
    generator_version: str = GENERATOR_VERSION,
    fit_group_numbers: set[str] | None = None,
) -> list[dict[str, object]]:
    if not 0 <= target_correlation <= 1:
        raise ValueError("target_correlation은 0~1이어야 합니다")
    group_numbers = sorted(group_features)
    fit_group_numbers = fit_group_numbers or set(group_numbers)
    fit_indices = [index for index, key in enumerate(group_numbers) if key in fit_group_numbers]
    if not fit_indices:
        raise ValueError("표준화 기준 그룹이 없습니다")
    redness_z = _standardize([group_features[key][0].redness for key in group_numbers], fit_indices)
    coverage_z = _standardize([group_features[key][0].red_coverage for key in group_numbers], fit_indices)
    uniformity_z = _standardize([group_features[key][0].color_uniformity for key in group_numbers], fit_indices)
    raw_visual = [0.45 * r + 0.30 * c + 0.25 * u for r, c, u in zip(redness_z, coverage_z, uniformity_z)]
    visual_scores = _standardize(raw_visual, fit_indices)
    rows: list[dict[str, object]] = []
    noise_scale = math.sqrt(1.0 - target_correlation**2)
    for index, group_no in enumerate(group_numbers):
        feature, view_variation, valid_views = group_features[group_no]
        z_brix = target_correlation * visual_scores[index] + noise_scale * _seeded_normal(group_no, generator_version)
        virtual_brix = min(18.0, max(9.0, mean_brix + std_brix * z_brix))
        uncertainty = min(1.0, max(0.0, 0.45 + 1.5 * view_variation + 0.5 * feature.texture + 0.5 * feature.lenticel_proxy))
        rows.append(
            {
                "group_no": group_no,
                "virtual_brix": f"{virtual_brix:.1f}",
                "brix_uncertainty": f"{uncertainty:.4f}",
                "brix_source": "simulated_rgb_proxy",
                "brix_is_measured": "false",
                "brix_generator_version": generator_version,
                "brix_target_correlation": f"{target_correlation:.2f}",
                "feature_version": FEATURE_VERSION,
                "feature_redness": f"{feature.redness:.6f}",
                "feature_red_coverage": f"{feature.red_coverage:.6f}",
                "feature_color_uniformity": f"{feature.color_uniformity:.6f}",
                "feature_texture": f"{feature.texture:.6f}",
                "feature_lenticel_proxy": f"{feature.lenticel_proxy:.6f}",
                "valid_view_count": valid_views,
            }
        )
    return rows


def extract_group_features(groups: Iterable[GroupRecord], raw_root: Path, *, views: int = 12) -> dict[str, tuple[RGBProxyFeatures, float, int]]:
    result: dict[str, tuple[RGBProxyFeatures, float, int]] = {}
    archives: dict[Path, object] = {}
    from zipfile import ZipFile

    try:
        for group in groups:
            selected = select_views(group.frames, views).real_frames
            features = []
            for frame in selected:
                archive_path = raw_root / frame.image_archive
                archive = archives.setdefault(archive_path, ZipFile(archive_path))
                features.append(extract_rgb_proxy(archive.read(frame.image_member)))
            result[group.group_no] = aggregate_features(features)
    finally:
        for archive in archives.values():
            archive.close()
    return result


def write_virtual_brix(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def load_virtual_brix(path: Path) -> dict[str, tuple[float, float]]:
    values: dict[str, tuple[float, float]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"group_no", "virtual_brix", "brix_uncertainty", "brix_source", "brix_is_measured"}
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"가상 당도 CSV 필드 누락: {sorted(missing)}")
        for row in reader:
            group_no = row["group_no"]
            if group_no in values:
                raise ValueError(f"가상 당도 group_no 중복: {group_no}")
            if row["brix_source"] != "simulated_rgb_proxy" or row["brix_is_measured"].lower() != "false":
                raise ValueError(f"실측값으로 오인할 수 있는 가상 당도 행입니다: {group_no}")
            brix = float(row["virtual_brix"])
            uncertainty = float(row["brix_uncertainty"])
            if not math.isfinite(brix) or not 9.0 <= brix <= 18.0:
                raise ValueError(f"가상 당도 범위 오류: {group_no}={brix}")
            if not math.isfinite(uncertainty) or not 0.0 <= uncertainty <= 1.0:
                raise ValueError(f"가상 당도 불확실성 범위 오류: {group_no}={uncertainty}")
            values[group_no] = (brix, uncertainty)
    if not values:
        raise ValueError("가상 당도 CSV가 비어 있습니다")
    return values


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="RGB 기반 시연용 가상 당도 생성")
    parser.add_argument("--manifest", type=Path, default=Path("data/processed/manifest.csv"))
    parser.add_argument("--splits", type=Path, default=Path("configs/splits/seed-42.csv"))
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/virtual-brix.csv"))
    parser.add_argument("--views", type=int, default=12)
    parser.add_argument("--target-correlation", type=float, default=0.34)
    args = parser.parse_args(argv)
    groups = load_groups(args.manifest, args.splits)
    features = extract_group_features(groups, args.raw_root, views=args.views)
    development_groups = {group.group_no for group in groups if group.split != "test"}
    rows = build_virtual_brix_rows(
        features,
        target_correlation=args.target_correlation,
        fit_group_numbers=development_groups,
    )
    write_virtual_brix(args.output, rows)
    print(f"virtual_brix={args.output} groups={len(rows)} measured=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
