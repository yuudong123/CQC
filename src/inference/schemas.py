"""추론 서버의 상태 확인·예측 응답 필드와 자료형을 정의한다."""

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
    approval_status: str = Field(default="unknown", examples=["unverified_candidate"])
    threshold_status: str = Field(default="unknown", examples=["not_calibrated"])
    checkpoint_sha256: str = ""
    quality_temperature: float = Field(default=1.0, gt=0)
    cultivar_temperature: float = Field(default=1.0, gt=0)
    decode_workers: int = Field(default=1, ge=1)


class PredictionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inspection_id: str = Field(min_length=1)
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
    used_frame_count: int = Field(ge=1, le=12)
