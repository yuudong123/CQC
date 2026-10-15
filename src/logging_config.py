"""서비스 공통 콘솔·오류 파일 로깅 설정."""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

DEFAULT_LOG_DIR = "logs"
DEFAULT_MAX_BYTES = 10 * 1024 * 1024
DEFAULT_BACKUP_COUNT = 5
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def configure_service_logging() -> Path:
    """콘솔 로그와 ERROR 이상 회전 파일 로그를 설정한다."""

    log_dir = Path(os.environ.get("LOG_DIR", DEFAULT_LOG_DIR))
    max_bytes = int(os.environ.get("LOG_MAX_BYTES", str(DEFAULT_MAX_BYTES)))
    backup_count = int(os.environ.get("LOG_BACKUP_COUNT", str(DEFAULT_BACKUP_COUNT)))
    if max_bytes <= 0:
        raise ValueError("LOG_MAX_BYTES must be greater than zero")
    if backup_count <= 0:
        raise ValueError("LOG_BACKUP_COUNT must be greater than zero")

    log_dir.mkdir(parents=True, exist_ok=True)
    error_log = log_dir / "error.log"
    formatter = logging.Formatter(LOG_FORMAT)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(formatter)
    root.addHandler(console)

    error_file = RotatingFileHandler(
        error_log,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    error_file.setLevel(logging.ERROR)
    error_file.setFormatter(formatter)
    root.addHandler(error_file)

    return error_log
