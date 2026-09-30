"""오판 의심 검수의 공유 HTTP 계약."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from src.api.core.config import Settings
from src.api.main import create_app


class _ReviewRepository:
    def __init__(self) -> None:
        self.values: dict[str, str] = {"inspection-1": "NONE"}
        self.fail = False

    def set_misclassification(self, inspection_id: str, value: str) -> bool:
        if self.fail:
            raise SQLAlchemyError("DB unavailable")
        if inspection_id not in self.values:
            return False
        self.values[inspection_id] = value
        return True


def test_review_set_clear_missing_and_db_failure() -> None:
    app = create_app(Settings())
    repository = _ReviewRepository()
    app.state.inspection_review_repository = repository
    with TestClient(app) as client:
        marked = client.patch(
            "/v1/quality/inspections/inspection-1/review",
            json={"misclassification": "QUALITY_SUSPECT"},
        )
        assert marked.status_code == 200
        assert marked.json() == {
            "inspectionId": "inspection-1",
            "misclassification": "QUALITY_SUSPECT",
        }
        assert marked.headers["cache-control"] == "no-store"
        cleared = client.patch(
            "/v1/quality/inspections/inspection-1/review",
            json={"misclassification": "NONE"},
        )
        assert cleared.status_code == 200
        assert repository.values["inspection-1"] == "NONE"
        missing = client.patch(
            "/v1/quality/inspections/unknown/review",
            json={"misclassification": "OTHER"},
        )
        assert missing.status_code == 404
        assert missing.json() == {"code": "INSPECTION_EXPIRED"}
        invalid = client.patch(
            "/v1/quality/inspections/inspection-1/review",
            json={"misclassification": "OTHER", "extra": True},
        )
        assert invalid.status_code == 422
        assert invalid.json() == {"code": "INVALID_REVIEW"}
        repository.fail = True
        unavailable = client.patch(
            "/v1/quality/inspections/inspection-1/review",
            json={"misclassification": "OTHER"},
        )
        assert unavailable.status_code == 503
        assert unavailable.json() == {"code": "DB_UNAVAILABLE"}


def test_review_openapi_matches_shared_contract() -> None:
    contract = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "docs/contracts/quality-operations.openapi.json"
        ).read_text(encoding="utf-8")
    )
    actual = create_app(Settings()).openapi()
    endpoint = actual["paths"]["/v1/quality/inspections/{id}/review"]["patch"]
    shared = contract["paths"]["/inspections/{id}/review"]["patch"]
    assert set(endpoint["responses"]) == set(shared["responses"])
    assert (
        endpoint["parameters"][0]["schema"]["pattern"]
        == shared["parameters"][0]["schema"]["pattern"]
    )
    assert endpoint["parameters"][0]["schema"]["maxLength"] == 64
