from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE_SPEC = importlib.util.spec_from_file_location(
    "compose_snapshot", ROOT / "scripts/ci/snapshot-compose.py"
)
snapshot_module = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(snapshot_module)


def container(service, *, health="healthy"):
    return {
        "Image": f"sha256:{service}-old",
        "Config": {
            "Labels": {
                "com.docker.compose.project": "cqc",
                "com.docker.compose.service": service,
            },
            "Env": ["MODE=old", "PASSWORD=old$literal${value}"],
            "Cmd": ["sh", "-c", "echo $MODE && old-server"],
            "Entrypoint": None,
            "WorkingDir": "/app",
            "User": "1000",
            "Healthcheck": {
                "Test": ["CMD-SHELL", 'test -n "$MODE"'],
                "Interval": 10_000_000_000,
                "Retries": 5,
            },
        },
        "State": {"Running": True, "Health": {"Status": health}},
        "HostConfig": {
            "RestartPolicy": {"Name": "unless-stopped"},
            "PortBindings": {"8000/tcp": [{"HostIp": "127.0.0.1", "HostPort": "8100"}]},
            "NetworkMode": "cqc_default",
        },
        "Mounts": [
            {
                "Type": "volume",
                "Name": f"cqc_{service}_data",
                "Destination": "/data",
                "RW": True,
            },
            {
                "Type": "bind",
                "Source": "/srv/dataset",
                "Destination": "/dataset",
                "RW": False,
            },
        ],
        "NetworkSettings": {"Networks": {"cqc_default": {"Aliases": [service]}}},
    }


def test_snapshot_preserves_runtime_settings_and_escapes_dollars():
    spec = snapshot_module.snapshot([container("backend")])
    service = spec["services"]["backend"]
    assert service["image"] == "sha256:backend-old"
    assert service["environment"] == ["MODE=old", "PASSWORD=old$$literal$${value}"]
    assert service["command"][-1] == "echo $$MODE && old-server"
    assert service["healthcheck"]["test"][-1] == 'test -n "$$MODE"'
    assert service["ports"][0] == {
        "target": 8000,
        "published": "8100",
        "host_ip": "127.0.0.1",
        "protocol": "tcp",
    }
    assert service["volumes"][0]["source"] == "cqc_backend_data"
    assert service["volumes"][1]["read_only"] is True
    assert spec["networks"]["cqc_default"]["external"] is True
    assert spec["volumes"]["cqc_backend_data"]["external"] is True


def test_snapshot_rejects_unhealthy_previous_version():
    with pytest.raises(ValueError, match="must be running and healthy"):
        snapshot_module.snapshot([container("backend", health="unhealthy")])


def test_snapshot_rejects_ambiguous_scaled_service():
    with pytest.raises(ValueError, match="one Compose container"):
        snapshot_module.snapshot([container("backend"), container("backend")])


def shell_path(path):
    path = Path(path).resolve()
    if os.name == "nt":
        return f"/{path.drive[0].lower()}{path.as_posix()[2:]}"
    return str(path)


@pytest.fixture
def runtime(tmp_path):
    shell = shutil.which("sh")
    if not shell and os.name == "nt":
        shell = "C:/Program Files/Git/bin/bash.exe"
    if not shell or not Path(shell).exists():
        pytest.skip("A POSIX shell is required for deployment-script tests")
    tools = tmp_path / "bin"
    tools.mkdir()
    for name in ("docker", "docker-compose"):
        launcher = tools / name
        launcher.write_text(
            f'#!/bin/sh\nexec "$MOCK_PYTHON" "$MOCK_TOOL" {name} "$@"\n',
            encoding="utf-8",
            newline="\n",
        )
        launcher.chmod(0o755)
    initial = {f"old-{name}": container(name) for name in ("backend", "logistics-web")}
    state = tmp_path / "runtime.json"
    state.write_text(
        json.dumps({"containers": initial, "templates": initial, "calls": []})
    )
    candidate = tmp_path / "candidate.json"
    spec = snapshot_module.snapshot(list(initial.values()))
    for entry in spec["services"].values():
        entry["image"] = entry["image"].replace("old", "new")
        entry["environment"] = ["MODE=new"]
        entry["command"] = ["new-server"]
        entry["ports"][0]["published"] = "9999"
    candidate.write_text(json.dumps(spec))
    env = dict(
        os.environ,
        MOCK_BIN=shell_path(tools),
        MOCK_PYTHON=shell_path(sys.executable),
        MOCK_TOOL=str(ROOT / "tests/ci/fake_docker.py"),
        MOCK_STATE_FILE=str(state),
        MOCK_SNAPSHOT_SCRIPT=str(ROOT / "scripts/ci/snapshot-compose.py"),
        COMPOSE_FILE=str(candidate),
        CQC_DEPLOY_STATE_DIR=str(tmp_path / "deploy-state"),
        HEALTH_SERVICES="backend logistics-web",
        HEALTH_ATTEMPTS="1",
        HEALTH_INTERVAL_SECONDS="0",
    )

    def run(script, **overrides):
        if script.startswith("stage:"):
            stage = re.escape(script.removeprefix("stage:"))
            matched = re.search(
                rf"stage\('{stage}'\).*?sh '''(.*?)'''",
                (ROOT / "Jenkinsfile").read_text(encoding="utf-8"),
                re.DOTALL,
            )
            command = matched.group(1)
        else:
            command = f"sh scripts/ci/{script}"
        return subprocess.run(
            [shell, "-c", f'export PATH="$MOCK_BIN:$PATH"; {command}'],
            cwd=ROOT,
            env=dict(env, **overrides),
            capture_output=True,
            text=True,
            check=False,
        )

    return run, state, tmp_path / "deploy-state", initial


def test_health_failure_restores_old_image_and_runtime_configuration(runtime):
    run, state, directory, initial = runtime
    assert run("compose-deploy.sh", MOCK_CANDIDATE_UNHEALTHY="1").returncode == 0
    assert run("verify-compose-health.sh").returncode == 1
    assert (
        json.loads(state.read_text())["containers"]["candidate-backend"]["Image"]
        == "sha256:backend-new"
    )
    recovered = run("compose-rollback.sh", CQC_FORCE_HEALTH_FAILURE="true")
    assert recovered.returncode == 0, recovered.stderr
    actual = json.loads(state.read_text())["containers"]
    for name in ("backend", "logistics-web"):
        old, restored = initial[f"old-{name}"], actual[f"restored-{name}"]
        assert restored["Image"] == old["Image"]
        assert restored["Config"]["Env"] == old["Config"]["Env"]
        assert restored["Config"]["Cmd"] == old["Config"]["Cmd"]
        assert (
            restored["HostConfig"]["PortBindings"] == old["HostConfig"]["PortBindings"]
        )
    assert not (directory / "pending").exists()


def test_interrupted_deploy_is_recoverable_without_verify(runtime):
    run, _, directory, _ = runtime
    assert run("compose-deploy.sh").returncode == 0
    assert (directory / "pending").exists()
    assert run("compose-rollback.sh").returncode == 0
    assert not (directory / "pending").exists()


def test_partial_deploy_failure_restores_previous_version(runtime):
    run, state, directory, _ = runtime
    assert run("compose-deploy.sh", MOCK_DEPLOY_UP_FAIL="1").returncode == 1
    assert (directory / "pending").exists()
    assert run("compose-rollback.sh").returncode == 0
    restored = json.loads(state.read_text())["containers"]["restored-backend"]
    assert restored["Image"] == "sha256:backend-old"


def test_first_deployment_reports_absence_of_previous_version(runtime):
    run, state, directory, _ = runtime
    current = json.loads(state.read_text())
    current["containers"] = {}
    state.write_text(json.dumps(current))
    assert run("compose-deploy.sh").returncode == 0
    recovered = run("compose-rollback.sh")
    assert recovered.returncode == 1
    assert "no previous deployment" in recovered.stderr
    assert (directory / "pending").exists()


@pytest.mark.parametrize(
    "failure", ["MOCK_ROLLBACK_UP_FAIL", "MOCK_ROLLBACK_UNHEALTHY"]
)
def test_recovery_failure_preserves_snapshot_and_blocks_next_deploy(runtime, failure):
    run, _, directory, _ = runtime
    assert run("compose-deploy.sh").returncode == 0
    assert run("compose-rollback.sh", **{failure: "1"}).returncode != 0
    assert (directory / "pending").exists()
    assert (directory / "rollback.json").exists()
    assert run("compose-deploy.sh").returncode != 0


def test_build_failure_before_deploy_leaves_old_containers_unchanged(runtime):
    run, state, directory, initial = runtime
    assert run("stage:Docker Build", MOCK_BUILD_FAILURE="1").returncode == 1
    # Jenkins skips Deploy when Build fails; unsuccessful calls rollback only if pending.
    assert run("compose-rollback.sh").returncode == 0
    assert json.loads(state.read_text())["containers"] == initial
    assert not directory.exists()


def test_jenkins_build_failure_injection_leaves_old_containers_unchanged(runtime):
    run, state, directory, initial = runtime
    failed = run("stage:Docker Build", FORCE_BUILD_FAILURE="true")
    assert failed.returncode == 1
    assert "[EXPECTED TEST FAILURE]" in failed.stdout
    assert json.loads(state.read_text())["containers"] == initial
    assert not directory.exists()


def test_snapshot_failure_does_not_start_deployment(runtime):
    run, state, directory, _ = runtime
    current = json.loads(state.read_text())
    current["containers"]["old-backend"]["State"]["Health"]["Status"] = "unhealthy"
    state.write_text(json.dumps(current))
    assert run("compose-deploy.sh").returncode != 0
    assert not (directory / "pending").exists()
    actual = json.loads(state.read_text())
    assert actual["containers"] == current["containers"]
    assert not any("up" in call for call in actual["calls"])
