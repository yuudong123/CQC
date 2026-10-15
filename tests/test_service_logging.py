from __future__ import annotations

import logging
from pathlib import Path

import pytest

from src.logging_config import configure_service_logging


@pytest.fixture(autouse=True)
def restore_root_handlers() -> None:
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level
    yield
    for handler in root.handlers:
        handler.close()
    root.handlers[:] = original_handlers
    root.setLevel(original_level)


def test_only_error_and_above_are_written_and_rotated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LOG_DIR", str(tmp_path))
    monkeypatch.setenv("LOG_MAX_BYTES", "120")
    monkeypatch.setenv("LOG_BACKUP_COUNT", "2")
    error_log = configure_service_logging()

    logger = logging.getLogger("test.service")
    logger.info("not-in-error-file")
    logger.warning("warning-not-in-error-file")
    for index in range(20):
        logger.error("rotating-error-%02d-%s", index, "x" * 40)
    logger.critical("critical-in-error-file")
    for handler in logging.getLogger().handlers:
        handler.flush()

    files = sorted(tmp_path.glob("error.log*"))
    assert error_log in files
    assert 1 < len(files) <= 3
    contents = "".join(path.read_text(encoding="utf-8") for path in files)
    assert "critical-in-error-file" in contents
    assert "rotating-error" in contents
    assert "not-in-error-file" not in contents
    assert "warning-not-in-error-file" not in contents
    assert all(path.stat().st_size <= 120 for path in files)


def test_uvicorn_errors_reach_error_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fastapi import FastAPI
    from uvicorn import Config

    monkeypatch.setenv("LOG_DIR", str(tmp_path))
    error_log = configure_service_logging()
    Config(FastAPI(), log_config=None)

    logging.getLogger("uvicorn.error").error("uvicorn-error-probe")
    for handler in logging.getLogger().handlers:
        handler.flush()

    assert "uvicorn-error-probe" in error_log.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("name", "value"),
    (("LOG_MAX_BYTES", "0"), ("LOG_BACKUP_COUNT", "0")),
)
def test_invalid_rotation_limits_fail_fast(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    value: str,
) -> None:
    monkeypatch.setenv("LOG_DIR", str(tmp_path))
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError):
        configure_service_logging()
