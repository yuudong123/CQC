"""Real MySQL primary-key conflicts stop duplicate API side effects."""

from __future__ import annotations

import asyncio
import os
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import delete, func, select

from src.api.core.config import Settings
from src.api.db.models import ControlAttempt, Inspection, InspectionError
from src.api.db.session import create_db_engine, create_session_factory
from src.api.repositories import InspectionPersistence

from .test_duplicate_inspections import _request, _setup


@pytest.mark.parametrize("concurrent", [False, True])
def test_mysql_duplicate_requests_process_once_and_preserve_row(
    concurrent: bool,
) -> None:
    url = os.getenv("CQC_TEST_DATABASE_URL")
    if not url:
        pytest.skip("CQC_TEST_DATABASE_URL이 없어 MySQL duplicate test를 건너뜁니다")
    engine = create_db_engine(Settings(database_url=url))
    session_factory = create_session_factory(engine)
    inspection_id = f"kb01-{uuid4()}"
    # Independent persistence instances prove that the DB PK, not a Python lock,
    # resolves the race between separate workers.
    setups = [_setup(InspectionPersistence(session_factory)) for _ in range(2)]
    payload = _request()
    payload["data"]["inspection_id"] = inspection_id

    def stored_row() -> dict:
        with session_factory() as session:
            return dict(
                session.execute(
                    select(Inspection.__table__).where(
                        Inspection.inspection_id == inspection_id
                    )
                )
                .mappings()
                .one()
            )

    async def run() -> list[httpx.Response]:
        async with (
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=setups[0][0]), base_url="http://test"
            ) as first,
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=setups[1][0]), base_url="http://test"
            ) as second,
        ):
            if concurrent:
                return await asyncio.gather(
                    first.post("/v1/inspections", **payload),
                    second.post("/v1/inspections", **payload),
                )
            response = await first.post("/v1/inspections", **payload)
            assert response.status_code == 200
            assert response.json()["persistence_status"] == "SUCCEEDED"
            original = stored_row()
            # A late result and fault images would be possible if the duplicate ran.
            setups[1][1].next_response = "timeout"
            duplicate = await second.post("/v1/inspections", **payload)
            assert stored_row() == original
            return [response, duplicate]

    try:
        responses = asyncio.run(run())
        assert sorted(response.status_code for response in responses) == [200, 409]
        winner = next(response for response in responses if response.status_code == 200)
        loser = next(response for response in responses if response.status_code == 409)
        assert winner.json()["persistence_status"] == "SUCCEEDED"
        assert loser.json() == {"detail": "inspection_id가 이미 존재합니다"}
        assert sum(setup[1].calls for setup in setups) == 1
        assert sum(len(setup[2].requests) for setup in setups) == 1
        for _, _, _, system_images, low_images, late in setups:
            system_images.save.assert_not_called()
            low_images.save.assert_not_called()
            assert late.active_count == 0
            assert late.results == []
        row = stored_row()
        assert row["target_bin_code"] == winner.json()["target_bin_code"]
        assert row["inspection_status"] == "COMPLETED"
        assert row["persistence_status"] == "SUCCEEDED"
        assert row["late_result_payload"] is None
        with session_factory() as session:
            for model, expected in [
                (Inspection, 1),
                (ControlAttempt, 1),
                (InspectionError, 0),
            ]:
                assert (
                    session.scalar(
                        select(func.count())
                        .select_from(model)
                        .where(model.inspection_id == inspection_id)
                    )
                    == expected
                )
    finally:
        with session_factory() as session, session.begin():
            session.execute(
                delete(Inspection).where(Inspection.inspection_id == inspection_id)
            )
        engine.dispose()
