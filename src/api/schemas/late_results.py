"""Business deadline 이후 도착한 Inference 진단 결과 Schema."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .inference import InferenceResponse


class LateInferenceResult(BaseModel):
    """확정 판정과 분리해 메모리에만 보관하는 늦은 응답."""

    model_config = ConfigDict(extra="forbid")

    inspection_id: str = Field(min_length=1)
    is_late: Literal[True] = True
    inference_response: InferenceResponse
