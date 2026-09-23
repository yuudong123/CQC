"""검사 이미지 metadata Schema."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel


class InspectionImageMetadata(BaseModel):
    """선택된 검사 이미지 한 장과 대응하는 metadata."""

    model_config = ConfigDict(extra="forbid")

    view_index: int = Field(ge=0)
    angle_direction: Literal["top", "bottom"]
    # 최종 각도 허용 범위는 별도 팀 계약이 확정된 후 적용한다.
    verticality_angle: int
    horizontality_angle: int


class InspectionMetadata(RootModel[list[InspectionImageMetadata]]):
    """반복 images 필드와 위치 기준으로 대응하는 순서가 있는 metadata 목록."""
