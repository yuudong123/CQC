"""BE-06 1단계의 독립 장애 이미지 저장소와 정상 이미지 비저장 계약."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from starlette.datastructures import UploadFile

from src.api.clients.inference import MockInferenceClient
from src.api.control.virtual_control import MockVirtualControl
from src.api.core.config import Settings
from src.api.db.models import Inspection
from src.api.main import create_app
from src.api.services.fault_image_storage import FaultImage, FaultImageStorage
from src.api.services.inspections import InspectionService
from src.api.services.late_results import LateResultManager

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
    assert response.status_code == 200
    assert invalid_response.status_code == 422
    assert len(closed) >= 2 and all(image.file.closed for image in closed)
    assert not fault_root.exists()
