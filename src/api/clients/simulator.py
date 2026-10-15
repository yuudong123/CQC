"""Backend에서 독립 Simulator 내부 API를 호출하는 공유 HTTP client."""

from __future__ import annotations

import httpx
from pydantic import ValidationError

from src.simulator.schemas import SimulatorSettingsUpdate, SimulatorStatus


class SimulatorUnavailable(RuntimeError):
    """Simulator와 통신하거나 내부 상태를 해석할 수 없을 때 발생한다."""


class SimulatorRevisionConflict(RuntimeError):
    """Simulator가 expectedRevision을 거부했을 때 발생한다."""


class SimulatorClient:
    """한 AsyncClient를 재사용하며 Simulator 상태를 조회·변경한다."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout_ms: int = 30_000,
        state_timeout_ms: int = 1_500,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._state_timeout = state_timeout_ms / 1000
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_ms / 1000, connect=2.0)
        )
        self._owns_client = client is None

    async def get_status(self) -> SimulatorStatus:
        try:
            response = await self._client.get(
                f"{self._base_url}/state", timeout=self._state_timeout
            )
            response.raise_for_status()
            return SimulatorStatus.model_validate(response.json())
        except (httpx.HTTPError, ValueError, ValidationError) as exc:
            raise SimulatorUnavailable("Simulator 상태 조회 실패") from exc

    async def update(self, update: SimulatorSettingsUpdate) -> SimulatorStatus:
        try:
            response = await self._client.put(
                f"{self._base_url}/state",
                json=update.model_dump(by_alias=True, exclude_unset=True),
            )
            if response.status_code == 409:
                raise SimulatorRevisionConflict("Simulator revision 충돌")
            response.raise_for_status()
            return SimulatorStatus.model_validate(response.json())
        except SimulatorRevisionConflict:
            raise
        except (httpx.HTTPError, ValueError, ValidationError) as exc:
            raise SimulatorUnavailable("Simulator 제어 실패") from exc

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()
