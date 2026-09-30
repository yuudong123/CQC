"""Simulator 프로세스가 단독 소유하는 제어 상태와 revision."""

from __future__ import annotations

from dataclasses import dataclass, replace
from threading import Lock

from .schemas import FaultScope, FaultType, SimulatorSettingsUpdate


@dataclass(frozen=True, slots=True)
class SimulatorRuntimeState:
    """프로세스 내부의 불변 Simulator 설정 snapshot."""

    revision: int = 0
    running: bool = False
    concurrency: int = 1
    faults: tuple[FaultType, ...] = ()
    scope: FaultScope = "ALL"


class RevisionMismatchError(ValueError):
    """요청 revision이 현재 Simulator 설정과 다를 때 발생한다."""

    def __init__(self, expected: int, current: int) -> None:
        super().__init__(f"Expected revision {expected}, current revision {current}")
        self.expected = expected
        self.current = current


class SimulatorStateService:
    """Simulator 프로세스 안에서 상태 변경과 NEXT claim을 원자 적용한다."""

    def __init__(self) -> None:
        self._state = SimulatorRuntimeState()
        self._lock = Lock()

    def get_state(self) -> SimulatorRuntimeState:
        """불변 snapshot을 반환한다."""

        with self._lock:
            return self._state

    def start_on_boot(self) -> SimulatorRuntimeState:
        """초기 자동 실행은 사용자 설정 변경이 아니므로 revision 0을 유지한다."""

        with self._lock:
            self._state = replace(self._state, running=True)
            return self._state

    def update_state(self, update: SimulatorSettingsUpdate) -> SimulatorRuntimeState:
        """revision을 비교한 뒤 모든 변경을 한 번에 적용한다."""

        changes = update.model_dump(exclude_unset=True, exclude={"expected_revision"})
        if "faults" in changes:
            changes["faults"] = tuple(changes["faults"])
        with self._lock:
            if update.expected_revision != self._state.revision:
                raise RevisionMismatchError(
                    update.expected_revision, self._state.revision
                )
            self._state = replace(
                self._state, **changes, revision=self._state.revision + 1
            )
            return self._state

    def claim_faults_for_inspection(self) -> tuple[FaultType, ...]:
        """새 Simulator 검사 1건에 적용할 장애를 원자적으로 가져온다.

        NEXT는 첫 검사에서만 비우고, FE 참조 구현처럼 scope는 유지한다.
        일반 Backend 검사 요청은 이 메서드를 호출하지 않는다.
        """

        with self._lock:
            faults = self._state.faults
            if faults and self._state.scope == "NEXT":
                self._state = replace(
                    self._state, faults=(), revision=self._state.revision + 1
                )
            return faults

    def force_stop(self) -> SimulatorRuntimeState:
        """실행 루프가 예상치 못하게 종료되면 공개 실행 상태를 정리한다."""

        with self._lock:
            if self._state.running:
                self._state = replace(
                    self._state, running=False, revision=self._state.revision + 1
                )
            return self._state
