from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from types import MappingProxyType

import pytest

from src.api.repositories.bin_mappings import (
    BinMappingConfigurationError,
    BinMappingSnapshot,
    BinMappingUnavailableError,
)
from src.api.services.bin_mapping_lkg import LkgBinMapping
from src.api.services.bin_policy import DEMO_NORMAL_BIN_MAPPING


def _snapshot(suffix: str) -> BinMappingSnapshot:
    return BinMappingSnapshot(
        {
            ("apple", cultivar, grade, sweetness): f"{code}-{suffix}"
            for (cultivar, grade, sweetness), code in DEMO_NORMAL_BIN_MAPPING.items()
        },
        f"REINSPECTION-{suffix}",
    )


class _ChangingRepository:
    def __init__(self, result: BinMappingSnapshot | Exception) -> None:
        self.result = result
        self.calls = 0

    def load_snapshot(self) -> BinMappingSnapshot:
        self.calls += 1
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def test_lkg_cold_start_unavailable_preserves_failure() -> None:
    repository = _ChangingRepository(BinMappingUnavailableError("offline"))
    lkg = LkgBinMapping(repository)  # type: ignore[arg-type]

    with pytest.raises(BinMappingUnavailableError):
        lkg.resolve()


def test_lkg_fallback_then_recovery_replaces_whole_snapshot() -> None:
    first, second = _snapshot("A"), _snapshot("B")
    repository = _ChangingRepository(first)
    lkg = LkgBinMapping(repository)  # type: ignore[arg-type]

    assert lkg.resolve() is first
    repository.result = BinMappingUnavailableError("offline")
    assert lkg.resolve() is first
    repository.result = second
    assert lkg.resolve() is second
    assert repository.calls == 3
    assert first.reinspection_bin == "REINSPECTION-A"
    assert second.reinspection_bin == "REINSPECTION-B"


def test_lkg_configuration_error_never_uses_cached_snapshot() -> None:
    repository = _ChangingRepository(_snapshot("A"))
    lkg = LkgBinMapping(repository)  # type: ignore[arg-type]
    lkg.resolve()
    repository.result = BinMappingConfigurationError("invalid active mapping")

    with pytest.raises(BinMappingConfigurationError):
        lkg.resolve()


def test_snapshot_copies_mapping_and_rejects_mutation() -> None:
    mutable = dict(_snapshot("A").normal_bins)
    snapshot = BinMappingSnapshot(mutable, "REINSPECTION-A")
    key = next(iter(mutable))
    mutable[key] = "CHANGED"

    assert snapshot.normal_bins[key] != "CHANGED"
    assert isinstance(snapshot.normal_bins, MappingProxyType)
    with pytest.raises(TypeError):
        snapshot.normal_bins[key] = "CHANGED"  # type: ignore[index]


def test_concurrent_resolve_observes_only_complete_snapshots() -> None:
    first, second = _snapshot("A"), _snapshot("B")
    repository = _ChangingRepository(first)
    lkg = LkgBinMapping(repository)  # type: ignore[arg-type]
    lkg.resolve()
    repository.result = second

    with ThreadPoolExecutor(max_workers=8) as pool:
        snapshots = list(pool.map(lambda _: lkg.resolve(), range(32)))

    assert all(snapshot in (first, second) for snapshot in snapshots)
    assert all(len(snapshot.normal_bins) == 12 for snapshot in snapshots)
