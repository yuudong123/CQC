"""Masked multi-view baseline with shared image features and two prediction heads."""

from __future__ import annotations

import torch
from torch import Tensor, nn
from torchvision.models import MobileNet_V3_Small_Weights, mobilenet_v3_small


class MultiViewBaseline(nn.Module):
    """Encode each view, aggregate valid features, and predict cultivar and quality."""

    def __init__(self, *, pretrained: bool = True, dropout: float = 0.2) -> None:
        super().__init__()
        weights = MobileNet_V3_Small_Weights.DEFAULT if pretrained else None
        backbone = mobilenet_v3_small(weights=weights)
        feature_dim = backbone.classifier[0].in_features
        self.encoder = nn.Sequential(backbone.features, backbone.avgpool, nn.Flatten(1))
        self.dropout = nn.Dropout(dropout)
        self.cultivar_head = nn.Linear(feature_dim, 2)
        self.quality_head = nn.Linear(feature_dim, 3)

    @staticmethod
    def masked_mean(features: Tensor, view_mask: Tensor) -> Tensor:
        if features.ndim != 3 or view_mask.ndim != 2:
            raise ValueError("features는 [B,V,F], view_mask는 [B,V]여야 합니다")
        if features.shape[:2] != view_mask.shape:
            raise ValueError("features와 view_mask의 B,V 크기가 다릅니다")
        valid = view_mask.to(dtype=features.dtype).unsqueeze(-1)
        counts = valid.sum(dim=1)
        if torch.any(counts == 0):
            raise ValueError("각 그룹에는 실제 이미지가 1장 이상 필요합니다")
        return (features * valid).sum(dim=1) / counts

    def forward(self, images: Tensor, view_mask: Tensor) -> dict[str, Tensor]:
        if images.ndim != 5:
            raise ValueError("images는 [B,V,C,H,W]여야 합니다")
        batch, views, channels, height, width = images.shape
        encoded = self.encoder(images.reshape(batch * views, channels, height, width))
        pooled = self.dropout(self.masked_mean(encoded.reshape(batch, views, -1), view_mask))
        return {
            "cultivar_logits": self.cultivar_head(pooled),
            "quality_logits": self.quality_head(pooled),
        }
