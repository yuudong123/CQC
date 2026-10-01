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
        snapshot, _ = self.resolve_for_inspection()
        return snapshot

    def resolve_for_inspection(
        self, *, skip_db: bool = False
    ) -> tuple[BinMappingSnapshot, bool]:
        """검사별 DB 사용 여부와 함께 완전한 snapshot을 반환한다."""

        # Serialize refreshes so older reads cannot overwrite newer snapshots.
        with self._refresh_lock:
            if skip_db:
                if self._snapshot is None:
                    raise BinMappingUnavailableError(
                        "사용 가능한 마지막 정상 bin mapping이 없습니다"
                    )
                return self._snapshot, False
            try:
                snapshot = self._repository.load_snapshot()
            except BinMappingUnavailableError:
                if self._snapshot is None:
                    raise
                return self._snapshot, False
            self._snapshot = snapshot
            return snapshot, True
