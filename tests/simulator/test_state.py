"""BE-07 1/3 Simulator 설정과 revision의 단일 프로세스 계약."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from pathlib import Path
from threading import Barrier

import pytest
from pydantic import ValidationError

from src.api.core.config import Settings
from src.api.main import create_app
from src.simulator.config import SimulatorSettings
from src.simulator.main import create_app as create_simulator_app
from src.simulator.state import (
    RevisionMismatchError,
    SimulatorSettingsUpdate,
    SimulatorStateService,
)


def _update(revision: int, **changes: object) -> SimulatorSettingsUpdate:
    return SimulatorSettingsUpdate.model_validate(
        {"expectedRevision": revision, **changes}
    )


def test_initial_state_is_stopped_and_has_no_fake_position() -> None:
    state = SimulatorStateService().get_state()
    assert state.revision == 0
    assert state.running is False
    assert state.concurrency == 1
    assert state.faults == ()
    assert state.scope == "ALL"
    assert not hasattr(state, "sequence")
    assert not hasattr(state, "tick")
    assert not hasattr(state, "position")


def test_updates_increment_revision_and_stale_revision_preserves_state() -> None:
    service = SimulatorStateService()
    original = service.get_state()
    first = service.update_state(_update(0, running=True, concurrency=4))
    assert first.revision == 1
    assert first.running is True
    assert first.concurrency == 4
    second = service.update_state(
        _update(1, faults=["INFERENCE_TIMEOUT"], scope="NEXT")
    )
    assert second.revision == 2
    assert second.faults == ("INFERENCE_TIMEOUT",)
    assert second.scope == "NEXT"
    with pytest.raises(RevisionMismatchError) as error:
        service.update_state(_update(1, running=False))
    assert (error.value.expected, error.value.current) == (1, 2)
    assert service.get_state() == second
    assert original.revision == 0
    assert original.running is False


def test_simultaneous_updates_with_same_revision_have_one_winner() -> None:
    service = SimulatorStateService()
    barrier = Barrier(2)

    def change(running: bool) -> str:
        barrier.wait()
        try:
            service.update_state(_update(0, running=running))
        except RevisionMismatchError:
            return "conflict"
        return "success"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(change, (True, False)))
    assert sorted(outcomes) == ["conflict", "success"]
    assert service.get_state().revision == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"concurrency": 0},
        {"concurrency": 65},
        {"concurrency": True},
        {"concurrency": 1.5},
        {"running": 1},
        {"scope": "OFF"},
        {"faults": ["NONE"]},
        {"faults": ["DB_ERROR", "DB_ERROR"]},
        {"faults": ["DB_ERROR"] * 6},
        {"faults": None},
        {"sequence": 1},
    ],
)
def test_invalid_settings_are_rejected(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        _update(0, **changes)


def test_snapshot_is_immutable_and_only_simulator_owns_runtime_service() -> None:
    app = create_simulator_app(
        SimulatorSettings(
            simulator_dataset_root=Path("."),
            simulator_position_path=Path("position.json"),
            simulator_backend_url="http://backend",
            simulator_fault_token="test-token",
        )
    )
    service = app.state.simulator_state_service
    state = service.get_state()
    with pytest.raises(FrozenInstanceError):
        state.running = True  # type: ignore[misc]
    assert service.get_state().running is False
    assert "put" in app.openapi()["paths"]["/state"]
    backend = create_app(Settings())
    assert not hasattr(backend.state, "simulator_state_service")
    assert not hasattr(backend.state, "simulator_runner")
