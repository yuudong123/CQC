"""환경변수 기반 백엔드 애플리케이션 설정."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
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
    inference_max_files: int = Field(default=12, ge=1)
    inference_max_request_bytes: int = Field(default=24 * 1024 * 1024, ge=1)


@lru_cache
def get_settings() -> Settings:
    """검증된 애플리케이션 설정을 프로세스 범위에서 재사용한다."""

    return Settings()
