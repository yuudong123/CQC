"""Issue #55 retention, review-image contracts and diagnostic logging."""

import json
import logging
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from fastapi.testclient import TestClient

from src.api.clients.inference import MockInferenceClient
from src.api.control.virtual_control import MockVirtualControl
from src.api.core.config import Settings
from src.api.main import create_app
from src.api.schemas.inspection_results import InspectionDecisionReason
from src.api.services.fault_image_storage import FaultImageStorage
from src.api.services.inspections import InspectionService
from src.api.services.late_results import LateResultManager

from .fakes import FakeBinMappingRepository, RecordingPersistence
from .test_fault_image_storage import JPEG, START, _jpeg


@pytest.fixture
def fault_root():
    with TemporaryDirectory(
        prefix="cqc-review-test-", dir=Path(__file__).resolve().parents[2]
    ) as directory:
        yield Path(directory) / "fault-images"


def _service(system=None, low=None, *, cultivar=0.95, quality=0.85, persistence=None):
    return InspectionService(
        MockInferenceClient(),
        MockVirtualControl(),
        cultivar_confidence_threshold=cultivar,
        quality_confidence_threshold=quality,
        inference_business_deadline_ms=500,
        late_result_manager=LateResultManager(hard_timeout_ms=2000, max_tasks=4),
        bin_mapping_repository=FakeBinMappingRepository(),
        persistence=persistence or RecordingPersistence(),
        fault_image_storage=system,
        low_confidence_image_storage=low,
    )


def _post(client, brix=15):
    data = {
        "inspection_id": "review-1",
        "metadata": json.dumps(
            [
                {
                    "view_index": 0,
                    "angle_direction": "top",
                    "verticality_angle": 0,
                    "horizontality_angle": 0,
                }
            ]
        ),
    }
    if brix is not None:
        data["virtual_brix"] = str(brix)
    response = client.post(
        "/v1/inspections", data=data, files=[("images", ("a.jpg", JPEG, "image/jpeg"))]
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize(
    "cultivar,quality,reason",
    [
        (0.95, 0.6, "LOW_CULTIVAR_CONFIDENCE"),
        (0.5, 0.85, "LOW_QUALITY_CONFIDENCE"),
        (0.95, 0.85, "LOW_BOTH_CONFIDENCE"),
    ],
)
def test_low_confidence_evidence_without_error_log(
    fault_root: Path, caplog, cultivar, quality, reason
):
    system = FaultImageStorage(fault_root)
    low = FaultImageStorage(fault_root / "low-confidence", limit=200)
    with (
        caplog.at_level(logging.ERROR),
        TestClient(
            create_app(
                Settings(fault_image_storage_root=fault_root),
                inspection_service=_service(
                    system, low, cultivar=cultivar, quality=quality
                ),
            )
        ) as client,
    ):
        result = _post(client)
        item = client.get("/v1/quality/fault-images").json()["items"][0]
    assert result["decision_reason"] == reason
    assert result["exclude_from_normal_stats"] is False
    assert result["target_bin_code"] == "TEST_REINSPECTION_BIN"
    assert system.count_files() == 0 and low.count_files() == 1
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]
    expected = {
        "category": "LOW_CONFIDENCE",
        "decisionReason": reason,
        "errorCode": None,
        "cultivarConfidence": 0.9,
        "qualityConfidence": 0.8,
        "appliedCultivarThreshold": cultivar,
        "appliedQualityThreshold": quality,
    }
    assert {key: item[key] for key in expected} == expected
    sidecar = next((fault_root / "low-confidence").glob("*/image_00.json"))
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    expected_metadata = {
        "inspection_id": "review-1",
        "category": "LOW_CONFIDENCE",
        "decision_reason": reason,
        "cultivar_confidence": 0.9,
        "quality_confidence": 0.8,
        "applied_cultivar_threshold": cultivar,
        "applied_quality_threshold": quality,
    }
    assert {key: data[key] for key in expected_metadata} == expected_metadata
    assert "cultivar_probabilities" not in data


@pytest.mark.parametrize("brix", [15, None])
def test_normal_and_missing_brix_not_saved(fault_root: Path, brix):
    system = FaultImageStorage(fault_root)
    low = FaultImageStorage(fault_root / "low-confidence", limit=200)
    with TestClient(
        create_app(
            Settings(),
            inspection_service=_service(system, low, cultivar=0.5, quality=0.6),
        )
    ) as client:
        _post(client, brix)
    assert system.count_files() == low.count_files() == 0


def test_independent_100_200_retention_and_bulk_api(fault_root: Path):
    app = create_app(Settings(fault_image_storage_root=fault_root))
    system, low = app.state.fault_image_storage, app.state.low_confidence_image_storage
    assert app.state.settings.fault_image_limit == 100
    assert app.state.settings.low_confidence_image_limit == 200
    system_ids, low_ids = [], []
    for index in range(101):
        system_ids.extend(
            system.save(
                inspection_id=f"system-{index}",
                error_code="INFERENCE_CONNECTION_ERROR",
                images=[_jpeg()],
                created_at=START + timedelta(seconds=index),
            )
        )
    for index in range(201):
        low_ids.extend(
            low.save(
                inspection_id=f"low-{index}",
                error_code=None,
                category="LOW_CONFIDENCE",
                decision_reason="LOW_BOTH_CONFIDENCE",
                images=[_jpeg()],
                created_at=START + timedelta(seconds=index),
            )
        )
    assert system.count_files() == 100 and low.count_files() == 200
    assert (
        system.read_image(system_ids[0]) is None and low.read_image(low_ids[0]) is None
    )
    assert system.read_image(system_ids[1]) == (JPEG, "image/jpeg")
    system.save(
        inspection_id="new-system",
        error_code="INFERENCE_HTTP_ERROR",
        images=[_jpeg()],
        created_at=START + timedelta(seconds=300),
    )
    assert system.read_image(system_ids[1]) is None
    assert low.read_image(low_ids[1]) == (JPEG, "image/jpeg")
    with TestClient(app) as client:
        items = client.get("/v1/quality/fault-images").json()["items"]
        assert len(items) == 300
        ids = [item["id"] for item in items]
        response = client.request(
            "DELETE", "/v1/quality/fault-images", json={"ids": ids}
        )
        assert response.status_code == 200 and response.json()["deletedIds"] == ids
    assert system.count_files() == low.count_files() == 0


def test_legacy_filters_preview_delete_without_db(fault_root: Path):
    system = FaultImageStorage(fault_root)
    low = FaultImageStorage(fault_root / "low-confidence", limit=200)
    legacy = system.save(
        inspection_id="same-inspection",
        error_code="INFERENCE_DEADLINE_EXCEEDED",
        images=[_jpeg()],
        created_at=START,
    )[0]
    sidecar = fault_root / legacy.split("_")[0] / "image_00.json"
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    data = {
        k: v
        for k, v in data.items()
        if k
        in {
            "id",
            "inspection_id",
            "created_at",
            "error_code",
            "image_index",
            "content_type",
        }
    }
    sidecar.write_text(json.dumps(data), encoding="utf-8")
    recent = low.save(
        inspection_id="same-inspection",
        error_code=None,
        category="LOW_CONFIDENCE",
        decision_reason="LOW_QUALITY_CONFIDENCE",
        images=[_jpeg()],
        created_at=START + timedelta(seconds=1),
    )[0]
    low.save(
        inspection_id="other",
        error_code=None,
        category="LOW_CONFIDENCE",
        decision_reason="LOW_CULTIVAR_CONFIDENCE",
        images=[_jpeg()],
    )
    with TestClient(
        create_app(Settings(database_url=None, fault_image_storage_root=fault_root))
    ) as client:
        items = client.get(
            "/v1/quality/fault-images", params={"inspectionId": "same-inspection"}
        ).json()["items"]
        assert [item["id"] for item in items] == [recent, legacy]
        assert items[1]["category"] == "SYSTEM_ERROR"
        assert items[1]["decisionReason"] == "INFERENCE_DEADLINE_EXCEEDED"
        assert items[1]["errorCode"] == "INFERENCE_TIMEOUT"
        assert (
            items[1]["cultivarConfidence"] is None
            and items[1]["appliedQualityThreshold"] is None
        )
        for category, count in [("LOW_CONFIDENCE", 2), ("SYSTEM_ERROR", 1)]:
            assert (
                len(
                    client.get(
                        "/v1/quality/fault-images", params={"category": category}
                    ).json()["items"]
                )
                == count
            )
        filtered = client.get(
            "/v1/quality/fault-images",
            params={"category": "LOW_CONFIDENCE", "inspectionId": "same-inspection"},
        )
        assert [item["id"] for item in filtered.json()["items"]] == [recent]
        for params in ({"category": "NORMAL"}, {"inspectionId": "../bad"}):
            assert (
                client.get("/v1/quality/fault-images", params=params).status_code == 422
            )
        for image_id in (legacy, recent):
            preview = client.get(f"/v1/quality/previews/{image_id}")
            assert (
                preview.content == JPEG
                and preview.headers["cache-control"] == "no-store"
            )
        assert client.request(
            "DELETE", "/v1/quality/fault-images", json={"ids": [recent, legacy]}
        ).json() == {"deletedIds": [recent, legacy]}
        for image_id in (legacy, recent):
            assert client.get(f"/v1/quality/previews/{image_id}").status_code == 410


@pytest.mark.parametrize(
    "reason",
    [
        "INFERENCE_DEADLINE_EXCEEDED",
        "INFERENCE_CONNECTION_ERROR",
        "INFERENCE_HTTP_ERROR",
        "INFERENCE_INVALID_RESPONSE",
    ],
)
@pytest.mark.parametrize("outcome", ["disabled", "saved", "failed"])
def test_system_error_logs_id_reason_outcome(
    fault_root: Path, caplog, monkeypatch, reason, outcome
):
    storage = None if outcome == "disabled" else FaultImageStorage(fault_root)
    if outcome == "failed":

        def fail_save(**kwargs):
            raise OSError("disk full")

        monkeypatch.setattr(storage, "save", fail_save)
    service = _service(storage)
    original = service.inspect

    async def injected(**kwargs):
        kwargs["injected_inference_reason"] = InspectionDecisionReason(reason)
        return await original(**kwargs)

    monkeypatch.setattr(service, "inspect", injected)
    with (
        caplog.at_level(logging.ERROR),
        TestClient(create_app(Settings(), inspection_service=service)) as client,
    ):
        result = _post(client)
    assert result["decision_reason"] == reason
    assert result["target_bin_code"] == "TEST_REINSPECTION_BIN"
    logs = [r for r in caplog.records if "Inspection image storage:" in r.message]
    assert len(logs) == 1
    assert "inspection_id=review-1" in logs[0].message
    assert f"decision_reason={reason}" in logs[0].message
    assert f"image_storage={outcome}" in logs[0].message
    assert f"images_saved={int(outcome == 'saved')}" in logs[0].message
    if outcome == "saved":
        record = storage.list_images()[0]
        assert record.category == "SYSTEM_ERROR"
        assert record.decision_reason == reason
        assert record.applied_cultivar_threshold == 0.95
        assert record.applied_quality_threshold == 0.85
        assert record.cultivar_confidence is None


def test_low_storage_failure_preserves_decision_and_control(
    fault_root: Path, monkeypatch, caplog
):
    low = FaultImageStorage(fault_root / "low-confidence", limit=200)
    persistence = RecordingPersistence()

    def fail_save(**kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(low, "save", fail_save)
    with (
        caplog.at_level(logging.ERROR),
        TestClient(
            create_app(
                Settings(),
                inspection_service=_service(low=low, persistence=persistence),
            )
        ) as client,
    ):
        result = _post(client)
    assert result["decision_reason"] == "LOW_BOTH_CONFIDENCE"
    assert result["target_bin_code"] == "TEST_REINSPECTION_BIN"
    assert (
        result["control_status"] == "SUCCEEDED"
        and result["persistence_status"] == "SUCCEEDED"
    )
    assert result["exclude_from_normal_stats"] is False
    assert persistence.final_values[0]["error_code"] == "LOW_BOTH_CONFIDENCE"
    assert any(
        "image_storage=failed" in r.message and "inspection_id=review-1" in r.message
        for r in caplog.records
    )


def test_db_failure_still_allows_sidecar_lookup(fault_root: Path):
    low = FaultImageStorage(fault_root / "low-confidence", limit=200)
    service = _service(low=low, persistence=RecordingPersistence(fail_create=True))
    with TestClient(
        create_app(
            Settings(database_url=None, fault_image_storage_root=fault_root),
            inspection_service=service,
        )
    ) as client:
        assert _post(client)["persistence_status"] == "FAILED"
        response = client.get(
            "/v1/quality/fault-images", params={"inspectionId": "review-1"}
        )
        assert response.status_code == 200
        image_id = response.json()["items"][0]["id"]
        assert client.get(f"/v1/quality/previews/{image_id}").content == JPEG


def test_shared_contract_covers_review_inventory():
    shared = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "docs/contracts/quality-operations.openapi.json"
        ).read_text(encoding="utf-8")
    )
    actual = create_app(Settings()).openapi()
    expected = shared["components"]["schemas"]["FaultImage"]
    runtime = actual["components"]["schemas"]["QualityFaultImage"]
    assert set(expected["properties"]) == set(runtime["properties"])
    assert set(expected["required"]) == set(runtime["required"])
    assert (
        expected["properties"]["category"]["enum"]
        == runtime["properties"]["category"]["enum"]
    )
    for schema, runtime_schema, field in [
        ("FaultImages", "QualityFaultImages", "items"),
        ("ImageDelete", "QualityImageDelete", "ids"),
        ("ImageDeleteAck", "QualityImageDeleteAck", "deletedIds"),
    ]:
        assert (
            shared["components"]["schemas"][schema]["properties"][field]["maxItems"]
            == actual["components"]["schemas"][runtime_schema]["properties"][field][
                "maxItems"
            ]
            == 300
        )
    assert {
        p["name"] for p in shared["paths"]["/fault-images"]["get"]["parameters"]
    } == {
        p["name"]
        for p in actual["paths"]["/v1/quality/fault-images"]["get"]["parameters"]
    }


def test_system_storage_error_reaches_error_log_but_low_success_does_not(
    fault_root: Path,
    monkeypatch,
):
    from src.logging_config import configure_service_logging

    root_logger = logging.getLogger()
    old_handlers, old_level = root_logger.handlers[:], root_logger.level
    monkeypatch.setenv("LOG_DIR", str(fault_root.parent / "logs"))
    try:
        error_log = configure_service_logging()
        system = FaultImageStorage(fault_root)
        low = FaultImageStorage(fault_root / "low-confidence", limit=200)
        service = _service(system, low)
        original = service.inspect

        async def injected(**kwargs):
            kwargs["injected_inference_reason"] = (
                InspectionDecisionReason.INFERENCE_CONNECTION_ERROR
            )
            return await original(**kwargs)

        monkeypatch.setattr(service, "inspect", injected)
        with TestClient(create_app(Settings(), inspection_service=service)) as client:
            _post(client)
            monkeypatch.setattr(service, "inspect", original)
            _post(client)
        for handler in root_logger.handlers:
            handler.flush()
        contents = error_log.read_text(encoding="utf-8")
        assert "inspection_id=review-1" in contents
        assert "decision_reason=INFERENCE_CONNECTION_ERROR" in contents
        assert "image_storage=saved" in contents
        assert "LOW_BOTH_CONFIDENCE" not in contents
    finally:
        for handler in root_logger.handlers:
            if handler not in old_handlers:
                handler.close()
        root_logger.handlers[:] = old_handlers
        root_logger.setLevel(old_level)
