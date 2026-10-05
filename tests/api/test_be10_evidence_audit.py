"""Audit stored effects for a completed BE-10 2/4 evidence run, opt-in only."""

from __future__ import annotations

import asyncio
import csv
import io
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import func, select

from src.api.core.config import Settings
from src.api.db.models import ControlAttempt, Inspection
from src.api.db.session import create_db_engine, create_session_factory
from src.api.main import create_app
from src.api.repositories.quality_history import HistoryFilters


def test_completed_run_api_db_control_statistics_and_csv_agree():
    """Check recorded inspection effects; no outage/retention/filter load test."""
    url = os.getenv("CQC_BE10_DATABASE_URL")
    run = os.getenv("CQC_BE10_AUDIT_RUN")
    evidence = os.getenv("CQC_BE10_EVIDENCE")
    if not all((url, run, evidence)):
        pytest.skip("completed isolated BE-10 evidence run not configured")
    path = Path(evidence)
    records = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
    ]
    expected = {}
    for record in records:
        if record["run"] != run:
            continue
        values = record.get("api", [])
        for value in values if isinstance(values, list) else [values]:
            if isinstance(value, dict) and "inspection_id" in value:
                expected[value["inspection_id"]] = value
    assert len(expected) >= 30, "incomplete evidence run"
    settings = Settings(_env_file=None, database_url=url)
    engine = create_db_engine(settings)
    sessions = create_session_factory(engine)

    async def audit():
        app = create_app(settings)
        async with app.router.lifespan_context(app):
            output = app.state.quality_operations_service.inspections_csv(
                HistoryFilters(), datetime.now(timezone.utc)
            )
            assert output.startswith("\ufeff")
            exported = {
                row["inspection_id"]: row
                for row in csv.DictReader(io.StringIO(output.lstrip("\ufeff")))
            }
            with sessions() as session:
                for identifier, api in expected.items():
                    row = session.get(Inspection, identifier)
                    assert row is not None
                    for key in (
                        "inspection_status",
                        "control_status",
                        "persistence_status",
                        "target_bin_code",
                        "review_required",
                        "exclude_from_normal_stats",
                        "used_frame_count",
                    ):
                        assert getattr(row, key) == api[key]
                    attempts = session.scalar(
                        select(func.count())
                        .select_from(ControlAttempt)
                        .where(ControlAttempt.inspection_id == identifier)
                    )
                    assert attempts == (
                        2 if row.error_code == "CONTROL_REJECTED" else 1
                    )
                    assert exported[identifier]["target_bin"] == row.target_bin_code
                    assert exported[identifier]["persistence_status"] == "SAVED"
                all_rows = session.scalars(select(Inspection)).all()
                summary = app.state.quality_operations_service._statistics.summary(
                    HistoryFilters(), datetime.now(timezone.utc)
                )
                assert summary["total"] == len(all_rows)
                assert summary["normal"] == sum(
                    not row.exclude_from_normal_stats for row in all_rows
                )
                assert summary["excluded"] == sum(
                    row.exclude_from_normal_stats for row in all_rows
                )
                assert summary["inferenceCount"] == sum(
                    not row.exclude_from_normal_stats
                    and row.inference_time_ms is not None
                    for row in all_rows
                )
            return {
                "test_id": "EFFECTS-AUDIT",
                "run": run,
                "audited_inspection_ids": sorted(expected),
                "api_db_control_csv_match": True,
                "statistics": summary,
            }

    try:
        result = asyncio.run(audit())
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(result, ensure_ascii=False) + "\n")
    finally:
        engine.dispose()
