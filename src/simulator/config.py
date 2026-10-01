"""독립 Simulator 프로세스의 환경변수 설정."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SimulatorSettings(BaseSettings):
    """MLOps가 Volume과 내부 네트워크 주소를 주입한다."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    simulator_dataset_root: Path
    simulator_brix_csv_path: Path | None = None
    simulator_position_path: Path
    simulator_backend_url: str
    simulator_fault_token: str = Field(min_length=1)
    simulator_interval_ms: int = Field(default=2000, ge=1)
    simulator_bind_host: str = "0.0.0.0"
    simulator_bind_port: int = Field(default=8002, ge=1, le=65535)
    simulator_max_request_bytes: int = Field(default=24 * 1024 * 1024, ge=1)
