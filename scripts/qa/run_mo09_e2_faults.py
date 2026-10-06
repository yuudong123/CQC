"""Run QA-SIM-06 fault cases against an explicitly isolated local Compose project."""

import argparse
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
    mysql = json.loads(
        subprocess.check_output(
            ["docker", "inspect", f"{project}-mysql-1"], text=True, timeout=15
        )
    )[0]
    env = dict(item.split("=", 1) for item in mysql["Config"]["Env"])
    result = subprocess.check_output(
        [
            "docker",
            "exec",
            "-e",
            f"MYSQL_PWD={env['MYSQL_PASSWORD']}",
            f"{project}-mysql-1",
            "mysql",
            "--protocol=TCP",
            "-h127.0.0.1",
            f"-u{env['MYSQL_USER']}",
            "-Nse",
            f"SELECT COUNT(*) FROM control_attempts WHERE inspection_id = '{inspection_id}'",
            env["MYSQL_DATABASE"],
        ],
        text=True,
        timeout=15,
    )
    return int(result.strip())


def wait_for(predicate, seconds=35):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        result = predicate()
        if result is not None:
            return result
        time.sleep(0.5)
    raise AssertionError(f"timed out after {seconds}s")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--backend", default="http://127.0.0.1:18000")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--actor", default="MO-09 automation")
    args = parser.parse_args()
    container = gate(args.project, args.backend)
    args.output.mkdir(parents=True, exist_ok=True)
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
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    results = []
    for fault, expected in FAULTS.items():
        entry = {"case": f"QA-SIM-06/{fault}", "fault": fault, "time_kst": now()}
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
                image_items = api(
                    args.backend,
                    "/v1/quality/fault-images?"
                    + urllib.parse.urlencode({"inspectionId": row["id"]}),
                )["items"]
                entry["fault_image_count"] = len(image_items)
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
            _, rows = snapshot(args.backend)
            if fault == "DB_ERROR":
                check(
                    not any(fault in row["faults"] for row in rows),
                    "DB_ERROR row unexpectedly saved",
                )
                entry["note"] = (
                    "NEXT claim cleared; no DB_ERROR history row; later normal row saved"
                )
            entry["status"] = "통과"
        except (
            AssertionError,
            OSError,
            ValueError,
            KeyError,
            TypeError,
            subprocess.SubprocessError,
        ) as error:
            entry["status"] = "실패"
            entry["error"] = str(error)
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
