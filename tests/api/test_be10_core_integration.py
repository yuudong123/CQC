"""BE-10 2/4: isolated MySQL, socket HTTP inference and real model checks.

Opt-in only: CQC_BE10_DATABASE_URL must name a disposable test database.
No shared Compose service is changed. Evidence contains no credentials.
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import os
import socket
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated
from uuid import uuid4

import httpx
import pytest
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, Response, UploadFile
from sqlalchemy import select

from src.api.clients.inference import MockInferenceClient
from src.api.control.virtual_control import MockVirtualControl
from src.api.core.config import Settings
from src.api.db.models import Inspection
from src.api.db.session import create_db_engine, create_session_factory
from src.api.main import create_app
from src.api.repositories.quality_history import HistoryFilters
from src.api.repositories.quality_statistics import QualityStatisticsRepository
from src.api.schemas.inference import InferenceRequest
from src.api.schemas.inspection_results import ControlStatus
from src.api.schemas.inspections import InspectionImageMetadata
from src.api.services.bin_policy import DEMO_NORMAL_BIN_MAPPING
from src.api.services.quality_history import to_quality_result
from src.simulator.schemas import SimulatorSettingsUpdate
from src.simulator.state import SimulatorStateService

from .test_inspection_request_size import CONTENT_TYPE, LIMIT, _body, _png

ROOT = Path(__file__).resolve().parents[2]
RUN = "be10-2-" + uuid4().hex[:8]


def _evidence(test_id: str, **values) -> None:
    record = {"run": RUN, "test_id": test_id, **values}
    path = os.getenv("CQC_BE10_EVIDENCE")
    if path:
        with Path(path).open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


@contextmanager
def _server(app):
    """Bind only a fresh loopback socket, and stop only this test server."""
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        # Match the application's logging policy and avoid mutating the process-wide
        # uvicorn logger configuration for later logging regression tests.
        server = uvicorn.Server(
            uvicorn.Config(app, log_config=None, log_level=None, lifespan="on")
        )
        thread = threading.Thread(
            target=server.run, kwargs={"sockets": [listener]}, daemon=True
        )
        thread.start()
        try:
            until = time.monotonic() + 10
            while not server.started:
                assert thread.is_alive() and time.monotonic() < until
                time.sleep(0.01)
            yield f"http://127.0.0.1:{port}"
        finally:
            server.should_exit = True
            thread.join(timeout=10)
            assert not thread.is_alive(), "isolated server failed to shut down"


@pytest.fixture
def environment(tmp_path):
    url = os.getenv("CQC_BE10_DATABASE_URL")
    if not url:
        pytest.skip("isolated CQC_BE10_DATABASE_URL not configured")
    settings = Settings(_env_file=None, database_url=url)
    engine = create_db_engine(settings)
    sessions = create_session_factory(engine)
    plans = {}
    calls = []
    inference = FastAPI()

    @inference.post("/v1/predict")
    async def predict(
        inspection_id: Annotated[str, Form()],
        metadata: Annotated[str, Form()],
        images: Annotated[list[UploadFile], File()],
    ):
        plan = plans.get(inspection_id, {})
        payload = [await image.read() for image in images]
        items = [InspectionImageMetadata(**item) for item in json.loads(metadata)]
        calls.append((inspection_id, len(payload), json.loads(metadata)))
        await asyncio.sleep(plan.get("delay", 0))
        if plan.get("http_error"):
            raise HTTPException(plan["http_error"], "controlled inference error")
        if plan.get("broken_json"):
            return Response('{"inspection_id":', media_type="application/json")
        response = await MockInferenceClient().predict(
            InferenceRequest(
                inspection_id=inspection_id, images=payload, metadata=items
            )
        )
        data = response.model_dump(mode="json")
        cultivar = plan.get("cultivar", "fuji")
        grade = plan.get("grade", "L")
        cc, qc = plan.get("cc", 0.9), plan.get("qc", 0.8)
        data.update(
            predicted_cultivar=cultivar,
            predicted_grade=grade,
            cultivar_confidence=cc,
            quality_confidence=qc,
            cultivar_probabilities={
                name: cc if name == cultivar else 1 - cc
                for name in ("fuji", "yanggwang")
            },
            quality_probabilities={
                name: qc if name == grade else (1 - qc) / 2 for name in ("L", "M", "S")
            },
        )
        data.update(plan.get("invalid", {}))
        if plan.get("missing_field"):
            data.pop(plan["missing_field"])
        return data

    def row(identifier):
        with sessions() as session:
            return dict(
                session.execute(
                    select(Inspection.__table__).where(
                        Inspection.inspection_id == identifier
                    )
                )
                .mappings()
                .one()
            )

    def app(inference_url):
        application = create_app(
            Settings(
                _env_file=None,
                database_url=url,
                inference_client_mode="http",
                inference_url=inference_url + "/v1/predict",
                simulator_fault_token=uuid4().hex,
                fault_image_storage_root=tmp_path / "images",
            )
        )
        application.state.be10_budgets = []

        async def trace(request):
            application.state.be10_budgets.append(request.extensions["timeout"].copy())

        application.state.inference_client._client.event_hooks["request"] = [trace]
        return application

    with _server(inference) as endpoint:
        yield app, endpoint, plans, calls, row, sessions
    engine.dispose()


def _payload(identifier, count=1, *, brix="14.0", bundle=None):
    if bundle:
        directory = ROOT / "data/processed/realtime-apple-arrival-demo/groups" / bundle
        source = json.loads((directory / "request.json").read_text(encoding="utf-8"))
        images = [(directory / name).read_bytes() for name in source["images"]][:count]
        metadata = source["metadata"][:count]
    else:
        images = [_png()] * count
        metadata = [
            {
                "view_index": i,
                "angle_direction": "top",
                "verticality_angle": 0,
                "horizontality_angle": 0,
            }
            for i in range(count)
        ]
    data = {"inspection_id": identifier, "metadata": json.dumps(metadata)}
    if brix is not None:
        data["virtual_brix"] = brix
    return {
        "data": data,
        "files": [
            ("images", (f"{i}.png", image, "image/png"))
            for i, image in enumerate(images)
        ],
    }


def _headers(app, interval):
    return {
        "X-CQC-Simulator-Token": app.state.settings.simulator_fault_token,
        "X-CQC-Simulator-Interval-Ms": str(interval),
        "X-CQC-Simulator-Bundle-ID": "be10-controlled-bundle",
    }


def _stored_contract(app, identifier, sessions):
    """Check this inspection's public history and CSV without a full 3/4 suite."""
    with sessions() as session:
        result = to_quality_result(session.get(Inspection, identifier))
    output = app.state.quality_operations_service.inspections_csv(
        HistoryFilters(), datetime.now(timezone.utc)
    )
    assert output.startswith("\ufeff")
    records = list(csv.DictReader(io.StringIO(output.lstrip("\ufeff"))))
    selected = [record for record in records if record["inspection_id"] == identifier]
    assert len(selected) == 1
    return {"history": result, "csv": selected[0]}


@pytest.mark.parametrize(
    "cc,qc,reason",
    [
        (0.49, 0.8, "LOW_CULTIVAR_CONFIDENCE"),
        (0.9, 0.59, "LOW_QUALITY_CONFIDENCE"),
        (0.49, 0.59, "LOW_BOTH_CONFIDENCE"),
        (0.50, 0.60, "NORMAL"),
        (0.499999, 0.8, "LOW_CULTIVAR_CONFIDENCE"),
        (0.500001, 0.8, "NORMAL"),
        (0.9, 0.599999, "LOW_QUALITY_CONFIDENCE"),
        (0.9, 0.600001, "NORMAL"),
    ],
)
def test_controlled_http_decision_db_and_image(environment, caplog, cc, qc, reason):
    factory, endpoint, plans, calls, row, sessions = environment
    identifier = f"{RUN}-{reason}-{uuid4().hex[:6]}"
    plans[identifier] = {"cc": cc, "qc": qc}

    async def run():
        app = factory(endpoint)
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url="http://backend"
            ) as client,
        ):
            statistics = QualityStatisticsRepository(sessions)
            before = statistics.summary(HistoryFilters(), datetime.now(timezone.utc))
            response = await client.post("/v1/inspections", **_payload(identifier))
            result = response.json()
            assert response.status_code == 200 and result["decision_reason"] == reason
            stored = row(identifier)
            assert stored["exclude_from_normal_stats"] is False
            assert (
                stored["control_status"] == stored["persistence_status"] == "SUCCEEDED"
            )
            assert stored["review_required"] == (reason != "NORMAL")
            inventory = (
                await client.get(
                    "/v1/quality/fault-images", params={"inspectionId": identifier}
                )
            ).json()["items"]
            if reason != "NORMAL":
                assert result["target_bin_code"] == "TEST_REINSPECTION_BIN"
                assert len(inventory) == 1
                assert inventory[0]["category"] == "LOW_CONFIDENCE"
                assert inventory[0]["decisionReason"] == reason
                assert inventory[0]["errorCode"] is None
                assert inventory[0]["cultivarConfidence"] == cc
                assert inventory[0]["qualityConfidence"] == qc
                assert inventory[0]["appliedCultivarThreshold"] == 0.5
                assert inventory[0]["appliedQualityThreshold"] == 0.6
            else:
                assert not inventory
            assert (
                len(calls)
                == len(app.state.inspection_service._virtual_control.requests)
                == 1
            )
            after = statistics.summary(HistoryFilters(), datetime.now(timezone.utc))
            assert after["total"] == before["total"] + 1
            assert after["normal"] == before["normal"] + 1
            assert after["excluded"] == before["excluded"]
            assert not [record for record in caplog.records if record.levelno >= 40]
            contract = _stored_contract(app, identifier, sessions)
            _evidence(
                "INS-02/03/04/05",
                inspection_id=identifier,
                api=result,
                db=stored,
                images=inventory,
                stats_before=before,
                stats_after=after,
                **contract,
            )

    asyncio.run(run())


@pytest.mark.parametrize("interval", [1000, 2000, 3000])
def test_socket_delay_late_and_hard_limits(environment, interval):
    factory, endpoint, plans, _calls, row, _sessions = environment

    async def run():
        app = factory(endpoint)
        manager = app.state.inspection_service._late_result_manager
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url="http://backend"
            ) as client,
        ):
            for kind, delay in [
                ("late", interval / 1000 + 0.3),
                ("hard", interval / 1000 + 1.5),
            ]:
                identifier = f"{RUN}-{kind}-{interval}"
                plans[identifier] = {"delay": delay}
                started = time.monotonic()
                response = await client.post(
                    "/v1/inspections",
                    headers=_headers(app, interval),
                    **_payload(identifier),
                )
                elapsed = time.monotonic() - started
                frozen = row(identifier)
                assert response.status_code == 200
                assert (
                    response.json()["decision_reason"] == "INFERENCE_DEADLINE_EXCEEDED"
                )
                assert frozen["exclude_from_normal_stats"] is True
                assert frozen["target_bin_code"] == "TEST_REINSPECTION_BIN"
                await asyncio.wait_for(manager.wait_until_idle(), interval / 1000 + 3)
                finished = time.monotonic() - started
                final = row(identifier)
                for field in (
                    "inspection_status",
                    "error_code",
                    "target_bin_code",
                    "control_status",
                    "exclude_from_normal_stats",
                    "predicted_cultivar",
                    "predicted_grade",
                ):
                    assert final[field] == frozen[field]
                assert bool(final["late_result_payload"]) == (kind == "late")
                if kind == "hard":
                    assert identifier in manager.hard_timeout_inspection_ids
                    assert interval / 1000 + 0.8 < finished < interval / 1000 + 1.8
                assert interval / 1000 - 0.1 < elapsed < interval / 1000 + 0.8
                _evidence(
                    "TIM-04/05",
                    inspection_id=identifier,
                    interval=interval,
                    delay=delay,
                    business_return_seconds=elapsed,
                    collection_seconds=finished,
                    api=response.json(),
                    db=final,
                    cancelled=identifier in manager.hard_timeout_inspection_ids,
                )
            assert len(app.state.inspection_service._virtual_control.requests) == 2

    asyncio.run(run())


def test_socket_late_a_does_not_wait_b_and_stats_stay_frozen(environment):
    factory, endpoint, plans, _calls, row, sessions = environment

    async def run():
        app = factory(endpoint)
        manager = app.state.inspection_service._late_result_manager
        a, b = f"{RUN}-late-a", f"{RUN}-normal-b"
        plans[a] = {"delay": 1.7}
        statistics = QualityStatisticsRepository(sessions)
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url="http://backend"
            ) as client,
        ):
            first = await client.post(
                "/v1/inspections", headers=_headers(app, 1000), **_payload(a)
            )
            assert first.json()["decision_reason"] == "INFERENCE_DEADLINE_EXCEEDED"
            assert manager.active_count == 1
            started = time.monotonic()
            second = await client.post(
                "/v1/inspections", headers=_headers(app, 1000), **_payload(b)
            )
            elapsed = time.monotonic() - started
            assert second.json()["decision_reason"] == "NORMAL"
            assert manager.active_count == 1 and elapsed < 0.5
            before = statistics.summary(HistoryFilters(), datetime.now(timezone.utc))
            await asyncio.wait_for(manager.wait_until_idle(), 3)
            after = statistics.summary(HistoryFilters(), datetime.now(timezone.utc))
            assert before == after
            assert row(a)["late_result_payload"] is not None
            assert row(b)["exclude_from_normal_stats"] is False
            assert len(app.state.inspection_service._virtual_control.requests) == 2
            _evidence(
                "TIM-06",
                inspection_id=[a, b],
                b_seconds=elapsed,
                stats_before=before,
                stats_after=after,
                db_a=row(a),
                db_b=row(b),
            )

    asyncio.run(run())


@pytest.mark.parametrize(
    "bundle,cultivar,grade",
    [
        ("demo-601031008000-000", "fuji", "L"),
        ("demo-601032016000-000", "fuji", "M"),
        ("demo-601033004000-000", "fuji", "S"),
        ("demo-601141012000-000", "yanggwang", "L"),
        ("demo-601142007000-000", "yanggwang", "M"),
        ("demo-601143013000-000", "yanggwang", "S"),
    ],
)
def test_real_model_normal_candidates_and_twelve_bins(
    environment, bundle, cultivar, grade
):
    endpoint = os.getenv("CQC_BE10_INFERENCE_URL")
    if not endpoint:
        pytest.skip("isolated real inference endpoint not configured")
    factory, _, _, _, row, _ = environment

    async def run():
        app = factory(endpoint)
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url="http://backend"
            ) as client,
        ):
            for brix, sweetness in [("13.9", "less_sweet"), ("14.0", "sweet")]:
                identifier = f"{RUN}-{bundle[-16:]}-{brix.replace('.', '_')}"
                response = await client.post(
                    "/v1/inspections",
                    headers=_headers(app, 2000),
                    **_payload(identifier, 12, brix=brix, bundle=bundle),
                )
                result = response.json()
                _evidence(
                    "INS-01",
                    inspection_id=identifier,
                    bundle=bundle,
                    api=result,
                    db=row(identifier),
                )
                assert (
                    response.status_code == 200
                    and result["decision_reason"] == "NORMAL"
                )
                assert (
                    result["predicted_cultivar"] == cultivar
                    and result["predicted_grade"] == grade
                )
                assert result["used_frame_count"] == 12
                assert (
                    result["target_bin_code"]
                    == DEMO_NORMAL_BIN_MAPPING[(cultivar, grade, sweetness)]
                )
                assert (
                    result["control_status"]
                    == result["persistence_status"]
                    == "SUCCEEDED"
                )
                assert (
                    not result["review_required"]
                    and not result["exclude_from_normal_stats"]
                )

    asyncio.run(run())


def test_real_model_one_frame_and_damaged_image(environment):
    endpoint = os.getenv("CQC_BE10_INFERENCE_URL")
    if not endpoint:
        pytest.skip("isolated real inference endpoint not configured")
    factory, _, _, _, row, _ = environment

    async def run():
        app = factory(endpoint)
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url="http://backend"
            ) as client,
        ):
            identifier = f"{RUN}-real-one"
            response = await client.post(
                "/v1/inspections",
                headers=_headers(app, 2000),
                **_payload(identifier, bundle="demo-601031008000-000"),
            )
            result = response.json()
            _evidence(
                "BND-01", inspection_id=identifier, api=result, db=row(identifier)
            )
            assert response.status_code == 200 and result["used_frame_count"] == 1
            assert result["decision_reason"] in {
                "NORMAL",
                "LOW_CULTIVAR_CONFIDENCE",
                "LOW_QUALITY_CONFIDENCE",
                "LOW_BOTH_CONFIDENCE",
            }
            bad = f"{RUN}-damaged"
            payload = _payload(bad)
            payload["files"] = [("images", ("bad.png", b"not-a-png", "image/png"))]
            failure = await client.post(
                "/v1/inspections", headers=_headers(app, 2000), **payload
            )
            assert (
                failure.status_code == 200
                and failure.json()["decision_reason"] == "INFERENCE_HTTP_ERROR"
            )
            _evidence("INS-08", inspection_id=bad, api=failure.json(), db=row(bad))

    asyncio.run(run())


def test_socket_backend_whole_multipart_boundaries(environment):
    factory, endpoint, _, calls, _, _ = environment
    app = factory(endpoint)
    with _server(app) as backend, httpx.Client(base_url=backend, timeout=10) as client:
        for declared in (True, False):
            for delta in (-1, 0, 1):
                # A fresh ID allows both valid requests to run independently.
                body = _body(size=LIMIT + delta).replace(
                    b"kb02-inspection", uuid4().hex[:15].encode()
                )
                assert len(body) == LIMIT + delta
                headers = {"content-type": CONTENT_TYPE}
                if declared:
                    headers["content-length"] = str(len(body))
                before = len(calls)
                response = client.post(
                    "/v1/inspections",
                    headers=headers,
                    content=(body[i : i + 65536] for i in range(0, len(body), 65536)),
                )
                assert response.status_code == (413 if delta > 0 else 200)
                assert len(calls) - before == int(delta <= 0)
                _evidence(
                    "BND-03/04",
                    declared=declared,
                    body_bytes=len(body),
                    http_status=response.status_code,
                    inference_calls=len(calls) - before,
                )


@pytest.mark.parametrize("interval", [1000, 2000, 3000])
@pytest.mark.parametrize("failure", ["ConnectError", "ConnectTimeout", "ReadTimeout"])
def test_transport_error_public_classification(environment, interval, failure):
    factory, endpoint, _, _, row, sessions = environment

    async def run():
        app = factory(endpoint)
        # Refusal uses a real socket; timeout exceptions are deterministic transport
        # doubles, separate from delayed socket responses and fault injection.
        with socket.socket() as closed:
            closed.bind(("127.0.0.1", 0))
            refused_port = closed.getsockname()[1]
        transport = app.state.inference_client._client
        if failure == "ConnectError":
            app.state.inference_client._url = (
                f"http://127.0.0.1:{refused_port}/v1/predict"
            )
        else:
            await transport.aclose()

            async def fail(request):
                raise getattr(httpx, failure)(
                    "controlled transport failure", request=request
                )

            app.state.inference_client._client = httpx.AsyncClient(
                transport=httpx.MockTransport(fail)
            )
        identifier = f"{RUN}-{failure}-{interval}"
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url="http://backend"
            ) as client,
        ):
            response = await client.post(
                "/v1/inspections",
                headers=_headers(app, interval),
                **_payload(identifier),
            )
            timeout = failure == "ReadTimeout"
            expected = (
                "INFERENCE_DEADLINE_EXCEEDED"
                if timeout
                else "INFERENCE_CONNECTION_ERROR"
            )
            assert (
                response.status_code == 200
                and response.json()["decision_reason"] == expected
            )
            assert row(identifier)["exclude_from_normal_stats"] is True
            contract = _stored_contract(app, identifier, sessions)
            assert contract["history"]["errorCode"] == (
                "INFERENCE_TIMEOUT" if timeout else "INFERENCE_ERROR"
            )
            _evidence(
                "INS-07/TIM-04",
                inspection_id=identifier,
                interval=interval,
                transport_failure=failure,
                api=response.json(),
                db=row(identifier),
                **contract,
            )

    asyncio.run(run())


@pytest.mark.parametrize(
    "plan",
    [
        {"http_error": 500},
        {"invalid": {"inspection_id": "wrong"}},
        {"invalid": {"used_frame_count": 12}},
        {"invalid": {"model_name": None}},
        {"broken_json": True},
        {"missing_field": "quality_confidence"},
    ],
)
def test_socket_http_and_invalid_response(environment, plan):
    factory, endpoint, plans, _, row, sessions = environment
    identifier = f"{RUN}-invalid-{uuid4().hex[:6]}"
    plans[identifier] = plan

    async def run():
        app = factory(endpoint)
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url="http://backend"
            ) as client,
        ):
            response = await client.post("/v1/inspections", **_payload(identifier))
            reason = (
                "INFERENCE_HTTP_ERROR"
                if "http_error" in plan
                else "INFERENCE_INVALID_RESPONSE"
            )
            assert (
                response.status_code == 200
                and response.json()["decision_reason"] == reason
            )
            contract = _stored_contract(app, identifier, sessions)
            assert contract["history"]["errorCode"] == "INFERENCE_ERROR"
            assert row(identifier)["exclude_from_normal_stats"] is True
            _evidence(
                "INS-08/09",
                inspection_id=identifier,
                input=plan,
                api=response.json(),
                db=row(identifier),
                **contract,
            )

    asyncio.run(run())


@pytest.mark.parametrize("interval", [1000, 2000, 3000])
@pytest.mark.parametrize("fault", ["INFERENCE_TIMEOUT", "INFERENCE_ERROR"])
@pytest.mark.parametrize("scope", ["NEXT", "ALL"])
def test_parallel_fault_claim_to_backend(environment, interval, fault, scope):
    factory, endpoint, _, calls, row, _ = environment
    state = SimulatorStateService(interval)
    state.update_state(
        SimulatorSettingsUpdate.model_validate(
            {"expectedRevision": 0, "faults": [fault], "scope": scope}
        )
    )

    async def run():
        app = factory(endpoint)
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url="http://backend"
            ) as client,
        ):

            async def inspect(index):
                claimed = await asyncio.to_thread(state.claim_faults_for_inspection)
                identifier = f"{RUN}-{scope}-{fault}-{interval}-{index}"
                headers = _headers(app, interval)
                headers["X-CQC-Simulator-Faults"] = ",".join(claimed)
                response = await client.post(
                    "/v1/inspections", headers=headers, **_payload(identifier)
                )
                assert response.status_code == 200
                _evidence(
                    "TIM-09",
                    inspection_id=identifier,
                    scope=scope,
                    fault=fault,
                    interval=interval,
                    claimed=claimed,
                    api=response.json(),
                    db=row(identifier),
                )
                return response.json()

            results = await asyncio.gather(inspect(0), inspect(1))
            expected = (
                "INFERENCE_DEADLINE_EXCEEDED"
                if fault == "INFERENCE_TIMEOUT"
                else "INFERENCE_HTTP_ERROR"
            )
            count = 1 if scope == "NEXT" else 2
            assert (
                sum(result["decision_reason"] == expected for result in results)
                == count
            )
            assert len(calls) == 2 - count
            assert app.state.inspection_service._late_result_manager.active_count == 0

    asyncio.run(run())


def test_socket_concurrent_intervals_and_setting_snapshot(environment):
    factory, endpoint, plans, _, row, _ = environment

    async def run():
        app = factory(endpoint)
        manager = app.state.inspection_service._late_result_manager
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url="http://backend"
            ) as client,
        ):
            ids = [f"{RUN}-mixed-{interval}" for interval in (1000, 2000, 3000)]
            for identifier in ids:
                plans[identifier] = {"delay": 1.2}
            results = await asyncio.gather(
                *(
                    client.post(
                        "/v1/inspections",
                        headers=_headers(app, interval),
                        **_payload(identifier),
                    )
                    for identifier, interval in zip(
                        ids, (1000, 2000, 3000), strict=True
                    )
                )
            )
            assert [response.json()["decision_reason"] for response in results] == [
                "INFERENCE_DEADLINE_EXCEEDED",
                "NORMAL",
                "NORMAL",
            ]
            assert [budget["read"] for budget in app.state.be10_budgets] == [
                2.0,
                3.0,
                4.0,
            ]
            assert all(budget["connect"] == 0.2 for budget in app.state.be10_budgets)
            await asyncio.wait_for(manager.wait_until_idle(), 3)
            _evidence(
                "TIM-01/03",
                inspection_id=ids,
                budgets=app.state.be10_budgets.copy(),
                api=[response.json() for response in results],
            )
            state = SimulatorStateService(2000)
            a, b = f"{RUN}-snapshot-a", f"{RUN}-snapshot-b"
            plans[a] = {"delay": 2.3}
            snapshot = state.get_state()
            pending = asyncio.create_task(
                client.post(
                    "/v1/inspections",
                    headers=_headers(app, snapshot.interval_ms),
                    **_payload(a),
                )
            )
            await asyncio.sleep(0.2)
            state.update_state(
                SimulatorSettingsUpdate.model_validate(
                    {"expectedRevision": 0, "intervalMs": 3000}
                )
            )
            next_response = await client.post(
                "/v1/inspections",
                headers=_headers(app, state.get_state().interval_ms),
                **_payload(b),
            )
            first = await pending
            assert first.json()["decision_reason"] == "INFERENCE_DEADLINE_EXCEEDED"
            assert next_response.json()["decision_reason"] == "NORMAL"
            assert [budget["read"] for budget in app.state.be10_budgets[-2:]] == [
                3.0,
                4.0,
            ]
            await asyncio.wait_for(manager.wait_until_idle(), 3)
            _evidence(
                "TIM-02",
                inspection_id=[a, b],
                frozen_interval=snapshot.interval_ms,
                next_interval=state.get_state().interval_ms,
                budgets=app.state.be10_budgets[-2:],
                db_a=row(a),
                db_b=row(b),
            )

    asyncio.run(run())


def test_real_model_low_quality_bundle(environment):
    endpoint = os.getenv("CQC_BE10_INFERENCE_URL")
    if not endpoint:
        pytest.skip("isolated real inference endpoint not configured")
    factory, _, _, _, row, sessions = environment

    async def run():
        app = factory(endpoint)
        identifier = f"{RUN}-real-low-quality"
        bundle = "demo-601031028000-000"
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url="http://backend"
            ) as client,
        ):
            response = await client.post(
                "/v1/inspections",
                headers=_headers(app, 2000),
                **_payload(identifier, 12, bundle=bundle),
            )
            result = response.json()
            assert (
                response.status_code == 200
                and result["decision_reason"] == "LOW_QUALITY_CONFIDENCE"
            )
            assert result["review_required"] and not result["exclude_from_normal_stats"]
            assert result["target_bin_code"] == "TEST_REINSPECTION_BIN"
            images = (
                await client.get(
                    "/v1/quality/fault-images", params={"inspectionId": identifier}
                )
            ).json()["items"]
            assert len(images) == 12
            assert all(
                image["category"] == "LOW_CONFIDENCE"
                and image["decisionReason"] == "LOW_QUALITY_CONFIDENCE"
                for image in images
            )
            _evidence(
                "INS-03",
                inspection_id=identifier,
                bundle=bundle,
                api=result,
                db=row(identifier),
                images=images,
                **_stored_contract(app, identifier, sessions),
            )

    asyncio.run(run())


@pytest.mark.parametrize(
    "case,status",
    [
        ("thirteen", 413),
        ("metadata_count", 422),
        ("mime", 415),
        ("duplicate", 422),
        ("gap", 422),
    ],
)
def test_input_rejected_before_service(environment, case, status):
    factory, endpoint, _, calls, _, sessions = environment

    async def run():
        app = factory(endpoint)
        identifier = f"{RUN}-input-{case}"
        payload = _payload(identifier, 13 if case == "thirteen" else 2)
        if case == "mime":
            payload["files"][0] = ("images", ("bad.txt", b"x", "text/plain"))
        if case in {"duplicate", "gap", "metadata_count"}:
            metadata = json.loads(payload["data"]["metadata"])
            if case == "metadata_count":
                metadata.pop()
            else:
                metadata[1]["view_index"] = 0 if case == "duplicate" else 2
            payload["data"]["metadata"] = json.dumps(metadata)
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url="http://backend"
            ) as client,
        ):
            response = await client.post("/v1/inspections", **payload)
            assert response.status_code == status
            assert (
                not calls and not app.state.inspection_service._virtual_control.requests
            )
            with sessions() as session:
                assert session.get(Inspection, identifier) is None
            _evidence(
                "BND-01/02",
                inspection_id=identifier,
                input=case,
                http_status=response.status_code,
                api=response.json(),
                inference_calls=0,
                control_calls=0,
                db_rows=0,
            )

    asyncio.run(run())


@pytest.mark.parametrize(
    "outcome", ["REJECTED", "NO_RESPONSE", "FAILED", "MISSING_BRIX"]
)
def test_control_outcomes_and_missing_brix(environment, outcome):
    factory, endpoint, _, calls, row, sessions = environment

    async def run():
        app = factory(endpoint)
        if outcome != "MISSING_BRIX":
            configured = [ControlStatus(outcome)]
            if outcome == "REJECTED":
                configured.append(ControlStatus.SUCCEEDED)
            app.state.inspection_service._virtual_control = MockVirtualControl(
                configured
            )
        identifier = f"{RUN}-control-{outcome}"
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url="http://backend"
            ) as client,
        ):
            response = await client.post(
                "/v1/inspections",
                **_payload(
                    identifier, brix=None if outcome == "MISSING_BRIX" else "14.0"
                ),
            )
            result = response.json()
            assert response.status_code == 200
            assert result["decision_reason"] == (
                "VIRTUAL_BRIX_MISSING" if outcome == "MISSING_BRIX" else "NORMAL"
            )
            assert len(app.state.inspection_service._virtual_control.requests) == (
                2 if outcome == "REJECTED" else 1
            )
            if outcome in {"REJECTED", "MISSING_BRIX"}:
                assert result["target_bin_code"] == "TEST_REINSPECTION_BIN"
            else:
                assert result["control_status"] == outcome
            assert not row(identifier)["exclude_from_normal_stats"]
            assert (
                await client.get(
                    "/v1/quality/fault-images", params={"inspectionId": identifier}
                )
            ).json()["items"] == []
            assert len(calls) == 1
            _evidence(
                "INS-06/10/11/12",
                inspection_id=identifier,
                outcome=outcome,
                api=result,
                db=row(identifier),
                **_stored_contract(app, identifier, sessions),
            )

    asyncio.run(run())


def test_default_fallback_business_and_hard_budget(environment):
    factory, endpoint, plans, _, row, _ = environment

    async def run():
        app = factory(endpoint)
        manager = app.state.inspection_service._late_result_manager
        identifier = f"{RUN}-fallback"
        plans[identifier] = {"delay": 0.7}
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url="http://backend"
            ) as client,
        ):
            started = time.monotonic()
            response = await client.post("/v1/inspections", **_payload(identifier))
            elapsed = time.monotonic() - started
            assert response.json()["decision_reason"] == "INFERENCE_DEADLINE_EXCEEDED"
            assert 0.4 < elapsed < 1.0
            assert app.state.be10_budgets[0]["read"] == 2.0
            assert app.state.be10_budgets[0]["connect"] == 0.2
            await asyncio.wait_for(manager.wait_until_idle(), 3)
            assert row(identifier)["late_result_payload"] is not None
            _evidence(
                "TIM-07",
                inspection_id=identifier,
                interval=None,
                business_seconds=elapsed,
                budgets=app.state.be10_budgets,
                db=row(identifier),
            )

    asyncio.run(run())


@pytest.mark.parametrize("count", range(2, 12))
def test_real_model_partial_frame_counts(environment, count):
    endpoint = os.getenv("CQC_BE10_INFERENCE_URL")
    if not endpoint:
        pytest.skip("isolated real inference endpoint not configured")
    factory, _, _, _, row, _ = environment

    async def run():
        app = factory(endpoint)
        identifier = f"{RUN}-real-frames-{count}"
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url="http://backend"
            ) as client,
        ):
            response = await client.post(
                "/v1/inspections",
                headers=_headers(app, 2000),
                **_payload(identifier, count, bundle="demo-601031008000-000"),
            )
            result = response.json()
            _evidence(
                "BND-01",
                inspection_id=identifier,
                frame_count=count,
                api=result,
                db=row(identifier),
            )
            assert response.status_code == 200 and result["used_frame_count"] == count
            assert result["decision_reason"] in {
                "NORMAL",
                "LOW_CULTIVAR_CONFIDENCE",
                "LOW_QUALITY_CONFIDENCE",
                "LOW_BOTH_CONFIDENCE",
            }

    asyncio.run(run())


def test_observed_image_filter_identifier_mismatch(environment):
    """A dotted inspection ID remains queryable after its review image is saved."""
    factory, endpoint, plans, _, row, _ = environment

    async def run():
        app = factory(endpoint)
        identifier = f"{RUN}.filter-observation"
        plans[identifier] = {"qc": 0.59}
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app, raise_app_exceptions=False),
                base_url="http://backend",
            ) as client,
        ):
            inspection = await client.post("/v1/inspections", **_payload(identifier))
            filtered = await client.get(
                "/v1/quality/fault-images", params={"inspectionId": identifier}
            )
            inventory = await client.get("/v1/quality/fault-images")
            assert inspection.status_code == 200
            _evidence(
                "OBS-01",
                inspection_id=identifier,
                inspection_status=inspection.status_code,
                filtered_status=filtered.status_code,
                unfiltered_status=inventory.status_code,
                expected_unfiltered_status=200,
                images_saved=app.state.low_confidence_image_storage.count_files(),
                db=row(identifier),
                disposition="OBS-01 resolved",
            )
            assert filtered.status_code == 200
            assert len(filtered.json()["items"]) == 1
            assert filtered.json()["items"][0]["inspectionId"] == identifier
            assert inventory.status_code == 200, (
                "accepted inspection ID must not break the whole image inventory"
            )

    asyncio.run(run())
