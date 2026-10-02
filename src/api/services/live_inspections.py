"""처리 중 검사 이미지 묶음의 미리보기를 메모리에서만 보관한다."""

from __future__ import annotations

import re
from dataclasses import dataclass
from threading import Lock
from time import monotonic

_JOB_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_PREVIEW_ID = re.compile(r"^[0-9a-f]{32}$")
_FRAME_ID = re.compile(r"^(?P<token>[0-9a-f]{32})_(?P<index>0[0-9]|1[01])$")


@dataclass(frozen=True)
class _LiveInspection:
    inspection_id: str
    images: tuple[tuple[bytes, str], ...]
    started_ms: int
    expires_at: float
    index: int


class LiveInspectionStore:
    """동시 검사 미리보기를 제한된 시간과 개수 동안 보관한다."""

    def __init__(self, *, limit: int, max_age_seconds: int) -> None:
        self._limit = limit
        self._max_age_seconds = max_age_seconds
        self._items: dict[str, _LiveInspection] = {}
        self._lock = Lock()
        self._next_index = 0

    def publish(
        self,
        token: str,
        *,
        inspection_id: str,
        images: list[tuple[bytes, str]],
        started_ms: int,
    ) -> bool:
        """유효한 검사 이미지 묶음을 게시한다. 한도 초과는 검사 흐름에 영향을 주지 않는다."""

        if (
            not _PREVIEW_ID.fullmatch(token)
            or not 1 <= len(images) <= 12
            or any(content_type not in {"image/png", "image/jpeg"} for _, content_type in images)
        ):
            return False
        with self._lock:
            self._prune_expired()
            if len(self._items) >= self._limit:
                return False
            index = self._next_index
            self._next_index += 1
            self._items[token] = _LiveInspection(
                inspection_id=inspection_id,
                images=tuple(images),
                started_ms=started_ms,
                expires_at=monotonic() + self._max_age_seconds,
                index=index,
            )
            return True

    def remove(self, token: str) -> None:
        """검사 완료·실패 시 해당 요청의 이미지 참조를 제거한다."""

        with self._lock:
            self._items.pop(token, None)

    def jobs(self) -> list[dict[str, object]]:
        """현재 처리 중인 검사만 공유 Job 계약으로 반환한다."""

        with self._lock:
            self._prune_expired()
            return [
                {
                    "id": (
                        item.inspection_id
                        if _JOB_ID.fullmatch(item.inspection_id)
                        else token
                    ),
                    "index": item.index,
                    "started": item.started_ms,
                    "finish": item.started_ms + self._max_age_seconds * 1000,
                    "faults": [],
                    "previewUrl": f"/api/quality/previews/live_{token}",
                    "previews": [
                        {
                            "index": index,
                            "previewUrl": f"/api/quality/previews/live_{token}_{index:02d}",
                        }
                        for index in range(len(item.images))
                    ],
                }
                for token, item in self._items.items()
            ]

    def read(self, token: str) -> tuple[bytes, str] | None:
        """검사가 활성 상태일 때만 이미지 bytes를 반환한다."""

        if _PREVIEW_ID.fullmatch(token):
            index = 0
        else:
            match = _FRAME_ID.fullmatch(token)
            if match is None:
                return None
            token = match.group("token")
            index = int(match.group("index"))
        with self._lock:
            self._prune_expired()
            item = self._items.get(token)
            return item.images[index] if item is not None and index < len(item.images) else None

    def clear(self) -> None:
        """애플리케이션 종료 시 모든 이미지 참조를 해제한다."""

        with self._lock:
            self._items.clear()

    def _prune_expired(self) -> None:
        now = monotonic()
        for token, item in tuple(self._items.items()):
            if item.expires_at <= now:
                del self._items[token]
