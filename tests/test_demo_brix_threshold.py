"""데이터 연결 노트북과 API가 같은 14 Brix 경계를 사용하는지 검증한다."""

import csv
import json
from pathlib import Path

import pytest

from src.api.services.bin_policy import DEMO_SWEETNESS_THRESHOLD_BRIX


def test_notebook_brix_boundary_and_metadata(tmp_path: Path) -> None:
    notebook_path = (
        Path(__file__).resolve().parents[1] / "notebooks/05_demo_bundles.ipynb"
    )
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    namespace = {"Path": Path, "csv": csv, "json": json}
    source = next(
        "".join(cell["source"])
        for cell in notebook["cells"]
        if "".join(cell.get("source", [])).startswith("def attach_demo_brix(")
    )
    # 저장소의 고정된 생성 함수만 실행하며 학습·서버 실행 셀은 제외한다.
    exec(compile(source, str(notebook_path), "exec"), namespace)  # noqa: S102
    values = [9.0, 12.0, 13.9, 14.0, 18.0]
    index = [
        {"inspection_id": f"demo-{i}", "source_group_id": str(i)}
        for i in range(len(values))
    ]
    (tmp_path / "index.json").write_text(json.dumps(index), encoding="utf-8")
    source_path = tmp_path / "source.csv"
    with source_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "group_no",
                "virtual_brix",
                "brix_is_measured",
                "brix_source",
                "brix_generator_version",
            ],
        )
        writer.writeheader()
        for i, value in enumerate(values):
            writer.writerow(
                {
                    "group_no": str(i),
                    "virtual_brix": value,
                    "brix_is_measured": "false",
                    "brix_source": "test-simulation",
                    "brix_generator_version": "test-v1",
                }
            )
    attach = namespace["attach_demo_brix"]
    attach(demo_root=tmp_path, virtual_brix=source_path)
    with (tmp_path / "demo-virtual-brix.csv").open(
        newline="", encoding="utf-8"
    ) as stream:
        rows = list(csv.DictReader(stream))
    assert DEMO_SWEETNESS_THRESHOLD_BRIX == 14.0
    assert [row["sweetness_band"] for row in rows] == [
        "less_sweet",
        "less_sweet",
        "less_sweet",
        "sweet",
        "sweet",
    ]
    assert [float(row["virtual_brix"]) for row in rows] == values
    assert all(row["brix_is_measured"] == "false" for row in rows)
    assert all(row["brix_generator_version"] == "test-v1" for row in rows)
    with pytest.raises(ValueError, match="Refusing to overwrite"):
        attach(demo_root=tmp_path, virtual_brix=source_path)
