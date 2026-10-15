from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Self

import pytest
from sqlalchemy.exc import OperationalError

from src.api.core.datetime import to_utc_naive, utc_now
from src.api.db.models import BinMapping
from src.api.repositories.bin_mappings import (
    BinMappingConfigurationError,
    BinMappingRepository,
    BinMappingUnavailableError,
)
from src.api.services.bin_policy import DEMO_NORMAL_BIN_MAPPING


class _ScalarSession:
    def __init__(self, values: list[BinMapping] | Exception) -> None:
        self._values = values

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def scalars(self, statement: object) -> _ScalarSession:
        del statement
        return self

    def all(self) -> list[BinMapping]:
        if isinstance(self._values, Exception):
            raise self._values
        return self._values


class _SessionFactory:
    def __init__(self, values: list[BinMapping] | Exception) -> None:
        self._values = values

    def __call__(self) -> _ScalarSession:
        return _ScalarSession(self._values)


def _mapping_rows() -> list[BinMapping]:
    rows = [
        BinMapping(
            crop_type="apple",
            cultivar=cultivar,
            quality_grade=grade,
            sweetness_band=sweetness,
            bin_code=code,
            is_reinspection=False,
            is_active=True,
        )
        for (cultivar, grade, sweetness), code in DEMO_NORMAL_BIN_MAPPING.items()
    ]
    rows.append(
        BinMapping(
            crop_type=None,
            cultivar=None,
            quality_grade=None,
            sweetness_band=None,
            bin_code="TEST_REINSPECTION_BIN",
            is_reinspection=True,
            is_active=True,
        )
    )
    return rows


def test_bin_mapping_repository_loads_complete_snapshot_once() -> None:
    repository = BinMappingRepository(_SessionFactory(_mapping_rows()))  # type: ignore[arg-type]
    snapshot = repository.load_snapshot()

    assert len(snapshot.normal_bins) == 12
    assert snapshot.reinspection_bin == "TEST_REINSPECTION_BIN"
    assert (
        snapshot.normal_bin(
            crop_type="apple",
            cultivar="fuji",
            quality_grade="L",
            sweetness_band="sweet",
        )
        == DEMO_NORMAL_BIN_MAPPING[("fuji", "L", "sweet")]
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_normal",
        "missing_reinspection",
        "duplicate_normal",
        "duplicate_reinspection",
        "wrong_key",
        "duplicate_code",
    ],
)
def test_bin_mapping_repository_rejects_invalid_snapshot(mutation: str) -> None:
    rows = _mapping_rows()
    if mutation == "missing_normal":
        rows.pop(0)
    elif mutation == "missing_reinspection":
        rows.pop()
    elif mutation == "duplicate_normal":
        rows.append(rows[0])
    elif mutation == "duplicate_reinspection":
        rows.append(rows[-1])
    elif mutation == "wrong_key":
        rows[0].cultivar = "unknown"
    else:
        rows[0].bin_code = rows[1].bin_code
    repository = BinMappingRepository(_SessionFactory(rows))  # type: ignore[arg-type]

    with pytest.raises(BinMappingConfigurationError):
        repository.load_snapshot()


def test_bin_mapping_repository_distinguishes_db_unavailable() -> None:
    failure = OperationalError("SELECT", {}, Exception("connection lost"))
    repository = BinMappingRepository(_SessionFactory(failure))  # type: ignore[arg-type]

    with pytest.raises(BinMappingUnavailableError):
        repository.load_snapshot()


def test_datetime_storage_converts_aware_value_to_utc_naive_milliseconds() -> None:
    kst_value = datetime(
        2026, 9, 29, 12, 34, 56, 123456, tzinfo=timezone(timedelta(hours=9))
    )

    stored = to_utc_naive(kst_value)

    assert stored == datetime.fromisoformat("2026-09-29T03:34:56.123")
    assert stored.tzinfo is None
    assert utc_now().tzinfo is timezone.utc


def test_datetime_storage_rejects_naive_application_value() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        to_utc_naive(datetime.fromisoformat("2026-09-29T00:00:00"))
