"""환경변수 기반 백엔드 애플리케이션 설정."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """환경변수와 로컬 .env 파일에서 실행 설정을 불러온다."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "CQC Backend"
    app_env: str = "local"
    app_host: str = "0.0.0.0"
    app_port: int = Field(default=8000, ge=1, le=65535)
    database_url: str | None = None
    db_connect_timeout_seconds: int = Field(default=1, ge=1)
    inspection_history_limit: int = Field(default=86_400, ge=2)
    inspection_history_delete_batch: int = Field(default=8_640, ge=1)
    inference_client_mode: Literal["mock", "http"] = "mock"
    inference_url: str = "http://inference:8001/v1/predict"
    inference_max_files: int = Field(default=12, ge=1)
    inference_max_request_bytes: int = Field(default=24 * 1024 * 1024, ge=1)
    cultivar_confidence_threshold: float = Field(default=0.50, ge=0, le=1)
    quality_confidence_threshold: float = Field(default=0.60, ge=0, le=1)
    inference_business_deadline_ms: int = Field(default=500, ge=1)
    inference_hard_timeout_ms: int = Field(default=2000, ge=1)
    inference_health_timeout_ms: int = Field(default=1_500, ge=1)
    max_late_tasks: int = Field(default=4, ge=0)
    fault_image_storage_root: Path | None = None
    fault_image_limit: int = Field(default=100, ge=1)
    simulator_internal_url: str | None = None
    simulator_internal_timeout_ms: int = Field(default=30_000, ge=1)
    simulator_state_timeout_ms: int = Field(default=1_500, ge=1)
    simulator_fault_token: str | None = None

    @model_validator(mode="after")
    def validate_inference_deadlines(self) -> Settings:
        """Hard timeout이 business deadline보다 뒤에 오도록 검증한다."""

        if self.inference_hard_timeout_ms <= self.inference_business_deadline_ms:
            raise ValueError(
                "INFERENCE_HARD_TIMEOUT_MS는 "
                "INFERENCE_BUSINESS_DEADLINE_MS보다 커야 합니다"
            )
        if self.inspection_history_delete_batch >= self.inspection_history_limit:
            raise ValueError(
                "INSPECTION_HISTORY_DELETE_BATCH는 INSPECTION_HISTORY_LIMIT보다 작아야 합니다"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """검증된 애플리케이션 설정을 프로세스 범위에서 재사용한다."""

    return Settings()
