"""시연 가상 당도 구간과 12-bin 계약 상수."""

from __future__ import annotations

TEMPORARY_REINSPECTION_BIN_CODE = "TEST_REINSPECTION_BIN"

# 시연용 12-bin 기본 mapping과 가상 당도 구간 기준.
DEMO_SWEETNESS_THRESHOLD_BRIX = 14.0
DEMO_SWEETNESS_LABELS = ("less_sweet", "sweet")
DEMO_NORMAL_BIN_MAPPING: dict[tuple[str, str, str], str] = {
    (cultivar, grade, sweetness): f"DEMO_BIN_{index:02d}"
    for index, (cultivar, grade, sweetness) in enumerate(
        (
            (cultivar, grade, sweetness)
            for cultivar in ("fuji", "yanggwang")
            for grade in ("L", "M", "S")
            for sweetness in DEMO_SWEETNESS_LABELS
        ),
        start=1,
    )
}
