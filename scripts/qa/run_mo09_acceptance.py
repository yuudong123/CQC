"""Repeatable, read-only MO-09 checks with ALL-04 compatible result rows."""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import secrets
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from itertools import pairwise
from pathlib import Path

KST = timezone(timedelta(hours=9), "KST")
ROOT = Path(__file__).resolve().parents[2]
CSV_HEADER = [
    "inspection_id",
    "date",
    "time_kst",
    "variety",
    "grade",
    "cultivar_confidence_pct",
    "quality_confidence_pct",
    "inference_ms",
    "model_version",
    "target_bin",
    "processing_status",
    "control_status",
    "persistence_status",
    "error_codes",
    "misclassification",
    "virtual_brix",
    "brix_is_measured",
]


@dataclass
class Result:
    case: str
    status: str
    actor: str
    time_kst: str
    commit_model: str
    note: str
    environment: str
    coverage: str = "전체"

    @property
    def qa_case(self) -> str:
        match = re.match(r"QA-[A-Z]+-\d+(?:-\d+)?", self.case)
        return match.group() if match else self.case

    @property
    def record_status(self) -> str:
        # A successful subset is evidence, not a full acceptance pass.
        return (
            "차단" if self.status == "통과" and self.coverage != "전체" else self.status
        )


def now() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")


def fetch(base: str, path: str) -> tuple[bytes, dict[str, str]]:
    with urllib.request.urlopen(base.rstrip("/") + path, timeout=20) as response:
        return response.read(), {
            key.lower(): value for key, value in response.headers.items()
        }


def get_json(base: str, path: str) -> dict:
    body, _ = fetch(base, path)
    value = json.loads(body)
    if not isinstance(value, dict):
        raise TypeError("JSON object expected")
    return value


def check(condition: bool, detail: str) -> None:
    if not condition:
        raise AssertionError(detail)


def git_sha() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def record(
    results: list[Result],
    args: argparse.Namespace,
    case: str,
    fn,
    *,
    environment: str = "E1",
    coverage: str = "전체",
) -> None:
    try:
        detail = fn()
        status = "통과"
    except (
        AssertionError,
        ValueError,
        TypeError,
        KeyError,
        urllib.error.HTTPError,
    ) as error:
        status, detail = "실패", str(error)
    except (OSError, urllib.error.URLError, subprocess.SubprocessError) as error:
        status, detail = "차단", str(error)
    results.append(
        Result(
            case,
            status,
            args.actor,
            now(),
            args.identity,
            str(detail),
            environment,
            coverage,
        )
    )
    print(f"{case}: {status} [{coverage}]", flush=True)


def live_checks(args: argparse.Namespace, results: list[Result]) -> None:
    backend, inference = args.backend, args.inference
    local_docker = urllib.parse.urlparse(backend).hostname in {
        "127.0.0.1",
        "localhost",
    } and urllib.parse.urlparse(inference).hostname in {"127.0.0.1", "localhost"}
    health = get_json(inference, "/health")
    args.identity = (
        f"deployed SHA unverified / {health.get('model_version', 'unknown')}"
    )

    def inference_health():
        check(
            health.get("status") == "ready" and health.get("model_loaded") is True,
            "Inference model is not ready",
        )
        check(
            health.get("views") == 12 and health.get("device") == "cpu",
            "Inference device/views mismatch",
        )
        check(
            health.get("model_version") == args.expected_model_version,
            "Inference model version differs from accepted QA value",
        )
        check(
            health.get("checkpoint_sha256") == args.expected_checkpoint_sha256,
            "Inference checkpoint SHA differs from accepted QA value",
        )
        check(
            health.get("model_name") == "mobilenet_v3_small_multiview"
            and health.get("approval_status") == "unverified_candidate"
            and health.get("threshold_status") == "calibrated_dev_oof",
            "Inference model metadata mismatch",
        )
        check(
            round(float(health.get("quality_temperature", -1)), 4) == 0.3908
            and round(float(health.get("cultivar_temperature", -1)), 4) == 0.3840
            and int(health.get("decode_workers", 0)) >= 1,
            "Inference calibration/worker settings mismatch",
        )
        return f"ready; model={health.get('model_version')}; checkpoint={health.get('checkpoint_sha256')}"

    record(results, args, "QA-DEP-02", inference_health)

    def backend_health():
        value = get_json(backend, "/health")
        check(
            value.get("status") == "ok"
            and value.get("service") == "CQC Backend"
            and "environment" in value,
            "Backend health fields mismatch",
        )
        if not local_docker:
            return "Backend /health status=ok; container settings need host-side check"
        settings = subprocess.check_output(
            [
                "docker",
                "exec",
                "cqc-cicd-backend-1",
                "sh",
                "-c",
                'printf "%s|%s|%s|%s" "$CULTIVAR_CONFIDENCE_THRESHOLD" "$QUALITY_CONFIDENCE_THRESHOLD" "$INFERENCE_URL" "$FAULT_IMAGE_STORAGE_ROOT"',
            ],
            text=True,
            timeout=15,
        ).split("|")
        check(
            settings
            == [
                "0.50",
                "0.60",
                "http://inference:8001/v1/predict",
                "/data/fault-images",
            ],
            "Backend threshold/inference/storage settings mismatch",
        )
        return "Backend /health and threshold/inference/storage settings OK"

    record(
        results,
        args,
        "QA-DEP-04",
        backend_health,
        coverage="전체"
        if local_docker
        else "부분: HTTP 상태만; 컨테이너 환경값 미확인",
    )

    def model_checksum():
        if not local_docker:
            raise OSError(
                "Remote deployment model file cannot be hashed from this host"
            )
        output = subprocess.check_output(
            [
                "docker",
                "exec",
                "cqc-cicd-inference-1",
                "sha256sum",
                "/app/models/approved/model.pt",
            ],
            text=True,
            timeout=30,
        )
        actual = output.split()[0]
        metadata = json.loads(
            subprocess.check_output(
                [
                    "docker",
                    "exec",
                    "cqc-cicd-inference-1",
                    "cat",
                    "/app/models/approved/model.json",
                ],
                text=True,
                timeout=15,
            )
        )
        check(
            actual
            == metadata["checkpoint_sha256"]
            == health["checkpoint_sha256"]
            == args.expected_checkpoint_sha256,
            "Deployed model file checksum mismatch",
        )
        return f"model.pt SHA-256={actual}"

    record(results, args, "QA-DEP-03", model_checksum)

    snapshot = get_json(backend, "/v1/quality/snapshot")

    def simulator_health():
        state = snapshot["state"]
        check(
            snapshot["components"]["Simulator"]["status"] == "healthy",
            "Simulator is not healthy",
        )
        check(
            state["running"] is True
            and state["intervalMs"] == 2000
            and state["concurrency"] == 1
            and not state["faults"],
            "Simulator is not in normal 2000ms mode",
        )
        return f"running; intervalMs=2000; revision={snapshot['revision']}"

    record(
        results,
        args,
        "QA-SIM-01",
        simulator_health,
        coverage="부분: 현재 설정·health만; 기동 직후 관찰 미실행",
    )

    today = datetime.now(KST).date().isoformat()
    fixed = int(time.time() * 1000)
    query = urllib.parse.urlencode({"from": today, "to": today, "snapshotAt": fixed})

    def history_csv():
        listing = get_json(backend, f"/v1/quality/inspections?{query}&pageSize=50")
        body, headers = fetch(backend, f"/v1/quality/inspections.csv?{query}")
        check(body.startswith(b"\xef\xbb\xbf"), "CSV UTF-8 BOM missing")
        check(
            b"\r\n" in body and b"\n" not in body.replace(b"\r\n", b""),
            "CSV CRLF line endings missing",
        )
        check(
            "text/csv" in headers.get("content-type", ""), "CSV content type mismatch"
        )
        check(
            "cqc-inspections.csv" in headers.get("content-disposition", "")
            and headers.get("cache-control") == "no-store",
            "CSV download/cache headers mismatch",
        )
        raw_lines = body.decode("utf-8-sig").split("\r\n")
        quoted = re.compile(r'^"(?:[^"]|"")*"(?:,"(?:[^"]|"")*")*$')
        check(
            all(quoted.fullmatch(line) for line in raw_lines if line),
            "CSV has an unquoted cell",
        )
        rows = list(csv.reader(io.StringIO(body.decode("utf-8-sig"))))
        check(rows[0] == CSV_HEADER, "CSV columns differ from QA-OPS-10")
        check(
            len(rows) - 1 == listing["total"],
            "CSV row count differs from fixed history snapshot",
        )
        check(
            all(row[-1] == "false" for row in rows[1:]),
            "CSV brix_is_measured should be false",
        )
        return f"date={today}; snapshotAt={fixed}; rows={len(rows) - 1}; BOM/CRLF/header OK"

    record(
        results,
        args,
        "QA-OPS-10",
        history_csv,
        coverage="부분: CSV 전송·형식·행 수; Excel 표시·오류 코드 결합 별도 확인",
    )

    def statistics_csv():
        body, _ = fetch(backend, f"/v1/quality/statistics.csv?{query}")
        check(body.startswith(b"\xef\xbb\xbf"), "Statistics CSV BOM missing")
        rows = list(csv.reader(io.StringIO(body.decode("utf-8-sig"))))
        check(
            rows[0] == ["mode", "from_kst", "to_kst", "group", "key", "value"],
            "Statistics CSV columns differ from QA-OPS-13",
        )
        check(
            all(row[0] == "BACKEND" for row in rows[1:]), "Statistics CSV mode mismatch"
        )
        check(
            {"reinspection_ratio", "average_inference_ms"}
            <= {row[4] for row in rows[1:] if row[3] == "total"},
            "Statistics CSV total rows missing",
        )
        current, _ = fetch(backend, "/v1/quality/statistics.csv")
        current_rows = list(csv.reader(io.StringIO(current.decode("utf-8-sig"))))
        check(
            current_rows[0]
            == ["mode", "date_kst", "section", "key", "value", "last_saved_at"],
            "Current statistics CSV columns differ from QA-OPS-13",
        )
        for minutes in (1, 5, 10, 30):
            minute_body, _ = fetch(
                backend, f"/v1/quality/statistics.csv?minutes={minutes}"
            )
            minute_rows = list(csv.reader(io.StringIO(minute_body.decode("utf-8-sig"))))
            check(
                minute_rows[0] == current_rows[0],
                "Minute statistics CSV header mismatch",
            )
            count = sum(row[2] == f"last_{minutes}_minutes" for row in minute_rows[1:])
            check(
                count == minutes * 60,
                f"Expected {minutes * 60} minute rows, got {count}",
            )
        try:
            fetch(backend, "/v1/quality/statistics.csv?minutes=2")
        except urllib.error.HTTPError as error:
            check(
                error.code == 422
                and json.loads(error.read()).get("code") == "INVALID_QUERY",
                "Invalid minutes should return 422 INVALID_QUERY",
            )
        else:
            raise AssertionError("Invalid minutes=2 was accepted")
        return f"date={today}; period/current and 1/5/10/30 minute CSV formats OK"

    record(
        results,
        args,
        "QA-OPS-13",
        statistics_csv,
        coverage="부분: CSV 헤더·분당 행 수·오류 응답; 집계 값·전체 셀 형식 별도 확인",
    )

    def containers():
        if not local_docker:
            raise OSError(
                "Remote Compose containers cannot be inspected from this host"
            )
        output = subprocess.check_output(
            [
                "docker",
                "ps",
                "--filter",
                "label=com.docker.compose.project=cqc-cicd",
                "--format",
                '{{.Label "com.docker.compose.service"}}|{{.Status}}|{{.Names}}',
            ],
            text=True,
            timeout=15,
        )
        found = {}
        for line in output.splitlines():
            service, status, name = line.split("|", 2)
            found[service] = (status, name)
        expected = {
            "mysql",
            "inference",
            "backend",
            "simulator",
            "logistics-mongodb",
            "logistics-api",
            "logistics-web",
        }
        check(
            expected <= found.keys(),
            f"Missing services: {sorted(expected - found.keys())}",
        )
        check(
            all("(healthy)" in found[name][0] for name in expected),
            "One or more services are not healthy",
        )
        for service in expected:
            policy = subprocess.check_output(
                [
                    "docker",
                    "inspect",
                    "--format",
                    "{{.HostConfig.RestartPolicy.Name}}",
                    found[service][1],
                ],
                text=True,
                timeout=15,
            ).strip()
            check(policy == "unless-stopped", f"{service} restart policy is {policy}")
        return f"7 expected services healthy: {', '.join(sorted(expected))}"

    record(results, args, "QA-DEP-01", containers)

    if args.observe_100:

        def observe():
            if not local_docker:
                raise OSError(
                    "Run 100-inspection observation on the Compose host to detect redeployments"
                )

            def running_ids():
                return subprocess.check_output(
                    [
                        "docker",
                        "ps",
                        "-q",
                        "--filter",
                        "label=com.docker.compose.project=cqc-cicd",
                    ],
                    text=True,
                    timeout=15,
                ).splitlines()

            if args.stable_minutes:
                while True:
                    ids = running_ids()
                    check(bool(ids), "No CQC Compose containers are running")
                    created = subprocess.check_output(
                        ["docker", "inspect", "--format", "{{.Created}}", *ids],
                        text=True,
                        timeout=15,
                    ).splitlines()
                    newest = max(
                        datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
                        for value in created
                    )
                    remaining = newest + 60 * args.stable_minutes - time.time()
                    if remaining <= 0:
                        break
                    time.sleep(min(5, remaining))

            initial_ids = set(running_ids())
            start = int(time.time() * 1000)
            deadline = time.monotonic() + args.observe_timeout
            items = []
            while time.monotonic() < deadline:
                query100 = urllib.parse.urlencode(
                    {"pageSize": 200, "snapshotAt": int(time.time() * 1000)}
                )
                listing = get_json(backend, f"/v1/quality/inspections?{query100}")
                items = sorted(
                    (
                        item
                        for item in listing["items"]
                        if item["timestamp"] >= start
                        and not str(item["id"]).startswith("qa-")
                    ),
                    key=lambda item: item["timestamp"],
                )
                if set(running_ids()) != initial_ids:
                    raise OSError(
                        "Compose containers changed during 100-inspection observation"
                    )
                if len(items) >= 100:
                    break
                time.sleep(5)
            check(
                len(items) >= 100,
                f"Only {len(items)} new saved inspections within timeout",
            )
            sample = items[:100]
            check(
                all(
                    item.get("persistence") == "SAVED" and not item.get("faults")
                    for item in sample
                ),
                "Sample contains unsaved or fault-injected inspections",
            )
            gaps = [
                (b["timestamp"] - a["timestamp"]) / 1000 for a, b in pairwise(sample)
            ]
            errors = [
                x for x in sample if x["processingStatus"] in {"TIMEOUT", "ERROR"}
            ]
            reviews = [x for x in sample if x["reviewRequired"]]
            median = statistics.median(gaps)
            p90 = statistics.quantiles(gaps, n=10, method="inclusive")[8]
            throughput = 99 / (
                (sample[-1]["timestamp"] - sample[0]["timestamp"]) / 1000
            )
            # Retain the sample even when the proposed acceptance thresholds fail.
            (args.output_dir / "normal-100.json").write_text(
                json.dumps(
                    {
                        "start": start,
                        "end": sample[-1]["timestamp"],
                        "median_seconds": median,
                        "p90_seconds": p90,
                        "max_seconds": max(gaps),
                        "throughput": throughput,
                        "reviews": len(reviews),
                        "errors": len(errors),
                        "items": sample,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            def spacing():
                check(
                    not errors
                    and abs(median - 2.0) <= 0.1
                    and p90 <= 2.2
                    and abs(throughput - 0.5) <= 0.05,
                    f"median={median:.3f}s p90={p90:.3f}s throughput={throughput:.3f}/s errors={len(errors)}",
                )
                return f"start={start}; end={int(sample[-1]['timestamp'])}; n=100; median={median:.3f}s; p90={p90:.3f}s; throughput={throughput:.3f}/s; timeouts=0"

            record(results, args, "QA-SIM-02", spacing)
            check(not errors, f"{len(errors)} timeout/error inspections")
            check(
                abs(median - 2.0) <= 0.1 and max(gaps) < 4.0,
                f"spacing median={median:.3f}s max={max(gaps):.3f}s",
            )
            check(len(reviews) <= 20, f"review ratio={len(reviews)}%")
            check(abs(throughput - 0.5) <= 0.05, f"throughput={throughput:.3f}/s")
            return (
                f"start={start}; end={int(sample[-1]['timestamp'])}; saved=100; "
                f"median={median:.3f}s; p90={p90:.3f}s; max={max(gaps):.3f}s; "
                f"throughput={throughput:.3f}/s; reviews={len(reviews)}; errors=0"
            )

        record(
            results,
            args,
            "QA-SIM-13",
            observe,
            coverage="제안 기준: 10-08 합의 전 예비 측정",
        )
    else:
        results.append(
            Result(
                "QA-SIM-13",
                "차단",
                args.actor,
                now(),
                args.identity,
                "--observe-100 미지정: 새 정상 100건 측정 미실행",
                "E1",
            )
        )


def isolated_checks(args: argparse.Namespace, results: list[Result]) -> None:
    cases = {
        "QA-INS-12": "tests/api/test_inspection_service.py::test_service_timeout_uses_reinspection_bin_without_retry",
        "QA-INS-13": "tests/api/test_inspection_service.py::test_db_outage_uses_lkg_for_decision_control_and_recovery",
        "QA-INS-15": "tests/api/test_inspection_service.py::test_rejected_normal_control_saves_two_attempts_in_order",
        "QA-SIM-06": "tests/api/test_simulator_faults.py::test_fault_injection_is_request_local_and_retains_only_inference_images",
        "QA-IMG-06": "tests/api/test_review_images.py::test_independent_100_200_retention_and_bulk_api",
        "QA-OPS-10": "tests/api/test_quality_operations_mysql_integration.py::test_mysql_snapshot_statistics_and_both_csv_formats",
        "QA-OPS-13": "tests/api/test_quality_operations_mysql_integration.py::test_mysql_snapshot_statistics_and_both_csv_formats",
        "FR-30-retention": "tests/api/test_history_retention_mysql_integration.py::test_retention_deletes_oldest_batches_and_read_apis_match",
    }
    for case, node in cases.items():
        required_url = (
            "CQC_RETENTION_TEST_DATABASE_URL"
            if case == "FR-30-retention"
            else "CQC_TEST_DATABASE_URL"
            if "_mysql_integration.py" in node
            else None
        )
        if required_url and not os.environ.get(required_url):
            results.append(
                Result(
                    f"{case} (자동 회귀)",
                    "차단",
                    args.actor,
                    now(),
                    args.identity,
                    f"{required_url} 미설정: 격리 MySQL 시험 미실행",
                    "격리 자동 시험",
                )
            )
            continue

        def run(node=node, required_url=required_url, case=case):
            if required_url:
                parsed = urllib.parse.urlparse(os.environ[required_url])
                suffix = "_retention" if case == "FR-30-retention" else "_test"
                if parsed.hostname not in {
                    "127.0.0.1",
                    "localhost",
                } or not parsed.path.endswith(suffix):
                    raise OSError(
                        f"{required_url}: loopback {suffix} test database required"
                    )
            completed = subprocess.run(
                [args.test_python, "-m", "pytest", "-q", "-rs", node],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                timeout=180,
                check=False,
            )
            log = completed.stdout + completed.stderr
            if (
                sys.platform == "win32"
                and case == "QA-IMG-06"
                and completed.returncode != 0
                and "WinError 5" in log
            ):
                (args.output_dir / "qa-img-06-windows.txt").write_text(
                    log, encoding="utf-8"
                )
                linux_name = f"cqc-mo09-linux-{os.getpid()}"
                command = (
                    "python -m pip install --disable-pip-version-check 'pytest>=9.1,<9.2' "
                    "&& mkdir -p /tmp/mo09 "
                    "&& cp -r /workspace/src /workspace/tests /workspace/alembic.ini /tmp/mo09/ "
                    f"&& cd /tmp/mo09 && python -m pytest -q -rs {node}"
                )
                print(
                    "QA-IMG-06: KI-8 Windows rename failure; checking Linux copy",
                    flush=True,
                )
                try:
                    completed = subprocess.run(
                        [
                            "docker",
                            "run",
                            "--rm",
                            "--name",
                            linux_name,
                            "--mount",
                            f"type=bind,source={ROOT},target=/workspace,readonly",
                            "--entrypoint",
                            "sh",
                            args.linux_test_image,
                            "-c",
                            command,
                        ],
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        timeout=180,
                        check=False,
                    )
                finally:
                    subprocess.run(
                        ["docker", "rm", "-f", linux_name],
                        capture_output=True,
                        timeout=30,
                        check=False,
                    )
                log = (
                    "KI-8: Windows failure preserved in qa-img-06-windows.txt; Linux rerun:\n"
                    + completed.stdout
                    + completed.stderr
                )
            for variable in (
                "CQC_TEST_DATABASE_URL",
                "CQC_RETENTION_TEST_DATABASE_URL",
            ):
                url = os.environ.get(variable)
                if url:
                    log = log.replace(url, "<test-db-url>")
                    password = urllib.parse.urlparse(url).password
                    if password:
                        log = log.replace(password, "<redacted>")
            (args.output_dir / f"{case.lower()}-pytest.txt").write_text(
                log, encoding="utf-8"
            )
            output = log.strip().splitlines()
            summary = " | ".join(output[-3:])[:350]
            if "skipped" in summary.lower():
                raise OSError(summary)
            check(completed.returncode == 0, summary)
            return f"자동 회귀: {node}; {summary} (E2 실환경 수용시험과 별개)"

        record(
            results,
            args,
            case,
            run,
            environment="격리 자동 시험",
            coverage="자동 회귀: E2 실환경 수용시험과 별개",
        )


def start_disposable_mysql(args: argparse.Namespace) -> str:
    """Start a loopback-only test server; caller always removes it."""
    name = f"cqc-mo09-mysql-{os.getpid()}"
    password = secrets.token_hex(16)
    subprocess.check_output(
        [
            "docker",
            "run",
            "--rm",
            "-d",
            "--name",
            name,
            "-e",
            f"MYSQL_ROOT_PASSWORD={password}",
            "-e",
            "MYSQL_DATABASE=cqc_test",
            "-p",
            "127.0.0.1::3306",
            "mysql:8.4",
        ],
        text=True,
        timeout=30,
    )
    try:
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            ready = subprocess.run(
                [
                    "docker",
                    "exec",
                    "-e",
                    f"MYSQL_PWD={password}",
                    name,
                    "mysql",
                    "--protocol=TCP",
                    "-h127.0.0.1",
                    "-uroot",
                    "-Nse",
                    "SELECT 1",
                ],
                capture_output=True,
                timeout=10,
                check=False,
            )
            if ready.returncode == 0:
                break
            time.sleep(2)
        else:
            raise TimeoutError("Disposable MySQL did not become ready")
        subprocess.check_call(
            [
                "docker",
                "exec",
                "-e",
                f"MYSQL_PWD={password}",
                name,
                "mysql",
                "-uroot",
                "-e",
                "CREATE DATABASE cqc_retention",
            ],
            stdout=subprocess.DEVNULL,
            timeout=15,
        )
        address = subprocess.check_output(
            ["docker", "port", name, "3306/tcp"],
            text=True,
            timeout=10,
        ).strip()
        port = int(address.rsplit(":", 1)[1])
        for variable, database in (
            ("CQC_TEST_DATABASE_URL", "cqc_test"),
            ("CQC_RETENTION_TEST_DATABASE_URL", "cqc_retention"),
        ):
            url = f"mysql+pymysql://root:{password}@127.0.0.1:{port}/{database}"
            os.environ[variable] = url
            migration_env = os.environ.copy()
            migration_env["DATABASE_URL"] = url
            subprocess.run(
                [args.test_python, "-m", "alembic", "upgrade", "head"],
                cwd=ROOT,
                env=migration_env,
                check=True,
                capture_output=True,
                timeout=90,
            )
        return name
    except BaseException:
        subprocess.run(
            ["docker", "rm", "-f", name], capture_output=True, timeout=30, check=False
        )
        raise


def write_results(results: list[Result], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    qa_document = (ROOT / "docs/wbs/reference/ALL/qa-test-cases.md").read_text(
        encoding="utf-8"
    )
    owners = dict(
        re.findall(
            r"^\| (QA-[A-Z]+-\d+(?:-\d+)?) \| (DM|BE|FE|MO) \|",
            qa_document,
            re.MULTILINE,
        )
    )

    def owner(row: Result) -> str:
        return owners.get(
            row.qa_case, "BE" if row.qa_case == "FR-30-retention" else "MO"
        )

    (output_dir / "results.json").write_text(
        json.dumps(
            [
                {
                    **asdict(row),
                    "qa_case": row.qa_case,
                    "owner": owner(row),
                    "record_status": row.record_status,
                }
                for row in results
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    lines = [
        "| 케이스 | 담당 | 결과 (통과/실패/차단) | 실행자 | 일시 | 커밋·모델 | 비고·결함 번호 |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in results:
        values = (
            row.qa_case,
            owner(row),
            row.record_status,
            row.actor,
            row.time_kst,
            row.commit_model,
            f"[{row.environment}] 관찰={row.status}; 범위={row.coverage}; {row.note}",
        )
        lines.append(
            "| "
            + " | ".join(
                str(value).replace("|", "/").replace("\n", " ") for value in values
            )
            + " |"
        )
    (output_dir / "all04-rows.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"Results: {output_dir.resolve()}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("live", "isolated", "all"), default="live")
    parser.add_argument("--backend", default="http://127.0.0.1:8000")
    parser.add_argument("--inference", default="http://127.0.0.1:8001")
    parser.add_argument("--actor", default="MO-09 automation")
    parser.add_argument(
        "--linux-test-image",
        default="cqc-cicd-backend:latest",
        help="Disposable Linux dependency image for the known Windows KI-8 case",
    )
    parser.add_argument(
        "--expected-model-version", default="cqc-apple-separate12-focal-v2-cal-20260930"
    )
    parser.add_argument(
        "--expected-checkpoint-sha256",
        default="b254206e4091732a49c5db02c12e5fb6dc3d996dbce694c2e82d442a2ba8753a",
    )
    default_python = (
        ROOT
        / ".venv"
        / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    )
    parser.add_argument(
        "--test-python",
        default=str(default_python if default_python.exists() else sys.executable),
    )
    default_output = (
        ROOT
        / "outputs"
        / "mo09-acceptance"
        / datetime.now(KST).strftime("%Y%m%d-%H%M%S")
    )
    parser.add_argument("--output-dir", type=Path, default=default_output)
    parser.add_argument("--observe-100", action="store_true")
    parser.add_argument("--observe-timeout", type=int, default=300)
    parser.add_argument("--stable-minutes", type=int, default=0)
    parser.add_argument(
        "--disposable-mysql",
        action="store_true",
        help="Create and remove a loopback-only MySQL for isolated DB tests",
    )
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.sha = git_sha()
    dirty = bool(
        subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT).strip()
    )
    local_identity = (
        f"local {args.sha[:12]}{' + uncommitted' if dirty else ''} / model unknown"
    )
    args.identity = local_identity
    (args.output_dir / "run.json").write_text(
        json.dumps(
            {
                "source_sha": args.sha,
                "working_tree_dirty": dirty,
                "started_kst": now(),
                "mode": args.mode,
                "actor": args.actor,
                "deployed_sha": "unverified",
                "table": "QA 6.4 / seven columns",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    results: list[Result] = []
    if args.mode in {"live", "all"}:
        try:
            live_checks(args, results)
        except (OSError, ValueError, TypeError, urllib.error.URLError) as error:
            results.append(
                Result(
                    "MO-09-live",
                    "차단",
                    args.actor,
                    now(),
                    args.identity,
                    str(error),
                    "E1",
                )
            )
    if args.mode in {"isolated", "all"}:
        args.identity = local_identity
        disposable = None
        try:
            if args.disposable_mysql:
                disposable = start_disposable_mysql(args)
            isolated_checks(args, results)
        except (OSError, subprocess.SubprocessError, TimeoutError) as error:
            results.append(
                Result(
                    "MO-09-disposable-MySQL",
                    "차단",
                    args.actor,
                    now(),
                    args.identity,
                    f"Disposable MySQL setup failed: {type(error).__name__}",
                    "격리 자동 시험",
                )
            )
        finally:
            if disposable:
                subprocess.run(
                    ["docker", "rm", "-f", disposable],
                    capture_output=True,
                    timeout=30,
                    check=False,
                )
    write_results(results, args.output_dir)
    if any(row.status == "실패" for row in results):
        return 1
    return 2 if any(row.status == "차단" for row in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
