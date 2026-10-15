from __future__ import annotations

import pytest

from src.api.services.bin_policy import (
    DEMO_NORMAL_BIN_MAPPING,
    DEMO_SWEETNESS_THRESHOLD_BRIX,
)
from src.api.services.inspections import _classify_sweetness


@pytest.mark.parametrize("cultivar", ["fuji", "yanggwang"])
@pytest.mark.parametrize("grade", ["L", "M", "S"])
def test_demo_bin_has_two_sweetness_destinations(cultivar: str, grade: str) -> None:
    lower = DEMO_NORMAL_BIN_MAPPING[(cultivar, grade, _classify_sweetness(13.9))]
    upper = DEMO_NORMAL_BIN_MAPPING[(cultivar, grade, _classify_sweetness(14.0))]
    assert lower != upper
    assert lower == DEMO_NORMAL_BIN_MAPPING[(cultivar, grade, "less_sweet")]
    assert upper == DEMO_NORMAL_BIN_MAPPING[(cultivar, grade, "sweet")]


def test_demo_mapping_has_twelve_distinct_normal_bins() -> None:
    assert DEMO_SWEETNESS_THRESHOLD_BRIX == 14.0
    assert len(DEMO_NORMAL_BIN_MAPPING) == 12
    assert set(DEMO_NORMAL_BIN_MAPPING.values()) == {
        f"DEMO_BIN_{index:02d}" for index in range(1, 13)
    }


@pytest.mark.parametrize(
    ("virtual_brix", "expected"),
    [
        (9.0, "less_sweet"),
        (12.0, "less_sweet"),
        (13.9, "less_sweet"),
        (14.0, "sweet"),
        (18.0, "sweet"),
    ],
)
def test_demo_sweetness_boundary(virtual_brix: float, expected: str) -> None:
    assert _classify_sweetness(virtual_brix) == expected


@pytest.mark.parametrize("virtual_brix", [8.9, 18.1, float("nan"), float("inf")])
def test_demo_sweetness_rejects_out_of_range_values(virtual_brix: float) -> None:
    with pytest.raises(ValueError, match="9~18"):
        _classify_sweetness(virtual_brix)
