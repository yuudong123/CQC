"""관제 검사 이력의 읽기 전용 쿼리."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from sqlalchemy import distinct, exists, func, or_, select
from sqlalchemy.orm import selectinload, sessionmaker

from ..db.models import Inspection, InspectionError

KST = timezone(timedelta(hours=9))
_CULTIVARS = {"부사": "fuji", "양광": "yanggwang"}
_GRADES = {"특": "L", "상": "M", "보통": "S"}
_INFERENCE_ERRORS = (
    "INFERENCE_CONNECTION_ERROR",
    "INFERENCE_HTTP_ERROR",
    "INFERENCE_INVALID_RESPONSE",
    "INFERENCE_ERROR",
)
_BUSINESS_REASONS = (
    "LOW_CULTIVAR_CONFIDENCE",
    "LOW_QUALITY_CONFIDENCE",
    "LOW_BOTH_CONFIDENCE",
    "VIRTUAL_BRIX_MISSING",
)


@dataclass(frozen=True)
class HistoryFilters:
    from_date: date | None = None
    to_date: date | None = None
    variety: str = "ALL"
    grade: str = "ALL"
    bin_code: str = "ALL"
    processing_status: str = "ALL"
    error_code: str = "ALL"
    misclassification: str = "ALL"


@dataclass(frozen=True)
class HistoryRows:
    items: list[Inspection]
    total: int
    bins: list[str]


class QualityHistoryRepository:
    """완료된 검사만 snapshot 경계 내에서 조회한다."""

    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    def list_page(
        self,
        filters: HistoryFilters,
        *,
        snapshot_at: datetime,
        page: int,
        page_size: int,
    ) -> HistoryRows:
        i = Inspection
        clauses: list[Any] = [
            i.completed_at.is_not(None),
            i.completed_at <= snapshot_at,
            i.inspection_status != "PROCESSING",
        ]
        if filters.from_date is not None:
            clauses.append(i.completed_at >= _kst_midnight_utc(filters.from_date))
        if filters.to_date is not None:
            clauses.append(
                i.completed_at < _kst_midnight_utc(filters.to_date + timedelta(days=1))
            )
        if filters.variety != "ALL":
            clauses.append(i.predicted_cultivar == _CULTIVARS[filters.variety])
        if filters.grade != "ALL":
            clauses.append(i.predicted_grade == _GRADES[filters.grade])
        if filters.bin_code != "ALL":
            clauses.append(i.target_bin_code == filters.bin_code)
        if filters.processing_status == "TIMEOUT":
            clauses.append(i.deadline_exceeded.is_(True))
        elif filters.processing_status == "ERROR":
            clauses.append(
                or_(
                    i.error_code.in_(
                        (*_INFERENCE_ERRORS, "BIN_MAPPING_CONFIGURATION_ERROR")
                    ),
                    i.persistence_status == "FAILED",
                )
            )
        elif filters.processing_status == "COMPLETED":
            clauses.extend(
                [
                    i.deadline_exceeded.is_(False),
                    or_(
                        i.error_code.is_(None),
                        ~i.error_code.in_(
                            (*_INFERENCE_ERRORS, "BIN_MAPPING_CONFIGURATION_ERROR")
                        ),
                    ),
                    i.persistence_status != "FAILED",
                ]
            )
        elif filters.processing_status == "INFERENCING":
            clauses.append(False)
        if filters.error_code != "ALL":
            clauses.append(_error_filter(filters.error_code))
        if filters.misclassification != "ALL":
            if filters.misclassification == "NONE":
                clauses.append(i.suspected_error_type.is_(None))
            else:
                clauses.append(i.suspected_error_type == filters.misclassification)

        with self._session_factory() as session:
            total = (
                session.scalar(select(func.count()).select_from(i).where(*clauses)) or 0
            )
            items = list(
                session.scalars(
                    select(i)
                    .where(*clauses)
                    .options(selectinload(i.control_attempts), selectinload(i.errors))
                    .order_by(i.completed_at.desc(), i.inspection_id.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            )
            bins = list(
                session.scalars(
                    select(distinct(i.target_bin_code))
                    .where(
                        i.completed_at.is_not(None),
                        i.completed_at <= snapshot_at,
                        i.inspection_status != "PROCESSING",
                        i.target_bin_code.is_not(None),
                    )
                    .order_by(i.target_bin_code)
                )
            )
            return HistoryRows(items=items, total=total, bins=bins)


def _kst_midnight_utc(day: date) -> datetime:
    return (
        datetime.combine(day, time.min, tzinfo=KST)
        .astimezone(timezone.utc)
        .replace(tzinfo=None)
    )


def _error_filter(code: str) -> Any:
    i = Inspection
    e = InspectionError
    recorded = exists(select(e.id).where(e.inspection_id == i.inspection_id))
    if code == "NONE":
        return ~recorded & or_(
            i.error_code.is_(None), i.error_code.in_(_BUSINESS_REASONS)
        )
    if code == "INFERENCE_TIMEOUT":
        raw_codes = ("INFERENCE_DEADLINE_EXCEEDED",)
    elif code == "INFERENCE_ERROR":
        raw_codes = _INFERENCE_ERRORS
    elif code == "DB_ERROR":
        raw_codes = ("DB_PERSISTENCE_ERROR", "BIN_MAPPING_CONFIGURATION_ERROR")
    else:
        raw_codes = (code,)
    return or_(
        i.error_code.in_(raw_codes),
        exists(
            select(e.id).where(
                e.inspection_id == i.inspection_id,
                e.error_code.in_(raw_codes),
            )
        ),
    )
