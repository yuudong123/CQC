from __future__ import annotations

import io
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
            files=[
                ("images", ("front.png", _png(), "image/png")),
                ("images", ("back.png", _png(), "image/png")),
            ],
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["predicted_cultivar"], "fuji")
        self.assertEqual(response.json()["predicted_grade"], "L")

    def test_predict_rejects_unsupported_content_type(self) -> None:
        response = self.client.post(
            "/v1/predict",
            files=[("images", ("note.txt", b"not-an-image", "text/plain"))],
        )
        self.assertEqual(response.status_code, 415)

    def test_openapi_contains_typed_prediction_contract(self) -> None:
        schema = self.client.app.openapi()
        response = schema["paths"]["/v1/predict"]["post"]["responses"]["200"]
        reference = response["content"]["application/json"]["schema"]["$ref"]
        self.assertEqual(reference, "#/components/schemas/PredictionResponse")


if __name__ == "__main__":
    unittest.main()
