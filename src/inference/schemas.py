"""Typed HTTP response contracts for the inference service."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = Field(examples=["ready"])
    model_loaded: bool
    model_name: str
    model_version: str
    device: str
    views: int = Field(ge=1)


class PredictionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    crop_type: str = Field(examples=["apple"])
    predicted_cultivar: str = Field(examples=["fuji"])
    cultivar_confidence: float = Field(ge=0, le=1)
    cultivar_probabilities: dict[str, float]
    predicted_grade: str = Field(examples=["L"])
    quality_confidence: float = Field(ge=0, le=1)
    quality_probabilities: dict[str, float]
    inference_time_ms: float = Field(ge=0)
    model_name: str
    model_version: str
    preprocessing_version: str
