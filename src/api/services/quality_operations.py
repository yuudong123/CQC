"""관제 snapshot·기간 통계·CSV를 저장된 검사 이력에서 구성한다."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from io import StringIO

from src.simulator.schemas import SimulatorStatus

from ..repositories.quality_history import HistoryFilters, QualityHistoryRepository
from ..repositories.quality_statistics import QualityStatisticsRepository
from .fault_image_storage import FaultImageStorage
from .live_inspections import LiveInspectionStore
from .quality_history import KST, to_quality_result

_INSPECTION_COLUMNS = [
    "inspection_id",
    "date",
    "time_kst",
    "variety",
    "grade",
    "cultivar_confidence_pct",
    "quality_confidence_pct",
    "inference_ms",
    "model_version",
    "target_bin",
    "processing_status",
    "control_status",
    "persistence_status",
    "error_codes",
    "misclassification",
    "virtual_brix",
    "brix_is_measured",
]


class QualityOperationsService:
    """통계와 CSV가 같은 Repository 집계·Result 변환을 사용하도록 조정한다."""

    def __init__(
        self,
        history: QualityHistoryRepository,
        statistics: QualityStatisticsRepository,
        fault_image_storage: FaultImageStorage | None = None,
        live_inspections: LiveInspectionStore | None = None,
    ) -> None:
        self._history = history
        self._statistics = statistics
        self._fault_image_storage = fault_image_storage
        self._live_inspections = live_inspections

    def statistics(
        self, filters: HistoryFilters, snapshot_at: datetime
    ) -> dict[str, object]:
        return self._statistics.summary(filters, snapshot_at)

    def snapshot(self, captured_at: datetime) -> dict[str, object]:
        rows = self._history.list_page(
            HistoryFilters(), snapshot_at=captured_at, page=1, page_size=200
        )
        today_date, today_summary = self._statistics.today(captured_at)
        day = captured_at.replace(tzinfo=timezone.utc).astimezone(KST).date()
        today_review = self._statistics.review_count(
            HistoryFilters(from_date=day, to_date=day), captured_at
        )
        last_saved = self._statistics.last_saved(captured_at)
        periods = self._statistics.period_totals(captured_at)
        points = self._statistics.points(captured_at)
        captured_ms = _epoch_ms(captured_at)
        image_count = (
            self._fault_image_storage.count_files()
            if self._fault_image_storage is not None
            else 0
        )
        jobs, recent_completed_jobs = (
            self._live_inspections.snapshot_jobs()
            if self._live_inspections is not None
            else ([], [])
        )
        component_unknown = {
            "status": "unknown",
            "lastSeenAt": None,
            "detail": "상태 확인 연동 전",
        }
        snapshot = {
            "contractVersion": "1",
            "source": "backend",
            "capturedAt": captured_ms,
            "revision": 0,
            "capabilities": {
                "control": False,
                "faults": False,
                "review": True,
                "deleteImages": self._fault_image_storage is not None,
                "concurrency": [],
                "intervals": [],
            },
            "components": {
                "Simulator": {
                    "status": "unknown",
                    "lastSeenAt": None,
                    "detail": "Simulator 연결 상태 확인 전",
                },
                "Inference": component_unknown,
                "Backend": {
                    "status": "healthy",
                    "lastSeenAt": captured_ms,
                    "detail": "관제 API 응답 중",
                },
                "MySQL": {
                    "status": "healthy",
                    "lastSeenAt": captured_ms,
                    "detail": "검사 이력 조회 성공",
                },
            },
            "retention": {"images": image_count},
            "periodTotals": periods,
            "state": {
                "throughput": points[-2]["count"] if len(points) >= 2 else 0,
                "running": False,
                "faults": [],
                "jobs": jobs,
                "recentCompletedJobs": recent_completed_jobs,
                "history": [to_quality_result(row) for row in rows.items],
                "images": [],
                "points": points,
                "errors": [
                    to_quality_result(row)
                    for row in self._history.recent_errors(captured_at)
                ],
                "today": {
                    "date": today_date,
                    "total": today_summary["total"],
                    "normal": today_summary["normal"],
                    "review": today_review,
                    "excluded": today_summary["excluded"],
                    "grades": {
                        key: today_summary["grades"].get(key, 0)
                        for key in ("특", "상", "보통")
                    },
                    "varieties": {
                        key: today_summary["varieties"].get(key, 0)
                        for key in ("부사", "양광")
                    },
                    "bins": today_summary["bins"],
                    "reinspection": today_summary["reinspection"],
                    "inferenceTotalMs": today_summary["inferenceTotalMs"],
                    "inferenceCount": today_summary["inferenceCount"],
                    "suspicions": {
                        key: today_summary["suspicions"].get(key, 0)
                        for key in ("CULTIVAR_SUSPECT", "QUALITY_SUSPECT", "OTHER")
                    },
                },
                "lastSaved": _epoch_ms(last_saved) if last_saved else None,
                "dbDown": False,
            },
        }
        return snapshot

    def with_simulator_state(
        self,
        snapshot: dict[str, object],
        state: SimulatorStatus | None = None,
    ) -> dict[str, object]:
        """Simulator 내부 API 결과를 공개 관제 snapshot에 반영한다."""

        if state is None:
            components = snapshot["components"]
            assert isinstance(components, dict)
            components["Simulator"] = {
                "status": "unknown",
                "lastSeenAt": None,
                "detail": "Simulator 연결 불가",
            }
            return snapshot
        snapshot["revision"] = state.revision
        capabilities = snapshot["capabilities"]
        assert isinstance(capabilities, dict)
        capabilities.update(
            {
                "control": True,
                "faults": True,
                "concurrency": [1, 2, 4],
                "intervals": [1000, 2000, 3000],
            }
        )
        simulator = snapshot["state"]
        assert isinstance(simulator, dict)
        simulator.update(
            {
                "running": state.running,
                "concurrency": state.concurrency,
                "intervalMs": state.interval_ms,
                "faults": state.faults,
                "scope": state.scope,
            }
        )
        components = snapshot["components"]
        assert isinstance(components, dict)
        components["Simulator"] = {
            "status": state.status,
            "lastSeenAt": state.lastSeenAt,
            "detail": "실행 실패"
            if state.status == "error"
            else "검사 전송 중"
            if state.status == "healthy"
            else "정지",
        }
        return snapshot

    def with_inference_health(
        self, snapshot: dict[str, object], ready: bool
    ) -> dict[str, object]:
        """실제 Inference health를 공개 component 상태에 반영한다."""

        components = snapshot["components"]
        assert isinstance(components, dict)
        components["Inference"] = {
            "status": "healthy" if ready else "error",
            "lastSeenAt": snapshot["capturedAt"] if ready else None,
            "detail": "추론 서비스 준비 완료"
            if ready
            else "추론 서비스 연결 또는 준비 실패",
        }
        return snapshot

    def inspections_csv(self, filters: HistoryFilters, snapshot_at: datetime) -> str:
        output, writer = _csv_writer()
        writer.writerow(_INSPECTION_COLUMNS)
        for batch in self._history.iter_filtered(filters, snapshot_at=snapshot_at):
            for row in batch:
                result = to_quality_result(row)
                writer.writerow(
                    [
                        result["id"],
                        result["date"],
                        result["time"],
                        result["variety"],
                        result["grade"],
                        result["cultivarConfidence"],
                        result["confidence"],
                        result["inferenceMs"],
                        result["modelVersion"],
                        result["bin"],
                        result["processingStatus"],
                        result["control"],
                        result["persistence"],
                        "|".join(result["faults"]),
                        result["misclassification"],
                        result["virtualBrix"],
                        "false",
                    ]
                )
        return output.getvalue()

    def statistics_csv(
        self,
        filters: HistoryFilters,
        snapshot_at: datetime,
        *,
        minutes: int,
    ) -> str:
        output, writer = _csv_writer()
        if filters.from_date is not None or filters.to_date is not None:
            summary = self.statistics(filters, snapshot_at)
            writer.writerow(["mode", "from_kst", "to_kst", "group", "key", "value"])

            def add(group: str, key: str, value: object) -> None:
                writer.writerow(
                    ["BACKEND", filters.from_date, filters.to_date, group, key, value]
                )

            for key, value in summary.items():
                if isinstance(value, dict):
                    for name, count in value.items():
                        add(key, name, count)
                else:
                    add("total", key, value)
            add("total", "reinspection_ratio", _ratio(summary))
            add("total", "average_inference_ms", _average(summary))
        else:
            day, summary = self._statistics.today(snapshot_at)
            last_saved = self._statistics.last_saved(snapshot_at)
            last_saved_kst = _kst_iso(last_saved) if last_saved else ""
            writer.writerow(
                ["mode", "date_kst", "section", "key", "value", "last_saved_at"]
            )

            def add(section: str, key: str, value: object) -> None:
                writer.writerow(["BACKEND", day, section, key, value, last_saved_kst])

            for key in ("total", "normal", "excluded", "reinspection"):
                add("today", key, summary[key])
            add("today", "reinspection_ratio", _ratio(summary))
            add("today", "average_inference_ms", _average(summary))
            for group in ("grades", "varieties", "bins", "suspicions"):
                for key, value in summary[group].items():
                    add(group, key, value)
            for point in self._statistics.points(snapshot_at, seconds=minutes * 60):
                at = datetime.fromtimestamp(point["at"] / 1000, timezone.utc)
                add(
                    f"last_{minutes}_minutes",
                    _kst_iso(at.replace(tzinfo=None)),
                    point["count"],
                )
        return output.getvalue()


def _epoch_ms(utc_naive: datetime) -> int:
    return int(utc_naive.replace(tzinfo=timezone.utc).timestamp() * 1000)


def _kst_iso(utc_naive: datetime) -> str:
    return (
        utc_naive.replace(tzinfo=timezone.utc)
        .astimezone(KST)
        .isoformat(timespec="milliseconds")
    )


def _ratio(summary: dict[str, object]) -> float:
    return summary["reinspection"] / summary["total"] if summary["total"] else 0


def _average(summary: dict[str, object]) -> float | str:
    return (
        summary["inferenceTotalMs"] / summary["inferenceCount"]
        if summary["inferenceCount"]
        else ""
    )


class _SafeCsvWriter:
    def __init__(self, output: StringIO) -> None:
        self._writer = csv.writer(output, quoting=csv.QUOTE_ALL, lineterminator="\r\n")

    def writerow(self, values: list[object]) -> None:
        prepared: list[str] = []
        for value in values:
            rendered = (
                ""
                if value is None
                else str(value).lower()
                if isinstance(value, bool)
                else str(value)
            )
            if rendered.startswith(("=", "+", "@", "-", "\t", "\r")):
                rendered = "'" + rendered
            prepared.append(rendered)
        self._writer.writerow(prepared)


def _csv_writer() -> tuple[StringIO, _SafeCsvWriter]:
    output = StringIO(newline="")
    output.write("\ufeff")
    return output, _SafeCsvWriter(output)
