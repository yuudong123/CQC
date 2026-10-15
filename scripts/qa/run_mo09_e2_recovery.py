"""Verify MySQL and Inference outage recovery in a guarded MO-09 E2 project."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path
from uuid import uuid4

from run_mo09_acceptance import Result, check, git_sha, now, write_results
from run_mo09_e2_faults import gate, snapshot, wait_for

PROBE = r"""
import json
import os
import sys
import time
from pathlib import Path

import httpx

from src.simulator.dataset import SimulatorDataset

dataset = SimulatorDataset(Path('/data/dataset'), 24 * 1024 * 1024)
bundle = dataset.load(0)
started = time.monotonic()
response = httpx.post(
    'http://backend:8000/v1/inspections',
    data={
        'inspection_id': sys.argv[1],
        'metadata': bundle.metadata_json,
        'virtual_brix': bundle.virtual_brix,
    },
    files=[('images', (name, content, mime)) for name, content, mime in bundle.images],
    headers={
        'X-CQC-Simulator-Token': os.environ['SIMULATOR_FAULT_TOKEN'],
        'X-CQC-Simulator-Bundle-ID': bundle.bundle_id,
        'X-CQC-Simulator-Interval-Ms': '2000',
    },
    timeout=15,
)
print(json.dumps({
    'inspection_id': sys.argv[1],
    'bundle_id': bundle.bundle_id,
    'http_status': response.status_code,
    'elapsed_seconds': round(time.monotonic() - started, 3),
    'body': response.json(),
}))
"""

SIM_HEALTH = r"""
import json
import urllib.request

with urllib.request.urlopen('http://127.0.0.1:8002/health', timeout=5) as response:
    print(json.dumps(json.load(response)))
"""


def docker(*args: str, timeout: int = 30) -> str:
    return subprocess.check_output(
        ["docker", *args], text=True, encoding="utf-8", timeout=timeout
    ).strip()


def container(project: str, service: str) -> str:
    name = f"{project}-{service}-1"
    data = json.loads(docker("inspect", name, timeout=15))[0]
    check(
        data["Config"]["Labels"]["com.docker.compose.project"] == project,
        f"{service} project mismatch",
    )
    return name


def health(name: str) -> str:
    data = json.loads(docker("inspect", name, timeout=15))[0]
    return data["State"]["Health"]["Status"]


def wait_healthy(name: str, seconds: int = 150) -> None:
    def ready() -> bool | None:
        return True if health(name) == "healthy" else None

    wait_for(ready, seconds)


def send(simulator: str, prefix: str) -> dict:
    inspection_id = f"qa-mo09-{prefix}-{uuid4().hex[:16]}"
    raw = docker(
        "exec",
        "-w",
        "/app",
        simulator,
        "python",
        "-c",
        PROBE,
        inspection_id,
        timeout=35,
    )
    return json.loads(raw.splitlines()[-1])


def simulator_health(simulator: str) -> dict:
    raw = docker("exec", simulator, "python", "-c", SIM_HEALTH, timeout=15)
    return json.loads(raw.splitlines()[-1])


def fields(probe: dict) -> dict:
    body = probe["body"]
    return {
        "inspection_id": probe["inspection_id"],
        "bundle_id": probe["bundle_id"],
        "http_status": probe["http_status"],
        "elapsed_seconds": probe["elapsed_seconds"],
        "inspection_status": body.get("inspection_status"),
        "decision_reason": body.get("decision_reason"),
        "target_bin_code": body.get("target_bin_code"),
        "control_status": body.get("control_status"),
        "persistence_status": body.get("persistence_status"),
        "exclude_from_normal_stats": body.get("exclude_from_normal_stats"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--backend", default="http://127.0.0.1:18000")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--actor", default="MO-09 automation")
    args = parser.parse_args()

    backend = gate(args.project, args.backend)
    inference = container(args.project, "inference")
    mysql = container(args.project, "mysql")
    simulator = container(args.project, "simulator")
    for name in (inference, mysql, simulator):
        check(health(name) == "healthy", f"{name} is not healthy")
    backend_id = backend["Id"]
    simulator_id = json.loads(docker("inspect", simulator))[0]["Id"]

    args.output.mkdir(parents=True, exist_ok=True)
    evidence: dict = {
        "project": args.project,
        "started_kst": now(),
        "source_sha": git_sha(),
        "backend_image_id": backend["Image"],
        "backend_container_id": backend_id,
        "simulator_container_id": simulator_id,
    }
    rows: list[Result] = []
    identity = f"E2 image SHA unverified; script HEAD {git_sha()[:12]}"
    stopped: set[str] = set()
    try:
        baseline = fields(send(simulator, "baseline"))
        check(baseline["http_status"] == 200, "Baseline HTTP status is not 200")
        check(
            baseline["decision_reason"] == "NORMAL"
            and baseline["persistence_status"] == "SUCCEEDED",
            f"Baseline is not normal: {baseline}",
        )
        evidence["baseline"] = baseline

        docker("stop", inference, timeout=40)
        stopped.add(inference)
        try:
            during_inference = fields(send(simulator, "inference-down"))
            check(
                during_inference["http_status"] == 200, "Inference outage HTTP failure"
            )
            check(
                during_inference["decision_reason"] == "INFERENCE_CONNECTION_ERROR"
                and during_inference["target_bin_code"] == "TEST_REINSPECTION_BIN"
                and during_inference["persistence_status"] == "SUCCEEDED"
                and during_inference["exclude_from_normal_stats"] is True,
                f"Inference outage response mismatch: {during_inference}",
            )
            evidence["inference_down"] = during_inference
        finally:
            docker("start", inference, timeout=40)
            stopped.discard(inference)
        wait_healthy(inference)
        after_inference = fields(send(simulator, "inference-recovered"))
        check(
            after_inference["http_status"] == 200
            and after_inference["decision_reason"] == "NORMAL"
            and after_inference["persistence_status"] == "SUCCEEDED",
            f"Inference did not recover: {after_inference}",
        )
        evidence["inference_recovered"] = after_inference
        inference_history = snapshot(args.backend)[1]
        inference_record = next(
            (
                row
                for row in inference_history
                if row["id"] == during_inference["inspection_id"]
            ),
            None,
        )
        evidence["inference_history"] = inference_record
        check(
            inference_record is not None,
            "Inference outage inspection is missing from history",
        )
        check(
            inference_record.get("processingStatus") == "ERROR"
            and inference_record.get("errorCode") == "INFERENCE_ERROR"
            and inference_record.get("excluded") is True,
            f"Inference outage history mismatch: {inference_record}",
        )
        rows.append(
            Result(
                "QA-INS-11",
                "통과",
                args.actor,
                now(),
                identity,
                "Inference 정지 중 재검사·저장, 재기동 후 Backend 재시작 없이 정상 저장 확인",
                "E2",
                "전체",
            )
        )

        before_mysql = simulator_health(simulator)
        docker("stop", mysql, timeout=40)
        stopped.add(mysql)
        try:
            during_mysql = fields(send(simulator, "mysql-down"))
            check(during_mysql["http_status"] == 200, "MySQL outage HTTP failure")
            check(
                during_mysql["decision_reason"] == "NORMAL"
                and during_mysql["target_bin_code"] == baseline["target_bin_code"]
                and during_mysql["control_status"] == "SUCCEEDED"
                and during_mysql["persistence_status"] == "FAILED",
                f"MySQL outage response mismatch: {during_mysql}",
            )
            evidence["mysql_down"] = during_mysql
            time.sleep(20)
            during_health = simulator_health(simulator)
            check(
                during_health["running"] is True
                and during_health["lastSeenAt"] > before_mysql["lastSeenAt"],
                "Simulator did not continue during MySQL outage",
            )
            evidence["simulator_before_mysql"] = before_mysql
            evidence["simulator_during_mysql"] = during_health
        finally:
            docker("start", mysql, timeout=40)
            stopped.discard(mysql)
        wait_healthy(mysql)
        after_mysql = fields(send(simulator, "mysql-recovered"))
        check(
            after_mysql["http_status"] == 200
            and after_mysql["decision_reason"] == "NORMAL"
            and after_mysql["persistence_status"] == "SUCCEEDED",
            f"MySQL did not recover: {after_mysql}",
        )
        evidence["mysql_recovered"] = after_mysql
        after_history = snapshot(args.backend)[1]
        check(
            any(row["id"] == after_mysql["inspection_id"] for row in after_history),
            "Recovered inspection is missing from history",
        )
        evidence["backend_container_unchanged"] = (
            json.loads(docker("inspect", f"{args.project}-backend-1"))[0]["Id"]
            == backend_id
        )
        evidence["simulator_container_unchanged"] = (
            json.loads(docker("inspect", simulator))[0]["Id"] == simulator_id
        )
        check(
            evidence["backend_container_unchanged"]
            and evidence["simulator_container_unchanged"],
            "Backend or Simulator restarted during recovery",
        )
        rows.extend(
            [
                Result(
                    "QA-INS-13",
                    "통과" if during_mysql["elapsed_seconds"] <= 2 else "실패",
                    args.actor,
                    now(),
                    identity,
                    f"MySQL 정지 중 HTTP 200·LKG 정상 bin·저장 실패; 응답 {during_mysql['elapsed_seconds']:.3f}초 (기준 ≤2초); 복구 후 정상 저장",
                    "E2",
                    "전체",
                ),
                Result(
                    "QA-SIM-09",
                    "통과",
                    args.actor,
                    now(),
                    identity,
                    "MySQL 20초 정지 중 lastSeenAt 증가, 복구 후 직접 요청 저장·컨테이너 ID 유지 확인; 자동 전송 저장 건수·components.Simulator.status 미확인",
                    "E2",
                    "부분: 자동 저장 건수·Simulator 구성요소 상태 미확인",
                ),
            ]
        )
    except (
        AssertionError,
        OSError,
        ValueError,
        KeyError,
        TypeError,
        subprocess.SubprocessError,
    ) as error:
        evidence["error"] = f"{type(error).__name__}: {error}"
        rows.append(
            Result(
                "MO-09-E2-recovery",
                "실패",
                args.actor,
                now(),
                identity,
                evidence["error"],
                "E2",
                "부분: 완료 전 중단",
            )
        )
    finally:
        for name in tuple(stopped):
            subprocess.run(
                ["docker", "start", name], capture_output=True, timeout=40, check=False
            )
        (args.output / "recovery-evidence.json").write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        write_results(rows, args.output)
    return 1 if any(row.status != "통과" for row in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
