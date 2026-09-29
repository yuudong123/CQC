"""확정된 장애 이미지 파일만 별도 저장하는 내부 저장 계층.

장애 저장 trigger와 공개 조회·삭제 API는 아직 확정되지 않아 연결하지 않는다.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


@dataclass(frozen=True)
class FaultImage:
    """이미 읽은 요청 bytes와 선언된 이미지 형식."""

    content: bytes
    content_type: str


@dataclass(frozen=True)
class _StoredImage:
    path: Path
    metadata_path: Path
    created_at: datetime


@dataclass(frozen=True)
class FaultImageRecord:
    id: str
    inspection_id: str
    image_index: int
    created_at: datetime
    error_code: str
    content_type: str


_IMAGE_ID = re.compile(r"^([0-9a-f]{32})_([0-9]{2})$")


class FaultImageStorage:
    """파일 100장 기준으로 원자적 묶음 저장과 단일 프로세스 prune을 수행한다."""

    def __init__(self, root: Path, *, limit: int = 100) -> None:
        if limit < 1:
            raise ValueError("장애 이미지 보존 한도는 1 이상이어야 합니다")
        self._root = root
        self._limit = limit
        self._lock = Lock()

    def save(
        self,
        *,
        inspection_id: str,
        error_code: str,
        images: list[FaultImage],
        created_at: datetime | None = None,
    ) -> list[str]:
        """검사 이미지 묶음을 게시한 뒤 파일 수가 한도를 넘으면 오래된 순서로 정리한다."""

        if not 1 <= len(images) <= 12:
            raise ValueError("장애 이미지 묶음은 1~12장이어야 합니다")
        if len(images) > self._limit:
            raise ValueError("이미지 묶음은 보존 한도보다 클 수 없습니다")
        extensions = [_extension(image) for image in images]
        recorded_at = created_at or datetime.now(timezone.utc)
        if recorded_at.tzinfo is None:
            raise ValueError("created_at은 timezone 정보가 필요합니다")
        group_id = uuid4().hex
        image_ids = [f"{group_id}_{index:02d}" for index in range(len(images))]
        self._root.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix=".pending-", dir=self._root))
        try:
            for index, (image, extension) in enumerate(zip(images, extensions)):
                stem = f"image_{index:02d}"
                self._write_image(stage / f"{stem}.{extension}", image.content)
                (stage / f"{stem}.json").write_text(
                    json.dumps(
                        {
                            "id": image_ids[index],
                            "inspection_id": inspection_id,
                            "created_at": recorded_at.isoformat(
                                timespec="milliseconds"
                            ),
                            "error_code": error_code,
                            "image_index": index,
                            "content_type": image.content_type,
                        }
                    ),
                    encoding="utf-8",
                )
            with self._lock:
                stage.rename(self._root / group_id)
                self._prune_locked()
        finally:
            if stage.exists():
                shutil.rmtree(stage)
        return image_ids

    def count_files(self) -> int:
        """현재 게시된 장애 이미지 파일 수를 반환한다."""

        with self._lock:
            return len(self._stored_images_locked())

    def list_images(self) -> list[FaultImageRecord]:
        """Return committed images newest first, without exposing storage paths."""
        with self._lock:
            return [
                record
                for image in reversed(self._stored_images_locked())
                if (record := self._record(image)) is not None
            ]

    def read_image(self, image_id: str) -> tuple[bytes, str] | None:
        """Resolve a validated image ID within the storage root."""
        if _IMAGE_ID.fullmatch(image_id) is None:
            return None
        with self._lock:
            for image in self._stored_images_locked():
                record = self._record(image)
                if record is not None and record.id == image_id:
                    try:
                        return image.path.read_bytes(), record.content_type
                    except FileNotFoundError:
                        return None
        return None

    def delete_images(self, image_ids: list[str]) -> list[str]:
        """Delete only requested committed image IDs; missing IDs are no-ops."""
        with self._lock:
            # Capture targets under the same lock used by save and prune. A later
            # save cannot become part of this deletion snapshot.
            stored = {
                record.id: image
                for image in self._stored_images_locked(cleanup_orphans=False)
                if (record := self._record(image)) is not None
            }
            deleted: list[str] = []
            for image_id in dict.fromkeys(image_ids):
                image = stored.get(image_id)
                if image is None:
                    continue
                try:
                    self._delete_image(image)
                except OSError:
                    logger.exception("Fault image deletion failed: %s", image_id)
                    self._repair_partial_delete_locked(image)
                else:
                    deleted.append(image_id)
            return deleted

    @staticmethod
    def _repair_partial_delete_locked(image: _StoredImage) -> None:
        """Try once to remove only the requested image's orphaned counterpart."""
        try:
            if not image.path.exists():
                image.metadata_path.unlink(missing_ok=True)
            elif not image.metadata_path.exists():
                image.path.unlink(missing_ok=True)
            if not any(image.path.parent.iterdir()):
                image.path.parent.rmdir()
        except OSError:
            logger.exception("Fault image orphan cleanup failed: %s", image.path)

    @staticmethod
    def _record(image: _StoredImage) -> FaultImageRecord | None:
        try:
            data = json.loads(image.metadata_path.read_text(encoding="utf-8"))
            image_id = data["id"]
            match = _IMAGE_ID.fullmatch(image_id)
            if (
                match is None
                or match.group(1) != image.path.parent.name
                or image.path.stem != f"image_{match.group(2)}"
                or data["image_index"] != int(match.group(2))
                or data["content_type"]
                != ("image/png" if image.path.suffix == ".png" else "image/jpeg")
            ):
                return None
            created_at = datetime.fromisoformat(data["created_at"])
            if created_at.tzinfo is None:
                return None
            return FaultImageRecord(
                id=image_id,
                inspection_id=data["inspection_id"],
                image_index=data["image_index"],
                created_at=created_at,
                error_code=data["error_code"],
                content_type=data["content_type"],
            )
        except (OSError, ValueError, KeyError, TypeError):
            return None

    @staticmethod
    def _write_image(path: Path, content: bytes) -> None:
        path.write_bytes(content)

    def _stored_images_locked(
        self, *, cleanup_orphans: bool = True
    ) -> list[_StoredImage]:
        stored: list[_StoredImage] = []
        if not self._root.exists():
            return stored
        for group in self._root.iterdir():
            if group.is_symlink() or not group.is_dir() or group.name.startswith("."):
                continue
            try:
                if UUID(group.name).version != 4:
                    continue
            except ValueError:
                continue
            if cleanup_orphans:
                for metadata_path in group.glob("image_*.json"):
                    if metadata_path.is_symlink():
                        continue
                    if not any(
                        (group / f"{metadata_path.stem}{extension}").is_file()
                        for extension in (".jpg", ".png")
                    ):
                        metadata_path.unlink(missing_ok=True)
            for path in group.iterdir():
                if path.is_symlink() or path.suffix not in {".jpg", ".png"}:
                    continue
                if not path.stem.startswith("image_"):
                    continue
                metadata_path = path.with_suffix(".json")
                if metadata_path.is_symlink() or not metadata_path.is_file():
                    if cleanup_orphans:
                        path.unlink(missing_ok=True)
                    continue
                try:
                    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                    created_at = datetime.fromisoformat(metadata["created_at"])
                    if created_at.tzinfo is None:
                        raise ValueError("timezone 없는 장애 이미지 시각")
                except (OSError, ValueError, KeyError, TypeError):
                    if cleanup_orphans:
                        logger.warning("Invalid fault image metadata removed: %s", path)
                        path.unlink(missing_ok=True)
                        metadata_path.unlink(missing_ok=True)
                    continue
                image = _StoredImage(path, metadata_path, created_at)
                if self._record(image) is None:
                    if cleanup_orphans:
                        path.unlink(missing_ok=True)
                        metadata_path.unlink(missing_ok=True)
                    continue
                stored.append(image)
            if cleanup_orphans and not any(group.iterdir()):
                group.rmdir()
        return sorted(stored, key=lambda item: (item.created_at, str(item.path)))

    def _prune_locked(self) -> None:
        images = self._stored_images_locked()
        for image in images[: max(0, len(images) - self._limit)]:
            try:
                self._delete_image(image)
            except OSError:
                # 삭제 실패는 기록하되 이미지 보존 때문에 검사 결과를 바꾸지 않는다.
                logger.exception(
                    "오래된 장애 이미지 삭제에 실패했습니다: %s", image.path
                )
                break

    @staticmethod
    def _delete_image(image: _StoredImage) -> None:
        image.path.unlink()
        image.metadata_path.unlink(missing_ok=True)
        if not any(image.path.parent.iterdir()):
            image.path.parent.rmdir()


def _extension(image: FaultImage) -> str:
    if image.content_type == "image/png" and image.content.startswith(_PNG_SIGNATURE):
        return "png"
    if image.content_type == "image/jpeg" and image.content.startswith(b"\xff\xd8\xff"):
        return "jpg"
    raise ValueError("장애 이미지는 Content-Type과 내용이 일치하는 PNG/JPEG여야 합니다")
