"""격리 QA Backend 진입점: 제품 정책을 변경하지 않고 send 호출만 관찰한다."""

import argparse
import atexit
import functools
import hashlib
import json
import os
import platform
import re
import runpy
import threading
import time
from datetime import datetime, timezone
from pathlib import Path


class ControlTrace:
    """모든 Mock 인스턴스의 호출을 검사별로 연결하고 기록 실패를 분리한다."""

    def __init__(self, write):
        self.write = write
        self.calls = {}
        self.sequence = 0
        self.errors = 0
        self.lock = threading.Lock()

    def emit(self, kind, request, call_no, **extra):
        """계측 오류가 제품 반환값이나 예외를 덮어쓰지 않게 한다."""
        try:
            with self.lock:
                self.sequence += 1
                self.write(
                    {
                        "kind": kind,
                        "sequence_no": self.sequence,
                        "pid": os.getpid(),
                        "recording_errors_so_far": self.errors,
                        "inspection_id": request.inspection_id,
                        "call_no": call_no,
                        "requested_bin_code": request.target_bin_code,
                        "utc": datetime.now(timezone.utc).isoformat(),
                        "monotonic_ns": time.monotonic_ns(),
                        **extra,
                    }
                )
        except Exception:  # noqa: BLE001 -- 계측 실패는 제품으로 전파하지 않는다.
            self.errors += 1

    def http_event(self, event):
        """SIM-07 wrapper 형식에 프로세스·순번·기록 오류 상태만 추가한다."""
        try:
            with self.lock:
                self.sequence += 1
                self.write(
                    event
                    | {
                        "sequence_no": self.sequence,
                        "pid": os.getpid(),
                        "recording_errors_so_far": self.errors,
                    }
                )
        except Exception:  # noqa: BLE001 -- HTTP 계측 실패도 원래 전송을 유지한다.
            self.errors += 1

    def install(self, control_class):
        """기존·신규 인스턴스에 공통인 클래스 메서드를 한 번만 감싼다."""
        original = control_class.send
        if getattr(original, "_mo09_traced", False):
            raise ValueError("Control tracing is already installed")

        @functools.wraps(original)
        async def traced(instance, request):
            # 계측 채번 실패도 제품 처리를 막지 않으며 증거에서 누락으로 취급한다.
            call_no = None
            try:
                with self.lock:
                    key = request.inspection_id
                    call_no = self.calls.get(key, 0) + 1
                    self.calls[key] = call_no
            except Exception:  # noqa: BLE001 -- 채번 실패도 제품 호출은 유지한다.
                self.errors += 1
            self.emit("send_enter", request, call_no)
            try:
                response = await original(instance, request)
            except BaseException as error:
                self.emit(
                    "send_raise", request, call_no, error_type=type(error).__name__
                )
                raise
            try:
                status = response.control_status.value
            except Exception:  # noqa: BLE001 -- 계측 필드 접근 오류를 분리한다.
                status = None
                self.errors += 1
            self.emit("send_return", request, call_no, control_status=status)
            return response

        traced._mo09_traced = True
        control_class.send = traced


def install_http_trace(client_class, trace, backend_url):
    """기존 SIM-07 방식으로 직접 전송을 관찰하며 프록시·재시도를 추가하지 않는다."""
    original = client_class.post
    if getattr(original, "_mo09_traced", False):
        raise ValueError("HTTP tracing is already installed")
    target = backend_url.rstrip("/") + "/v1/inspections"

    @functools.wraps(original)
    async def traced(instance, url, *args, **kwargs):
        if str(url) != target:
            return await original(instance, url, *args, **kwargs)
        base = None
        try:
            headers = {k.lower(): v for k, v in kwargs.get("headers", {}).items()}
            base = {
                "inspection_id": kwargs.get("data", {}).get("inspection_id"),
                "source_reference": headers.get("x-cqc-simulator-bundle-id"),
                "faults": [
                    v for v in headers.get("x-cqc-simulator-faults", "").split(",") if v
                ],
                "intervalMs": headers.get("x-cqc-simulator-interval-ms"),
                "start_monotonic": time.monotonic(),
                "started_utc": datetime.now(timezone.utc).isoformat(),
            }
            trace.http_event(base | {"kind": "request_start"})
        except Exception:  # noqa: BLE001 -- metadata 수집 실패도 요청을 보존한다.
            trace.errors += 1

        def finish_request(response=None, error_type=None):
            if base is None:
                return
            try:
                body, parse_error = None, None
                if response is not None:
                    try:
                        value = response.json()
                        if isinstance(value, dict):
                            fields = (
                                "inspection_id",
                                "inspection_status",
                                "control_status",
                                "persistence_status",
                                "error_code",
                                "target_bin_code",
                            )
                            body = {key: value.get(key) for key in fields}
                    except Exception as error:  # noqa: BLE001 -- 원래 HTTP 응답을 보존한다.
                        parse_error = type(error).__name__
                trace.http_event(
                    base
                    | {
                        "kind": "request_end",
                        "http_status": response.status_code
                        if response is not None
                        else None,
                        "response": body,
                        "error_type": error_type,
                        "response_parse_error": parse_error,
                        "end_monotonic": time.monotonic(),
                        "ended_utc": datetime.now(timezone.utc).isoformat(),
                    }
                )
            except Exception:  # noqa: BLE001 -- 종료 계측 오류가 반환·예외를 덮어쓰지 않는다.
                trace.errors += 1

        try:
            response = await original(instance, url, *args, **kwargs)
        except BaseException as error:
            finish_request(error_type=type(error).__name__)
            raise
        finish_request(response=response)
        return response

    traced._mo09_traced = True
    client_class.post = traced


def main(argv=None):
    """QA 전용 옵션 검증 후 동일 프로세스에서 기존 Backend main을 실행한다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--image-id", required=True)
    parser.add_argument(
        "--service", choices=("backend", "simulator"), default="backend"
    )
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args(argv)
    toggle = (
        "CQC_QA_CONTROL_TRACE" if args.service == "backend" else "CQC_QA_HTTP_TRACE"
    )
    if os.environ.get(toggle) != "1":
        parser.error(f"Explicit {toggle}=1 opt-in is required")
    if not re.fullmatch(r"cqc-mo09-e2-[A-Za-z0-9_-]+", args.project):
        parser.error("An isolated cqc-mo09-e2-* project is required")
    if not re.fullmatch(r"[0-9a-f]{40}", args.source_sha) or not re.fullmatch(
        r"sha256:[0-9a-f]{64}", args.image_id
    ):
        parser.error("A full source SHA and image sha256 ID are required")
    if args.output.exists() or args.output.is_symlink():
        parser.error("Trace output already exists; select a new directory")
    backend_url = os.environ.get("SIMULATOR_BACKEND_URL", "")
    if args.service == "simulator" and backend_url != "http://backend:8000":
        parser.error("Docker Simulator must target http://backend:8000")
    if args.check_only:
        return
    args.output.mkdir(parents=True, exist_ok=False)
    filename = (
        "control-events.jsonl" if args.service == "backend" else "http-events.jsonl"
    )
    stream = (args.output / filename).open("x", encoding="utf-8")

    def write(event):
        stream.write(json.dumps(event, ensure_ascii=False) + "\n")
        stream.flush()

    from src.api.control import virtual_control

    trace = ControlTrace(write)
    if args.service == "backend":
        trace.install(virtual_control.MockVirtualControl)
    else:
        import httpx

        install_http_trace(httpx.AsyncClient, trace, backend_url)
    root = Path(virtual_control.__file__).resolve().parents[3]
    files = (
        "src/api/control/virtual_control.py",
        "src/api/services/control_policy.py",
        "src/api/services/inspections.py",
        "src/api/main.py",
    )
    if args.service == "simulator":
        files = (
            "src/simulator/main.py",
            "src/simulator/runner.py",
            "src/simulator/config.py",
        )
    entrypoint = "src.api.main" if args.service == "backend" else "src.simulator.main"
    metadata = {
        "enabled": True,
        "service": args.service,
        "http_target": backend_url + "/v1/inspections"
        if args.service == "simulator"
        else None,
        "http_template": "existing SIM-07 httpx.AsyncClient.post wrapper",
        "python_version": platform.python_version(),
        "pid": os.getpid(),
        "project_declared": args.project,
        "source_sha_declared": args.source_sha,
        "image_id_declared": args.image_id,
        "deployment_identity": "must be verified against container/image inventory",
        "hook_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "product_sha256": {
            name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in files
        },
        "entrypoint": entrypoint,
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "timing_limit": "Synchronous evidence writes add overhead; not performance QA",
    }
    (args.output / "trace-run.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )

    def finish():
        try:
            (args.output / "trace-status.json").write_text(
                json.dumps(
                    {
                        "events_attempted": trace.sequence,
                        "recording_errors": trace.errors,
                        "calls_by_inspection": trace.calls,
                        "pid": os.getpid(),
                    }
                ),
                encoding="utf-8",
            )
            stream.close()
        except Exception:  # noqa: BLE001 -- 종료 증거 실패도 제품 종료를 보존한다.
            trace.errors += 1

    atexit.register(finish)
    runpy.run_module(entrypoint, run_name="__main__")


if __name__ == "__main__":
    main()
