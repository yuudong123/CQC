import asyncio

import httpx

from src.api.clients.inference import HttpInferenceClient
from src.api.schemas.inference import InferenceRequest
from src.api.schemas.inspections import InspectionImageMetadata


def test_http_client_sends_multipart_and_validates_response() -> None:
    png = b"\x89PNG\r\n\x1a\nexample"

    def respond(request: httpx.Request) -> httpx.Response:
        body = request.read()
        assert request.url.path == "/v1/predict"
        assert b'name="inspection_id"' in body
        assert b"inspection-1" in body
        assert b'filename="view-0.png"' in body
        assert b"image/png" in body
        assert b"\"view_index\": 0" in body
        return httpx.Response(200, json={
            "inspection_id": "inspection-1", "crop_type": "apple",
            "predicted_cultivar": "fuji", "cultivar_confidence": 0.9,
            "cultivar_probabilities": {"fuji": 0.9, "yanggwang": 0.1},
            "predicted_grade": "L", "quality_confidence": 0.8,
            "quality_probabilities": {"L": 0.8, "M": 0.1, "S": 0.1},
            "inference_time_ms": 100, "model_name": "real-model",
            "model_version": "v2", "preprocessing_version": "rgb-v1",
            "used_frame_count": 1,
        })

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as transport:
            client = HttpInferenceClient("http://inference:8001/v1/predict", client=transport)
            result = await client.predict(InferenceRequest(
                inspection_id="inspection-1", images=[png],
                metadata=[InspectionImageMetadata(view_index=0, angle_direction="top",
                    verticality_angle=0, horizontality_angle=0)],
            ))
            assert result.model_version == "v2"

    asyncio.run(run())
