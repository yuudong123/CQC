from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from httpx import Response

from src.api.clients.inference import HttpInferenceClient, MockInferenceClient
from src.api.control.virtual_control import MockVirtualControl
from src.api.core.config import Settings
from src.api.main import create_app
from src.api.schemas.inference import InferenceRequest, InferenceResponse
from src.api.services.inspections import InspectionService
from src.api.services.late_results import LateResultManager

from .fakes import FakeBinMappingRepository, RecordingPersistence


class MismatchedResponseClient(MockInferenceClient):
    def __init__(
        self, *, inspection_id: bool = False, frame_count: bool = False
    ) -> None:
        self._mismatch_inspection_id = inspection_id
        self._mismatch_frame_count = frame_count

    async def predict(self, request: InferenceRequest) -> InferenceResponse:
        response = await super().predict(request)
        if self._mismatch_inspection_id:
            response = response.model_copy(update={"inspection_id": "different-id"})
        if self._mismatch_frame_count:
            response = response.model_copy(update={"used_frame_count": 12})
        return response


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


def _application(settings: Settings | None = None):
    runtime_settings = settings or Settings()
    service = InspectionService(
        MockInferenceClient(),
        MockVirtualControl(),
        cultivar_confidence_threshold=runtime_settings.cultivar_confidence_threshold,
        quality_confidence_threshold=runtime_settings.quality_confidence_threshold,
        inference_business_deadline_ms=(
            runtime_settings.inference_business_deadline_ms
        ),
        late_result_manager=LateResultManager(
            hard_timeout_ms=runtime_settings.inference_hard_timeout_ms,
            max_tasks=runtime_settings.max_late_tasks,
        ),
        bin_mapping_repository=FakeBinMappingRepository(),
        persistence=RecordingPersistence(),
    )
    return create_app(runtime_settings, inspection_service=service)


@pytest.mark.parametrize(
    "inspection_id",
    [
        "inspection.001",
        "ordinary-id_1",
        "550e8400-e29b-41d4-a716-446655440000",
        "a" * 64,
    ],
)
def test_inspection_accepts_shared_identifier_contract(inspection_id: str) -> None:
    with TestClient(_application()) as client:
        response = _post(
            client,
            files=_images(1),
            metadata=_metadata([0]),
            inspection_id=inspection_id,
        )
    assert response.status_code == 200, response.text
    assert response.json()["inspection_id"] == inspection_id


@pytest.mark.parametrize("inspection_id", ["a" * 65, "   ", "a/b", r"a\b", "a b"])
def test_inspection_rejects_invalid_identifier_before_service(
    inspection_id: str,
) -> None:
    with TestClient(_application()) as client:
        response = _post(
            client,
            files=_images(1),
            metadata=_metadata([0]),
            inspection_id=inspection_id,
        )
    assert response.status_code == 422


def test_simulator_fault_headers_are_private_and_external_post_does_not_claim_next() -> (
    None
):
    app = _application(Settings(simulator_fault_token="test-token"))
    assert not hasattr(app.state, "simulator_state_service")
    data = {
        "inspection_id": "simulator-header-1",
        "metadata": _metadata([0]),
        "virtual_brix": "14.0",
    }
    with TestClient(app) as client:
        external = client.post("/v1/inspections", data=data, files=_images(1))
        assert external.status_code == 200
        assert external.json()["decision_reason"] == "NORMAL"
        forbidden = client.post(
            "/v1/inspections",
            data=data,
            files=_images(1),
            headers={
                "X-CQC-Simulator-Token": "wrong",
                "X-CQC-Simulator-Faults": "INFERENCE_ERROR",
                "X-CQC-Simulator-Bundle-ID": "demo-0",
            },
        )
        assert forbidden.status_code == 403
        internal = client.post(
            "/v1/inspections",
            data={**data, "inspection_id": "simulator-header-2"},
            files=_images(1),
            headers={
                "X-CQC-Simulator-Token": app.state.simulator_fault_token,
                "X-CQC-Simulator-Faults": "INFERENCE_ERROR",
                "X-CQC-Simulator-Bundle-ID": "demo-0",
            },
        )
        assert internal.status_code == 200
        assert internal.json()["decision_reason"] == "INFERENCE_HTTP_ERROR"


def test_inspection_accepts_valid_multipart_contract() -> None:
    with TestClient(_application()) as client:
        response = client.post(
            "/v1/inspections",
            data={
                "inspection_id": "inspection-001",
                "metadata": _metadata([0, 1]),
                "virtual_brix": "11.9",
            },
            files=_images(2),
        )

    assert response.status_code == 200
    assert response.json() == {
        "inspection_id": "inspection-001",
        "crop_type": "apple",
        "predicted_cultivar": "fuji",
        "cultivar_confidence": 0.9,
        "cultivar_probabilities": {"fuji": 0.9, "yanggwang": 0.1},
        "predicted_grade": "L",
        "quality_confidence": 0.8,
        "quality_probabilities": {"L": 0.8, "M": 0.1, "S": 0.1},
        "inference_time_ms": 12.5,
        "model_name": "mock-separate",
        "model_version": "mock-cqc-separate12-v1",
        "preprocessing_version": "mock-v1",
        "used_frame_count": 2,
        "inspection_status": "COMPLETED",
        "review_required": False,
        "exclude_from_normal_stats": False,
        "decision_reason": "NORMAL",
        "virtual_brix": 11.9,
        "brix_is_measured": False,
        "sweetness_band": "less_sweet",
        "target_bin_code": "DEMO_BIN_01",
        "control_status": "SUCCEEDED",
        "persistence_status": "SUCCEEDED",
    }


@pytest.mark.parametrize(
    ("virtual_brix", "target_bin", "sweetness_band"),
    [
        ("12.0", "DEMO_BIN_01", "less_sweet"),
        ("13.9", "DEMO_BIN_01", "less_sweet"),
        ("14.0", "DEMO_BIN_02", "sweet"),
    ],
)
def test_inspection_routes_demo_brix_to_twelve_bins(
    virtual_brix: str,
    target_bin: str,
    sweetness_band: str,
) -> None:
    with TestClient(_application()) as client:
        response = client.post(
            "/v1/inspections",
            data={
                "inspection_id": "demo-001",
                "metadata": _metadata([0]),
                "virtual_brix": virtual_brix,
            },
            files=_images(1),
        )
    assert response.status_code == 200
    body = response.json()
    assert body["target_bin_code"] == target_bin
    assert body["virtual_brix"] == float(virtual_brix)
    assert body["sweetness_band"] == sweetness_band
    assert body["brix_is_measured"] is False


@pytest.mark.parametrize("virtual_brix", ["8.9", "18.1", "nan", "inf"])
def test_inspection_rejects_invalid_demo_brix(virtual_brix: str) -> None:
    with TestClient(_application()) as client:
        response = client.post(
            "/v1/inspections",
            data={
                "inspection_id": "demo-invalid",
                "metadata": _metadata([0]),
                "virtual_brix": virtual_brix,
            },
            files=_images(1),
        )
    assert response.status_code == 422


def test_inspection_accepts_jpeg_content_type() -> None:
    with TestClient(_application()) as client:
        response = _post(
            client,
            files=_images(1, content_type="image/jpeg"),
            metadata=_metadata([0]),
        )

    assert response.status_code == 200


def test_inspection_accepts_twelve_images() -> None:
    with TestClient(_application()) as client:
        response = _post(
            client,
            files=_images(12),
            metadata=_metadata(list(range(12))),
        )

    assert response.status_code == 200
    assert response.json()["used_frame_count"] == 12


def test_inspection_uses_thresholds_from_settings() -> None:
    settings = Settings(
        cultivar_confidence_threshold=0.95,
        quality_confidence_threshold=0.50,
    )
    with TestClient(_application(settings)) as client:
        response = _post(client, files=_images(1), metadata=_metadata([0]))

    assert response.status_code == 200
    assert response.json()["inspection_status"] == "REINSPECTION_REQUIRED"
    assert response.json()["review_required"] is True
    assert response.json()["target_bin_code"] == "TEST_REINSPECTION_BIN"
    assert response.json()["control_status"] == "SUCCEEDED"


def test_inspection_returns_timeout_without_fabricated_prediction() -> None:
    service = InspectionService(
        MockInferenceClient(response_delay_ms=50),
        MockVirtualControl(),
        cultivar_confidence_threshold=0.50,
        quality_confidence_threshold=0.50,
        inference_business_deadline_ms=1,
        late_result_manager=LateResultManager(
            hard_timeout_ms=200,
            max_tasks=4,
        ),
        bin_mapping_repository=FakeBinMappingRepository(),
        persistence=RecordingPersistence(),
    )
    with TestClient(create_app(Settings(), inspection_service=service)) as client:
        response = _post(client, files=_images(1), metadata=_metadata([0]))

    assert response.status_code == 200
    body = response.json()
    assert body["inspection_id"] == "inspection-001"
    assert body["predicted_cultivar"] is None
    assert body["predicted_grade"] is None
    assert body["used_frame_count"] is None
    assert body["inspection_status"] == "REINSPECTION_REQUIRED"
    assert body["review_required"] is True
    assert body["exclude_from_normal_stats"] is True
    assert body["decision_reason"] == "INFERENCE_DEADLINE_EXCEEDED"
    assert body["target_bin_code"] == "TEST_REINSPECTION_BIN"
    assert body["control_status"] == "SUCCEEDED"


@pytest.mark.parametrize(
    "inference_client",
    [
        MismatchedResponseClient(inspection_id=True),
        MismatchedResponseClient(frame_count=True),
    ],
)
def test_inspection_returns_internal_error_for_mismatched_inference_response(
    inference_client: MockInferenceClient,
) -> None:
    service = InspectionService(
        inference_client,
        MockVirtualControl(),
        cultivar_confidence_threshold=0.50,
        quality_confidence_threshold=0.50,
        inference_business_deadline_ms=500,
        late_result_manager=LateResultManager(
            hard_timeout_ms=2000,
            max_tasks=4,
        ),
        bin_mapping_repository=FakeBinMappingRepository(),
        persistence=RecordingPersistence(),
    )
    with TestClient(create_app(Settings(), inspection_service=service)) as client:
        response = _post(client, files=_images(1), metadata=_metadata([0]))

    assert response.status_code == 200
    assert response.json()["decision_reason"] == "INFERENCE_INVALID_RESPONSE"
    assert response.json()["target_bin_code"] == "TEST_REINSPECTION_BIN"


@pytest.mark.parametrize(
    ("updates", "valid"),
    [
        pytest.param({"inference_time_ms": 12.5}, True, id="positive"),
        pytest.param({"inference_time_ms": 0.0}, True, id="zero"),
        pytest.param({"inference_time_ms": float("inf")}, False, id="infinity"),
        pytest.param({"inference_time_ms": float("nan")}, False, id="nan"),
        pytest.param(
            {"inference_time_ms": float("-inf")}, False, id="negative-infinity"
        ),
        pytest.param({"inference_time_ms": -1.0}, False, id="negative"),
        pytest.param(
            {"cultivar_probabilities": {"fuji": 0.9, "yanggwang": 0.2}},
            False,
            id="cultivar-sum",
        ),
        pytest.param({"cultivar_confidence": 0.8}, False, id="cultivar-confidence"),
        pytest.param(
            {"predicted_cultivar": "yanggwang"}, False, id="cultivar-prediction"
        ),
        pytest.param(
            {"quality_probabilities": {"L": 0.8, "M": 0.2, "S": 0.2}},
            False,
            id="quality-sum",
        ),
        pytest.param({"quality_confidence": 0.7}, False, id="quality-confidence"),
        pytest.param({"predicted_grade": "M"}, False, id="quality-prediction"),
    ],
)
def test_http_inference_response_validation_preserves_inspection_policy(
    updates: dict[str, object], valid: bool
) -> None:
    async def run() -> None:
        request = InferenceRequest(
            inspection_id="inspection-time",
            images=[b"image-bytes"],
            metadata=json.loads(_metadata([0])),
        )
        payload = (await MockInferenceClient().predict(request)).model_dump()
        payload.update(updates)

        def respond(_: httpx.Request) -> httpx.Response:
            # Raw JSON exercises nonstandard numeric tokens from an external peer.
            return httpx.Response(
                200,
                content=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
            )

        control = MockVirtualControl()
        persistence = RecordingPersistence()
        settings = Settings(_env_file=None)
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(respond)
        ) as transport:
            service = InspectionService(
                HttpInferenceClient("http://inference/v1/predict", client=transport),
                control,
                cultivar_confidence_threshold=settings.cultivar_confidence_threshold,
                quality_confidence_threshold=settings.quality_confidence_threshold,
                inference_business_deadline_ms=settings.inference_business_deadline_ms,
                late_result_manager=LateResultManager(
                    hard_timeout_ms=2000, max_tasks=4
                ),
                bin_mapping_repository=FakeBinMappingRepository(),
                persistence=persistence,
            )
            app = create_app(settings, inspection_service=service)
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://backend"
            ) as client:
                response = await client.post(
                    "/v1/inspections",
                    data={
                        "inspection_id": request.inspection_id,
                        "metadata": _metadata([0]),
                        "virtual_brix": "14.0",
                    },
                    files=_images(1),
                )

        assert response.status_code == 200
        body = response.json()
        assert body["control_status"] == "SUCCEEDED"
        assert body["persistence_status"] == "SUCCEEDED"
        assert control.call_count == 1
        saved = persistence.final_values[0]
        if valid:
            assert body["inspection_status"] == "COMPLETED"
            assert body["decision_reason"] == "NORMAL"
            assert body["target_bin_code"] == "DEMO_BIN_02"
            assert body["inference_time_ms"] == payload["inference_time_ms"]
            assert float(saved["inference_time_ms"]) == payload["inference_time_ms"]
            assert not persistence.errors
        else:
            assert body["inspection_status"] == "REINSPECTION_REQUIRED"
            assert body["decision_reason"] == "INFERENCE_INVALID_RESPONSE"
            assert body["review_required"] is True
            assert body["exclude_from_normal_stats"] is True
            assert body["target_bin_code"] == "TEST_REINSPECTION_BIN"
            assert control.requests[0].target_bin_code == "TEST_REINSPECTION_BIN"
            assert body["inference_time_ms"] is None
            assert saved["inference_time_ms"] is None
            assert saved["exclude_from_normal_stats"] is True
            assert persistence.errors[0].error_code == "INFERENCE_INVALID_RESPONSE"

    asyncio.run(run())


def test_inspection_requires_at_least_one_image() -> None:
    with TestClient(_application()) as client:
        response = client.post(
            "/v1/inspections",
            data={"inspection_id": "inspection-001", "metadata": "[]"},
        )

    assert response.status_code == 422


def test_inspection_rejects_more_than_twelve_images() -> None:
    with TestClient(_application()) as client:
        response = _post(client, files=_images(13), metadata=_metadata(list(range(13))))

    assert response.status_code == 413


def test_inspection_rejects_mismatched_image_and_metadata_counts() -> None:
    with TestClient(_application()) as client:
        response = _post(client, files=_images(2), metadata=_metadata([0]))

    assert response.status_code == 422


def test_inspection_rejects_duplicate_view_indexes() -> None:
    with TestClient(_application()) as client:
        response = _post(client, files=_images(2), metadata=_metadata([0, 0]))

    assert response.status_code == 422


def test_inspection_rejects_view_indexes_out_of_order() -> None:
    with TestClient(_application()) as client:
        response = _post(client, files=_images(2), metadata=_metadata([1, 0]))

    assert response.status_code == 422


def test_inspection_rejects_unknown_angle_direction() -> None:
    with TestClient(_application()) as client:
        response = _post(
            client,
            files=_images(1),
            metadata=_metadata([0], angle_direction="side"),
        )

    assert response.status_code == 422


def test_inspection_rejects_invalid_metadata_json() -> None:
    with TestClient(_application()) as client:
        response = _post(client, files=_images(1), metadata="not-json")

    assert response.status_code == 422


def test_inspection_rejects_unsupported_image_content_type() -> None:
    with TestClient(_application()) as client:
        response = _post(
            client,
            files=_images(1, content_type="text/plain"),
            metadata=_metadata([0]),
        )

    assert response.status_code == 415


def test_inspection_rejects_request_over_configured_size_limit() -> None:
    settings = Settings(inference_max_request_bytes=256)
    with TestClient(_application(settings)) as client:
        response = _post(
            client,
            files=_images(1, content=b"x" * 512),
            metadata=_metadata([0]),
        )

    assert response.status_code == 413
