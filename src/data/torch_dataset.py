"""PyTorch adapter using the same selected views as training and inference."""

from __future__ import annotations

from io import BytesIO
from typing import Any, Mapping

import torch
from PIL import Image
from torch import Tensor
from torch.utils.data import Dataset
from torchvision.transforms import v2

from .multiview import MultiViewDataset


IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


def build_transform(*, training: bool, image_size: int = 224) -> v2.Compose:
    operations: list[Any] = [v2.ToImage(), v2.Resize((image_size, image_size), antialias=True)]
    if training:
        operations.extend([v2.RandomHorizontalFlip(), v2.RandomRotation(8)])
    operations.extend([v2.ToDtype(torch.float32, scale=True), v2.Normalize(IMAGENET_MEAN, IMAGENET_STD)])
    return v2.Compose(operations)


class TorchMultiViewDataset(Dataset[dict[str, Any]]):
    def __init__(self, source: MultiViewDataset, *, training: bool, image_size: int = 224, virtual_brix: Mapping[str, tuple[float, float]] | None = None) -> None:
        self.source = source
        self.transform = build_transform(training=training, image_size=image_size)
        self.image_size = image_size
        self.virtual_brix = virtual_brix

    def __len__(self) -> int:
        return len(self.source)

    def __getitem__(self, index: int) -> dict[str, Any]:
        item = self.source[index]
        images: list[Tensor] = []
        for image_bytes in item["images"]:
            if image_bytes is None:
                images.append(torch.zeros(3, self.image_size, self.image_size))
                continue
            with Image.open(BytesIO(image_bytes)) as image:
                images.append(self.transform(image.convert("RGB")))
        result = {
            "group_no": item["group_no"],
            "images": torch.stack(images),
            "view_mask": torch.tensor(item["view_mask"], dtype=torch.bool),
            "cultivar_target": torch.tensor(item["cultivar_index"], dtype=torch.long),
            "quality_target": torch.tensor(item["quality_index"], dtype=torch.long),
        }
        if self.virtual_brix is not None:
            if item["group_no"] not in self.virtual_brix:
                raise KeyError(f"가상 당도 누락: {item['group_no']}")
            brix, uncertainty = self.virtual_brix[item["group_no"]]
            result["virtual_brix"] = torch.tensor(brix, dtype=torch.float32)
            result["brix_uncertainty"] = torch.tensor(uncertainty, dtype=torch.float32)
        return result
