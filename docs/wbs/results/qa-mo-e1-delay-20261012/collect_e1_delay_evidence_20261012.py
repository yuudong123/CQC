"""Read-only E1 SQL/log collection for the 2026-10-12 acceptance delay."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))
UTC = timezone.utc
ROOT = next(p for p in Path(__file__).resolve().parents if (p / "scripts/qa/run_mo09_acceptance.py").is_file())
SAMPLE = ROOT / "docs/wbs/results/qa-mo-20261012-stage3/normal-100-run/normal-100.json"
INDICES = [5, 6, 7, 8, 91, 92, 93, 94, 95]
WINDOWS = {
    "initial-snapshot": ("2026-10-12T09:43:55+09:00", "2026-10-12T09:45:00+09:00"),
    "gap-0946": ("2026-10-12T09:46:24+09:00", "2026-10-12T09:46:40+09:00"),
    "gap-0949": ("2026-10-12T09:49:22+09:00", "2026-10-12T09:49:42+09:00"),
}
SERVICES = ["backend", "simulator", "inference"]


def docker(*args: str, input_bytes: bytes | None = None) -> bytes:
    return subprocess.check_output(
        ["docker", *args], input=input_bytes, stderr=subprocess.STDOUT, timeout=45
    )


def save_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def parse_utc(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


def stamp(value: str | None) -> str | None:
    parsed = parse_utc(value)
    return parsed.astimezone(KST).isoformat(timespec="milliseconds") if parsed else None


def delta(a: str | None, b: str | None) -> float | None:
    left, right = parse_utc(a), parse_utc(b)
    return round((right - left).total_seconds(), 6) if left and right else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    out = parser.parse_args().output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    logs_dir = out / "logs"
    logs_dir.mkdir()
    sample_bytes = SAMPLE.read_bytes()
    sample = json.loads(sample_bytes)
    selected = [sample["items"][i] for i in INDICES]
    ids = [row["id"] for row in selected]
    assert len(set(ids)) == 9 and all(re.fullmatch(r"[0-9a-f-]{36}", x) for x in ids)
    save_json(out / "selected-inspections.json", {
        "source": SAMPLE.relative_to(ROOT).as_posix(),
        "source_sha256": hashlib.sha256(sample_bytes).hexdigest(),
        "source_commit": "86b9b973b53f8695a11d7401ecb09fcb0671abcc",
        "selection": "Nine surrounding records reconstructed from original 100-record evidence. The BE comment does not enumerate IDs; this is an explicit collector selection, not a verified copy of BE's separate list.",
        "zero_based_indices": INDICES,
        "items": selected,
    })
    in_clause = ",".join("'" + value + "'" for value in ids)
    inspection_fields = ["inspection_id", "created_at", "completed_at", "updated_at", "inference_time_ms", "inspection_status", "control_status", "persistence_status", "error_code", "model_version"]
    control_fields = ["id", "command_id", "inspection_id", "attempt_no", "requested_bin_code", "command_type", "control_status", "requested_at", "responded_at", "response_time_ms", "failure_reason"]

    def expression(kind: str, fields: list[str]) -> str:
        return "JSON_OBJECT('kind','" + kind + "'," + ",".join("'" + key + "'," + key for key in fields) + ")"

    sql = (
        "SET SESSION time_zone = '+00:00';\n"
        "SET SESSION TRANSACTION READ ONLY;\n"
        "START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY;\n"
        "SELECT JSON_OBJECT('kind','database_info','queried_utc',UTC_TIMESTAMP(3),'mysql_version',VERSION(),'session_time_zone',@@session.time_zone);\n"
        f"SELECT {expression('inspection', inspection_fields)} FROM inspections WHERE inspection_id IN ({in_clause}) ORDER BY completed_at,inspection_id;\n"
        f"SELECT {expression('control_attempt', control_fields)} FROM control_attempts WHERE inspection_id IN ({in_clause}) ORDER BY requested_at,inspection_id,attempt_no;\n"
        "ROLLBACK;\n"
    )
    (out / "query.sql").write_text(sql, encoding="utf-8", newline="\n")
    raw = docker(
        "exec", "-i", "cqc-cicd-mysql-1", "sh", "-c",
        'MYSQL_PWD="$MYSQL_PASSWORD" exec mysql -u"$MYSQL_USER" "$MYSQL_DATABASE" --batch --raw --skip-column-names --default-character-set=utf8mb4',
        input_bytes=sql.encode("utf-8"),
    )
    (out / "mysql-result.jsonl").write_bytes(raw)
    records = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
    inspections = [{k: v for k, v in row.items() if k != "kind"} for row in records if row["kind"] == "inspection"]
    controls = [{k: v for k, v in row.items() if k != "kind"} for row in records if row["kind"] == "control_attempt"]
    assert set(x["inspection_id"] for x in inspections) == set(ids), "Missing inspection records"
    assert all(x["inspection_id"] in ids for x in controls)
    save_json(out / "inspections.json", inspections)
    save_json(out / "control-attempts.json", controls)
    info = next(x for x in records if x["kind"] == "database_info")
    info["time_semantics"] = "UTC-naive DATETIME(3) written by utc_now/to_utc_naive; KST values in derived tables are UTC + 09:00."
    save_json(out / "database-info.json", info)

    by_id = {row["inspection_id"]: row for row in inspections}
    derived = []
    for index, source in zip(INDICES, selected):
        row = by_id[source["id"]]
        completed = parse_utc(row["completed_at"])
        assert completed and abs(completed.timestamp() * 1000 - source["timestamp"]) < 0.001
        own_controls = [c for c in controls if c["inspection_id"] == source["id"]]
        derived.append({
            "sample_index": index,
            "inspection_id": row["inspection_id"],
            "created_kst": stamp(row["created_at"]),
            "completed_kst": stamp(row["completed_at"]),
            "updated_kst": stamp(row["updated_at"]),
            "created_to_completed_seconds": delta(row["created_at"], row["completed_at"]),
            "inference_time_ms": row["inference_time_ms"],
            "control_attempt_count": len(own_controls),
            "control_attempts": [{**c, "requested_kst": stamp(c["requested_at"]), "responded_kst": stamp(c["responded_at"])} for c in own_controls],
        })
    save_json(out / "timing-by-inspection.json", derived)
    target_gaps = []
    for previous_index, next_index in [(6, 7), (92, 93), (93, 94)]:
        before = by_id[sample["items"][previous_index]["id"]]
        after = by_id[sample["items"][next_index]["id"]]
        before_duration = delta(before["created_at"], before["completed_at"])
        after_duration = delta(after["created_at"], after["completed_at"])
        completed_gap = delta(before["completed_at"], after["completed_at"])
        created_gap = delta(before["created_at"], after["created_at"])
        duration_delta = round(after_duration - before_duration, 6)
        assert abs(completed_gap - created_gap - duration_delta) < 0.000001
        target_gaps.append({
            "previous_id": before["inspection_id"], "next_id": after["inspection_id"],
            "previous_completed_kst": stamp(before["completed_at"]), "next_completed_kst": stamp(after["completed_at"]),
            "completed_gap_seconds": completed_gap, "created_gap_seconds": created_gap,
            "previous_created_to_completed_seconds": before_duration, "next_created_to_completed_seconds": after_duration,
            "duration_delta_seconds": duration_delta, "next_inference_ms": after["inference_time_ms"],
        })
    save_json(out / "gap-decomposition.json", target_gaps)

    log_inventory = []
    for window, (begin, end) in WINDOWS.items():
        since = datetime.fromisoformat(begin).astimezone(UTC).isoformat()
        until = datetime.fromisoformat(end).astimezone(UTC).isoformat()
        for service in SERVICES:
            body = docker("logs", "--timestamps", "--since", since, "--until", until, "cqc-cicd-" + service + "-1")
            path = logs_dir / (window + "-" + service + ".log")
            path.write_bytes(body)
            log_inventory.append({"window": window, "service": service, "since_utc": since, "until_utc": until, "file": path.relative_to(out).as_posix(), "bytes": len(body), "lines": len(body.splitlines()), "matching_selected_id_lines": sum(any(x in line for x in ids) for line in body.decode("utf-8", errors="replace").splitlines())})
    save_json(out / "log-inventory.json", log_inventory)
    captures = []
    for service in SERVICES:
        container = json.loads(docker("inspect", "cqc-cicd-" + service + "-1"))[0]
        captures.append({"service": service, "container_id": container["Id"], "image_id": container["Image"], "created_utc": container["Created"], "state": container["State"]["Status"], "log_driver": container["HostConfig"]["LogConfig"]["Type"]})
    save_json(out / "collection.json", {
        "collected_kst": datetime.now(KST).isoformat(),
        "request_comment": "https://github.com/yuudong123/CQC/issues/65#issuecomment-6116341359",
        "inspection_count": len(inspections), "control_attempt_count": len(controls),
        "matching_sample_completion_count": len(derived),
        "read_only_transaction": True, "containers": captures,
        "limits": ["No historical CPU/memory/disk time series was recorded by this collector during the failed run; current measurements cannot reconstruct those values.", "created_at is an application-assigned inspection timestamp, not an HTTP socket-entry timestamp; completed_at is assigned before final persistence finishes. These fields do not independently time individual SQL operations."],
    })
    print(json.dumps({"output": str(out), "inspection_count": len(inspections), "control_attempt_count": len(controls), "gaps": target_gaps, "log_inventory": log_inventory}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
