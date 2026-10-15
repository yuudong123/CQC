"""BE-06 1단계의 독립 장애 이미지 저장소와 정상 이미지 비저장 계약."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient
from starlette.datastructures import UploadFile

from src.api.clients.inference import MockInferenceClient
from src.api.control.virtual_control import MockVirtualControl
from src.api.core.config import Settings
from src.api.db.models import Inspection
from src.api.main import create_app
from src.api.repositories import BinMappingConfigurationError
from src.api.schemas.inspection_results import ControlStatus
from src.api.services.fault_image_storage import FaultImage, FaultImageStorage
from src.api.services.inspections import InspectionService
from src.api.services.late_results import LateResultManager
from src.api.services.quality_operations import QualityOperationsService

from .fakes import FakeBinMappingRepository, RecordingPersistence

PNG = b"\x89PNG\r\n\x1a\n" + b"sample"
JPEG = b"\xff\xd8\xff" + b"sample"
START = datetime(2026, 9, 29, tzinfo=timezone.utc)


@pytest.fixture
def fault_root() -> Iterator[Path]:
    # OS 전역 temp 권한에 의존하지 않고 종료 시 파일을 모두 제거한다.
    workspace = Path(__file__).resolve().parents[2]
    with TemporaryDirectory(prefix="cqc-fault-test-", dir=workspace) as directory:
        yield Path(directory) / "fault-images"


def _jpeg() -> FaultImage:
    return FaultImage(JPEG, "image/jpeg")


def _metadata(root: Path) -> list[dict[str, object]]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in root.glob("*/image_*.json")
    ]


def test_fault_group_saves_jpeg_png_and_minimal_sidecars(fault_root: Path) -> None:
    storage = FaultImageStorage(fault_root)
    ids = storage.save(
        inspection_id="../untrusted-inspection",
        error_code="INFERENCE_ERROR",
        images=[_jpeg(), FaultImage(PNG, "image/png")],
        created_at=START,
    )

    assert len(ids) == 2
    assert len({item.split("_")[0] for item in ids}) == 1
    UUID(ids[0].split("_")[0], version=4)
    assert storage.count_files() == 2
    groups = list(fault_root.iterdir())
    assert len(groups) == 1
    assert sorted(path.name for path in groups[0].iterdir()) == [
        "image_00.jpg",
        "image_00.json",
        "image_01.json",
        "image_01.png",
    ]
    assert (groups[0] / "image_00.jpg").read_bytes() == JPEG
    assert (groups[0] / "image_01.png").read_bytes() == PNG
    records = sorted(_metadata(fault_root), key=lambda row: row["image_index"])
    assert [row["id"] for row in records] == ids
    assert [row["image_index"] for row in records] == [0, 1]
    assert all(row["inspection_id"] == "../untrusted-inspection" for row in records)
    assert all(row["error_code"] == "INFERENCE_ERROR" for row in records)
    assert all(
        row["created_at"] == START.isoformat(timespec="milliseconds") for row in records
    )
    assert not (fault_root.parent / "untrusted-inspection").exists()


@pytest.mark.parametrize(
    "image", [FaultImage(PNG, "image/jpeg"), FaultImage(JPEG, "image/png")]
)
def test_fault_storage_rejects_content_type_mismatch(
    fault_root: Path, image: FaultImage
) -> None:
    with pytest.raises(ValueError, match="Content-Type"):
        FaultImageStorage(fault_root).save(
            inspection_id="inspection-1",
            error_code="INFERENCE_ERROR",
            images=[image],
        )
    assert not fault_root.exists()


def test_partial_write_never_publishes_a_fault_group(
    fault_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    storage = FaultImageStorage(fault_root)
    original_write = FaultImageStorage._write_image
    calls = 0

    def fail_third(path: Path, content: bytes) -> None:
        nonlocal calls
        calls += 1
        if calls == 3:
            raise OSError("disk full")
        original_write(path, content)

    monkeypatch.setattr(FaultImageStorage, "_write_image", staticmethod(fail_third))
    with pytest.raises(OSError, match="disk full"):
        storage.save(
            inspection_id="inspection-1",
            error_code="INFERENCE_ERROR",
            images=[_jpeg(), _jpeg(), _jpeg()],
        )
    assert storage.count_files() == 0
    assert list(fault_root.iterdir()) == []


def test_file_limit_keeps_newest_hundred_images(fault_root: Path) -> None:
    storage = FaultImageStorage(fault_root)
    first_id = ""
    for index in range(100):
        ids = storage.save(
            inspection_id=f"inspection-{index}",
            error_code="INFERENCE_ERROR",
            images=[_jpeg()],
            created_at=START + timedelta(seconds=index),
        )
        if index == 0:
            first_id = ids[0]
    assert storage.count_files() == 100

    newest = storage.save(
        inspection_id="inspection-100",
        error_code="INFERENCE_ERROR",
        images=[_jpeg()],
        created_at=START + timedelta(seconds=100),
    )[0]
    retained_ids = {row["id"] for row in _metadata(fault_root)}
    assert storage.count_files() == 100
    assert first_id not in retained_ids
    assert newest in retained_ids


def test_limit_counts_files_across_multi_image_groups(fault_root: Path) -> None:
    storage = FaultImageStorage(fault_root, limit=3)
    first_ids = storage.save(
        inspection_id="first-inspection",
        error_code="INFERENCE_ERROR",
        images=[_jpeg(), _jpeg()],
        created_at=START,
    )
    second_ids = storage.save(
        inspection_id="second-inspection",
        error_code="INFERENCE_ERROR",
        images=[_jpeg(), _jpeg()],
        created_at=START + timedelta(seconds=1),
    )
    retained = {row["id"] for row in _metadata(fault_root)}
    assert storage.count_files() == 3
    assert first_ids[0] not in retained
    assert set(first_ids[1:] + second_ids) == retained


def test_prune_failure_logs_and_does_not_discard_new_image(
    fault_root: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    storage = FaultImageStorage(fault_root, limit=2)
    for index in range(2):
        storage.save(
            inspection_id=f"inspection-{index}",
            error_code="INFERENCE_ERROR",
            images=[_jpeg()],
            created_at=START + timedelta(seconds=index),
        )
    original_delete = FaultImageStorage._delete_image

    def fail_delete(_image: object) -> None:
        raise OSError("permission denied")

    monkeypatch.setattr(FaultImageStorage, "_delete_image", staticmethod(fail_delete))
    with caplog.at_level(logging.ERROR):
        new_id = storage.save(
            inspection_id="inspection-new",
            error_code="INFERENCE_ERROR",
            images=[_jpeg()],
            created_at=START + timedelta(seconds=2),
        )[0]
    assert new_id in {row["id"] for row in _metadata(fault_root)}
    assert storage.count_files() == 3
    assert "삭제에 실패" in caplog.text

    monkeypatch.setattr(
        FaultImageStorage, "_delete_image", staticmethod(original_delete)
    )
    storage.save(
        inspection_id="inspection-later",
        error_code="INFERENCE_ERROR",
        images=[_jpeg()],
        created_at=START + timedelta(seconds=3),
    )
    assert storage.count_files() == 2


def test_concurrent_saves_have_unique_ids_and_serialized_prune(
    fault_root: Path,
) -> None:
    storage = FaultImageStorage(fault_root, limit=2)
    storage.save(
        inspection_id="old",
        error_code="INFERENCE_ERROR",
        images=[_jpeg()],
        created_at=START,
    )

    def save(index: int) -> str:
        return storage.save(
            inspection_id=f"concurrent-{index}",
            error_code="INFERENCE_ERROR",
            images=[_jpeg()],
            created_at=START + timedelta(seconds=index + 1),
        )[0]

    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(save, range(2)))
    assert len(set(ids)) == 2
    assert storage.count_files() == 2
    assert set(ids) == {row["id"] for row in _metadata(fault_root)}


def test_settings_and_inspection_schema_keep_images_outside_db(
    fault_root: Path,
) -> None:
    settings = Settings(fault_image_storage_root=fault_root, fault_image_limit=100)
    assert settings.fault_image_storage_root == fault_root
    assert settings.fault_image_limit == 100
    assert {"image", "image_path", "storage_key", "blob"}.isdisjoint(
        Inspection.__table__.columns.keys()
    )


def test_normal_request_closes_uploads_without_persisting_image(
    fault_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(fault_image_storage_root=fault_root)
    service = InspectionService(
        MockInferenceClient(),
        MockVirtualControl(),
        cultivar_confidence_threshold=0.5,
        quality_confidence_threshold=0.5,
        inference_business_deadline_ms=500,
        late_result_manager=LateResultManager(hard_timeout_ms=2000, max_tasks=4),
        bin_mapping_repository=FakeBinMappingRepository(),
        persistence=RecordingPersistence(),
    )
    original_close = UploadFile.close
    closed: list[UploadFile] = []

    async def record_close(image: UploadFile) -> None:
        await original_close(image)
        closed.append(image)

    monkeypatch.setattr(UploadFile, "close", record_close)
    with TestClient(create_app(settings, inspection_service=service)) as client:
        response = client.post(
            "/v1/inspections",
            data={
                "inspection_id": "normal-1",
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
                "virtual_brix": "14.0",
            },
            files=[("images", ("../untrusted.jpg", JPEG, "image/jpeg"))],
        )
        invalid_response = client.post(
            "/v1/inspections",
            data={"inspection_id": "invalid-1", "metadata": "[]"},
            files=[("images", ("../untrusted.jpg", JPEG, "image/jpeg"))],
        )
        normal_preview = client.get("/v1/quality/previews/normal-1")
    assert response.status_code == 200
    assert invalid_response.status_code == 422
    assert normal_preview.status_code == 410
    assert len(closed) >= 2 and all(image.file.closed for image in closed)
    assert not fault_root.exists()


def test_inventory_and_preview_are_per_image_and_do_not_expose_paths(
    fault_root: Path,
) -> None:
    storage = FaultImageStorage(fault_root)
    first = storage.save(
        inspection_id="inspection-1",
        error_code="INFERENCE_DEADLINE_EXCEEDED",
        images=[_jpeg(), FaultImage(PNG, "image/png")],
        created_at=START,
    )
    second = storage.save(
        inspection_id="inspection-2",
        error_code="INFERENCE_HTTP_ERROR",
        images=[_jpeg()],
        created_at=START + timedelta(seconds=1),
    )
    with TestClient(
        create_app(Settings(fault_image_storage_root=fault_root))
    ) as client:
        response = client.get("/v1/quality/fault-images")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        items = response.json()["items"]
        assert [item["id"] for item in items] == second + first[::-1]
        assert [item["inspectionId"] for item in items] == [
            "inspection-2",
            "inspection-1",
            "inspection-1",
        ]
        assert [item["imageIndex"] for item in items] == [0, 1, 0]
        assert items[0]["errorCode"] == "INFERENCE_HTTP_ERROR"
        assert items[1]["errorCode"] == "INFERENCE_TIMEOUT"
        assert all(item["createdAt"] > 0 for item in items)
        assert all(
            item["previewUrl"] == f"/api/quality/previews/{item['id']}"
            for item in items
        )
        assert str(fault_root).encode() not in response.content
        assert b"image_00" not in response.content
        for image_id, expected_type, expected_bytes in (
            (first[0], "image/jpeg", JPEG),
            (first[1], "image/png", PNG),
        ):
            preview = client.get(f"/v1/quality/previews/{image_id}")
            assert preview.status_code == 200
            assert preview.headers["content-type"] == expected_type
            assert preview.headers["cache-control"] == "no-store"
            assert preview.content == expected_bytes
        for image_id in ("missing", "..", f"{first[0]}../image_00"):
            preview = client.get(f"/v1/quality/previews/{image_id}")
            assert preview.status_code in (404, 410)
            if preview.status_code == 410:
                assert preview.headers["cache-control"] == "no-store"


def test_empty_inventory_and_pruning_remove_sidecars_and_empty_group(
    fault_root: Path,
) -> None:
    storage = FaultImageStorage(fault_root, limit=2)
    with TestClient(
        create_app(Settings(fault_image_storage_root=fault_root))
    ) as client:
        assert client.get("/v1/quality/fault-images").json() == {"items": []}
    first = storage.save(
        inspection_id="inspection-1",
        error_code="INFERENCE_CONNECTION_ERROR",
        images=[_jpeg(), _jpeg()],
        created_at=START,
    )
    second = storage.save(
        inspection_id="inspection-2",
        error_code="INFERENCE_INVALID_RESPONSE",
        images=[_jpeg()],
        created_at=START + timedelta(seconds=1),
    )
    assert {item.id for item in storage.list_images()} == {first[1], second[0]}
    assert storage.read_image(first[0]) is None
    assert storage.read_image(first[1]) == (JPEG, "image/jpeg")
    first_group = fault_root / first[0].split("_")[0]
    assert not (first_group / "image_00.json").exists()
    storage.save(
        inspection_id="inspection-3",
        error_code="INFERENCE_HTTP_ERROR",
        images=[_jpeg()],
        created_at=START + timedelta(seconds=2),
    )
    assert not first_group.exists()
    orphan = fault_root / second[0].split("_")[0] / "image_09.json"
    orphan.write_text("{}", encoding="utf-8")
    orphan_image = orphan.with_suffix(".jpg")
    orphan_image.write_bytes(JPEG)
    orphan.unlink()
    orphan_sidecar = orphan.with_name("image_08.json")
    orphan_sidecar.write_text("{}", encoding="utf-8")
    storage.list_images()
    assert not orphan.exists()
    assert not orphan_image.exists()
    assert not orphan_sidecar.exists()


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        ("timeout", "INFERENCE_DEADLINE_EXCEEDED"),
        ("connection", "INFERENCE_CONNECTION_ERROR"),
        ("http", "INFERENCE_HTTP_ERROR"),
        ("invalid", "INFERENCE_INVALID_RESPONSE"),
    ],
)
def test_inference_faults_store_original_upload_bytes(
    fault_root: Path, failure: str, expected: str
) -> None:
    class FailingClient(MockInferenceClient):
        async def predict(self, request):
            if failure == "timeout":
                return await MockInferenceClient(response_delay_ms=20).predict(request)
            if failure == "connection":
                raise httpx.ConnectError(
                    "offline", request=httpx.Request("POST", "http://test")
                )
            if failure == "http":
                raise httpx.HTTPStatusError(
                    "bad response",
                    request=httpx.Request("POST", "http://test"),
                    response=httpx.Response(500),
                )
            return (await super().predict(request)).model_copy(
                update={"inspection_id": "wrong"}
            )

    storage = FaultImageStorage(fault_root)
    service = InspectionService(
        FailingClient(),
        MockVirtualControl(),
        cultivar_confidence_threshold=0.5,
        quality_confidence_threshold=0.5,
        inference_business_deadline_ms=1 if failure == "timeout" else 500,
        late_result_manager=LateResultManager(hard_timeout_ms=2000, max_tasks=4),
        bin_mapping_repository=FakeBinMappingRepository(),
        persistence=RecordingPersistence(),
        fault_image_storage=storage,
    )
    with TestClient(create_app(Settings(), inspection_service=service)) as client:
        response = client.post(
            "/v1/inspections",
            data={
                "inspection_id": "fault-1",
                "metadata": json.dumps(
                    [
                        {
                            "view_index": 0,
                            "angle_direction": "top",
                            "verticality_angle": 0,
                            "horizontality_angle": 0,
                        },
                        {
                            "view_index": 1,
                            "angle_direction": "bottom",
                            "verticality_angle": 0,
                            "horizontality_angle": 0,
                        },
                    ]
                ),
            },
            files=[
                ("images", ("a.jpg", JPEG, "image/jpeg")),
                ("images", ("b.png", PNG, "image/png")),
            ],
        )
    assert response.status_code == 200
    assert response.json()["decision_reason"] == expected
    records = storage.list_images()
    assert len(records) == 2
    assert [record.image_index for record in records] == [1, 0]
    assert all(record.error_code == expected for record in records)
    assert storage.read_image(records[0].id) == (PNG, "image/png")
    assert storage.read_image(records[1].id) == (JPEG, "image/jpeg")


def test_fault_storage_failure_does_not_change_inspection_result(
    fault_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class ConnectionFailureClient(MockInferenceClient):
        async def predict(self, request):
            raise httpx.ConnectError(
                "offline", request=httpx.Request("POST", "http://test")
            )

    storage = FaultImageStorage(fault_root)

    def fail_save(**kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(storage, "save", fail_save)
    persistence = RecordingPersistence()
    service = InspectionService(
        ConnectionFailureClient(),
        MockVirtualControl(),
        cultivar_confidence_threshold=0.5,
        quality_confidence_threshold=0.5,
        inference_business_deadline_ms=500,
        late_result_manager=LateResultManager(hard_timeout_ms=2000, max_tasks=4),
        bin_mapping_repository=FakeBinMappingRepository(),
        persistence=persistence,
        fault_image_storage=storage,
    )
    with TestClient(create_app(Settings(), inspection_service=service)) as client:
        response = client.post(
            "/v1/inspections",
            data={
                "inspection_id": "fault-1",
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
            },
            files=[("images", ("a.jpg", JPEG, "image/jpeg"))],
        )
    assert response.status_code == 200
    result = response.json()
    assert result["decision_reason"] == "INFERENCE_CONNECTION_ERROR"
    assert result["target_bin_code"] == "TEST_REINSPECTION_BIN"
    assert result["control_status"] == "SUCCEEDED"
    assert result["persistence_status"] == "SUCCEEDED"
    assert persistence.final_values[0]["error_code"] == "INFERENCE_CONNECTION_ERROR"


@pytest.mark.parametrize(
    "excluded_case",
    [
        "low_confidence",
        "control_rejected",
        "control_no_response",
        "control_failed",
        "db_failure",
        "mapping_error",
    ],
)
def test_non_inference_failures_do_not_store_fault_images(
    fault_root: Path, excluded_case: str
) -> None:
    class BrokenMapping(FakeBinMappingRepository):
        def load_snapshot(self):
            raise BinMappingConfigurationError("missing mapping")

    control_outcomes = {
        "control_rejected": [ControlStatus.REJECTED, ControlStatus.SUCCEEDED],
        "control_no_response": [ControlStatus.NO_RESPONSE],
        "control_failed": [ControlStatus.FAILED],
    }
    service = InspectionService(
        MockInferenceClient(),
        MockVirtualControl(control_outcomes.get(excluded_case)),
        cultivar_confidence_threshold=0.95
        if excluded_case == "low_confidence"
        else 0.5,
        quality_confidence_threshold=0.5,
        inference_business_deadline_ms=500,
        late_result_manager=LateResultManager(hard_timeout_ms=2000, max_tasks=4),
        bin_mapping_repository=(
            BrokenMapping()
            if excluded_case == "mapping_error"
            else FakeBinMappingRepository()
        ),
        persistence=RecordingPersistence(fail_finalize=excluded_case == "db_failure"),
        fault_image_storage=FaultImageStorage(fault_root),
    )
    with TestClient(create_app(Settings(), inspection_service=service)) as client:
        response = client.post(
            "/v1/inspections",
            data={
                "inspection_id": "non-fault",
                "virtual_brix": "14.0",
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
            },
            files=[("images", ("a.jpg", JPEG, "image/jpeg"))],
        )
    assert response.status_code == (500 if excluded_case == "mapping_error" else 200)
    assert not fault_root.exists()


def test_delete_api_removes_only_requested_images_and_preserves_others(
    fault_root: Path,
) -> None:
    storage = FaultImageStorage(fault_root)
    first = storage.save(
        inspection_id="inspection-1",
        error_code="INFERENCE_HTTP_ERROR",
        images=[_jpeg(), _jpeg()],
        created_at=START,
    )
    second = storage.save(
        inspection_id="inspection-2",
        error_code="INFERENCE_INVALID_RESPONSE",
        images=[_jpeg()],
        created_at=START + timedelta(seconds=1),
    )
    with TestClient(
        create_app(Settings(fault_image_storage_root=fault_root))
    ) as client:
        response = client.request(
            "DELETE", "/v1/quality/fault-images", json={"ids": [first[0], second[0]]}
        )
        assert response.status_code == 200
        assert response.json() == {"deletedIds": [first[0], second[0]]}
        assert response.headers["cache-control"] == "no-store"
        assert [
            item["id"]
            for item in client.get("/v1/quality/fault-images").json()["items"]
        ] == [first[1]]
        expired = client.get(f"/v1/quality/previews/{first[0]}")
        assert expired.status_code == 410
        assert expired.headers["cache-control"] == "no-store"
        assert client.get(f"/v1/quality/previews/{first[1]}").status_code == 200
        assert client.get(f"/v1/quality/previews/{second[0]}").status_code == 410
    first_group = fault_root / first[0].split("_")[0]
    second_group = fault_root / second[0].split("_")[0]
    assert not (first_group / "image_00.jpg").exists()
    assert not (first_group / "image_00.json").exists()
    assert (first_group / "image_01.jpg").exists()
    assert (first_group / "image_01.json").exists()
    assert not second_group.exists()


def test_delete_all_uses_confirmation_id_snapshot_and_keeps_new_images(
    fault_root: Path,
) -> None:
    storage = FaultImageStorage(fault_root)
    old = storage.save(
        inspection_id="inspection-old",
        error_code="INFERENCE_HTTP_ERROR",
        images=[_jpeg(), _jpeg()],
        created_at=START,
    )
    with TestClient(
        create_app(Settings(fault_image_storage_root=fault_root))
    ) as client:
        captured = [
            item["id"]
            for item in client.get("/v1/quality/fault-images").json()["items"]
        ]
        newer = storage.save(
            inspection_id="inspection-new",
            error_code="INFERENCE_HTTP_ERROR",
            images=[_jpeg()],
            created_at=START + timedelta(seconds=1),
        )[0]
        response = client.request(
            "DELETE", "/v1/quality/fault-images", json={"ids": captured}
        )
        assert set(response.json()["deletedIds"]) == set(old)
        assert [
            item["id"]
            for item in client.get("/v1/quality/fault-images").json()["items"]
        ] == [newer]
        assert client.request(
            "DELETE", "/v1/quality/fault-images", json={"ids": [newer]}
        ).json() == {"deletedIds": [newer]}
        assert client.get("/v1/quality/fault-images").json() == {"items": []}
        assert client.request(
            "DELETE", "/v1/quality/fault-images", json={"ids": []}
        ).json() == {"deletedIds": []}
    assert storage.count_files() == 0


def test_delete_is_idempotent_for_missing_pruned_and_duplicate_ids(
    fault_root: Path,
) -> None:
    storage = FaultImageStorage(fault_root, limit=1)
    pruned = storage.save(
        inspection_id="old",
        error_code="INFERENCE_ERROR",
        images=[_jpeg()],
        created_at=START,
    )[0]
    current = storage.save(
        inspection_id="new",
        error_code="INFERENCE_ERROR",
        images=[_jpeg()],
        created_at=START + timedelta(seconds=1),
    )[0]
    with TestClient(
        create_app(Settings(fault_image_storage_root=fault_root, fault_image_limit=1))
    ) as client:
        response = client.request(
            "DELETE",
            "/v1/quality/fault-images",
            json={"ids": [pruned, "a" * 32 + "_00", current, current]},
        )
        assert response.status_code == 200
        assert response.json() == {"deletedIds": [current]}
        assert client.request(
            "DELETE", "/v1/quality/fault-images", json={"ids": [current]}
        ).json() == {"deletedIds": []}
        for payload in ({}, {"ids": ["../outside"]}, {"ids": [], "all": True}):
            invalid = client.request("DELETE", "/v1/quality/fault-images", json=payload)
            assert invalid.status_code == 422
            assert invalid.json() == {"code": "INVALID_IDS"}
            assert invalid.headers["cache-control"] == "no-store"


def test_delete_does_not_clean_unrelated_record_directory(fault_root: Path) -> None:
    storage = FaultImageStorage(fault_root)
    target = storage.save(
        inspection_id="target", error_code="INFERENCE_ERROR", images=[_jpeg()]
    )[0]
    unrelated = storage.save(
        inspection_id="unrelated", error_code="INFERENCE_ERROR", images=[_jpeg()]
    )[0]
    unrelated_group = fault_root / unrelated.split("_")[0]
    unrelated_image = unrelated_group / "image_00.jpg"
    unrelated_sidecar = unrelated_group / "image_00.json"
    unrelated_image.unlink()
    assert storage.delete_images([target]) == [target]
    assert unrelated_sidecar.exists()
    assert unrelated_group.exists()
    storage.list_images()
    assert not unrelated_group.exists()


def test_delete_without_configured_storage_is_unavailable() -> None:
    with TestClient(create_app(Settings())) as client:
        response = client.request(
            "DELETE", "/v1/quality/fault-images", json={"ids": []}
        )
    assert response.status_code == 503
    assert response.json() == {"code": "IMAGE_UNAVAILABLE"}
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("failure", ["image", "metadata", "directory"])
def test_delete_partial_failure_reports_only_completed_ids(
    fault_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    storage = FaultImageStorage(fault_root)
    failing = storage.save(
        inspection_id="first",
        error_code="INFERENCE_ERROR",
        images=[_jpeg()],
        created_at=START,
    )[0]
    succeeding = storage.save(
        inspection_id="second",
        error_code="INFERENCE_ERROR",
        images=[_jpeg()],
        created_at=START + timedelta(seconds=1),
    )[0]
    failing_group = fault_root / failing.split("_")[0]
    target = {
        "image": failing_group / "image_00.jpg",
        "metadata": failing_group / "image_00.json",
        "directory": failing_group,
    }[failure]
    method = "rmdir" if failure == "directory" else "unlink"
    original = getattr(Path, method)
    calls = 0

    def fail_once(path: Path, *args, **kwargs):
        nonlocal calls
        if path == target and calls == 0:
            calls += 1
            raise OSError("simulated delete failure")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, method, fail_once)
    with TestClient(
        create_app(Settings(fault_image_storage_root=fault_root))
    ) as client:
        response = client.request(
            "DELETE", "/v1/quality/fault-images", json={"ids": [failing, succeeding]}
        )
        assert response.status_code == 200
        assert response.json() == {"deletedIds": [succeeding]}
        assert response.headers["cache-control"] == "no-store"
        assert client.get("/v1/quality/fault-images").status_code == 200
    assert calls == 1
    assert storage.count_files() == (1 if failure == "image" else 0)
    if failure != "image":
        assert not any(fault_root.glob("*/image_*.json"))


def test_delete_and_save_share_lock_and_preserve_new_arrival(
    fault_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = FaultImageStorage(fault_root)
    old = storage.save(
        inspection_id="old",
        error_code="INFERENCE_ERROR",
        images=[_jpeg()],
        created_at=START,
    )[0]
    deleting = Event()
    release = Event()
    original_delete = FaultImageStorage._delete_image

    def paused_delete(image):
        deleting.set()
        assert release.wait(5)
        original_delete(image)

    monkeypatch.setattr(FaultImageStorage, "_delete_image", staticmethod(paused_delete))
    with ThreadPoolExecutor(max_workers=2) as pool:
        delete_future = pool.submit(storage.delete_images, [old])
        assert deleting.wait(5)
        save_future = pool.submit(
            storage.save,
            inspection_id="new",
            error_code="INFERENCE_ERROR",
            images=[_jpeg()],
            created_at=START + timedelta(seconds=1),
        )
        release.set()
        assert delete_future.result(timeout=5) == [old]
        new_id = save_future.result(timeout=5)[0]
    assert [item.id for item in storage.list_images()] == [new_id]


def test_prune_list_and_preview_race_with_delete_keep_consistent_files(
    fault_root: Path,
) -> None:
    storage = FaultImageStorage(fault_root, limit=2)
    old = storage.save(
        inspection_id="old",
        error_code="INFERENCE_ERROR",
        images=[_jpeg()],
        created_at=START,
    )[0]

    def save_and_prune() -> str:
        for index in range(2):
            result = storage.save(
                inspection_id=f"new-{index}",
                error_code="INFERENCE_ERROR",
                images=[_jpeg()],
                created_at=START + timedelta(seconds=index + 1),
            )[0]
        return result

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [
            pool.submit(storage.delete_images, [old]),
            pool.submit(save_and_prune),
            pool.submit(storage.list_images),
            pool.submit(storage.read_image, old),
        ]
        for future in futures:
            future.result(timeout=5)
    records = storage.list_images()
    assert len(records) <= 2
    assert old not in {item.id for item in records}
    assert len(list(fault_root.glob("*/image_*.jpg"))) == len(records)
    assert len(list(fault_root.glob("*/image_*.json"))) == len(records)


def test_snapshot_reflects_actual_image_count_and_delete_capability(
    fault_root: Path,
) -> None:
    history_row = Inspection(
        inspection_id="inspection-retained",
        completed_at=datetime(2026, 9, 29, 14, 59, 59, 123000),  # noqa: DTZ001 - DB UTC naive
        predicted_cultivar="fuji",
        predicted_grade="L",
        quality_confidence=Decimal("0.8"),
        cultivar_confidence=Decimal("0.9"),
        exclude_from_normal_stats=False,
        review_required=True,
        deadline_exceeded=False,
        persistence_status="SUCCEEDED",
        control_status="SUCCEEDED",
        target_bin_code="DEMO_BIN_02",
        error_code=None,
        suspected_error_type="CULTIVAR_SUSPECT",
        virtual_brix=Decimal("14.0"),
        inference_time_ms=Decimal("120.125"),
        model_version="demo-v1",
    )
    history_row.control_attempts = []
    history_row.errors = []

    class FakeHistory:
        def recent_rows(self, *args, **kwargs):
            return [history_row]

        def recent_errors(self, *args, **kwargs):
            return []

    class FakeStatistics:
        def today(self, *args, **kwargs):
            return "2026-09-29", {
                "total": 0,
                "normal": 0,
                "excluded": 0,
                "grades": {},
                "varieties": {},
                "bins": {},
                "suspicions": {"CULTIVAR_SUSPECT": 1},
                "reinspection": 0,
                "inferenceTotalMs": 0,
                "inferenceCount": 0,
            }

        def review_count(self, *args, **kwargs):
            return 0

        def last_saved(self, *args, **kwargs):
            return None

        def period_totals(self, *args, **kwargs):
            return {key: 0 for key in ("1", "5", "10", "30")}

        def points(self, *args, **kwargs):
            return []

    storage = FaultImageStorage(fault_root, limit=2)
    app = create_app(Settings(fault_image_storage_root=fault_root, fault_image_limit=2))
    app.state.quality_operations_service = QualityOperationsService(
        FakeHistory(), FakeStatistics(), storage
    )
    unconfigured = QualityOperationsService(FakeHistory(), FakeStatistics()).snapshot(
        datetime(2026, 9, 29, 0, 0, 0)  # noqa: DTZ001 - DB UTC naive
    )
    assert unconfigured["capabilities"]["deleteImages"] is False
    assert unconfigured["retention"]["images"] == 0
    with TestClient(app) as client:

        def snapshot() -> dict:
            response = client.get("/v1/quality/snapshot")
            assert response.status_code == 200
            return response.json()

        assert snapshot()["retention"]["images"] == 0
        first = storage.save(
            inspection_id="first",
            error_code="INFERENCE_ERROR",
            images=[_jpeg()],
            created_at=START,
        )[0]
        assert snapshot()["retention"]["images"] == 1
        storage.save(
            inspection_id="second",
            error_code="INFERENCE_ERROR",
            images=[_jpeg()],
            created_at=START + timedelta(seconds=1),
        )
        assert snapshot()["retention"]["images"] == 2
        storage.save(
            inspection_id="third",
            error_code="INFERENCE_ERROR",
            images=[_jpeg()],
            created_at=START + timedelta(seconds=2),
        )
        assert snapshot()["retention"]["images"] == 2
        assert storage.read_image(first) is None
        ids = [item.id for item in storage.list_images()]
        assert (
            client.request(
                "DELETE", "/v1/quality/fault-images", json={"ids": ids[:1]}
            ).status_code
            == 200
        )
        assert snapshot()["retention"]["images"] == 1
        assert (
            client.request(
                "DELETE", "/v1/quality/fault-images", json={"ids": ids[1:]}
            ).status_code
            == 200
        )
        state = snapshot()
        assert state["retention"]["images"] == 0
        assert state["capabilities"]["deleteImages"] is True
        assert state["state"]["images"] == []
        assert state["state"]["history"][0]["id"] == "inspection-retained"
        assert state["state"]["history"][0]["misclassification"] == "CULTIVAR_SUSPECT"
        low_storage = app.state.low_confidence_image_storage
        app.state.quality_operations_service = QualityOperationsService(
            FakeHistory(),
            FakeStatistics(),
            storage,
            low_confidence_image_storage=low_storage,
        )
        low_id = low_storage.save(
            inspection_id="retained-low",
            error_code=None,
            category="LOW_CONFIDENCE",
            decision_reason="LOW_BOTH_CONFIDENCE",
            images=[_jpeg()],
        )[0]
        assert snapshot()["retention"]["images"] == 1
        assert snapshot()["state"]["history"][0]["id"] == "inspection-retained"
        assert client.request(
            "DELETE", "/v1/quality/fault-images", json={"ids": [low_id]}
        ).json() == {"deletedIds": [low_id]}
        assert snapshot()["retention"]["images"] == 0
