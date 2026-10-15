"""Simulator의 다음 재생 위치를 작은 JSON 파일에 보존한다."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

from .dataset import SimulatorDataset


class SimulatorPositionError(ValueError):
    """저장된 재생 위치를 안전하게 복구할 수 없을 때 발생한다."""


class SimulatorPositionStore:
    """완료된 연속 묶음 다음의 절대 순번을 원자적으로 저장한다."""

    def __init__(self, path: Path, dataset: SimulatorDataset) -> None:
        self.path = path
        ids = [bundle_id for bundle_id, _ in dataset.entries]
        self.dataset_id = hashlib.sha256(
            json.dumps(ids, ensure_ascii=False).encode("utf-8")
        ).hexdigest()

    def load(self) -> int:
        if not self.path.exists():
            return 0
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise SimulatorPositionError(
                "Simulator 위치 파일을 읽을 수 없습니다"
            ) from exc
        if (
            not isinstance(data, dict)
            or data.get("dataset_id") != self.dataset_id
            or type(data.get("next_position")) is not int
            or data["next_position"] < 0
        ):
            raise SimulatorPositionError(
                "Simulator 위치 파일이 현재 dataset과 맞지 않습니다"
            )
        return data["next_position"]

    def save(self, next_position: int) -> None:
        """같은 디렉터리의 임시 파일을 fsync한 후 원자 교체한다."""

        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.path.parent, delete=False
            ) as handle:
                temporary = Path(handle.name)
                json.dump(
                    {"dataset_id": self.dataset_id, "next_position": next_position},
                    handle,
                )
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
