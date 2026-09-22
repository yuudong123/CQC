from __future__ import annotations

import io
import json
import unittest

from fastapi.testclient import TestClient
from PIL import Image

from src.inference.api import create_app
from src.inference.predictor import Prediction


class _FakePredictor:
    def health(self) -> dict[str, object]:
        return {
            "status": "ready",
            "model_loaded": True,
            "model_name": "fake",
            "model_version": "test-v1",
            "device": "cpu",
            "views": 4,
        }

    def predict(self, images: list[bytes]) -> Prediction:
        if not images:
            raise ValueError("이미지는 1장 이상 필요합니다")
        return Prediction(
            crop_type="apple",
            predicted_cultivar="fuji",
            cultivar_confidence=0.9,
            cultivar_probabilities={"fuji": 0.9, "yanggwang": 0.1},
            predicted_grade="L",
            quality_confidence=0.8,
            quality_probabilities={"L": 0.8, "M": 0.1, "S": 0.1},
            inference_time_ms=10.0,
            model_name="fake",
            model_version="test-v1",
            preprocessing_version="rgb-resize-imagenet-v1",
            used_frame_count=len(images),
        )


def _png() -> bytes:
    stream = io.BytesIO()
    Image.new("RGB", (8, 8), (1, 2, 3)).save(stream, format="PNG")
    return stream.getvalue()


class InferenceApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(create_app(_FakePredictor()))

    def test_health_reports_ready(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ready")

    def test_predict_accepts_repeated_image_fields(self) -> None:
        response = self.client.post(
            "/v1/predict",
            data={
                "inspection_id": "inspection-001",
                "metadata": json.dumps(
                    [
                        {"view_index": 0, "angle_direction": "top", "verticality_angle": 0, "horizontality_angle": 0},
                        {"view_index": 1, "angle_direction": "bottom", "verticality_angle": 0, "horizontality_angle": 180},
                    ]
                ),
            },
            files=[
                ("images", ("front.png", _png(), "image/png")),
                ("images", ("back.png", _png(), "image/png")),
            ],
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["predicted_cultivar"], "fuji")
        self.assertEqual(response.json()["predicted_grade"], "L")
        self.assertEqual(response.json()["inspection_id"], "inspection-001")
        self.assertEqual(response.json()["used_frame_count"], 2)

    def test_predict_rejects_unsupported_content_type(self) -> None:
        response = self.client.post(
            "/v1/predict",
            data={"inspection_id": "inspection-002", "metadata": json.dumps([{"view_index": 0, "angle_direction": "top", "verticality_angle": 0, "horizontality_angle": 0}])},
            files=[("images", ("note.txt", b"not-an-image", "text/plain"))],
        )
        self.assertEqual(response.status_code, 415)

    def test_predict_rejects_more_files_than_model_views(self) -> None:
        response = self.client.post(
            "/v1/predict",
            data={
                "inspection_id": "inspection-003",
                "metadata": json.dumps(
                    [
                        {"view_index": index, "angle_direction": "top", "verticality_angle": 0, "horizontality_angle": index * 10}
                        for index in range(5)
                    ]
                ),
            },
            files=[
                ("images", (f"{index}.png", _png(), "image/png"))
                for index in range(5)
            ],
        )
        self.assertEqual(response.status_code, 413)
        self.assertIn("최대 4장", response.json()["detail"])

    def test_predict_rejects_metadata_count_mismatch(self) -> None:
        response = self.client.post(
            "/v1/predict",
            data={"inspection_id": "inspection-004", "metadata": "[]"},
            files=[("images", ("front.png", _png(), "image/png"))],
        )
        self.assertEqual(response.status_code, 422)
        self.assertIn("항목 수", response.json()["detail"])

    def test_openapi_contains_typed_prediction_contract(self) -> None:
        schema = self.client.app.openapi()
        response = schema["paths"]["/v1/predict"]["post"]["responses"]["200"]
        reference = response["content"]["application/json"]["schema"]["$ref"]
        self.assertEqual(reference, "#/components/schemas/PredictionResponse")


if __name__ == "__main__":
    unittest.main()
