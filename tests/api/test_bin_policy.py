from __future__ import annotations

import pytest

from src.api.services.bin_policy import DEMO_NORMAL_BIN_MAPPING


@pytest.mark.parametrize("cultivar", ["fuji", "yanggwang"])
@pytest.mark.parametrize("grade", ["L", "M", "S"])
def test_demo_bin_has_two_sweetness_destinations(cultivar: str, grade: str) -> None:
    lower = DEMO_NORMAL_BIN_MAPPING[(cultivar, grade, "less_sweet")]
    upper = DEMO_NORMAL_BIN_MAPPING[(cultivar, grade, "sweet")]
    assert lower != upper
    assert lower == DEMO_NORMAL_BIN_MAPPING[(cultivar, grade, "less_sweet")]
    assert upper == DEMO_NORMAL_BIN_MAPPING[(cultivar, grade, "sweet")]


def test_demo_mapping_has_twelve_distinct_normal_bins() -> None:
    assert len(DEMO_NORMAL_BIN_MAPPING) == 12
    assert len(set(DEMO_NORMAL_BIN_MAPPING.values())) == 12
