"""기본 공유 모델, 품종·품질 분리 모델, 가상 당도 결합 모델을 생성한다."""

from __future__ import annotations

import torch
from torch import Tensor, nn
from torchvision.models import MobileNet_V3_Small_Weights, mobilenet_v3_small

from src.models.multiview import MultiViewBaseline


MODEL_KINDS = ("joint", "separate")
TRAIN_MODEL_KINDS = MODEL_KINDS + ("separate_brix",)


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
        """사진과 유효 마스크를 받아 품종·품질 예측 점수를 계산한다."""
        batch, views, channels, height, width = images.shape
        encoded = self.encoder(images.reshape(batch * views, channels, height, width))
        pooled = MultiViewBaseline.masked_mean(
            encoded.reshape(batch, views, -1), view_mask
        )
        return self.head(self.dropout(pooled))


class SeparateTaskBaseline(nn.Module):
    """품종과 품질에 독립적인 이미지 특징 추출기를 사용한다."""

    def __init__(self, *, pretrained: bool = True, dropout: float = 0.2) -> None:
        super().__init__()
        self.cultivar_model = _TaskEncoder(
            2, pretrained=pretrained, dropout=dropout
        )
        self.quality_model = _TaskEncoder(3, pretrained=pretrained, dropout=dropout)

    def forward(self, images: Tensor, view_mask: Tensor) -> dict[str, Tensor]:
        """사진과 유효 마스크를 받아 품종·품질 예측 점수를 계산한다."""
        if images.ndim != 5:
            raise ValueError("images는 [B,V,C,H,W]여야 합니다")
        return {
            "cultivar_logits": self.cultivar_model(images, view_mask),
            "quality_logits": self.quality_model(images, view_mask),
        }


class SeparateTaskBrixFusion(nn.Module):
    """시연용 가상 당도와 불확실성을 품질 예측에만 결합한다."""

    def __init__(self, *, pretrained: bool = True, dropout: float = 0.2) -> None:
        super().__init__()
        self.cultivar_model = _TaskEncoder(2, pretrained=pretrained, dropout=dropout)
        self.quality_encoder = _TaskEncoder(3, pretrained=pretrained, dropout=dropout)
        feature_dim = self.quality_encoder.head.in_features
        self.quality_encoder.head = nn.Identity()
        self.quality_head = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(feature_dim + 2, 128),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(128, 3),
        )

    def forward(self, images: Tensor, view_mask: Tensor, virtual_brix: Tensor | None = None, brix_uncertainty: Tensor | None = None) -> dict[str, Tensor]:
        """사진과 유효 마스크를 받아 품종·품질 예측 점수를 계산한다."""
        if virtual_brix is None or brix_uncertainty is None:
            raise ValueError("separate_brix 모델에는 virtual_brix와 brix_uncertainty가 필요합니다")
        quality_features = self.quality_encoder(images, view_mask)
        brix_features = torch.stack(((virtual_brix - 14.0) / 1.5, brix_uncertainty), dim=1)
        return {
            "cultivar_logits": self.cultivar_model(images, view_mask),
            "quality_logits": self.quality_head(torch.cat((quality_features, brix_features), dim=1)),
        }


def build_model(kind: str, *, pretrained: bool = True, dropout: float = 0.2) -> nn.Module:
    """모델 종류에 맞는 신경망을 만들고 사전학습·드롭아웃 설정을 적용한다."""
    if kind == "joint":
        return MultiViewBaseline(pretrained=pretrained, dropout=dropout)
    if kind == "separate":
        return SeparateTaskBaseline(pretrained=pretrained, dropout=dropout)
    if kind == "separate_brix":
        return SeparateTaskBrixFusion(pretrained=pretrained, dropout=dropout)
    raise ValueError(f"지원하지 않는 모델 종류입니다: {kind!r}; {TRAIN_MODEL_KINDS} 중 선택")
