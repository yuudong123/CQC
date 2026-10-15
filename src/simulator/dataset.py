"""이미 선정된 시연 묶음과 가상 당도를 읽는다."""

from __future__ import annotations

import csv
import json
import mimetypes
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from ..api.schemas.inspections import InspectionMetadata


class SimulatorDatasetError(ValueError):
    """시연 자료가 계약을 만족하지 않을 때 발생한다."""


@dataclass(frozen=True)
class SimulatorBundle:
    bundle_id: str
    images: tuple[tuple[str, bytes, str], ...]
    metadata_json: str
    virtual_brix: str


class SimulatorDataset:
    """index.json의 기본 재생 묶음을 기록된 순서 그대로 순환한다."""

    def __init__(
        self, root: Path, max_bytes: int, brix_csv_path: Path | None = None
    ) -> None:
        self.root = root.resolve(strict=True)
        self.max_bytes = max_bytes
        csv_path = brix_csv_path or self.root / "demo-virtual-brix.csv"
        try:
            index = json.loads((self.root / "index.json").read_text(encoding="utf-8"))
            with csv_path.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
        except (OSError, ValueError) as exc:
            raise SimulatorDatasetError(
                "시연 index 또는 가상 당도 CSV를 읽을 수 없습니다"
            ) from exc
        if not isinstance(index, list):
            raise SimulatorDatasetError("index.json은 배열이어야 합니다")
        brix: dict[str, str] = {}
        for row in rows:
            bundle_id = row.get("demo_bundle_id", "")
            try:
                value = float(row["virtual_brix"])
            except (KeyError, TypeError, ValueError) as exc:
                raise SimulatorDatasetError(
                    "가상 당도 CSV 값이 잘못되었습니다"
                ) from exc
            if not bundle_id or bundle_id in brix or not 9 <= value <= 18:
                raise SimulatorDatasetError(
                    "가상 당도 CSV의 ID 또는 범위가 잘못되었습니다"
                )
            brix[bundle_id] = row["virtual_brix"]
        entries: list[tuple[str, Path]] = []
        seen: set[str] = set()
        for item in index:
            if not isinstance(item, dict) or not item.get("default_playback"):
                continue
            bundle_id, relative = item.get("inspection_id"), item.get("path")
            if not isinstance(bundle_id, str) or not isinstance(relative, str):
                raise SimulatorDatasetError("기본 재생 묶음의 ID 또는 경로가 없습니다")
            if (
                bundle_id in seen
                or bundle_id not in brix
                or item.get("frame_count") != 12
            ):
                raise SimulatorDatasetError(
                    "기본 재생 묶음의 ID·당도·12장 구성이 잘못되었습니다"
                )
            path = (self.root / relative).resolve()
            if self.root not in path.parents or path.parent.name != "groups":
                raise SimulatorDatasetError(
                    "기본 재생 묶음 경로가 허용 범위를 벗어났습니다"
                )
            entries.append((bundle_id, path))
            seen.add(bundle_id)
        if not entries:
            raise SimulatorDatasetError("기본 재생 가능한 12장 묶음이 없습니다")
        self.entries = tuple(entries)
        self.brix = brix

    def __len__(self) -> int:
        return len(self.entries)

    def bundle_id(self, position: int) -> str:
        return self.entries[position % len(self.entries)][0]

    def load(self, position: int) -> SimulatorBundle:
        """request.json의 이미지 순서와 metadata를 검증해 그대로 준비한다."""

        bundle_id, directory = self.entries[position % len(self.entries)]
        try:
            request = json.loads(
                (directory / "request.json").read_text(encoding="utf-8")
            )
            names = request["images"]
            metadata = InspectionMetadata.model_validate(request["metadata"]).root
        except (OSError, ValueError, KeyError, TypeError, ValidationError) as exc:
            raise SimulatorDatasetError(
                f"묶음 요청을 읽을 수 없습니다: {bundle_id}"
            ) from exc
        if request.get("inspection_id") != bundle_id or not isinstance(names, list):
            raise SimulatorDatasetError(
                f"묶음 ID 또는 이미지 목록이 잘못되었습니다: {bundle_id}"
            )
        if len(names) != 12 or len(names) != len(metadata):
            raise SimulatorDatasetError(
                f"이미지와 metadata 수가 잘못되었습니다: {bundle_id}"
            )
        if [item.view_index for item in metadata] != list(range(len(names))):
            raise SimulatorDatasetError(
                f"view_index 순서가 잘못되었습니다: {bundle_id}"
            )
        images: list[tuple[str, bytes, str]] = []
        total = 0
        for name in names:
            if not isinstance(name, str) or Path(name).name != name:
                raise SimulatorDatasetError(
                    f"이미지 경로가 잘못되었습니다: {bundle_id}"
                )
            mime = mimetypes.guess_type(name)[0]
            if mime not in ("image/png", "image/jpeg"):
                raise SimulatorDatasetError(
                    f"이미지 형식이 잘못되었습니다: {bundle_id}"
                )
            try:
                content = (directory / name).read_bytes()
            except OSError as exc:
                raise SimulatorDatasetError(
                    f"이미지가 없습니다: {bundle_id}/{name}"
                ) from exc
            total += len(content)
            if total > self.max_bytes:
                raise SimulatorDatasetError(
                    f"이미지 합계가 제한을 초과했습니다: {bundle_id}"
                )
            images.append((name, content, mime))
        return SimulatorBundle(
            bundle_id=bundle_id,
            images=tuple(images),
            metadata_json=json.dumps([item.model_dump() for item in metadata]),
            virtual_brix=self.brix[bundle_id],
        )
