"""SIM-06 CLI 선택과 기존 증거 보호를 서비스 접속 없이 검증한다."""

import asyncio
import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def runner(monkeypatch):
    script_dir = Path(__file__).resolve().parents[2] / "scripts/qa"
    monkeypatch.syspath_prepend(str(script_dir))
    spec = importlib.util.spec_from_file_location(
        "mo09_e2_faults", script_dir / "run_mo09_e2_faults.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def control_hook(monkeypatch):
    script = Path(__file__).resolve().parents[2] / "scripts/qa/trace_mo09_control.py"
    spec = importlib.util.spec_from_file_location("mo09_control_trace", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def arguments(output, *extra):
    return ["--project", "cqc-mo09-e2-unit", "--output", str(output), *extra]


def forbid_connections(runner, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("CLI validation must precede Docker/API access")

    monkeypatch.setattr(runner, "gate", forbidden)
    monkeypatch.setattr(runner, "api", forbidden)


def test_default_preserves_all_faults(runner, tmp_path):
    args = runner.parse_args(arguments(tmp_path / "new-run"))
    assert args.faults == tuple(runner.FAULTS)
    assert not args.output.exists()


@pytest.mark.parametrize(
    "fault",
    ["CONTROL_REJECTED", "CONTROL_NO_RESPONSE", "CONTROL_FAILED", "DB_ERROR"],
)
def test_selects_one_supplement_fault(runner, tmp_path, fault):
    args = runner.parse_args(arguments(tmp_path / "new-run", "--faults", fault))
    assert args.faults == (fault,)


def test_repeated_options_preserve_order(runner, tmp_path):
    args = runner.parse_args(
        arguments(
            tmp_path / "new-run",
            "--faults",
            "CONTROL_FAILED",
            "--faults",
            "DB_ERROR",
        )
    )
    assert args.faults == ("CONTROL_FAILED", "DB_ERROR")


@pytest.mark.parametrize("fault", ["UNKNOWN", "INFERENCE_ERROR"])
def test_invalid_selection_rejected_before_access(runner, monkeypatch, tmp_path, fault):
    forbid_connections(runner, monkeypatch)
    output = tmp_path / "new-run"
    with pytest.raises(SystemExit) as exc:
        runner.main(arguments(output, "--faults", fault))
    assert exc.value.code == 2
    assert not output.exists()


@pytest.mark.parametrize("repeated_flag", [False, True])
def test_duplicate_selection_rejected_before_access(
    runner, monkeypatch, tmp_path, repeated_flag
):
    forbid_connections(runner, monkeypatch)
    output = tmp_path / "new-run"
    extra = ["--faults", "DB_ERROR"]
    extra += ["--faults", "DB_ERROR"] if repeated_flag else ["DB_ERROR"]
    with pytest.raises(SystemExit) as exc:
        runner.main(arguments(output, *extra))
    assert exc.value.code == 2
    assert not output.exists()


@pytest.mark.parametrize("directory", [False, True])
def test_existing_output_preserved_before_access(
    runner, monkeypatch, tmp_path, directory
):
    output = tmp_path / "previous-run"
    if directory:
        output.mkdir()
        evidence = output / "fault-evidence.json"
    else:
        evidence = output
    evidence.write_bytes(b"original evidence\r\n")
    forbid_connections(runner, monkeypatch)
    with pytest.raises(SystemExit) as exc:
        runner.main(arguments(output))
    assert exc.value.code == 2
    assert evidence.read_bytes() == b"original evidence\r\n"


def test_output_race_preserved_before_api(runner, monkeypatch, tmp_path):
    output = tmp_path / "new-run"
    evidence = output / "run.json"

    def gate(*args):
        output.mkdir()
        evidence.write_bytes(b"another run")
        return {"Image": "unit-image"}

    def forbidden(*args, **kwargs):
        pytest.fail("Output reservation must precede API access")

    monkeypatch.setattr(runner, "gate", gate)
    monkeypatch.setattr(runner, "api", forbidden)
    with pytest.raises(FileExistsError):
        runner.main(arguments(output))
    assert evidence.read_bytes() == b"another run"


@pytest.mark.parametrize("selected", [None, ["CONTROL_FAILED", "DB_ERROR"]])
def test_dispatch_and_reports_include_only_selected_faults(
    runner, monkeypatch, tmp_path, capsys, selected
):
    dispatched = []
    output = tmp_path / "new-run"
    monkeypatch.setattr(runner, "gate", lambda *args: {"Image": "unit-image"})
    monkeypatch.setattr(runner, "git_sha", lambda: "unit-sha")
    monkeypatch.setattr(runner.subprocess, "check_output", lambda *a, **k: b"")
    monkeypatch.setattr(
        runner,
        "snapshot",
        lambda *args: (
            {
                "revision": 0,
                "state": {
                    "running": True,
                    "faults": [],
                    "concurrency": 1,
                },
            },
            [],
        ),
    )

    def api(base, path, payload=None):
        if path == "/health":
            return {"model_version": "unit-model"}
        assert path == "/v1/quality/simulator"
        assert payload["scope"] == "NEXT"
        dispatched.extend(payload["faults"])
        return {"revision": 1}

    def unobserved(*args):
        raise AssertionError("No runtime observation in this CLI unit test")

    monkeypatch.setattr(runner, "api", api)
    monkeypatch.setattr(runner, "wait_for", unobserved)
    extra = [] if selected is None else ["--faults", *selected]
    with pytest.raises(SystemExit) as exc:
        runner.main(arguments(output, *extra))
    assert exc.value.code == 1
    expected = list(runner.FAULTS) if selected is None else selected
    assert dispatched == expected
    metadata = json.loads((output / "run.json").read_text(encoding="utf-8"))
    results = json.loads((output / "fault-evidence.json").read_text(encoding="utf-8"))
    assert metadata["selected_faults"] == expected
    assert [row["fault"] for row in results] == expected
    assert (output / "results.json").exists()
    assert (output / "all04-rows.md").exists()
    assert "Selected faults: " + ", ".join(expected) in capsys.readouterr().out


def controls():
    return [
        {
            "id": 1,
            "inspection_id": "fault-id",
            "command_id": "command-1",
            "attempt_no": 1,
            "requested_bin_code": "DEMO_BIN_01",
            "control_status": "REJECTED",
            "requested_at": "2026-10-14 00:00:00.001",
        },
        {
            "id": 2,
            "inspection_id": "fault-id",
            "command_id": "command-2",
            "attempt_no": 2,
            "requested_bin_code": "TEST_REINSPECTION_BIN",
            "control_status": "SUCCEEDED",
            "requested_at": "2026-10-14 00:00:00.002",
        },
    ]


def test_control_rows_and_mysql_query(runner, monkeypatch):
    rows = controls()
    calls = []

    def command(args, **kwargs):
        calls.append(args)
        return "\n".join(json.dumps(row) for row in rows)

    monkeypatch.setattr(runner.subprocess, "check_output", command)
    actual = runner.mysql_records(
        "unit-project", "control_attempts", runner.CONTROL_FIELDS, "fault-id"
    )
    assert actual == rows
    runner.validate_controls(actual, "fault-id", "CONTROL_REJECTED", 2)
    assert calls[0][-1].endswith(" ORDER BY attempt_no, id")
    assert 'MYSQL_PWD="$MYSQL_PASSWORD"' in calls[0][5]
    assert "DROP TABLE" not in runner.sql_value("'; DROP TABLE inspections; --")


@pytest.mark.parametrize(
    "change", ["order", "duplicate", "count", "id", "status", "bin", "missing"]
)
def test_bad_control_evidence_rejected(runner, change):
    rows = controls()
    count = 2
    if change == "order":
        rows.reverse()
    elif change == "duplicate":
        rows[1]["command_id"] = rows[0]["command_id"]
    elif change == "count":
        count = 1
    elif change == "id":
        rows[0]["inspection_id"] = "other"
    elif change == "status":
        rows[1]["control_status"] = "FAILED"
    elif change == "bin":
        rows[1]["requested_bin_code"] = rows[0]["requested_bin_code"]
    else:
        del rows[0]["requested_at"]
    with pytest.raises((AssertionError, KeyError)):
        runner.validate_controls(rows, "fault-id", "CONTROL_REJECTED", count)


@pytest.mark.parametrize("status", ["NO_RESPONSE", "FAILED"])
def test_single_persisted_control_is_not_call_measurement(runner, status):
    row = controls()[0] | {"control_status": status}
    runner.validate_controls([row], "fault-id", "CONTROL_" + status, 1)


@pytest.mark.parametrize(
    "case", ["valid", "missing", "wrong-status", "contribution", "wrong-bin"]
)
def test_no_response_statistics_target_only(runner, monkeypatch, case):
    row = {
        "inspection_id": "fault-id",
        "control_status": "NO_RESPONSE",
        "target_bin_code": "DEMO_BIN_01",
        "completed_at": "2026-10-14 00:00:01",
        "persistence_status": "SUCCEEDED",
    }
    if case == "wrong-status":
        row["control_status"] = "SUCCEEDED"
    if case == "wrong-bin":
        row["target_bin_code"] = "OTHER"
    rows = [] if case == "missing" else [row]
    monkeypatch.setattr(runner, "mysql_records", lambda *a: rows)
    queries = []

    def query(project, sql):
        queries.append(sql)
        return "1" if case == "contribution" else "0"

    monkeypatch.setattr(runner, "mysql_query", query)
    entry = {"fault_row": {"bin": "DEMO_BIN_01"}}
    if case == "valid":
        runner.collect_no_response_stats("unit", "fault-id", entry)
        assert entry["successful_bin_contribution"]["count"] == 0
        assert "target inspection only" in entry["successful_bin_contribution"]["scope"]
    else:
        with pytest.raises(AssertionError):
            runner.collect_no_response_stats("unit", "fault-id", entry)
    assert entry["statistics_inspection_rows"] == rows
    assert runner.sql_value("fault-id") in queries[0]


def http_events():
    events = []
    for index, fault in enumerate((["DB_ERROR"], [])):
        start = {
            "kind": "request_start",
            "inspection_id": f"auto-{index}",
            "source_reference": f"bundle-{index}",
            "faults": fault,
            "started_utc": f"2026-10-14T00:00:0{index}+00:00",
            "start_monotonic": index * 2.0,
        }
        events.append(start)
        events.append(
            start
            | {
                "kind": "request_end",
                "end_monotonic": index * 2.0 + 1,
                "http_status": 200,
                "error_type": None,
                "response": {
                    "inspection_id": f"auto-{index}",
                    "persistence_status": "FAILED" if fault else "SUCCEEDED",
                    "inspection_status": "COMPLETED",
                    "control_status": "SUCCEEDED",
                },
            }
        )
    return events


def test_http_stream_read_only_new_slice(runner, tmp_path):
    path = tmp_path / "http-events.jsonl"
    previous = b'{"previous_run": true}\n'
    path.write_bytes(
        previous
        + b"".join(
            json.dumps(e | {"authorization": "secret"}).encode() + b"\n"
            for e in http_events()
        )
        + b'{"incomplete":'
    )
    original = path.read_bytes()
    trace = runner.read_http_events(path, len(previous))
    assert trace["incomplete_tail_bytes"] > 0
    assert len(trace["events"]) == 4
    assert "secret" not in json.dumps(trace)
    assert path.read_bytes() == original
    pair = runner.db_error_sequence(trace["events"])
    assert [e["inspection_id"] for e in pair[:2]] == ["auto-0", "auto-1"]


@pytest.mark.parametrize(
    "case",
    [
        "no-target",
        "no-next",
        "no-end",
        "duplicate",
        "wrong-id",
        "wrong-fault",
        "not-failed",
        "not-saved",
        "overlap",
    ],
)
def test_db_error_sequence_requires_immediate_complete_pair(runner, case):
    events = http_events()
    if case == "no-target":
        events[0]["faults"] = []
    elif case == "no-next":
        events = events[:2]
    elif case == "no-end":
        events = events[:-1]
    elif case == "duplicate":
        events.append(events[0])
    elif case == "wrong-id":
        events[1]["response"]["inspection_id"] = "other"
    elif case == "wrong-fault":
        events[2]["faults"] = ["CONTROL_FAILED"]
        events[3]["faults"] = ["CONTROL_FAILED"]
    elif case == "not-failed":
        events[1]["response"]["persistence_status"] = "SUCCEEDED"
    elif case == "not-saved":
        events[3]["response"]["persistence_status"] = "FAILED"
    else:
        events[2]["start_monotonic"] = 0.5
        events[3]["start_monotonic"] = 0.5
    if case in {"no-target", "no-next", "no-end"}:
        assert runner.db_error_sequence(events) is None
    else:
        with pytest.raises(AssertionError):
            runner.db_error_sequence(events)


def test_db_error_successor_matches_real_status_contract(runner):
    from src.api.schemas.inspection_results import (
        InspectionDecisionReason,
        InspectionStatus,
    )

    events = http_events()
    pair = runner.db_error_sequence(events)
    assert pair[3]["response"]["inspection_status"] == InspectionStatus.COMPLETED.value
    assert InspectionDecisionReason.NORMAL.value != InspectionStatus.COMPLETED.value


@pytest.mark.parametrize(
    "status",
    ["NORMAL", "PROCESSING", "REINSPECTION_REQUIRED", "ERROR", "TIMEOUT", None],
)
def test_db_error_successor_rejects_non_completed_http_status(runner, status):
    events = http_events()
    events[3]["response"]["inspection_status"] = status
    with pytest.raises(AssertionError, match="not normal/control succeeded"):
        runner.db_error_sequence(events)


def test_missing_http_input_rejected_before_access(runner, monkeypatch, tmp_path):
    forbid_connections(runner, monkeypatch)
    with pytest.raises(SystemExit) as exc:
        runner.main(
            arguments(tmp_path / "new-run", "--http-events", str(tmp_path / "missing"))
        )
    assert exc.value.code == 2


def test_truncated_http_input_rejected(runner, tmp_path):
    path = tmp_path / "events"
    path.write_bytes(b"\n")
    with pytest.raises(AssertionError, match="truncated"):
        runner.read_http_events(path, 2)


@pytest.mark.parametrize(
    "case", ["normal", "bad-json", "write-error", "http-error", "cancel", "other-url"]
)
def test_docker_http_hook_preserves_request_and_response(control_hook, case):
    events, calls = [], []
    error = (
        asyncio.CancelledError() if case == "cancel" else RuntimeError("secret-error")
    )
    body = {
        "inspection_id": "auto-id",
        "persistence_status": "FAILED",
        "secret": "response-secret",
    }

    def response_json():
        if case == "bad-json":
            raise ValueError("secret-json")
        return body

    response = SimpleNamespace(status_code=200, json=response_json)

    class Client:
        async def post(self, url, *args, **kwargs):
            calls.append((url, args, kwargs))
            if case in {"http-error", "cancel"}:
                raise error
            return response

    def write(event):
        if case == "write-error":
            raise OSError("secret-disk")
        events.append(event)

    trace = control_hook.ControlTrace(write)
    control_hook.install_http_trace(Client, trace, "http://backend:8000")
    url = (
        "http://backend:8000/health"
        if case == "other-url"
        else "http://backend:8000/v1/inspections"
    )
    payload = {
        "data": {"inspection_id": "auto-id", "metadata": "unchanged"},
        "files": [object()],
        "headers": {
            "X-CQC-Simulator-Token": "token-secret",
            "X-CQC-Simulator-Bundle-ID": "bundle-id",
            "X-CQC-Simulator-Faults": "DB_ERROR",
        },
    }
    if case in {"http-error", "cancel"}:
        with pytest.raises(type(error)) as caught:
            asyncio.run(Client().post(url, **payload))
        assert caught.value is error
    else:
        assert asyncio.run(Client().post(url, **payload)) is response
    assert calls == [(url, (), payload)]
    if case in {"write-error", "other-url"}:
        assert events == []
        assert trace.errors == (2 if case == "write-error" else 0)
    else:
        assert [e["kind"] for e in events] == ["request_start", "request_end"]
        assert events[0]["inspection_id"] == "auto-id"
        assert events[0]["source_reference"] == "bundle-id"
        assert events[0]["faults"] == ["DB_ERROR"]
        assert events[1]["sequence_no"] == 2
        assert "secret" not in json.dumps(events)
        if case == "bad-json":
            assert events[1]["response_parse_error"] == "ValueError"
    with pytest.raises(ValueError, match="already installed"):
        control_hook.install_http_trace(Client, trace, "http://backend:8000")


@pytest.mark.parametrize("change", ["gap", "pid", "error"])
def test_http_continuity_metadata_rejected(runner, change):
    events = [
        e | {"sequence_no": i + 1, "pid": 100, "recording_errors_so_far": 0}
        for i, e in enumerate(http_events())
    ]
    if change == "gap":
        events[-1]["sequence_no"] += 1
    elif change == "pid":
        events[-1]["pid"] = 101
    else:
        events[-1]["recording_errors_so_far"] = 1
    with pytest.raises(AssertionError):
        runner.db_error_sequence(events)


def test_http_continuity_metadata_preserved(runner, tmp_path):
    events = [
        e | {"sequence_no": i + 10, "pid": 100, "recording_errors_so_far": 0}
        for i, e in enumerate(http_events())
    ]
    path = tmp_path / "http-events.jsonl"
    path.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    trace = runner.read_http_events(path, 0)
    assert trace["events"][0]["sequence_no"] == 10
    assert runner.db_error_sequence(trace["events"])[0]["inspection_id"] == "auto-0"


@pytest.mark.parametrize("service", ["backend", "simulator"])
def test_trace_check_only_never_starts_or_creates_files(
    control_hook, monkeypatch, tmp_path, service
):
    monkeypatch.setenv("CQC_QA_CONTROL_TRACE", "1")
    monkeypatch.setenv("CQC_QA_HTTP_TRACE", "1")
    monkeypatch.setenv("SIMULATOR_BACKEND_URL", "http://backend:8000")
    monkeypatch.setattr(
        control_hook.runpy,
        "run_module",
        lambda *a, **k: pytest.fail("Static check must not start services"),
    )
    output = tmp_path / "new-run"
    control_hook.main(
        [
            "--project",
            "cqc-mo09-e2-unit",
            "--output",
            str(output),
            "--source-sha",
            "a" * 40,
            "--image-id",
            "sha256:" + "b" * 64,
            "--service",
            service,
            "--check-only",
        ]
    )
    assert not output.exists()


def test_simulator_trace_entrypoint(control_hook, monkeypatch, tmp_path):
    import httpx

    monkeypatch.setattr(httpx.AsyncClient, "post", httpx.AsyncClient.post)
    monkeypatch.setenv("CQC_QA_HTTP_TRACE", "1")
    monkeypatch.setenv("SIMULATOR_BACKEND_URL", "http://backend:8000")
    launches, finish = [], []
    monkeypatch.setattr(
        control_hook.runpy, "run_module", lambda name, **kw: launches.append(name)
    )
    monkeypatch.setattr(control_hook.atexit, "register", finish.append)
    output = tmp_path / "http-run"
    control_hook.main(
        [
            "--project",
            "cqc-mo09-e2-unit",
            "--output",
            str(output),
            "--source-sha",
            "a" * 40,
            "--image-id",
            "sha256:" + "b" * 64,
            "--service",
            "simulator",
        ]
    )
    assert launches == ["src.simulator.main"]
    assert (output / "http-events.jsonl").is_file()
    meta = json.loads((output / "trace-run.json").read_text())
    assert meta["http_target"] == "http://backend:8000/v1/inspections"
    assert len(meta["product_sha256"]) == 3
    finish[0]()


@pytest.mark.parametrize("enabled", ["0", "1"])
def test_compose_connection_static_config(tmp_path, enabled):
    if shutil.which("docker") is None:
        pytest.skip("Docker Compose CLI is required for offline config rendering")
    root = Path(__file__).resolve().parents[2]
    project = "cqc-mo09-e2-unit-static"
    run_root = tmp_path / "new-run"
    environment = os.environ.copy()
    environment.update(
        {
            "CQC_QA_PROJECT": project,
            "CQC_QA_SOURCE_SHA": "a" * 40,
            "CQC_QA_MYSQL_IMAGE": "sha256:" + "b" * 64,
            "CQC_QA_BACKEND_IMAGE": "sha256:" + "c" * 64,
            "CQC_QA_INFERENCE_IMAGE": "sha256:" + "d" * 64,
            "CQC_QA_SIMULATOR_IMAGE": "sha256:" + "e" * 64,
            "CQC_QA_MYSQL_PASSWORD": "static-only-not-a-secret",
            "CQC_QA_MYSQL_ROOT_PASSWORD": "static-only-not-a-secret",
            "CQC_QA_FAULT_TOKEN": "static-only-not-a-secret",
            "CQC_QA_RUN_ROOT": str(run_root),
            "SIMULATOR_DATASET_HOST_PATH": str(tmp_path / "dataset"),
            "CQC_QA_CONTROL_TRACE": enabled,
            "CQC_QA_HTTP_TRACE": enabled,
        }
    )
    result = subprocess.run(
        [
            "docker",
            "compose",
            "--project-directory",
            str(root),
            "--env-file",
            os.devnull,
            "-f",
            str(
                root
                / "docs/wbs/results/qa-mo-sim04-sim05-20261013/isolated-compose.json"
            ),
            "-f",
            str(root / "scripts/qa/compose.sim06.yaml"),
            "config",
            "--format",
            "json",
        ],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    config = json.loads(result.stdout)
    assert config["name"] == project
    services = config["services"]
    assert set(services) == {"mysql", "inference", "backend", "simulator"}
    for name, port in (("backend", 18000), ("inference", 18001), ("simulator", 18002)):
        assert len(services[name]["ports"]) == 1
        assert services[name]["ports"][0]["host_ip"] == "127.0.0.1"
        assert int(services[name]["ports"][0]["published"]) == port
    assert config["networks"]["qa"]["internal"] is True
    assert all(
        v["name"].startswith(project + "_") and not v.get("external")
        for v in config["volumes"].values()
    )
    assert len(config["volumes"]) == 6
    for name in services:
        assert "build" not in services[name]
        assert services[name]["pull_policy"] == "never"
        assert services[name]["restart"] == "no"
    for name in ("backend", "simulator"):
        mounts = {v["target"]: v for v in services[name]["volumes"]}
        assert mounts["/app/qa-trace.py"]["read_only"] is True
        # Some Compose versions omit the default false value from config output.
        assert mounts["/qa-evidence"].get("bind", {}).get("create_host_path", False) is False
        assert "exec python /app/qa-trace.py" in services[name]["command"][2]
    assert services["backend"]["command"][2].index("--check-only") < services[
        "backend"
    ]["command"][2].index("alembic upgrade head")
    assert "exec python -m src.api.main" in services["backend"]["command"][2]
    assert "exec python -m src.simulator.main" in services["simulator"]["command"][2]
    assert services["backend"]["environment"]["CQC_QA_CONTROL_TRACE"] == enabled
    assert services["simulator"]["environment"]["CQC_QA_HTTP_TRACE"] == enabled
    assert (
        services["simulator"]["environment"]["SIMULATOR_BACKEND_URL"]
        == "http://backend:8000"
    )
    dataset = next(
        v for v in services["simulator"]["volumes"] if v["target"] == "/data/dataset"
    )
    assert dataset["type"] == "bind" and dataset["read_only"] is True
    assert not run_root.exists()


@pytest.mark.parametrize("status", ["REJECTED", "NO_RESPONSE", "FAILED"])
def test_hook_covers_existing_and_new_mock_instances(control_hook, monkeypatch, status):
    from src.api.control.virtual_control import MockVirtualControl
    from src.api.schemas.control import VirtualControlRequest
    from src.api.schemas.inspection_results import ControlStatus

    monkeypatch.setattr(MockVirtualControl, "send", MockVirtualControl.send)
    existing = MockVirtualControl([ControlStatus(status), ControlStatus.SUCCEEDED])
    events = []
    trace = control_hook.ControlTrace(events.append)
    trace.install(MockVirtualControl)
    request = VirtualControlRequest(
        inspection_id="trace-id", target_bin_code="DEMO_BIN_01"
    )

    async def run():
        first = await existing.send(request)
        second = await existing.send(request)
        third = await MockVirtualControl().send(
            request.model_copy(update={"inspection_id": "new-id"})
        )
        return first, second, third

    first, second, third = asyncio.run(run())
    assert first.control_status.value == status
    assert second.control_status is third.control_status is ControlStatus.SUCCEEDED
    assert [e["kind"] for e in events] == ["send_enter", "send_return"] * 3
    assert [e["call_no"] for e in events] == [1, 1, 2, 2, 1, 1]
    assert [e["sequence_no"] for e in events] == list(range(1, 7))
    assert all(
        e["requested_bin_code"] == "DEMO_BIN_01" and e["utc"] and e["pid"]
        for e in events
    )
    assert existing.call_count == 2
    assert trace.errors == 0
    with pytest.raises(ValueError, match="already installed"):
        trace.install(MockVirtualControl)


@pytest.mark.parametrize(
    "error", [RuntimeError("secret-message"), asyncio.CancelledError()]
)
def test_hook_preserves_exception_and_cancellation(control_hook, error):
    events = []

    class Control:
        async def send(self, request):
            raise error

    trace = control_hook.ControlTrace(events.append)
    trace.install(Control)
    request = SimpleNamespace(inspection_id="error-id", target_bin_code="BIN")
    with pytest.raises(type(error)) as caught:
        asyncio.run(Control().send(request))
    assert caught.value is error
    assert [e["kind"] for e in events] == ["send_enter", "send_raise"]
    assert events[1]["error_type"] == type(error).__name__
    assert "secret-message" not in json.dumps(events)


@pytest.mark.parametrize(
    "failure", [OSError("disk-secret"), ValueError("serialization-secret")]
)
def test_recording_failure_keeps_exact_response_and_single_call(control_hook, failure):
    response = SimpleNamespace(control_status=SimpleNamespace(value="SUCCEEDED"))
    calls = []

    class Control:
        async def send(self, request):
            calls.append(request)
            return response

    def broken_write(event):
        raise failure

    trace = control_hook.ControlTrace(broken_write)
    trace.install(Control)
    request = SimpleNamespace(inspection_id="write-id", target_bin_code="BIN")
    assert asyncio.run(Control().send(request)) is response
    assert calls == [request]
    assert trace.errors == 2


@pytest.mark.parametrize("invalid", ["opt-in", "project", "source", "image", "output"])
def test_hook_preflight_rejects_before_backend_import(
    control_hook, monkeypatch, tmp_path, invalid
):
    monkeypatch.setenv("CQC_QA_CONTROL_TRACE", "1")
    output = tmp_path / "trace-run"
    project, source, image = "cqc-mo09-e2-unit", "a" * 40, "sha256:" + "b" * 64
    if invalid == "opt-in":
        monkeypatch.delenv("CQC_QA_CONTROL_TRACE")
    elif invalid == "project":
        project = "cqc"
    elif invalid == "source":
        source = "unknown"
    elif invalid == "image":
        image = "latest"
    else:
        output.mkdir()
        (output / "original").write_bytes(b"preserved")
    monkeypatch.setattr(
        control_hook.runpy,
        "run_module",
        lambda *a, **k: pytest.fail("Must not start Backend"),
    )
    with pytest.raises(SystemExit) as caught:
        control_hook.main(
            [
                "--project",
                project,
                "--output",
                str(output),
                "--source-sha",
                source,
                "--image-id",
                image,
            ]
        )
    assert caught.value.code == 2
    if invalid == "output":
        assert (output / "original").read_bytes() == b"preserved"
    else:
        assert not output.exists()


def test_hook_entrypoint_provenance_without_service_start(
    control_hook, monkeypatch, tmp_path
):
    from src.api.control.virtual_control import MockVirtualControl

    monkeypatch.setattr(MockVirtualControl, "send", MockVirtualControl.send)
    monkeypatch.setenv("CQC_QA_CONTROL_TRACE", "1")
    launches, finish = [], []
    monkeypatch.setattr(
        control_hook.runpy, "run_module", lambda name, **kw: launches.append((name, kw))
    )
    monkeypatch.setattr(control_hook.atexit, "register", finish.append)
    output = tmp_path / "trace-run"
    control_hook.main(
        [
            "--project",
            "cqc-mo09-e2-unit",
            "--output",
            str(output),
            "--source-sha",
            "a" * 40,
            "--image-id",
            "sha256:" + "b" * 64,
        ]
    )
    assert launches == [("src.api.main", {"run_name": "__main__"})]
    metadata = json.loads((output / "trace-run.json").read_text())
    assert metadata["enabled"] is True
    assert len(metadata["product_sha256"]) == 4
    assert len(metadata["hook_sha256"]) == 64
    assert "declared" in " ".join(metadata)
    finish[0]()
    assert (
        json.loads((output / "trace-status.json").read_text())["recording_errors"] == 0
    )


@pytest.mark.parametrize(
    "status,count", [("REJECTED", 2), ("NO_RESPONSE", 1), ("FAILED", 1)]
)
def test_hook_preserves_real_control_policy_order(
    control_hook, monkeypatch, status, count
):
    from src.api.control.virtual_control import MockVirtualControl
    from src.api.schemas.inspection_results import ControlStatus
    from src.api.services.control_policy import execute_virtual_control

    monkeypatch.setattr(MockVirtualControl, "send", MockVirtualControl.send)
    events = []
    trace = control_hook.ControlTrace(events.append)
    trace.install(MockVirtualControl)
    control = MockVirtualControl([ControlStatus(status), ControlStatus.SUCCEEDED])
    result = asyncio.run(
        execute_virtual_control(
            control,
            inspection_id="policy-id",
            target_bin_code="DEMO_BIN_01",
            reinspection_bin_code="TEST_REINSPECTION_BIN",
        )
    )
    entered = [e for e in events if e["kind"] == "send_enter"]
    returned = [e for e in events if e["kind"] == "send_return"]
    assert (
        len(entered)
        == len(returned)
        == len(result.traces)
        == control.call_count
        == count
    )
    assert [e["call_no"] for e in entered] == list(range(1, count + 1))
    assert [e["requested_bin_code"] for e in entered] == (
        ["DEMO_BIN_01", "TEST_REINSPECTION_BIN"] if count == 2 else ["DEMO_BIN_01"]
    )
    assert [e["control_status"] for e in returned] == (
        ["REJECTED", "SUCCEEDED"] if count == 2 else [status]
    )


def test_malformed_http_preserves_slice_metadata(runner, tmp_path):
    path = tmp_path / "events"
    path.write_bytes(json.dumps(http_events()[0]).encode() + b"\ninvalid\n")
    trace = runner.read_http_events(path, 0)
    assert len(trace["events"]) == 1
    assert trace["parse_error"]["line_in_slice"] == 2
    assert trace["end_offset"] == path.stat().st_size
    assert len(trace["sha256"]) == 64


@pytest.mark.parametrize(
    "case",
    [
        "no-response",
        "db-no-stream",
        "db-stream",
        "db-unexpected-row",
        "image-mismatch",
        "db-query-error",
        "db-processing",
        "db-reinspection",
        "db-error-status",
        "db-normal-status",
        "db-missing-status",
    ],
)
def test_main_preserves_collected_evidence_and_partial_status(
    runner, monkeypatch, tmp_path, case
):
    bad_db_statuses = {
        "db-processing": "PROCESSING",
        "db-reinspection": "REINSPECTION_REQUIRED",
        "db-error-status": "ERROR",
        "db-normal-status": "NORMAL",
        "db-missing-status": None,
    }
    with_stream = case in {"db-stream", "db-unexpected-row"} or case in bad_db_statuses
    fault = (
        "DB_ERROR"
        if case.startswith("db-")
        else ("CONTROL_FAILED" if case == "image-mismatch" else "CONTROL_NO_RESPONSE")
    )
    output = tmp_path / "new-run"
    trace_path = tmp_path / "events.jsonl"
    trace_path.write_bytes(b"")
    monkeypatch.setattr(runner, "gate", lambda *a: {"Image": "unit-image"})
    monkeypatch.setattr(runner, "git_sha", lambda: "unit-sha")
    monkeypatch.setattr(runner.subprocess, "check_output", lambda *a, **k: b"")
    control_status = "FAILED" if fault == "CONTROL_FAILED" else "NO_RESPONSE"
    fault_row = {
        "id": "fault-id",
        "status": "REVIEW",
        "control": control_status,
        "processingStatus": "COMPLETED",
        "persistence": "SAVED",
        "errorCode": fault,
        "bin": "DEMO_BIN_01",
        "faults": [fault],
        "timestamp": 1,
    }
    immediate = {
        "id": "auto-1",
        "processingStatus": "COMPLETED",
        "persistence": "SAVED",
        "faults": [],
        "timestamp": 2,
    }
    later = immediate | {"id": "later-normal", "timestamp": 3}
    snap = {
        "revision": 2,
        "capturedAt": 100,
        "state": {
            "running": True,
            "faults": [],
            "concurrency": 1,
            "today": {"bins": {"DEMO_BIN_01": 5}},
        },
    }
    monkeypatch.setattr(
        runner, "snapshot", lambda *a: (snap | {"revision": 0}, [immediate])
    )
    images = (
        [{"id": "image-1", "index": 0, "inspectionId": "fault-id"}]
        if case == "image-mismatch"
        else []
    )

    def api(base, path, payload=None):
        if path == "/health":
            return {"model_version": "unit-model"}
        if path.startswith("/v1/quality/fault-images?"):
            return {"items": images}
        assert path == "/v1/quality/simulator"
        if with_stream:
            trace_path.write_text(
                "".join(json.dumps(e) + "\n" for e in http_events()), encoding="utf-8"
            )
        return {"revision": 1}

    def wait(predicate, **kwargs):
        if predicate.__name__ == "claimed":
            return snap, []
        if predicate.__name__ == "fault_row":
            return fault_row
        if predicate.__name__ == "next_normal":
            return later
        return predicate()

    def records(project, table, fields, inspection_id):
        if table == "control_attempts":
            return [controls()[0] | {"control_status": control_status}]
        if inspection_id == "auto-0":
            return [{"inspection_id": "auto-0"}] if case == "db-unexpected-row" else []
        return [
            {
                "inspection_id": inspection_id,
                "source_reference": "bundle-1",
                "inspection_status": bad_db_statuses.get(case, "COMPLETED"),
                "control_status": "SUCCEEDED"
                if inspection_id == "auto-1"
                else "NO_RESPONSE",
                "target_bin_code": "DEMO_BIN_01",
                "completed_at": "2026-10-14 00:00:01",
                "persistence_status": "SUCCEEDED",
            }
        ]

    monkeypatch.setattr(runner, "api", api)
    monkeypatch.setattr(runner, "wait_for", wait)
    monkeypatch.setattr(runner, "mysql_count", lambda *a: 1)
    monkeypatch.setattr(runner, "mysql_records", records)

    def query(*args):
        if case == "db-query-error":
            raise runner.subprocess.CalledProcessError(1, ["mysql", "secret-password"])
        return "0"

    # Trigger the query error after control evidence has been collected.
    if case == "db-query-error":
        fault = "CONTROL_NO_RESPONSE"
        fault_row["faults"] = [fault]
        fault_row["errorCode"] = fault
    monkeypatch.setattr(runner, "mysql_query", query)
    extra = ["--faults", fault]
    if with_stream:
        extra += ["--http-events", str(trace_path)]
    with pytest.raises(SystemExit) as exc:
        runner.main(arguments(output, *extra))
    evidence = json.loads((output / "fault-evidence.json").read_text(encoding="utf-8"))[
        0
    ]
    assert evidence["actual_send_call_count"] is None
    assert evidence["official_qa_verdict"] == "not assessed"
    if case == "db-no-stream":
        assert evidence["status"] == "부분 충족"
        assert exc.value.code == 1
    elif case == "db-stream":
        assert evidence["next_normal_id"] == "later-normal"
        assert evidence["immediate_next_request"]["inspection_id"] == "auto-1"
        assert evidence["db_error_db_rows"] == []
        assert (
            evidence["immediate_next_db_rows"][0]["persistence_status"] == "SUCCEEDED"
        )
        assert exc.value.code == 0
    elif case == "db-unexpected-row":
        assert evidence["db_error_db_rows"] == [{"inspection_id": "auto-0"}]
        assert evidence["status"] == "실패"
    elif case in bad_db_statuses:
        assert (
            evidence["immediate_next_response"]["response"]["inspection_status"]
            == "COMPLETED"
        )
        assert (
            evidence["immediate_next_db_rows"][0]["inspection_status"]
            == bad_db_statuses[case]
        )
        assert evidence["status"] == "실패"
        assert evidence["error"] == "Immediately next DB save not complete"
        assert exc.value.code == 1
    else:
        assert len(evidence["control_attempts"]) == 1
        if case == "image-mismatch":
            assert evidence["fault_image_items"] == images
            assert evidence["status"] == "실패"
        elif case == "db-query-error":
            assert evidence["error"] == "CalledProcessError"
            assert "secret-password" not in json.dumps(evidence)
        else:
            assert evidence["successful_bin_contribution"]["count"] == 0
            assert evidence["statistics_after"]["today"]["bins"] == {"DEMO_BIN_01": 5}
            assert exc.value.code == 0
