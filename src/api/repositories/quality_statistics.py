"""관제 통계의 DB 집계 쿼리."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import case, exists, func, select
from sqlalchemy.orm import sessionmaker

from ..db.models import ControlAttempt, Inspection
from .quality_history import KST, HistoryFilters, history_clauses

_CULTIVARS = {"fuji": "부사", "yanggwang": "양광"}
_GRADES = {"L": "특", "M": "상", "S": "보통"}
_SUSPICIONS = {
    "CULTIVAR_SUSPECT": "CULTIVAR_SUSPECT",
    "QUALITY_SUSPECT": "QUALITY_SUSPECT",
    "OTHER": "OTHER",
}


class StatisticsContractError(ValueError):
    """저장된 category 값을 공개 통계 계약으로 변환할 수 없다."""


class QualityStatisticsRepository:
    """검사 전체를 로드하지 않고 count·sum·category를 DB에서 계산한다."""

    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    def summary(
        self, filters: HistoryFilters, snapshot_at: datetime
    ) -> dict[str, object]:
        i = Inspection
        clauses = history_clauses(filters, snapshot_at)
        review = _review_condition()
        measured = i.exclude_from_normal_stats.is_(False)
        with self._session_factory() as session:
            values = session.execute(
                select(
                    func.count(),
                    func.coalesce(func.sum(case((measured, 1), else_=0)), 0),
                    func.coalesce(
                        func.sum(
                            case((i.exclude_from_normal_stats.is_(True), 1), else_=0)
                        ),
                        0,
                    ),
                    func.coalesce(func.sum(case((review, 1), else_=0)), 0),
                    func.coalesce(
                        func.sum(
                            case(
                                (
                                    measured & i.inference_time_ms.is_not(None),
                                    i.inference_time_ms,
                                ),
                                else_=0,
                            )
                        ),
                        0,
                    ),
                    func.coalesce(
                        func.sum(
                            case(
                                (measured & i.inference_time_ms.is_not(None), 1),
                                else_=0,
                            )
                        ),
                        0,
                    ),
                ).where(*clauses)
            ).one()
            varieties = _group_counts(
                session, i.predicted_cultivar, clauses + [measured], _CULTIVARS
            )
            grades = _group_counts(
                session, i.predicted_grade, clauses + [measured], _GRADES
            )
            bins = _group_counts(
                session,
                i.target_bin_code,
                clauses + [i.control_status == "SUCCEEDED"],
            )
            suspicions = _group_counts(
                session, i.suspected_error_type, clauses, _SUSPICIONS
            )
        return {
            "total": int(values[0]),
            "normal": int(values[1]),
            "excluded": int(values[2]),
            "reinspection": int(values[3]),
            "inferenceTotalMs": float(values[4]),
            "inferenceCount": int(values[5]),
            "varieties": varieties,
            "grades": grades,
            "bins": bins,
            "suspicions": suspicions,
        }

    def today(self, snapshot_at: datetime) -> tuple[str, dict[str, object]]:
        day = snapshot_at.replace(tzinfo=timezone.utc).astimezone(KST).date()
        summary = self.summary(HistoryFilters(from_date=day, to_date=day), snapshot_at)
        return day.isoformat(), summary

    def review_count(self, filters: HistoryFilters, snapshot_at: datetime) -> int:
        i = Inspection
        with self._session_factory() as session:
            return (
                session.scalar(
                    select(func.count())
                    .select_from(i)
                    .where(
                        *history_clauses(filters, snapshot_at),
                        i.exclude_from_normal_stats.is_(False),
                        _review_condition(),
                    )
                )
                or 0
            )

    def last_saved(self, snapshot_at: datetime) -> datetime | None:
        i = Inspection
        with self._session_factory() as session:
            return session.scalar(
                select(func.max(i.completed_at)).where(
                    *history_clauses(HistoryFilters(), snapshot_at)
                )
            )

    def period_totals(self, snapshot_at: datetime) -> dict[str, int]:
        i = Inspection
        boundaries = [snapshot_at - timedelta(minutes=n) for n in (1, 5, 10, 30)]
        with self._session_factory() as session:
            row = session.execute(
                select(
                    *[
                        func.coalesce(
                            func.sum(case((i.completed_at > boundary, 1), else_=0)), 0
                        )
                        for boundary in boundaries
                    ]
                ).where(*history_clauses(HistoryFilters(), snapshot_at))
            ).one()
        return {
            str(n): int(value) for n, value in zip((1, 5, 10, 30), row, strict=True)
        }

    def points(self, snapshot_at: datetime, seconds: int = 30) -> list[dict[str, int]]:
        """최대 30초의 작은 시각 목록만 가져와 초 단위 빈 bucket을 채운다."""

        i = Inspection
        floor = snapshot_at.replace(microsecond=0)
        start = floor - timedelta(seconds=seconds - 1)
        with self._session_factory() as session:
            rows = session.execute(
                select(
                    i.completed_at, _review_condition(), i.exclude_from_normal_stats
                ).where(
                    *history_clauses(HistoryFilters(), snapshot_at),
                    i.completed_at >= start,
                )
            ).all()
        buckets: dict[int, dict[str, int]] = {}
        for offset in range(seconds):
            moment = start + timedelta(seconds=offset)
            at = int(moment.replace(tzinfo=timezone.utc).timestamp() * 1000)
            buckets[at] = {"at": at, "count": 0, "review": 0, "excluded": 0}
        for completed_at, review, excluded in rows:
            at = int(
                completed_at.replace(microsecond=0, tzinfo=timezone.utc).timestamp()
                * 1000
            )
            bucket = buckets[at]
            bucket["count"] += 1
            bucket["review"] += int(bool(review) and not excluded)
            bucket["excluded"] += int(bool(excluded))
        return list(buckets.values())


def _review_condition():
    i = Inspection
    a = ControlAttempt
    fallback = exists(
        select(a.id).where(a.inspection_id == i.inspection_id, a.attempt_no > 1)
    )
    return (
        i.review_required.is_(True)
        | i.control_status.in_(("REJECTED", "NO_RESPONSE", "FAILED"))
        | fallback
    )


def _group_counts(session, field, clauses, labels=None) -> dict[str, int]:
    rows = session.execute(
        select(field, func.count()).where(*clauses, field.is_not(None)).group_by(field)
    ).all()
    if labels is None:
        return {key: int(count) for key, count in rows}
    try:
        return {labels[key]: int(count) for key, count in rows}
    except KeyError as exc:
        raise StatisticsContractError("지원하지 않는 통계 라벨") from exc
