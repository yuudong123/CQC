"""Process-local last known good bin mapping for temporary DB outages."""

from __future__ import annotations

from threading import Lock

from ..repositories.bin_mappings import (
    BinMappingRepository,
    BinMappingSnapshot,
    BinMappingUnavailableError,
)


class LkgBinMapping:
    """Publish only complete snapshots; fall back only when DB access fails."""

    def __init__(self, repository: BinMappingRepository) -> None:
        self._repository = repository
        self._snapshot: BinMappingSnapshot | None = None
        self._refresh_lock = Lock()

    def resolve(self) -> BinMappingSnapshot:
        # Serialize refreshes so older reads cannot overwrite newer snapshots.
        with self._refresh_lock:
            try:
                snapshot = self._repository.load_snapshot()
            except BinMappingUnavailableError:
                if self._snapshot is None:
                    raise
                return self._snapshot
            self._snapshot = snapshot
            return snapshot
