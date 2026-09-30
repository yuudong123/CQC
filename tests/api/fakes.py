"""Backend Service 단위 테스트용 명시적 저장·mapping test double."""

from __future__ import annotations

from datetime import datetime

from src.api.repositories.records import ControlAttemptRecord, InspectionErrorRecord
from src.api.services.bin_policy import (
    DEMO_NORMAL_BIN_MAPPING,
    TEMPORARY_REINSPECTION_BIN_CODE,
)


class FakeBinMappingRepository:
    """12-bin seed와 동일한 값을 반환하는 Repository test double."""

    def __init__(self) -> None:
        self.normal_calls: list[dict[str, str]] = []
        self.reinspection_calls = 0

    def find_normal_bin(
        self,
        *,
        crop_type: str,
        cultivar: str,
        quality_grade: str,
        sweetness_band: str,
    ) -> str:
        self.normal_calls.append(
            {
                "crop_type": crop_type,
                "cultivar": cultivar,
                "quality_grade": quality_grade,
                "sweetness_band": sweetness_band,
            }
        )
        return DEMO_NORMAL_BIN_MAPPING[(cultivar, quality_grade, sweetness_band)]

    def find_reinspection_bin(self) -> str:
        self.reinspection_calls += 1
        return TEMPORARY_REINSPECTION_BIN_CODE


class RecordingPersistence:
    """트랜잭션 호출값을 메모리에 기록하는 persistence test double."""

    def __init__(
        self,
        *,
        fail_create: bool = False,
        fail_finalize: bool = False,
        fail_late: bool = False,
    ) -> None:
        self.fail_create = fail_create
        self.fail_finalize = fail_finalize
        self.fail_late = fail_late
        self.pending_values: list[dict[str, object]] = []
        self.final_values: list[dict[str, object]] = []
        self.control_attempts: list[ControlAttemptRecord] = []
        self.errors: list[InspectionErrorRecord] = []
        self.failed_ids: list[str] = []
        self.late_results: list[tuple[str, datetime, dict[str, object]]] = []

    def create_pending(self, values: dict[str, object]) -> None:
        if self.fail_create:
            raise RuntimeError("create failed")
        self.pending_values.append(values)

    def finalize(
        self,
        *,
        inspection_id: str,
        inspection_values: dict[str, object],
        control_attempts: list[ControlAttemptRecord],
        errors: list[InspectionErrorRecord],
    ) -> None:
        del inspection_id
        if self.fail_finalize:
            raise RuntimeError("finalize failed")
        self.final_values.append(inspection_values)
        self.control_attempts.extend(control_attempts)
        self.errors.extend(errors)

    def mark_failed(
        self,
        *,
        inspection_id: str,
        updated_at: object,
        error: InspectionErrorRecord,
    ) -> None:
        del updated_at
        self.failed_ids.append(inspection_id)
        self.errors.append(error)

    def save_late_result(
        self,
        *,
        inspection_id: str,
        received_at: datetime,
        payload: dict[str, object],
    ) -> None:
        if self.fail_late:
            raise RuntimeError("late result save failed")
        self.late_results.append((inspection_id, received_at, payload))
