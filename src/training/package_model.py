"""Package an approved checkpoint with immutable inference metadata."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from src.data.multiview import CULTIVAR_CLASSES, QUALITY_CLASSES
from src.data.torch_dataset import IMAGENET_MEAN, IMAGENET_STD


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="승인 모델 패키지 생성")
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--model-kind", choices=("joint", "separate"), required=True)
    parser.add_argument("--views", type=int, choices=(4, 8, 12, 16, 40), required=True)
    parser.add_argument("--image-size", type=int, default=224)
    parser.add_argument("--output-root", type=Path, default=Path("models"))
    args = parser.parse_args(argv)
    destination = args.output_root / args.version
    if destination.exists():
        parser.error(f"이미 존재하는 모델 버전입니다: {destination}")
    destination.mkdir(parents=True)
    model_path = destination / "model.pt"
    shutil.copy2(args.checkpoint, model_path)
    manifest = {
        "model_name": "mobilenet_v3_small_multiview",
        "model_version": args.version,
        "model_kind": args.model_kind,
        "views": args.views,
        "image_size": args.image_size,
        "preprocessing_version": "rgb-resize-imagenet-v1",
        "cultivar_classes": list(CULTIVAR_CLASSES),
        "quality_classes": list(QUALITY_CLASSES),
        "normalization": {"mean": list(IMAGENET_MEAN), "std": list(IMAGENET_STD)},
        "checkpoint_sha256": sha256(model_path),
    }
    (destination / "model.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"package={destination} sha256={manifest['checkpoint_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
