"""Run QA-SIM-06 fault cases against an explicitly isolated local Compose project."""

import argparse
import hashlib
import json
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path

from run_mo09_acceptance import Result, check, git_sha, now, write_results

FAULTS = {
    "INFERENCE_TIMEOUT": {
        "processingStatus": "TIMEOUT",
        "errorCode": "INFERENCE_TIMEOUT",
        "status": "FAIL",
    },
    "INFERENCE_ERROR": {
        "processingStatus": "ERROR",
        "errorCode": "INFERENCE_ERROR",
        "status": "FAIL",
    },
    "DB_ERROR": None,
    "CONTROL_REJECTED": {
        "control": "FALLBACK",
        "status": "REVIEW",
        "bin": "TEST_REINSPECTION_BIN",
    },
    "CONTROL_NO_RESPONSE": {
        "control": "NO_RESPONSE",
        "status": "REVIEW",
        "errorCode": "CONTROL_NO_RESPONSE",
    },
    "CONTROL_FAILED": {
        "control": "FAILED",
        "status": "REVIEW",
        "errorCode": "CONTROL_FAILED",
    },
}

SUPPLEMENT_FAULTS = (
    "CONTROL_REJECTED",
    "CONTROL_NO_RESPONSE",
    "CONTROL_FAILED",
    "DB_ERROR",
)


def api(base, path, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(
        base + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="PUT" if data else "GET",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def gate(project, base):
    check(project.startswith("cqc-mo09-e2-"), "E2 project name required")
    check(base == "http://127.0.0.1:18000", "E2 loopback backend URL required")
    raw = subprocess.check_output(
        ["docker", "inspect", f"{project}-backend-1"], text=True, timeout=15
    )
    container = json.loads(raw)[0]
    check(
        container["Config"]["Labels"]["com.docker.compose.project"] == project,
        "Backend project mismatch",
    )
    check(container["State"]["Running"], "E2 backend is not running")
    check(
        container["HostConfig"]["PortBindings"]["8000/tcp"]
        == [{"HostIp": "127.0.0.1", "HostPort": "18000"}],
        "E2 port mismatch",
    )
    env = dict(item.split("=", 1) for item in container["Config"]["Env"])
    check(
        urllib.parse.urlparse(env.get("DATABASE_URL", "")).hostname == "mysql",
        "E2 must use project-local mysql",
    )
    mysql = json.loads(
        subprocess.check_output(
            ["docker", "inspect", f"{project}-mysql-1"], text=True, timeout=15
        )
    )[0]
    check(
        mysql["Config"]["Labels"]["com.docker.compose.project"] == project,
        "MySQL project mismatch",
    )
    return container


def snapshot(base):
    s = api(base, "/v1/quality/snapshot")
    return s, s["state"]["history"]


def mysql_count(project, inspection_id):
    result = mysql_query(
        project,
        "SELECT COUNT(*) FROM control_attempts WHERE inspection_id = "
        + sql_value(inspection_id),
    )
    return int(result.strip())


def sql_value(value: str) -> str:
    """SQL 값은 UTF-8 hex로 전달해 식별자에 의한 SQL 삽입을 방지한다."""
    check(bool(value), "Empty SQL evidence identifier")
    return f"CONVERT(0x{value.encode('utf-8').hex()} USING utf8mb4)"


def mysql_query(project: str, sql: str) -> str:
    """기존 컨테이너 환경변수를 사용하고 비밀번호를 호스트 인자에 넣지 않는다."""
    return subprocess.check_output(
        [
            "docker",
            "exec",
            f"{project}-mysql-1",
            "sh",
            "-c",
            (
                'MYSQL_PWD="$MYSQL_PASSWORD" mysql --protocol=TCP -h127.0.0.1 '
                '-u"$MYSQL_USER" "$MYSQL_DATABASE" -N --raw -e "$1"'
            ),
            "sh",
            sql,
        ],
        text=True,
        timeout=15,
    )


def mysql_records(project: str, table: str, fields: tuple, inspection_id: str) -> list:
    """허용된 증거 테이블의 개별 행을 JSON으로 수집한다."""
    check(table in {"inspections", "control_attempts"}, "Invalid evidence table")
    pairs = ", ".join(f"'{field}', {field}" for field in fields)
    order = " ORDER BY attempt_no, id" if table == "control_attempts" else ""
    raw = mysql_query(
        project,
        f"SELECT JSON_OBJECT({pairs}) FROM {table} WHERE inspection_id = "
        + sql_value(inspection_id)
        + order,
    )
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


CONTROL_FIELDS = (
    "id",
    "inspection_id",
    "command_id",
    "attempt_no",
    "requested_bin_code",
    "command_type",
    "control_status",
    "requested_at",
    "responded_at",
    "response_time_ms",
    "failure_reason",
)
INSPECTION_FIELDS = (
    "inspection_id",
    "source_reference",
    "created_at",
    "completed_at",
    "inspection_status",
    "control_status",
    "persistence_status",
    "error_code",
    "target_bin_code",
    "exclude_from_normal_stats",
)


def validate_controls(rows: list, inspection_id: str, fault: str, count: int) -> None:
    """저장 행의 순서를 검증하며 실제 send 호출 수와 구분한다."""
    expected = 2 if fault == "CONTROL_REJECTED" else 1
    check(len(rows) == count == expected, "Control row/count mismatch")
    check(
        all(row["inspection_id"] == inspection_id for row in rows),
        "Control ID mismatch",
    )
    check(
        [row["attempt_no"] for row in rows] == list(range(1, expected + 1)),
        "Control attempt order mismatch",
    )
    check(len({row["command_id"] for row in rows}) == expected, "Duplicate command ID")
    check(len({row["id"] for row in rows}) == expected, "Duplicate control row ID")
    check(
        all(
            row["command_id"] and row["requested_bin_code"] and row["requested_at"]
            for row in rows
        ),
        "Missing control metadata",
    )
    check(
        [row["requested_at"] for row in rows]
        == sorted(row["requested_at"] for row in rows),
        "Control time order mismatch",
    )
    if fault.startswith("CONTROL_"):
        statuses = (
            ["REJECTED", "SUCCEEDED"]
            if expected == 2
            else [fault.removeprefix("CONTROL_")]
        )
        check(
            [row["control_status"] for row in rows] == statuses,
            "Control result order mismatch",
        )
    if expected == 2:
        check(
            rows[0]["requested_bin_code"] != rows[1]["requested_bin_code"],
            "Fallback bin unchanged",
        )


def collect_no_response_stats(project: str, inspection_id: str, entry: dict) -> None:
    """공개 bin 집계와 같은 성공 제어 조건으로 해당 ID의 기여분을 확인한다."""
    records = mysql_records(project, "inspections", INSPECTION_FIELDS, inspection_id)
    entry["statistics_inspection_rows"] = records
    predicate = "control_status = 'SUCCEEDED' AND completed_at IS NOT NULL AND inspection_status <> 'PROCESSING'"
    raw = mysql_query(
        project,
        "SELECT COUNT(*) FROM inspections WHERE inspection_id = "
        + sql_value(inspection_id)
        + " AND "
        + predicate,
    )
    entry["successful_bin_contribution"] = {
        "predicate": predicate,
        "count": int(raw.strip()),
        "scope": "target inspection only; not a whole-run aggregate reconciliation",
    }
    check(len(records) == 1, "Missing/duplicate statistics inspection")
    row = records[0]
    check(
        row["inspection_id"] == inspection_id
        and row["control_status"] == "NO_RESPONSE",
        "Statistics control identity mismatch",
    )
    check(
        row["target_bin_code"] == entry["fault_row"]["bin"], "Statistics bin mismatch"
    )
    check(
        row["completed_at"] and row["persistence_status"] == "SUCCEEDED",
        "Statistics inspection not saved/completed",
    )
    check(
        entry["successful_bin_contribution"]["count"] == 0,
        "NO_RESPONSE contributed to successful bins",
    )


def read_http_events(path: Path, offset: int) -> dict:
    """기존 wrapper의 이번 회차 완결 JSONL만 읽으며 원본은 변경하지 않는다."""
    with path.open("rb") as stream:
        check(stream.seek(0, 2) >= offset, "HTTP event file truncated")
        stream.seek(offset)
        raw = stream.read()
    complete = raw[: raw.rfind(b"\n") + 1]
    fields = (
        "kind",
        "inspection_id",
        "source_reference",
        "faults",
        "intervalMs",
        "started_utc",
        "ended_utc",
        "start_monotonic",
        "end_monotonic",
        "http_status",
        "error_type",
        "response_parse_error",
        "sequence_no",
        "pid",
        "recording_errors_so_far",
    )
    response_fields = (
        "inspection_id",
        "inspection_status",
        "control_status",
        "persistence_status",
        "error_code",
        "target_bin_code",
    )
    events = []
    parse_error = None
    for line_no, line in enumerate(complete.splitlines(), 1):
        try:
            value = json.loads(line)
            check(isinstance(value, dict), "HTTP event must be an object")
        except (ValueError, AssertionError) as error:
            parse_error = {"line_in_slice": line_no, "error_type": type(error).__name__}
            break
        event = {key: value.get(key) for key in fields}
        event["line_in_slice"] = line_no
        response = value.get("response")
        event["response"] = (
            {key: response.get(key) for key in response_fields}
            if isinstance(response, dict)
            else None
        )
        events.append(event)
    return {
        "path": str(path),
        "start_offset": offset,
        "end_offset": offset + len(complete),
        "sha256": hashlib.sha256(complete).hexdigest(),
        "events": events,
        "incomplete_tail_bytes": len(raw) - len(complete),
        "parse_error": parse_error,
    }


def db_error_sequence(events: list) -> tuple | None:
    """자동 요청 시작 순서상 DB_ERROR와 바로 다음 요청의 응답을 연결한다."""
    if any(e.get("sequence_no") is not None for e in events):
        numbers = [e.get("sequence_no") for e in events]
        check(
            all(isinstance(n, int) for n in numbers), "Missing HTTP sequence metadata"
        )
        check(
            numbers == list(range(numbers[0], numbers[0] + len(numbers))),
            "HTTP event sequence gap",
        )
        check(
            len({e.get("pid") for e in events}) == 1 and events[0].get("pid"),
            "HTTP process changed",
        )
        check(
            all(e.get("recording_errors_so_far") == 0 for e in events),
            "HTTP recording errors detected",
        )
    starts = [e for e in events if e["kind"] == "request_start"]
    check(
        len({e["inspection_id"] for e in starts}) == len(starts),
        "Duplicate automatic request start",
    )
    targets = [i for i, e in enumerate(starts) if e["faults"] == ["DB_ERROR"]]
    check(len(targets) <= 1, "Multiple DB_ERROR automatic requests")
    if not targets or targets[0] + 1 >= len(starts):
        return None
    pair = starts[targets[0] : targets[0] + 2]
    ends = []
    for start in pair:
        check(
            start["inspection_id"] and start["source_reference"],
            "Missing automatic request identity",
        )
        matching = [
            e
            for e in events
            if e["kind"] == "request_end"
            and e["inspection_id"] == start["inspection_id"]
        ]
        check(len(matching) <= 1, "Duplicate automatic response")
        if not matching:
            return None
        end = matching[0]
        check(
            end["faults"] == start["faults"]
            and end["source_reference"] == start["source_reference"],
            "Automatic response identity mismatch",
        )
        check(
            end["response"]
            and end["response"]["inspection_id"] == start["inspection_id"],
            "Response inspection ID mismatch",
        )
        check(
            end["http_status"] == 200 and not end["error_type"],
            "Automatic request HTTP failure",
        )
        check(
            end["started_utc"] == start["started_utc"]
            and end["start_monotonic"] == start["start_monotonic"]
            and end["end_monotonic"] >= start["start_monotonic"],
            "Automatic request time mismatch",
        )
        ends.append(end)
    check(
        pair[1]["start_monotonic"] >= ends[0]["end_monotonic"],
        "Automatic request order violates concurrency 1",
    )
    check(not pair[1]["faults"], "Immediately next request is not normal")
    check(
        ends[0]["response"]["persistence_status"] == "FAILED",
        "DB_ERROR response did not fail persistence",
    )
    check(
        ends[1]["response"]["persistence_status"] == "SUCCEEDED",
        "Immediately next response not saved",
    )
    check(
        ends[1]["response"]["inspection_status"] == "COMPLETED"
        and ends[1]["response"]["control_status"] == "SUCCEEDED",
        "Immediately next response not normal/control succeeded",
    )
    return pair[0], pair[1], ends[0], ends[1]


def wait_for(predicate, seconds=35):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        result = predicate()
        if result is not None:
            return result
        time.sleep(0.5)
    raise AssertionError(f"timed out after {seconds}s")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """서비스 접근 전에 선택 유형과 신규 출력 경로를 검증한다."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--backend", default="http://127.0.0.1:18000")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--actor", default="MO-09 automation")
    parser.add_argument(
        "--http-events",
        type=Path,
        help="Read an existing Simulator wrapper JSONL stream for DB_ERROR request order",
    )
    parser.add_argument(
        "--faults",
        nargs="+",
        action="append",
        choices=SUPPLEMENT_FAULTS,
        help="Run only these supplement faults; omit to run all six faults",
    )
    args = parser.parse_args(argv)
    selected = (
        tuple(fault for group in args.faults for fault in group)
        if args.faults is not None
        else tuple(FAULTS)
    )
    if len(set(selected)) != len(selected):
        parser.error("Duplicate fault types are not allowed")
    if args.output.exists() or args.output.is_symlink():
        parser.error("Output already exists; choose a new run directory")
    if args.http_events is not None and not args.http_events.is_file():
        parser.error("HTTP event input must be an existing file")
    args.faults = selected
    return args


def main(argv: list[str] | None = None) -> None:
    """기존 격리 확인 후 선택한 장애만 독립 출력 디렉터리에 기록한다."""
    args = parse_args(argv)
    print("Selected faults: " + ", ".join(args.faults), flush=True)
    container = gate(args.project, args.backend)
    # 사전 검사 후 다른 실행이 경로를 만들었어도 서비스 호출 전에 거부한다.
    args.output.mkdir(parents=True, exist_ok=False)
    model = api("http://127.0.0.1:18001", "/health").get("model_version", "unknown")
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain"]).strip())
    identity = f"image SHA unverified / {model}; script HEAD {git_sha()[:12]}{' + uncommitted' if dirty else ''}"
    (args.output / "run.json").write_text(
        json.dumps(
            {
                "source_sha": git_sha(),
                "working_tree_dirty": dirty,
                "project": args.project,
                "started_kst": now(),
                "backend_image_id": container["Image"],
                "model_version": model,
                "deployed_sha": "unverified",
                "coverage": "partial E2 fault injection",
                "selected_faults": args.faults,
                "http_events": str(args.http_events) if args.http_events else None,
                "official_qa_verdict": "unchanged; collector checks are not official PASS",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    results = []
    for fault in args.faults:
        expected = FAULTS[fault]
        entry = {
            "case": f"QA-SIM-06/{fault}",
            "fault": fault,
            "time_kst": now(),
            "limitations": [
                "Persisted control rows do not observe actual send() calls"
            ],
            "actual_send_call_count": None,
            "official_qa_verdict": "not assessed",
        }
        try:
            before, history = snapshot(args.backend)
            check(
                before["state"]["running"] and not before["state"]["faults"],
                "Simulator must be running without faults",
            )
            check(
                before["state"]["concurrency"] == 1,
                "E2 NEXT checks require concurrency 1",
            )
            revision = before["revision"]
            entry["statistics_before"] = {
                "capturedAt": before.get("capturedAt"),
                "today": before["state"].get("today"),
            }
            trace_offset = None
            if fault == "DB_ERROR" and args.http_events is not None:
                with args.http_events.open("rb") as stream:
                    trace_offset = stream.seek(0, 2)
                    if trace_offset:
                        stream.seek(-1, 2)
                        check(
                            stream.read(1) == b"\n",
                            "HTTP input must end at a complete event boundary",
                        )
            known = {row["id"] for row in history}
            reply = api(
                args.backend,
                "/v1/quality/simulator",
                {"expectedRevision": revision, "faults": [fault], "scope": "NEXT"},
            )
            entry["set_revision"] = reply["revision"]
            check(
                reply["revision"] == revision + 1,
                "Setting revision did not advance once",
            )

            def claimed(revision=revision):
                s, rows = snapshot(args.backend)
                if s["revision"] < revision + 2 or s["state"]["faults"]:
                    return None
                return s, rows

            claimed_snapshot, claimed_history = wait_for(claimed)
            entry["clear_revision"] = claimed_snapshot["revision"]

            if expected is not None:

                def fault_row(known=known, fault=fault):
                    _, rows = snapshot(args.backend)
                    return next(
                        (
                            row
                            for row in rows
                            if row["id"] not in known and fault in row["faults"]
                        ),
                        None,
                    )

                row = wait_for(fault_row)
                for key, value in expected.items():
                    check(
                        row.get(key) == value, f"{key}: {row.get(key)!r} != {value!r}"
                    )
                entry["fault_row"] = {
                    key: row.get(key)
                    for key in (
                        "id",
                        "status",
                        "processingStatus",
                        "errorCode",
                        "control",
                        "persistence",
                        "bin",
                        "faults",
                    )
                }
                entry["control_attempt_count"] = mysql_count(args.project, row["id"])
                entry["control_attempts"] = mysql_records(
                    args.project, "control_attempts", CONTROL_FIELDS, row["id"]
                )
                validate_controls(
                    entry["control_attempts"],
                    row["id"],
                    fault,
                    entry["control_attempt_count"],
                )
                if fault == "CONTROL_REJECTED":
                    check(
                        entry["control_attempts"][-1]["requested_bin_code"]
                        == row["bin"],
                        "Fallback result bin mismatch",
                    )
                elif fault == "CONTROL_NO_RESPONSE":
                    collect_no_response_stats(args.project, row["id"], entry)
                if fault in {"CONTROL_NO_RESPONSE", "CONTROL_FAILED"}:
                    check(
                        entry["control_attempts"][0]["requested_bin_code"]
                        == row["bin"],
                        "Control/history requested bin mismatch",
                    )
                image_items = api(
                    args.backend,
                    "/v1/quality/fault-images?"
                    + urllib.parse.urlencode({"inspectionId": row["id"]}),
                )["items"]
                entry["fault_image_count"] = len(image_items)
                entry["fault_image_items"] = image_items
                if fault in {"INFERENCE_TIMEOUT", "INFERENCE_ERROR"}:
                    check(
                        len(image_items) == 12,
                        f"{fault} should retain 12 fault images, got {len(image_items)}",
                    )
                else:
                    check(
                        len(image_items) == 0,
                        f"{fault} should not retain fault images, got {len(image_items)}",
                    )
                expected_attempts = 2 if fault == "CONTROL_REJECTED" else 1
                check(
                    entry["control_attempt_count"] == expected_attempts,
                    f"{fault} control attempts={entry['control_attempt_count']}, expected {expected_attempts}",
                )
                normal_after = row["timestamp"]
            else:
                # A failed database write has no history row by contract.
                entry["fault_row"] = None
                # Require a new normal save after the claimed snapshot; a row
                # arriving between the baseline GET and PUT is not recovery.
                known.update(row["id"] for row in claimed_history)
                normal_after = 0

            def next_normal(known=known, normal_after=normal_after):
                _, rows = snapshot(args.backend)
                candidates = [
                    row
                    for row in rows
                    if row["id"] not in known
                    and row["timestamp"] > normal_after
                    and not row["faults"]
                    and row["processingStatus"] == "COMPLETED"
                    and row["persistence"] == "SAVED"
                ]
                return candidates[0] if candidates else None

            normal = wait_for(next_normal)
            entry["next_normal_id"] = normal["id"]
            after, rows = snapshot(args.backend)
            entry["statistics_after"] = {
                "capturedAt": after.get("capturedAt"),
                "today": after["state"].get("today"),
            }
            entry["next_normal_relation"] = (
                "later saved normal; adjacency not established"
            )
            if fault == "CONTROL_NO_RESPONSE":
                entry["limitations"].append(
                    "Public statistics before/after are context only; other normal increments are not attributed to this fault"
                )
            if fault == "DB_ERROR":
                check(
                    not any(fault in row["faults"] for row in rows),
                    "DB_ERROR row unexpectedly saved",
                )
                entry["note"] = (
                    "NEXT claim cleared; no DB_ERROR history row; later normal row saved"
                )
                if trace_offset is None:
                    entry["limitations"].append(
                        "DB_ERROR ID/FAILED response/immediately next automatic save require an existing HTTP event stream"
                    )
                    entry["status"] = "부분 충족"
                else:

                    def automatic_pair(trace_offset=trace_offset, entry=entry):
                        trace = read_http_events(args.http_events, trace_offset)
                        entry["http_evidence"] = trace
                        check(
                            trace["parse_error"] is None,
                            "Malformed HTTP evidence; slice metadata and preceding events retained",
                        )
                        return db_error_sequence(trace["events"])

                    target, following, failed, saved = wait_for(automatic_pair)
                    entry["db_error_request"] = target
                    entry["db_error_response"] = failed
                    entry["immediate_next_request"] = following
                    entry["immediate_next_response"] = saved
                    target_id, next_id = (
                        target["inspection_id"],
                        following["inspection_id"],
                    )
                    entry["db_error_db_rows"] = mysql_records(
                        args.project, "inspections", INSPECTION_FIELDS, target_id
                    )
                    check(
                        not entry["db_error_db_rows"],
                        "DB_ERROR inspection unexpectedly exists in DB",
                    )
                    check(
                        not any(row["id"] == target_id for row in rows),
                        "DB_ERROR inspection exists in history",
                    )

                    def next_saved(next_id=next_id):
                        _, history_rows = snapshot(args.backend)
                        return next(
                            (row for row in history_rows if row["id"] == next_id), None
                        )

                    next_row = wait_for(next_saved)
                    entry["immediate_next_history_row"] = next_row
                    entry["immediate_next_db_rows"] = mysql_records(
                        args.project, "inspections", INSPECTION_FIELDS, next_id
                    )
                    next_db = entry["immediate_next_db_rows"]
                    check(
                        len(next_db) == 1
                        and next_db[0]["inspection_id"] == next_id
                        and next_db[0]["source_reference"]
                        == following["source_reference"],
                        "Immediately next DB identity mismatch",
                    )
                    check(
                        next_db[0]["persistence_status"] == "SUCCEEDED"
                        and next_db[0]["completed_at"]
                        and next_db[0]["inspection_status"] == "COMPLETED"
                        and next_db[0]["control_status"] == "SUCCEEDED",
                        "Immediately next DB save not complete",
                    )
                    check(
                        not next_row["faults"]
                        and next_row["processingStatus"] == "COMPLETED"
                        and next_row["persistence"] == "SAVED",
                        "Immediately next history not normal/saved",
                    )
                    entry["next_normal_relation"] = (
                        "immediately next request_start in supplied Simulator stream"
                    )
                    entry["limitations"].append(
                        "HTTP stream continuity/deployment identity requires run provenance; no internal send observation"
                    )
            entry.setdefault("status", "통과")
        except (
            AssertionError,
            OSError,
            ValueError,
            KeyError,
            TypeError,
            subprocess.SubprocessError,
        ) as error:
            entry["status"] = "실패"
            entry["error"] = (
                type(error).__name__
                if isinstance(error, subprocess.SubprocessError)
                else str(error)
            )
        results.append(entry)
        print(f"{entry['case']}: {entry['status']}", flush=True)
        (args.output / "fault-evidence.json").write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    rows = []
    for result in results:
        observed = result.get("error") or (
            f"{result['fault']}; fault row={result.get('fault_row')}; "
            f"next normal={result.get('next_normal_id')}; rev={result.get('set_revision')}->{result.get('clear_revision')}"
        )
        rows.append(
            Result(
                result["case"],
                result["status"],
                args.actor,
                result["time_kst"],
                identity,
                observed,
                "E2",
                "부분: 장애 상태·NEXT 해제·후속 저장·장애 이미지 장수·제어 시도 확인; 전체 통계 별도 확인",
            )
        )
    write_results(rows, args.output)
    raise SystemExit(1 if any(r["status"] != "통과" for r in results) else 0)


if __name__ == "__main__":
    main()
