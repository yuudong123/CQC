"""BE-10 3/4 acceptance on a disposable Linux filesystem and actual MySQL.

Opt in with CQC_BE10_3_DATABASE_URL. This suite clears only a database named
be10_3. MySQL stop/start is delegated to the labelled-resource host harness.
"""

from __future__ import annotations

import asyncio
import csv
import json
import logging
import os
import signal
import socket
import statistics
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.engine import make_url

from src.api.control.virtual_control import MockVirtualControl
from src.api.core.config import Settings
from src.api.db.models import BinMapping, ControlAttempt, Inspection, InspectionError
from src.api.db.session import create_db_engine, create_session_factory
from src.api.repositories.persistence import InspectionPersistence
from src.api.schemas.inspection_results import ControlStatus
from src.api.services.fault_image_storage import FaultImage

from . import test_be10_core_integration as core
from .test_inspection_request_size import _png

EVIDENCE = Path("/evidence")
KST = timezone(timedelta(hours=9))


def evidence(test_id: str, **values: object) -> None:
    if EVIDENCE.exists():
        with (EVIDENCE / "acceptance-evidence.jsonl").open(
            "a", encoding="utf-8"
        ) as out:
            out.write(
                json.dumps(
                    {"test_id": test_id, **values}, default=str, ensure_ascii=False
                )
                + "\n"
            )


def mysql_action(action: str) -> None:
    """Request only the dedicated host harness's labelled MySQL container."""
    assert action in {"stop", "start"}
    if not EVIDENCE.exists():
        pytest.skip("dedicated stop/start harness is required")
    request = {"id": uuid4().hex, "action": action}
    (EVIDENCE / "action.json").write_text(json.dumps(request), encoding="utf-8")
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        try:
            if (
                json.loads((EVIDENCE / "ack.json").read_text(encoding="utf-8"))
                == request
            ):
                return
        except (OSError, ValueError):
            pass
        threading.Event().wait(0.02)
    raise AssertionError("dedicated MySQL action was not acknowledged")


@pytest.fixture
def ops(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    url = os.getenv("CQC_BE10_3_DATABASE_URL")
    if not url:
        pytest.skip("isolated CQC_BE10_3_DATABASE_URL not configured")
    if make_url(url).database != "be10_3":
        pytest.fail("acceptance must use disposable be10_3 schema")
    monkeypatch.setenv("CQC_BE10_DATABASE_URL", url)
    engine = create_db_engine(Settings(_env_file=None, database_url=url))
    sessions = create_session_factory(engine)
    with sessions() as session, session.begin():
        session.execute(delete(Inspection))
        mappings = list(session.scalars(select(BinMapping)))
        baseline = [(m.id, m.bin_code, m.is_active) for m in mappings]
    generator = core.environment.__wrapped__(tmp_path)
    environment = next(generator)
    try:
        yield environment
    finally:
        generator.close()
        with sessions() as session, session.begin():
            for identifier, code, active in baseline:
                session.execute(
                    update(BinMapping)
                    .where(BinMapping.id == identifier)
                    .values(bin_code=code, is_active=active)
                )
        engine.dispose()


def post(
    client: TestClient, identifier: str, *, count: int = 1, brix: str | None = "14.0"
) -> dict:
    response = client.post(
        "/v1/inspections", **core._payload(identifier, count, brix=brix)
    )
    assert response.status_code == 200, response.text
    return response.json()


def compare(response: dict, stored: dict) -> None:
    for key in (
        "inspection_id",
        "inspection_status",
        "persistence_status",
        "control_status",
        "predicted_cultivar",
        "predicted_grade",
        "used_frame_count",
        "model_name",
        "model_version",
        "preprocessing_version",
        "target_bin_code",
        "review_required",
        "exclude_from_normal_stats",
    ):
        assert response[key] == stored[key], (key, response[key], stored[key])
    for key in ("cultivar_confidence", "quality_confidence", "inference_time_ms"):
        assert (response[key] is None and stored[key] is None) or (
            response[key] == pytest.approx(float(stored[key]), abs=0.001)
        )
    assert stored["created_at"] <= stored["completed_at"] <= stored["updated_at"]
    assert all(
        stored[key].microsecond % 1000 == 0
        for key in ("created_at", "completed_at", "updated_at")
    )


def csv_rows(response):
    assert response.status_code == 200, response.text
    assert response.content.startswith(b"\xef\xbb\xbf")
    assert response.headers["cache-control"] == "no-store"
    return list(csv.reader(StringIO(response.content.decode("utf-8-sig"))))


def populate_twenty(client, plans, row):
    ids = []
    for index in range(20):
        identifier = f"be10-3.fixture-{index:02d}"
        ids.append(identifier)
        if index < 12:
            plans[identifier] = {
                "cultivar": ("fuji", "yanggwang")[index // 6],
                "grade": ("L", "M", "S")[(index // 2) % 3],
            }
        elif index < 15:
            plans[identifier] = {
                "cc": 0.4 if index != 13 else 0.9,
                "qc": 0.4 if index != 12 else 0.8,
            }
        elif index < 19:
            plans[identifier] = (
                {"http_error": 500}
                if index % 2
                else {"invalid": {"inspection_id": "mismatch"}}
            )
        result = post(
            client,
            identifier,
            brix=None
            if index == 19
            else ("13.9" if index < 12 and index % 2 == 0 else "14.0"),
        )
        compare(result, row(identifier))
    return ids


def test_mysql_storage_duplicate_and_dotted_id(ops):
    factory, endpoint, plans, calls, row, sessions = ops
    app = factory(endpoint)
    identifier = "be10-3.duplicate-low"
    plans[identifier] = {"cc": 0.4}
    with TestClient(app) as client:
        result = post(client, identifier, count=3)
        before = row(identifier)
        compare(result, before)
        control = app.state.inspection_service._virtual_control
        manager = app.state.inspection_service._late_result_manager
        images = client.get(
            "/v1/quality/fault-images", params={"inspectionId": identifier}
        ).json()
        counters = (len(calls), control.call_count, manager.active_count, images)
        assert len(images["items"]) == 3
        duplicate = client.post("/v1/inspections", **core._payload(identifier))
        assert duplicate.status_code == 409
        assert row(identifier) == before
        assert counters == (
            len(calls),
            control.call_count,
            manager.active_count,
            client.get(
                "/v1/quality/fault-images", params={"inspectionId": identifier}
            ).json(),
        )
        concurrent = "be10-3.concurrent-duplicate"
        with ThreadPoolExecutor(max_workers=2) as pool:
            replies = list(
                pool.map(
                    lambda _: client.post(
                        "/v1/inspections", **core._payload(concurrent)
                    ),
                    range(2),
                )
            )
        assert sorted(r.status_code for r in replies) == [200, 409]
        assert sum(c[0] == concurrent for c in calls) == 1
        assert control.call_count == 2 and manager.active_count == 0
        history = client.get("/v1/quality/inspections").json()
        assert identifier in {item["id"] for item in history["items"]}
        snapshot = client.get("/v1/quality/snapshot")
        assert snapshot.status_code == 200
        assert identifier in {
            item["id"] for item in snapshot.json()["state"]["history"]
        }
        assert snapshot.json()["state"]["jobs"] == []
        assert snapshot.json()["state"]["recentCompletedJobs"]
        review = client.patch(
            f"/v1/quality/inspections/{identifier}/review",
            json={"misclassification": "OTHER"},
        )
        assert review.status_code == 200
        after = row(identifier)
        assert after["predicted_cultivar"] == before["predicted_cultivar"]
        assert after["predicted_grade"] == before["predicted_grade"]
        exported = csv_rows(client.get("/v1/quality/inspections.csv"))
        assert identifier in {item[0] for item in exported[1:]}
        assert (
            client.get(f"/v1/quality/previews/{images['items'][0]['id']}").status_code
            == 200
        )
        with sessions() as session:
            attempts = [
                dict(v)
                for v in session.execute(select(ControlAttempt.__table__)).mappings()
            ]
        evidence(
            "KB-01/OBS-01/STORAGE",
            api=result,
            db=before,
            duplicates=[r.status_code for r in replies],
            calls=calls,
            controls=attempts,
            images=images,
            history=history,
            snapshot=snapshot.json(),
            csv=exported,
        )


def test_statistics_twenty_and_image_scope(ops):
    factory, endpoint, plans, _, row, sessions = ops
    app = factory(endpoint)
    with TestClient(app) as client:
        ids = populate_twenty(client, plans, row)
        summary = client.get("/v1/quality/statistics").json()
        assert {
            key: summary[key]
            for key in ("total", "normal", "excluded", "reinspection", "inferenceCount")
        } == {
            "total": 20,
            "normal": 16,
            "excluded": 4,
            "reinspection": 8,
            "inferenceCount": 16,
        }
        assert (
            sum(summary["varieties"].values()) == sum(summary["grades"].values()) == 16
        )
        assert len(summary["bins"]) == 13
        snapshot = client.get("/v1/quality/snapshot").json()
        assert snapshot["state"]["today"]["total"] == 20
        assert snapshot["state"]["today"]["excluded"] == 4
        assert len(snapshot["state"]["history"]) == 20
        items = client.get("/v1/quality/fault-images").json()["items"]
        assert len(items) == 7
        low = [v for v in items if v["category"] == "LOW_CONFIDENCE"]
        system = [v for v in items if v["category"] == "SYSTEM_ERROR"]
        assert len(low) == 3 and len(system) == 4
        assert all(v["errorCode"] is None for v in low)
        assert all(v["errorCode"] and v["decisionReason"] for v in system)
        assert all(
            v["appliedCultivarThreshold"] == 0.5 and v["appliedQualityThreshold"] == 0.6
            for v in items
        )
        for outcome in (
            ControlStatus.FAILED,
            ControlStatus.NO_RESPONSE,
            ControlStatus.REJECTED,
        ):
            app.state.inspection_service._virtual_control = MockVirtualControl(
                [outcome, ControlStatus.SUCCEEDED]
                if outcome == ControlStatus.REJECTED
                else [outcome]
            )
            post(client, f"be10-3.control-{outcome.value}")
        assert len(client.get("/v1/quality/fault-images").json()["items"]) == 7
        with sessions() as session:
            db = [
                dict(v)
                for v in session.execute(
                    select(Inspection.__table__).where(
                        Inspection.inspection_id.in_(ids)
                    )
                ).mappings()
            ]
        sidecars = [
            json.loads(p.read_text())
            for p in app.state.settings.fault_image_storage_root.rglob("*.json")
        ]
        evidence("BE10-OPS-02", api=summary, snapshot=snapshot, db=db)
        evidence(
            "BE10-IMG-01",
            api=items,
            sidecars=sidecars,
            db_count=len(db),
            control_image_count=0,
        )


def test_history_filters_pagination_review_and_csv(ops):
    factory, endpoint, plans, _, row, sessions = ops
    app = factory(endpoint)
    with TestClient(app) as client:
        ids = populate_twenty(client, plans, row)
        now = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=123000)
        base = dict(row(ids[0]))
        base.pop("late_result_payload", None)
        for i in range(199):
            values = dict(
                base,
                inspection_id=f"be10-3.page-{i:03d}",
                created_at=now - timedelta(seconds=1),
                completed_at=now - timedelta(seconds=1),
                updated_at=now - timedelta(seconds=1),
            )
            with sessions() as session, session.begin():
                session.execute(insert(Inspection).values(**values))
        for i in range(6):
            identifier = f"be10-3.additional-error-{i:02d}"
            plans[identifier] = {"http_error": 500}
            post(client, identifier)
        fixed = int(datetime.now(timezone.utc).timestamp() * 1000)
        history = client.get(
            "/v1/quality/inspections", params={"pageSize": 200, "snapshotAt": fixed}
        ).json()
        assert history["total"] == 225 and len(history["items"]) == 200
        page2 = client.get(
            "/v1/quality/inspections",
            params={"pageSize": 200, "page": 2, "snapshotAt": fixed},
        ).json()
        assert len(page2["items"]) == 25
        assert not (
            {v["id"] for v in history["items"]} & {v["id"] for v in page2["items"]}
        )
        with sessions() as session:
            db_order = list(
                session.scalars(
                    select(Inspection.inspection_id).order_by(
                        Inspection.completed_at.desc(), Inspection.inspection_id.desc()
                    )
                )
            )
        assert [v["id"] for v in history["items"] + page2["items"]] == db_order
        checks = [
            {"variety": "양광"},
            {"grade": "상"},
            {"bin": "TEST_REINSPECTION_BIN"},
            {"processingStatus": "ERROR"},
            {"errorCode": "INFERENCE_ERROR"},
            {
                "from": datetime.now(KST).date().isoformat(),
                "to": datetime.now(KST).date().isoformat(),
            },
        ]
        comparisons = []
        for query in checks:
            params = dict(query, snapshotAt=fixed, pageSize=200)
            listed = client.get("/v1/quality/inspections", params=params)
            assert listed.status_code == 200, listed.text
            exported = csv_rows(
                client.get("/v1/quality/inspections.csv", params=params)
            )
            assert len(exported) - 1 == listed.json()["total"]
            assert {v["id"] for v in listed.json()["items"]} <= {
                v[0] for v in exported[1:]
            }
            comparisons.append(
                {"filters": query, "api": listed.json(), "csv_count": len(exported) - 1}
            )
        for page_size in (50, 100, 200):
            assert (
                len(
                    client.get(
                        "/v1/quality/inspections", params={"pageSize": page_size}
                    ).json()["items"]
                )
                == page_size
            )
        for query in (
            {"pageSize": 201},
            {"modelVersion": "mock-v1"},
            {"inspectionId": ids[0]},
            {"from": "bad"},
        ):
            assert (
                client.get("/v1/quality/inspections", params=query).status_code == 422
            )
        assert (
            client.patch(
                "/v1/quality/inspections/be10-3.missing/review",
                json={"misclassification": "OTHER"},
            ).status_code
            == 404
        )
        assert (
            client.patch(
                f"/v1/quality/inspections/{ids[0]}/review",
                json={"misclassification": "OTHER"},
            ).status_code
            == 200
        )
        assert (
            client.get(
                "/v1/quality/inspections", params={"misclassification": "OTHER"}
            ).json()["total"]
            == 1
        )
        complete_csv = client.get(
            "/v1/quality/inspections.csv", params={"snapshotAt": fixed, "pageSize": 50}
        )
        rows = csv_rows(complete_csv)
        assert len(rows) - 1 == 225
        assert {v[0] for v in rows[1:]} == set(db_order)
        assert "부사" in complete_csv.text and "특" in complete_csv.text
        assert any(".123" in v[2] for v in rows[1:])
        snap = client.get("/v1/quality/snapshot").json()
        assert len(snap["state"]["history"]) == 200
        assert len(snap["state"]["errors"]) == 8
        day = datetime.now(KST).date().isoformat()
        stat_csv = csv_rows(
            client.get(
                "/v1/quality/statistics.csv",
                params={"from": day, "to": day, "snapshotAt": fixed},
            )
        )
        assert any(v[3:] == ["total", "total", "225"] for v in stat_csv[1:])
        evidence(
            "BE10-OPS-01",
            db_order=db_order,
            pagination=history,
            second_page=page2,
            filters=comparisons,
            unsupported_filters=["inspectionId", "modelVersion"],
            snapshot=snap,
        )
        evidence(
            "BE10-OPS-03",
            header=rows[0],
            csv_count=225,
            csv_samples=rows[1:4],
            statistics_csv=stat_csv,
            bom=complete_csv.content[:3].hex(),
            kst_milliseconds=True,
        )


def test_images_independent_retention_filter_legacy_orphan_and_delete(ops):
    factory, endpoint, plans, _, row, sessions = ops
    app = factory(endpoint)
    with TestClient(app) as client:
        for category, amount in (("SYSTEM_ERROR", 101), ("LOW_CONFIDENCE", 201)):
            for i in range(amount):
                identifier = f"be10-3.{category}-{i:03d}"
                plans[identifier] = (
                    {"http_error": 500} if category == "SYSTEM_ERROR" else {"cc": 0.4}
                )
                post(client, identifier)
            items = client.get(
                "/v1/quality/fault-images", params={"category": category}
            ).json()["items"]
            assert len(items) == amount - 1
            assert {v["inspectionId"] for v in items} == {
                f"be10-3.{category}-{i:03d}" for i in range(1, amount)
            }
            assert row(f"be10-3.{category}-000")["persistence_status"] == "SUCCEEDED"
        inventory = client.get("/v1/quality/fault-images").json()["items"]
        assert len(inventory) == 300
        orphan = inventory[0]
        assert client.get(
            "/v1/quality/fault-images", params={"inspectionId": orphan["inspectionId"]}
        ).json()["items"] == [orphan]
        for query in ({"category": "INVALID"}, {"inspectionId": "bad/path"}):
            assert (
                client.get("/v1/quality/fault-images", params=query).status_code == 422
            )
        preview = client.get(f"/v1/quality/previews/{orphan['id']}")
        assert (
            preview.status_code == 200
            and preview.headers["cache-control"] == "no-store"
        )
        with sessions() as session, session.begin():
            session.execute(
                delete(Inspection).where(
                    Inspection.inspection_id == orphan["inspectionId"]
                )
            )
        assert (
            client.patch(
                f"/v1/quality/inspections/{orphan['inspectionId']}/review",
                json={"misclassification": "OTHER"},
            ).status_code
            == 404
        )
        assert client.get(f"/v1/quality/previews/{orphan['id']}").status_code == 200
        assert client.get(
            "/v1/quality/fault-images", params={"inspectionId": orphan["inspectionId"]}
        ).json()["items"] == [orphan]
        evidence(
            "BE10-IMG-02",
            categories={"SYSTEM_ERROR": 100, "LOW_CONFIDENCE": 200},
            api=inventory,
            db_count=302,
            oldest_db_preserved=True,
            linux_filesystem=str(app.state.settings.fault_image_storage_root),
        )
        evidence("BE10-IMG-04", api=orphan, db_deleted=True, preview=200, review=404)
        captured = [v["id"] for v in inventory]
        # Delete a real sidecar's new fields to read the original six-field format.
        system_item = next(v for v in inventory if v["category"] == "SYSTEM_ERROR")
        system_root = app.state.settings.fault_image_storage_root
        sidecar = system_root / system_item["id"].split("_")[0] / "image_00.json"
        original = json.loads(sidecar.read_text())
        sidecar.write_text(
            json.dumps(
                {
                    key: original[key]
                    for key in (
                        "id",
                        "inspection_id",
                        "created_at",
                        "error_code",
                        "image_index",
                        "content_type",
                    )
                }
            )
        )
        legacy = client.get(
            "/v1/quality/fault-images",
            params={"inspectionId": system_item["inspectionId"]},
        ).json()["items"][0]
        assert (
            legacy["category"] == "SYSTEM_ERROR" and legacy["qualityConfidence"] is None
        )
        evidence(
            "BE10-IMG-03",
            legacy=legacy,
            categories=["SYSTEM_ERROR", "LOW_CONFIDENCE"],
            dotted_filter=200,
            invalid_filter=422,
        )
        # Confirmed selection does not expand to include a later save.
        # Make room without pruning one of the captured records implicitly.
        deleted = client.request(
            "DELETE",
            "/v1/quality/fault-images",
            json={"ids": [captured[0], captured[0]]},
        )
        assert deleted.status_code == 200 and deleted.json()["deletedIds"] == [
            captured[0]
        ]
        post(client, "be10-3.new-after-confirmation")  # Normal: no image added.
        storage = app.state.low_confidence_image_storage
        new_id = storage.save(
            inspection_id="be10-3.new-sidecar",
            error_code=None,
            category="LOW_CONFIDENCE",
            decision_reason="LOW_CULTIVAR_CONFIDENCE",
            images=[FaultImage(_png(), "image/png")],
        )[0]
        bulk = client.request(
            "DELETE", "/v1/quality/fault-images", json={"ids": captured}
        )
        assert bulk.status_code == 200 and len(bulk.json()["deletedIds"]) == 299
        assert client.get(f"/v1/quality/previews/{captured[0]}").status_code == 410
        assert client.get(f"/v1/quality/previews/{new_id}").status_code == 200
        assert (
            client.request(
                "DELETE", "/v1/quality/fault-images", json={"ids": ["bad/path"]}
            ).status_code
            == 422
        )
        assert (
            client.request(
                "DELETE", "/v1/quality/fault-images", json={"ids": captured}
            ).json()["deletedIds"]
            == []
        )
        evidence(
            "BE10-IMG-05",
            selected_count=300,
            already_deleted=deleted.json(),
            bulk=bulk.json(),
            protected_new_id=new_id,
            expired_preview=410,
            new_preview=200,
        )


def test_database_outage_recovery_lkg_and_invalid_mapping(ops):
    factory, endpoint, plans, _, row, sessions = ops
    app = factory(endpoint)
    with TestClient(app) as client:
        warm = post(client, "be10-3.warm-lkg")
        with sessions() as session:
            active = [
                dict(v)
                for v in session.execute(
                    select(BinMapping.__table__).where(BinMapping.is_active.is_(True))
                ).mappings()
            ]
        assert len(active) == 13
        plans["be10-3.outage-low"] = {"cc": 0.4}
        mysql_action("stop")
        try:
            normal = post(client, "be10-3.outage-normal")
            low = post(client, "be10-3.outage-low")
            assert normal["persistence_status"] == low["persistence_status"] == "FAILED"
            assert normal["target_bin_code"] == warm["target_bin_code"]
            assert low["target_bin_code"] == "TEST_REINSPECTION_BIN"
            assert normal["control_status"] == low["control_status"] == "SUCCEEDED"
            status = {}
            for path in (
                "inspections",
                "statistics",
                "snapshot",
                "inspections.csv",
                "statistics.csv",
            ):
                response = client.get(f"/v1/quality/{path}")
                assert response.status_code == 503
                assert "DB_UNAVAILABLE" in response.text
                status[path] = response.json()
            image = client.get(
                "/v1/quality/fault-images", params={"inspectionId": "be10-3.outage-low"}
            ).json()["items"][0]
            assert client.get(f"/v1/quality/previews/{image['id']}").status_code == 200
            cold = factory(endpoint)
            with TestClient(cold) as cold_client:
                response = cold_client.post(
                    "/v1/inspections", **core._payload("be10-3.cold-outage")
                )
                assert response.status_code == 500
                assert cold.state.inspection_service._virtual_control.call_count == 0
            evidence(
                "BE10-DB-01",
                api=[normal, low],
                db_rows_added=0,
                query_errors=status,
                lkg=active,
                sidecar_without_db=image,
                cold_status=response.status_code,
            )
        finally:
            mysql_action("start")
        with sessions() as session, session.begin():
            mapping = session.scalar(
                select(BinMapping).where(BinMapping.bin_code == warm["target_bin_code"])
            )
            mapping.bin_code = "BE10_RECOVERED_BIN"
        recovered = post(client, "be10-3.recovered")
        assert recovered["target_bin_code"] == "BE10_RECOVERED_BIN"
        compare(recovered, row("be10-3.recovered"))
        with sessions() as session:
            assert session.get(Inspection, "be10-3.outage-normal") is None
            assert session.get(Inspection, "be10-3.outage-low") is None
        assert client.get("/v1/quality/inspections").status_code == 200
        evidence(
            "BE10-DB-02",
            api=recovered,
            db=row("be10-3.recovered"),
            same_backend=True,
            backfill_count=0,
        )
        headers = core._headers(app, 1000)
        headers["X-CQC-Simulator-Faults"] = "DB_ERROR"
        injected = client.post(
            "/v1/inspections",
            headers=headers,
            **core._payload("be10-3.injected-db-error"),
        )
        assert injected.status_code == 200
        assert injected.json()["persistence_status"] == "FAILED"
        assert injected.json()["control_status"] == "SUCCEEDED"
        with sessions() as session:
            assert session.get(Inspection, "be10-3.injected-db-error") is None
        assert client.get("/v1/quality/statistics").status_code == 200
        evidence(
            "BE10-DB-01-INJECTED",
            api=injected.json(),
            db_row=None,
            database_healthy=True,
            query_status=200,
            distinguished_from_actual_outage=True,
        )
        with sessions() as session, session.begin():
            session.execute(
                update(BinMapping)
                .where(BinMapping.bin_code == "BE10_RECOVERED_BIN")
                .values(is_active=False)
            )
        before_control = app.state.inspection_service._virtual_control.call_count
        invalid = client.post(
            "/v1/inspections", **core._payload("be10-3.invalid-mapping")
        )
        assert invalid.status_code == 500
        bad_row = row("be10-3.invalid-mapping")
        assert (
            bad_row["control_status"] == "NOT_REQUESTED"
            and bad_row["target_bin_code"] is None
        )
        assert (
            bad_row["inspection_status"] == "COMPLETED"
            and bad_row["persistence_status"] == "SUCCEEDED"
        )
        assert bad_row["error_code"] == "BIN_MAPPING_CONFIGURATION_ERROR"
        assert (
            app.state.inspection_service._virtual_control.call_count == before_control
        )
        evidence(
            "BE10-DB-03",
            cold_http=500,
            cold_control_calls=0,
            invalid_api=invalid.json(),
            db=bad_row,
        )


def test_final_persistence_outage_and_error_log(ops, tmp_path):
    factory, endpoint, plans, _, row, _sessions = ops
    app = factory(endpoint)
    path = tmp_path / "error.log"
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setLevel(logging.ERROR)
    logging.getLogger().addHandler(handler)
    try:
        with TestClient(app) as client:
            post(client, "be10-3.final-warm")
            # Stop after the normal inference decision, before final persistence.
            # This avoids making container stop latency an inference timeout.
            original = app.state.inspection_service._virtual_control

            class StopDatabaseControl(MockVirtualControl):
                async def send(self, request):
                    await asyncio.to_thread(mysql_action, "stop")
                    return await super().send(request)

            app.state.inspection_service._virtual_control = StopDatabaseControl()
            try:
                result = post(client, "be10-3.final-outage")
                assert result["persistence_status"] == "FAILED"
                assert result["control_status"] == "SUCCEEDED"
                assert result["decision_reason"] == "NORMAL"
            finally:
                mysql_action("start")
                app.state.inspection_service._virtual_control = original
            initial = row("be10-3.final-outage")
            assert (
                initial["persistence_status"] == "PENDING"
            )  # best effort mark_failed was offline
            recovered = post(client, "be10-3.final-recovered")
            assert recovered["persistence_status"] == "SUCCEEDED"
            plans["be10-3.log-saved"] = {"http_error": 500}
            saved = post(client, "be10-3.log-saved")
            plans["be10-3.log-low"] = {"cc": 0.4}
            low = post(client, "be10-3.log-low")
            handler.flush()
            text = path.read_text()
            assert "be10-3.log-saved" in text and "be10-3.final-outage" in text
            assert "be10-3.log-low" not in text
            service = app.state.inspection_service
            system_storage = service._fault_image_storage
            service._fault_image_storage = None
            plans["be10-3.log-disabled"] = {"http_error": 500}
            disabled = post(client, "be10-3.log-disabled")
            service._fault_image_storage = system_storage
            # Point only this test instance at a file, forcing a real mkdir failure.
            blocked = tmp_path / "blocked"
            blocked.write_text("not a directory")
            from src.api.services.fault_image_storage import FaultImageStorage

            service._fault_image_storage = FaultImageStorage(blocked)
            plans["be10-3.log-failed"] = {"http_error": 500}
            failed = post(client, "be10-3.log-failed")
            service._low_confidence_image_storage = FaultImageStorage(blocked)
            plans["be10-3.log-low-failed"] = {"cc": 0.4}
            low_failed = post(client, "be10-3.log-low-failed")
            assert (
                failed["decision_reason"]
                == saved["decision_reason"]
                == disabled["decision_reason"]
            )
            assert low_failed["decision_reason"] == low["decision_reason"]
            assert all(
                v["persistence_status"] == "SUCCEEDED"
                for v in (saved, low, disabled, failed, low_failed)
            )
            handler.flush()
            text = path.read_text()
            assert all(
                i in text
                for i in (
                    "be10-3.log-disabled",
                    "be10-3.log-failed",
                    "be10-3.log-low-failed",
                )
            )
            if EVIDENCE.exists():
                (EVIDENCE / "error.log").write_text(text, encoding="utf-8")
            evidence(
                "BE10-LOG-01",
                api=[saved, low, disabled, failed, low_failed],
                db=[
                    row(i)
                    for i in (
                        "be10-3.log-saved",
                        "be10-3.log-low",
                        "be10-3.log-disabled",
                        "be10-3.log-failed",
                        "be10-3.log-low-failed",
                    )
                ],
                log_file="error.log",
                final_outage_api=result,
                final_outage_db=initial,
                recovered=recovered,
            )
    finally:
        logging.getLogger().removeHandler(handler)
        handler.close()


def test_full_scale_performance_and_retention(ops):
    factory, endpoint, _, _, row, sessions = ops
    app = factory(endpoint)
    with TestClient(app) as client:
        post(client, "be10-3.template")
        template = row("be10-3.template")
        with sessions() as session, session.begin():
            session.execute(delete(Inspection))
        base = datetime.now(timezone.utc).replace(
            tzinfo=None, microsecond=123000
        ) - timedelta(hours=1)
        for offset in range(0, 86400, 2000):
            batch = [
                dict(
                    template,
                    inspection_id=f"be10-3.scale-{i:05d}",
                    created_at=base + timedelta(milliseconds=i),
                    completed_at=base + timedelta(milliseconds=i),
                    updated_at=base + timedelta(milliseconds=i),
                )
                for i in range(offset, min(offset + 2000, 86400))
            ]
            with sessions() as session, session.begin():
                session.execute(insert(Inspection), batch)
        measurements = {}
        for path in ("inspections", "statistics", "snapshot", "inspections.csv"):
            timings = []
            for _ in range(5):
                start = time.perf_counter()
                response = client.get(f"/v1/quality/{path}")
                assert response.status_code == 200, response.text[:200]
                timings.append((time.perf_counter() - start) * 1000)
            measurements[path] = {
                "samples_ms": timings,
                "p50_ms": statistics.median(timings),
                "p95_ms": max(timings),
                "max_ms": max(timings),
                "bytes": len(response.content),
            }
            if path == "inspections.csv":
                assert len(csv_rows(response)) - 1 == 86400
            if path in ("statistics", "inspections"):
                assert response.json()["total"] == 86400
        evidence(
            "BE10-OPS-04",
            rows=86400,
            measurements=measurements,
            quantitative_gate="DEFERRED_BY_USER",
            p95_method="nearest-rank; 5 samples, observational only",
        )
        # Exact default boundary: 86,399 -> insert 86,400 -> oldest 8,640 deleted.
        with sessions() as session, session.begin():
            session.execute(
                delete(Inspection).where(
                    Inspection.inspection_id == "be10-3.scale-86399"
                )
            )
            session.add(
                ControlAttempt(
                    inspection_id="be10-3.scale-00000",
                    command_id=uuid4().hex,
                    attempt_no=1,
                    requested_bin_code="DEMO_BIN_02",
                    command_type="SORT",
                    control_status="SUCCEEDED",
                    requested_at=base,
                    response_time_ms=1,
                )
            )
            session.add(
                InspectionError(
                    inspection_id="be10-3.scale-00000",
                    component="test",
                    error_code="TEST_ERROR",
                    occurred_at=base,
                )
            )
        persistence = InspectionPersistence(sessions)
        created = datetime.now(timezone.utc)
        values = dict(
            template,
            inspection_id="be10-3.boundary",
            created_at=created,
            updated_at=created,
            completed_at=None,
            inspection_status="PROCESSING",
            control_status="PENDING",
            persistence_status="PENDING",
        )
        persistence.create_pending(values)
        persistence.finalize(
            inspection_id="be10-3.boundary",
            inspection_values={
                "completed_at": created,
                "updated_at": created,
                "inspection_status": "COMPLETED",
                "control_status": "SUCCEEDED",
                "persistence_status": "SUCCEEDED",
            },
            control_attempts=[],
            errors=[],
        )
        with sessions() as session:
            count = session.scalar(select(func.count()).select_from(Inspection))
            ids = set(session.scalars(select(Inspection.inspection_id)))
            assert session.scalar(select(func.count()).select_from(ControlAttempt)) == 0
            assert (
                session.scalar(select(func.count()).select_from(InspectionError)) == 0
            )
        assert count == 77760 and persistence._history_count == 77760
        assert "be10-3.scale-08639" not in ids and "be10-3.scale-08640" in ids
        assert "be10-3.boundary" in ids
        assert client.get("/v1/quality/inspections").json()["total"] == 77760
        assert client.get("/v1/quality/statistics").json()["total"] == 77760
        assert len(csv_rows(client.get("/v1/quality/inspections.csv"))) - 1 == 77760
        # An externally oversized DB also converges at the next create_pending.
        with sessions() as session, session.begin():
            session.execute(delete(Inspection))
            session.execute(
                insert(Inspection),
                [dict(template, inspection_id=f"be10-3.small-{i}") for i in range(6)],
            )
        small = InspectionPersistence(sessions, history_limit=5, history_delete_batch=2)
        values.update(inspection_id="be10-3.small-new")
        small.create_pending(values)
        with sessions() as session:
            small_count = session.scalar(select(func.count()).select_from(Inspection))
        assert small_count == small._history_count == 3
        # A cached count is corrected at a boundary after an external deletion.
        with sessions() as session, session.begin():
            session.execute(
                delete(Inspection).where(Inspection.inspection_id == "be10-3.small-4")
            )
        for name in ("cache-a", "cache-b"):
            values.update(inspection_id=f"be10-3.{name}")
            small.create_pending(values)
        with sessions() as session:
            corrected = session.scalar(select(func.count()).select_from(Inspection))
        assert corrected == small._history_count == 4
        evidence(
            "BE10-RET-01",
            before=86399,
            at=86400,
            removed=8640,
            remaining=count,
            first_remaining="be10-3.scale-08640",
            newest="be10-3.boundary",
            api_total=77760,
            csv_count=77760,
            oversize_before=6,
            oversize_insert=7,
            oversize_after=small_count,
            fk_cascade=True,
            external_delete_cache_corrected=corrected,
        )


def test_kst_midnight_and_millisecond_snapshot(ops):
    factory, endpoint, _plans, _calls, row, sessions = ops
    app = factory(endpoint)
    with TestClient(app) as client:
        post(client, "be10-3.kst-template")
        template = row("be10-3.kst-template")
        today = datetime.now(KST).date()
        midnight = datetime.combine(today, datetime.min.time(), tzinfo=KST).astimezone(
            timezone.utc
        )
        before = midnight - timedelta(milliseconds=1)
        after = midnight + timedelta(milliseconds=123)
        with sessions() as session, session.begin():
            session.execute(delete(Inspection))
            for identifier, at in (
                ("be10-3.kst-before", before),
                ("be10-3.kst-at", midnight),
                ("be10-3.kst-after", after),
            ):
                at = at.replace(tzinfo=None)
                session.execute(
                    insert(Inspection).values(
                        **dict(
                            template,
                            inspection_id=identifier,
                            created_at=at,
                            completed_at=at,
                            updated_at=at,
                        )
                    )
                )
        query = {"from": today.isoformat(), "to": today.isoformat()}
        history = client.get("/v1/quality/inspections", params=query).json()
        assert history["total"] == 2
        assert [v["id"] for v in history["items"]] == [
            "be10-3.kst-after",
            "be10-3.kst-at",
        ]
        exported = csv_rows(client.get("/v1/quality/inspections.csv", params=query))
        assert len(exported) - 1 == 2 and exported[1][2] == "00:00:00.123"
        limited = client.get(
            "/v1/quality/inspections",
            params=dict(query, snapshotAt=int(after.timestamp() * 1000) - 1),
        ).json()
        assert limited["total"] == 1 and limited["items"][0]["id"] == "be10-3.kst-at"
        previous = client.get(
            "/v1/quality/inspections",
            params={
                "from": (today - timedelta(days=1)).isoformat(),
                "to": (today - timedelta(days=1)).isoformat(),
            },
        ).json()
        assert previous["total"] == 1
        evidence(
            "BE10-OPS-01/03-KST",
            api=history,
            db=[
                row(v)
                for v in ("be10-3.kst-before", "be10-3.kst-at", "be10-3.kst-after")
            ],
            csv=exported,
            previous_day=previous,
            millisecond_snapshot=limited,
        )


def test_simulator_process_position_recovery_with_mysql(ops, tmp_path):
    from tests.simulator.test_runner import _dataset

    factory, endpoint, _plans, calls, row, _sessions = ops
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    _dataset(dataset)
    for image in dataset.rglob("*.png"):
        image.write_bytes(_png())
    position = tmp_path / "state" / "position.json"
    app = factory(endpoint)
    trace = []

    def await_condition(check, seconds=15):
        until = time.monotonic() + seconds
        while time.monotonic() < until:
            try:
                result = check()
                if result:
                    return result
            except (httpx.HTTPError, OSError, ValueError):
                pass
            threading.Event().wait(0.02)
        raise AssertionError("Simulator readiness/position condition timed out")

    def next_position():
        return (
            json.loads(position.read_text())["next_position"]
            if position.exists()
            else 0
        )

    with core._server(app) as backend:
        for iteration in range(2):
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                port = listener.getsockname()[1]
            env = dict(
                os.environ,
                SIMULATOR_DATASET_ROOT=str(dataset),
                SIMULATOR_POSITION_PATH=str(position),
                SIMULATOR_BACKEND_URL=backend,
                SIMULATOR_FAULT_TOKEN=app.state.settings.simulator_fault_token,
                SIMULATOR_INTERVAL_MS="1000",
                SIMULATOR_BIND_HOST="127.0.0.1",
                SIMULATOR_BIND_PORT=str(port),
                LOG_DIR=str(tmp_path / "logs"),
            )
            start_position = next_position()
            call_start = len(calls)
            with (tmp_path / f"simulator-{iteration}.log").open("w") as log:
                process = subprocess.Popen(
                    [sys.executable, "-m", "src.simulator.main"],
                    env=env,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                )
                try:
                    base = f"http://127.0.0.1:{port}"
                    with httpx.Client(timeout=3) as client:
                        state = await_condition(
                            lambda base=base: (
                                client.get(base + "/state").raise_for_status().json()
                            )
                        )
                        assert state["faults"] == []
                        await_condition(
                            lambda start_position=start_position: (
                                next_position() >= start_position + 2
                            )
                        )
                        state = client.get(base + "/state").json()
                        stopped = client.put(
                            base + "/state",
                            json={
                                "expectedRevision": state["revision"],
                                "running": False,
                            },
                        )
                        assert stopped.status_code == 200
                        stopped_position = next_position()
                        assert stopped_position >= start_position + 2
                        assert client.get(base + "/health").status_code == 503
                        if iteration == 0:
                            state = stopped.json()
                            resumed = client.put(
                                base + "/state",
                                json={
                                    "expectedRevision": state["revision"],
                                    "running": True,
                                    "faults": ["INFERENCE_ERROR"],
                                    "scope": "NEXT",
                                },
                            )
                            assert resumed.status_code == 200
                            await_condition(
                                lambda stopped_position=stopped_position: (
                                    next_position() > stopped_position
                                )
                            )
                        trace.append(
                            {
                                "pid": process.pid,
                                "start_position": start_position,
                                "stopped_position": stopped_position,
                                "state": stopped.json(),
                                "first_inspection_id": calls[call_start][0],
                                "first_db": row(calls[call_start][0]),
                            }
                        )
                finally:
                    process.terminate()
                    process.wait(timeout=15)
            assert process.returncode in (0, -signal.SIGTERM)
            assert (
                "Application shutdown complete"
                in (tmp_path / f"simulator-{iteration}.log").read_text()
            )
        assert trace[1]["start_position"] >= trace[0]["stopped_position"]
        assert trace[0]["pid"] != trace[1]["pid"]
        logs = {p.name: p.read_text() for p in tmp_path.glob("simulator-*.log")}
        evidence(
            "BE10-SIM-01",
            processes=trace,
            final_position=json.loads(position.read_text()),
            logs=logs,
            recreation="independent Linux process; container-volume recreation is not exercised",
        )


def test_injected_database_error_keeps_policy_and_healthy_reads(ops):
    factory, endpoint, _plans, calls, row, sessions = ops
    app = factory(endpoint)
    with TestClient(app) as client:
        warm = post(client, "be10-3.injected-warm")
        headers = core._headers(app, 1000)
        headers["X-CQC-Simulator-Faults"] = "DB_ERROR"
        response = client.post(
            "/v1/inspections",
            headers=headers,
            **core._payload("be10-3.injected-db-error"),
        )
        assert response.status_code == 200
        result = response.json()
        assert result["persistence_status"] == "FAILED"
        assert result["control_status"] == "SUCCEEDED"
        assert result["decision_reason"] == "NORMAL"
        assert result["target_bin_code"] == warm["target_bin_code"]
        with sessions() as session:
            assert session.get(Inspection, "be10-3.injected-db-error") is None
        assert (
            len(calls) == app.state.inspection_service._virtual_control.call_count == 2
        )
        summary = client.get("/v1/quality/statistics")
        assert summary.status_code == 200 and summary.json()["total"] == 1
        assert app.state.inspection_service._late_result_manager.active_count == 0
        evidence(
            "BE10-DB-01-INJECTED",
            api=result,
            db_row=None,
            database_healthy=True,
            stored_warm=row("be10-3.injected-warm"),
            statistics=summary.json(),
        )


def test_mixed_default_retention_preserves_image_store(ops):
    factory, endpoint, plans, _calls, row, sessions = ops
    app = factory(endpoint)
    with TestClient(app) as client:
        identifiers = populate_twenty(client, plans, row)
        templates = [row(identifier) for identifier in identifiers]
        images_before = client.get("/v1/quality/fault-images").json()
        assert len(images_before["items"]) == 7
        old_id = identifiers[15]
        base = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
        with sessions() as session, session.begin():
            session.execute(delete(Inspection))
        for offset in range(0, 86399, 2000):
            batch = []
            for index in range(offset, min(offset + 2000, 86399)):
                values = dict(templates[15 if index == 0 else index % 20])
                at = base + timedelta(milliseconds=index)
                values.update(
                    inspection_id=old_id if index == 0 else f"be10-3.mixed-{index:05d}",
                    created_at=at,
                    completed_at=at,
                    updated_at=at,
                )
                batch.append(values)
            with sessions() as session, session.begin():
                session.execute(insert(Inspection), batch)
        with sessions() as session, session.begin():
            assert session.scalar(select(func.count()).select_from(Inspection)) == 86399
            session.add(
                ControlAttempt(
                    inspection_id=old_id,
                    command_id=uuid4().hex,
                    attempt_no=1,
                    requested_bin_code="TEST_REINSPECTION_BIN",
                    command_type="SORT",
                    control_status="SUCCEEDED",
                    requested_at=base,
                    response_time_ms=1,
                )
            )
            session.add(
                InspectionError(
                    inspection_id=old_id,
                    component="inference",
                    error_code="INFERENCE_HTTP_ERROR",
                    occurred_at=base,
                )
            )
        persistence = InspectionPersistence(sessions)
        created = datetime.now(timezone.utc)
        pending = dict(
            templates[0],
            inspection_id="be10-3.mixed-new",
            created_at=created,
            updated_at=created,
            completed_at=None,
            inspection_status="PROCESSING",
            persistence_status="PENDING",
            control_status="PENDING",
        )
        persistence.create_pending(pending)
        persistence.finalize(
            inspection_id="be10-3.mixed-new",
            inspection_values={
                "completed_at": created,
                "updated_at": created,
                "inspection_status": "COMPLETED",
                "persistence_status": "SUCCEEDED",
                "control_status": "SUCCEEDED",
            },
            control_attempts=[],
            errors=[],
        )
        with sessions() as session:
            assert session.get(Inspection, old_id) is None
            assert session.get(Inspection, "be10-3.mixed-08640") is not None
            assert session.get(Inspection, "be10-3.mixed-new") is not None
            assert session.scalar(select(func.count()).select_from(Inspection)) == 77760
            assert session.scalar(select(func.count()).select_from(ControlAttempt)) == 0
            assert (
                session.scalar(select(func.count()).select_from(InspectionError)) == 0
            )
            excluded = session.scalar(
                select(func.count())
                .select_from(Inspection)
                .where(Inspection.exclude_from_normal_stats.is_(True))
            )
        assert excluded == sum(i % 20 in (15, 16, 17, 18) for i in range(8640, 86399))
        statistics_response = client.get("/v1/quality/statistics").json()
        history = client.get("/v1/quality/inspections").json()
        exported = csv_rows(client.get("/v1/quality/inspections.csv"))
        assert (
            history["total"]
            == statistics_response["total"]
            == len(exported) - 1
            == 77760
        )
        assert statistics_response["excluded"] == excluded
        assert client.get("/v1/quality/fault-images").json() == images_before
        preview = next(v for v in images_before["items"] if v["inspectionId"] == old_id)
        assert client.get(f"/v1/quality/previews/{preview['id']}").status_code == 200
        assert persistence._history_count == 77760
        evidence(
            "BE10-RET-01-MIXED",
            before=86399,
            at=86400,
            removed=8640,
            remaining=77760,
            excluded=excluded,
            statistics=statistics_response,
            history_total=history["total"],
            csv_count=len(exported) - 1,
            fk_cascade=True,
            pruned_inspection_id=old_id,
            preserved_sidecar=preview,
            image_count=7,
            image_preview=200,
            newest_db=row("be10-3.mixed-new"),
        )


def test_period_filter_performance_at_86400_rows(ops):
    factory, endpoint, _plans, _calls, row, sessions = ops
    app = factory(endpoint)
    with TestClient(app) as client:
        post(client, "be10-3.period-template")
        template = row("be10-3.period-template")
        today = datetime.now(KST).date()
        midnight = (
            datetime.combine(today, datetime.min.time(), tzinfo=KST)
            .astimezone(timezone.utc)
            .replace(tzinfo=None)
        )
        with sessions() as session, session.begin():
            session.execute(delete(Inspection))
        for offset in range(0, 86400, 2000):
            batch = []
            for index in range(offset, min(offset + 2000, 86400)):
                at = midnight + timedelta(
                    hours=1 if index < 43200 else -1, milliseconds=index % 43200
                )
                batch.append(
                    dict(
                        template,
                        inspection_id=f"be10-3.period-{index:05d}",
                        created_at=at,
                        completed_at=at,
                        updated_at=at,
                    )
                )
            with sessions() as session, session.begin():
                session.execute(insert(Inspection.__table__), batch)
        with sessions() as session:
            total = session.scalar(select(func.count()).select_from(Inspection))
            selected = session.scalar(
                select(func.count())
                .select_from(Inspection)
                .where(
                    Inspection.completed_at >= midnight,
                    Inspection.completed_at < midnight + timedelta(days=1),
                )
            )
        assert total == 86400 and selected == 43200
        params = {
            "from": today.isoformat(),
            "to": today.isoformat(),
            "snapshotAt": int(datetime.now(timezone.utc).timestamp() * 1000),
        }
        timings = []
        for _ in range(5):
            start = time.perf_counter()
            response = client.get("/v1/quality/inspections", params=params)
            timings.append((time.perf_counter() - start) * 1000)
            assert response.status_code == 200 and response.json()["total"] == selected
            assert len(response.json()["items"]) == 50
        start = time.perf_counter()
        exported = client.get("/v1/quality/inspections.csv", params=params)
        csv_ms = (time.perf_counter() - start) * 1000
        rows = csv_rows(exported)
        assert len(rows) - 1 == selected
        assert {v[0] for v in rows[1:]} == {
            f"be10-3.period-{index:05d}" for index in range(43200)
        }
        with sessions() as session:
            assert session.scalar(select(func.count()).select_from(Inspection)) == total
        evidence(
            "BE10-OPS-04-PERIOD",
            rows=total,
            selected=selected,
            filters=params,
            samples_ms=timings,
            p50_ms=statistics.median(timings),
            p95_ms=max(timings),
            max_ms=max(timings),
            csv_samples=1,
            csv_ms=csv_ms,
            csv_count=len(rows) - 1,
            csv_bytes=len(exported.content),
            immutable_db_count=total,
            quantitative_gate="DEFERRED_BY_USER",
        )
