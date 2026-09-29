from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Self

import pytest

from src.api.core.datetime import to_utc_naive, utc_now
from src.api.repositories.bin_mappings import (
    BinMappingConfigurationError,
    BinMappingRepository,
)


class _ScalarSession:
    def __init__(self, values: list[str]) -> None:
        self._values = values

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def scalars(self, statement: object) -> _ScalarSession:
        del statement
        return self

    def all(self) -> list[str]:
        return self._values


class _SessionFactory:
    def __init__(self, values: list[str]) -> None:
        self._values = values

    def __call__(self) -> _ScalarSession:
        return _ScalarSession(self._values)


@pytest.mark.parametrize("values", [[], ["BIN_A", "BIN_B"]])
@pytest.mark.parametrize("mapping_type", ["normal", "reinspection"])
def test_bin_mapping_repository_requires_exactly_one_active_mapping(
    values: list[str],
    mapping_type: str,
) -> None:
    repository = BinMappingRepository(_SessionFactory(values))  # type: ignore[arg-type]

    with pytest.raises(BinMappingConfigurationError, match="정확히 1개"):
        if mapping_type == "normal":
            repository.find_normal_bin(
                crop_type="apple",
                cultivar="fuji",
                quality_grade="L",
                sweetness_band="less_sweet",
            )
        else:
            repository.find_reinspection_bin()


def test_datetime_storage_converts_aware_value_to_utc_naive_milliseconds() -> None:
    kst_value = datetime(
        2026,
        9,
        29,
        12,
        34,
        56,
        123456,
        tzinfo=timezone(timedelta(hours=9)),
    )

    stored = to_utc_naive(kst_value)

    assert stored == datetime.fromisoformat("2026-09-29T03:34:56.123")
    assert stored.tzinfo is None
    assert utc_now().tzinfo is timezone.utc


def test_datetime_storage_rejects_naive_application_value() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        to_utc_naive(datetime.fromisoformat("2026-09-29T00:00:00"))
