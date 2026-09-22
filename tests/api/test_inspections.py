from __future__ import annotations

import json

from fastapi.testclient import TestClient
from httpx import Response

from src.api.core.config import Settings
from src.api.main import create_app


def _metadata(
    view_indexes: list[int],
    *,
    angle_direction: str = "top",
) -> str:
    return json.dumps(
        [
            {
                "view_index": view_index,
                "angle_direction": angle_direction,
                "verticality_angle": view_index * 10 - 20,
                "horizontality_angle": view_index * 15 - 30,
            }
            for view_index in view_indexes
        ]
    )


def _images(
    count: int,
    *,
    content_type: str = "image/png",
    content: bytes = b"image-bytes",
) -> list[tuple[str, tuple[str, bytes, str]]]:
    return [
        ("images", (f"view-{index}.png", content, content_type))
        for index in range(count)
    ]


def _post(
    client: TestClient,
    *,
    files: list[tuple[str, tuple[str, bytes, str]]],
    metadata: str,
    inspection_id: str = "inspection-001",
) -> Response:
    return client.post(
        "/v1/inspections",
        data={"inspection_id": inspection_id, "metadata": metadata},
        files=files,
    )


def test_inspection_accepts_valid_multipart_contract() -> None:
    with TestClient(create_app(Settings())) as client:
        response = _post(client, files=_images(2), metadata=_metadata([0, 1]))

    assert response.status_code == 200
    assert response.json() == {
        "inspection_id": "inspection-001",
        "image_count": 2,
        "validation": "passed",
    }


def test_inspection_accepts_jpeg_content_type() -> None:
    with TestClient(create_app(Settings())) as client:
        response = _post(
            client,
            files=_images(1, content_type="image/jpeg"),
            metadata=_metadata([0]),
        )

    assert response.status_code == 200


def test_inspection_accepts_twelve_images() -> None:
    with TestClient(create_app(Settings())) as client:
        response = _post(
            client,
            files=_images(12),
            metadata=_metadata(list(range(12))),
        )

    assert response.status_code == 200
    assert response.json()["image_count"] == 12


def test_inspection_requires_at_least_one_image() -> None:
    with TestClient(create_app(Settings())) as client:
        response = client.post(
            "/v1/inspections",
            data={"inspection_id": "inspection-001", "metadata": "[]"},
        )

    assert response.status_code == 422


def test_inspection_rejects_more_than_twelve_images() -> None:
    with TestClient(create_app(Settings())) as client:
        response = _post(client, files=_images(13), metadata=_metadata(list(range(13))))

    assert response.status_code == 413


def test_inspection_rejects_mismatched_image_and_metadata_counts() -> None:
    with TestClient(create_app(Settings())) as client:
        response = _post(client, files=_images(2), metadata=_metadata([0]))

    assert response.status_code == 422


def test_inspection_rejects_duplicate_view_indexes() -> None:
    with TestClient(create_app(Settings())) as client:
        response = _post(client, files=_images(2), metadata=_metadata([0, 0]))

    assert response.status_code == 422


def test_inspection_rejects_view_indexes_out_of_order() -> None:
    with TestClient(create_app(Settings())) as client:
        response = _post(client, files=_images(2), metadata=_metadata([1, 0]))

    assert response.status_code == 422


def test_inspection_rejects_unknown_angle_direction() -> None:
    with TestClient(create_app(Settings())) as client:
        response = _post(
            client,
            files=_images(1),
            metadata=_metadata([0], angle_direction="side"),
        )

    assert response.status_code == 422


def test_inspection_rejects_invalid_metadata_json() -> None:
    with TestClient(create_app(Settings())) as client:
        response = _post(client, files=_images(1), metadata="not-json")

    assert response.status_code == 422


def test_inspection_rejects_unsupported_image_content_type() -> None:
    with TestClient(create_app(Settings())) as client:
        response = _post(
            client,
            files=_images(1, content_type="text/plain"),
            metadata=_metadata([0]),
        )

    assert response.status_code == 415


def test_inspection_rejects_request_over_configured_size_limit() -> None:
    settings = Settings(inference_max_request_bytes=256)
    with TestClient(create_app(settings)) as client:
        response = _post(
            client,
            files=_images(1, content=b"x" * 512),
            metadata=_metadata([0]),
        )

    assert response.status_code == 413
