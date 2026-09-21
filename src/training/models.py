"""Model variants used by the DM-05/DM-06 training experiments."""

from __future__ import annotations

import torch
from torch import Tensor, nn
from torchvision.models import MobileNet_V3_Small_Weights, mobilenet_v3_small

from src.models.multiview import MultiViewBaseline


MODEL_KINDS = ("joint", "separate")


class _TaskEncoder(nn.Module):
    def __init__(self, classes: int, *, pretrained: bool, dropout: float) -> None:
        super().__init__()
        weights = MobileNet_V3_Small_Weights.DEFAULT if pretrained else None
        backbone = mobilenet_v3_small(weights=weights)
        feature_dim = backbone.classifier[0].in_features
        self.encoder = nn.Sequential(backbone.features, backbone.avgpool, nn.Flatten(1))
        self.dropout = nn.Dropout(dropout)
        self.head = nn.Linear(feature_dim, classes)

    def forward(self, images: Tensor, view_mask: Tensor) -> Tensor:
        batch, views, channels, height, width = images.shape
        encoded = self.encoder(images.reshape(batch * views, channels, height, width))
        pooled = MultiViewBaseline.masked_mean(
            encoded.reshape(batch, views, -1), view_mask
        )
        return self.head(self.dropout(pooled))


class SeparateTaskBaseline(nn.Module):
    """Use independent encoders for cultivar and quality classification."""

    def __init__(self, *, pretrained: bool = True, dropout: float = 0.2) -> None:
        super().__init__()
        self.cultivar_model = _TaskEncoder(
            2, pretrained=pretrained, dropout=dropout
        )
        self.quality_model = _TaskEncoder(3, pretrained=pretrained, dropout=dropout)

    def forward(self, images: Tensor, view_mask: Tensor) -> dict[str, Tensor]:
        if images.ndim != 5:
            raise ValueError("images는 [B,V,C,H,W]여야 합니다")
        return {
            "cultivar_logits": self.cultivar_model(images, view_mask),
            "quality_logits": self.quality_model(images, view_mask),
        }


def build_model(kind: str, *, pretrained: bool = True, dropout: float = 0.2) -> nn.Module:
    if kind == "joint":
        return MultiViewBaseline(pretrained=pretrained, dropout=dropout)
    if kind == "separate":
        return SeparateTaskBaseline(pretrained=pretrained, dropout=dropout)
    raise ValueError(f"지원하지 않는 모델 종류입니다: {kind!r}; {MODEL_KINDS} 중 선택")
