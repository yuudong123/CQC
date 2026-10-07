"""Collect read-only deployment provenance and historical QA timing evidence."""

from __future__ import annotations

import argparse
import json
import re
import statistics
import subprocess
from datetime import datetime, timedelta, timezone
from itertools import pairwise
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KST = timezone(timedelta(hours=9))


def docker(*args: str, input_text: str | None = None) -> str:
    return subprocess.check_output(
        ["docker", *args], input=input_text, text=True, encoding="utf-8", timeout=40
    ).strip()


def metrics(values: list[float]) -> dict:
    return {
        "count": len(values),
        "median_seconds": statistics.median(values),
        "p90_seconds": statistics.quantiles(values, n=10, method="inclusive")[8],
        "max_seconds": max(values),
        "over_2_2_seconds": sum(value > 2.2 for value in values),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--build", type=int, default=115)
    args = parser.parse_args()
    if args.build < 1:
        parser.error("build must be positive")
    if args.output.exists():
        parser.error("output already exists; choose a new run directory")
    out = args.output
    out.mkdir(parents=True)
    queried = datetime.now(KST).isoformat()
    build_log = docker(
        "exec",
        "jenkins",
        "cat",
        f"/var/jenkins_home/jobs/CQC-CICD/builds/{args.build}/log",
    )
    source_sha = re.findall(r"Checking out Revision ([0-9a-f]{40})", build_log)[-1]
    selected = [
        line
        for line in build_log.splitlines()
        if "Checking out Revision" in line
        or "Branch policy:" in line
        or "exporting manifest list sha256:" in line
        or "naming to docker.io/library/cqc-cicd-" in line
        or "VERIFY SUCCESS" in line
    ]
    node_digests = dict(
        re.findall(r"#(\d+) exporting manifest list (sha256:[0-9a-f]{64})", build_log)
    )
    service_digests = {}
    for node, service in re.findall(
        r"#(\d+) naming to docker.io/library/cqc-cicd-([a-z-]+):latest", build_log
    ):
        if node in node_digests:
            service_digests[service] = node_digests[node]
    services = []
    for service in ("backend", "inference", "simulator", "logistics-web"):
        container = json.loads(docker("inspect", f"cqc-cicd-{service}-1"))[0]
        services.append(
            {
                "service": service,
                "image_id": container["Image"],
                "container_created_utc": container["Created"],
                "build_manifest_list": service_digests.get(service),
                "matches": container["Image"] == service_digests.get(service),
            }
        )
    daemon_same = docker("info", "--format", "{{.ID}}") == docker(
        "exec", "jenkins", "docker", "info", "--format", "{{.ID}}"
    )
    provenance = {
        "queried_kst": queried,
        "source_sha": source_sha,
        "jenkins_build": args.build,
        "same_docker_daemon": daemon_same,
        "services": services,
        "verified": daemon_same and all(row["matches"] for row in services),
    }
    (out / "deployment-provenance.json").write_text(
        json.dumps(provenance, indent=2), encoding="utf-8"
    )
    (out / f"build-{args.build}-selected-log.txt").write_text(
        "\n".join(selected) + "\n", encoding="utf-8"
    )

    runs = {
        "20261006-1104": ROOT
        / "docs/wbs/results/qa-mo-20261007-evidence/prior-1104-normal-100.json",
        "20261006-1423": ROOT
        / "docs/wbs/results/qa-mo-20261007-evidence/20261006-1425-normal-100.json",
        "20261007-0951": ROOT
        / "docs/wbs/results/qa-mo-20261007-evidence/live-normal-100.json",
    }
    summaries = {}
    largest_gaps = {}
    for name, path in runs.items():
        sample = json.loads(path.read_text(encoding="utf-8"))
        ids = [item["id"] for item in sample["items"]]
        if not all(re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", value) for value in ids):
            raise ValueError("unexpected inspection ID")
        sql = (
            "SELECT inspection_id,created_at,completed_at,inference_time_ms FROM inspections WHERE inspection_id IN ("
            + ",".join("'" + value + "'" for value in ids)
            + ")"
        )
        raw = docker(
            "exec",
            "cqc-cicd-mysql-1",
            "sh",
            "-c",
            'MYSQL_PWD="$MYSQL_PASSWORD" mysql -u"$MYSQL_USER" "$MYSQL_DATABASE" -N -e "$1"',
            "sh",
            sql,
        )
        records = []
        for line in raw.splitlines():
            inspection_id, created, completed, inference = line.split("\t")
            records.append(
                {
                    "inspection_id": inspection_id,
                    "created_at_utc": created,
                    "completed_at_utc": completed,
                    "inference_ms": float(inference) if inference != "NULL" else None,
                }
            )
        records.sort(key=lambda row: row["completed_at_utc"])
        summary = {
            "source": str(path.relative_to(ROOT)),
            "requested_ids": len(ids),
            "matched_ids": len(records),
        }
        if len(records) == len(ids):
            created = [datetime.fromisoformat(row["created_at_utc"]) for row in records]
            completed = [
                datetime.fromisoformat(row["completed_at_utc"]) for row in records
            ]
            summary["created_gaps"] = metrics(
                [(b - a).total_seconds() for a, b in pairwise(created)]
            )
            summary["completed_gaps"] = metrics(
                [(b - a).total_seconds() for a, b in pairwise(completed)]
            )
            summary["processing_duration"] = metrics(
                [(b - a).total_seconds() for a, b in zip(created, completed)]
            )
            largest_index = max(
                range(len(completed) - 1),
                key=lambda i: (completed[i + 1] - completed[i]).total_seconds(),
            )
            previous, current = records[largest_index : largest_index + 2]
            largest_gaps[name] = {
                "previous_id": previous["inspection_id"],
                "current_id": current["inspection_id"],
                "previous_completed_utc": previous["completed_at_utc"],
                "current_completed_utc": current["completed_at_utc"],
                "created_gap_seconds": (
                    created[largest_index + 1] - created[largest_index]
                ).total_seconds(),
                "completed_gap_seconds": (
                    completed[largest_index + 1] - completed[largest_index]
                ).total_seconds(),
                "previous_processing_seconds": (
                    completed[largest_index] - created[largest_index]
                ).total_seconds(),
                "current_processing_seconds": (
                    completed[largest_index + 1] - created[largest_index + 1]
                ).total_seconds(),
                "current_inference_ms": current["inference_ms"],
            }
        (out / f"timing-{name}.json").write_text(
            json.dumps(
                {"queried_kst": queried, **summary, "records": records}, indent=2
            ),
            encoding="utf-8",
        )
        summaries[name] = summary
    (out / "timing-summary.json").write_text(
        json.dumps(summaries, indent=2), encoding="utf-8"
    )
    (out / "largest-gap-decomposition.json").write_text(
        json.dumps(largest_gaps, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "provenance_verified": provenance["verified"],
                "source_sha": source_sha,
                "timing": summaries,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
