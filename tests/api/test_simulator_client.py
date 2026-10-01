"""Backend의 Simulator 내부 HTTP client 계약."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from src.api.clients.simulator import (
    SimulatorClient,
    SimulatorRevisionConflict,
    SimulatorUnavailable,
)
from src.simulator.schemas import SimulatorSettingsUpdate


def _status(revision: int = 1) -> dict[str, object]:
    return {
        "revision": revision,
        "running": True,
        "concurrency": 2,
        "intervalMs": 2000,
        "faults": [],
        "scope": "ALL",
        "status": "healthy",
        "lastSeenAt": None,
    }


def test_client_uses_internal_state_api_and_shared_transport() -> None:
    async def exercise() -> None:
        seen: list[httpx.Request] = []

        async def respond(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(200, json=_status())

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(respond)
        ) as transport:
            client = SimulatorClient("http://simulator:8002", client=transport)
            state = await client.get_status()
            changed = await client.update(
                SimulatorSettingsUpdate(expectedRevision=0, running=True, concurrency=2)
            )
            assert state.revision == changed.revision == 1
            assert [item.method for item in seen] == ["GET", "PUT"]
            assert all(item.url.path == "/state" for item in seen)
            assert b'"expectedRevision":0' in seen[1].content
            assert b'"concurrency":2' in seen[1].content
            assert seen[0].extensions["timeout"]["read"] == 1.5
            assert seen[1].extensions["timeout"]["read"] != 1.5

    asyncio.run(exercise())


def test_client_maps_conflict_unavailable_and_invalid_payload() -> None:
    async def exercise() -> None:
        responses = [
            httpx.Response(409, json={"code": "REVISION_CONFLICT"}),
            httpx.Response(503, json={"code": "SIMULATOR_DATASET_UNAVAILABLE"}),
            httpx.Response(200, json={"revision": "bad"}),
        ]

        async def respond(_: httpx.Request) -> httpx.Response:
            return responses.pop(0)

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(respond)
        ) as transport:
            client = SimulatorClient("http://simulator:8002", client=transport)
            update = SimulatorSettingsUpdate(expectedRevision=0, running=True)
            with pytest.raises(SimulatorRevisionConflict):
                await client.update(update)
            with pytest.raises(SimulatorUnavailable):
                await client.update(update)
            with pytest.raises(SimulatorUnavailable):
                await client.get_status()

    asyncio.run(exercise())


def test_state_timeout_is_separate_and_unavailable_is_reported() -> None:
    async def exercise() -> None:
        def respond(request: httpx.Request) -> httpx.Response:
            assert request.extensions["timeout"]["read"] == 0.2
            raise httpx.ReadTimeout("state hung", request=request)

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(respond)
        ) as transport:
            client = SimulatorClient(
                "http://simulator:8002", state_timeout_ms=200, client=transport
            )
            with pytest.raises(SimulatorUnavailable):
                await client.get_status()

    asyncio.run(exercise())
