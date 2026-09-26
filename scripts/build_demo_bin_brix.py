"""Join the existing demo bundle index to fixed, simulated Brix values."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--demo-root",
        type=Path,
        default=Path("data/processed/realtime-apple-arrival-demo"),
    )
    parser.add_argument(
        "--virtual-brix", type=Path, default=Path("data/processed/virtual-brix.csv")
    )
    args = parser.parse_args()
    output = args.demo_root / "demo-virtual-brix.csv"
    if output.exists():
        parser.error(f"Refusing to overwrite {output}")

    index = json.loads((args.demo_root / "index.json").read_text(encoding="utf-8"))
    with args.virtual_brix.open(newline="", encoding="utf-8-sig") as stream:
        by_group = {row["group_no"]: row for row in csv.DictReader(stream)}
    if len(by_group) == 0 or len({item["inspection_id"] for item in index}) != len(
        index
    ):
        raise ValueError("Missing Brix source or duplicate demo bundle ID")

    rows = []
    for item in index:
        source = by_group[item["source_group_id"]]
        if source["brix_is_measured"].lower() != "false":
            raise ValueError("Demo Brix must be explicitly marked unmeasured")
        value = float(source["virtual_brix"])
        if not 9 <= value <= 18:
            raise ValueError("Virtual Brix outside 9..18")
        rows.append(
            {
                "demo_bundle_id": item["inspection_id"],
                "virtual_brix": f"{value:.1f}",
                "sweetness_band": "sweet" if value >= 12.0 else "less_sweet",
                "brix_source": source["brix_source"],
                "brix_is_measured": "false",
                "brix_generator_version": source["brix_generator_version"],
            }
        )
    with output.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(
        f"demo_brix={output} bundles={len(rows)} less_sweet={sum(row['sweetness_band'] == 'less_sweet' for row in rows)}"
    )


if __name__ == "__main__":
    main()
