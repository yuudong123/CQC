"""Stateful Docker/Compose stand-in used only by the CI recovery tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def main():
    tool, *args = sys.argv[1:]
    state_path = Path(os.environ["MOCK_STATE_FILE"])
    state = json.loads(state_path.read_text())
    state["calls"].append([tool, *args])
    state_path.write_text(json.dumps(state))
    containers = state["containers"]
    if tool == "docker":
        if args[0] == "ps":
            print("\n".join(containers))
        elif args[0] == "inspect":
            if args[1].startswith("--format="):
                record = containers[args[2]]
                if "com.docker.compose.project" in args[1]:
                    print(record["Config"]["Labels"]["com.docker.compose.project"])
                elif "State.Health" in args[1]:
                    print(record["State"]["Health"]["Status"])
                else:
                    raise AssertionError(args)
            else:
                print(json.dumps([containers[key] for key in args[1:]]))
        elif args[0] == "run":
            if os.environ.get("MOCK_HOST_WORKSPACE_UNAVAILABLE") == "1" and any(
                argument in {"-v", "--volume", "--mount"} for argument in args
            ):
                print("Host Docker cannot mount the client workspace", file=sys.stderr)
                return 1
            python_args = args[args.index("python") + 1 :]
            completed = subprocess.run(
                [sys.executable, *python_args],
                input=sys.stdin.read(),
                text=True,
                capture_output=True,
                check=False,
            )
            sys.stdout.write(completed.stdout)
            sys.stderr.write(completed.stderr)
            return completed.returncode
        else:
            raise AssertionError(args)
        return 0

    assert tool == "docker-compose"
    file_index = args.index("-f")
    spec_path = Path(args[file_index + 1])
    command = args[file_index + 2 :]
    if command[:2] == ["ps", "-q"]:
        service = command[2] if len(command) > 2 else None
        print(
            "\n".join(
                key
                for key, item in containers.items()
                if service is None
                or item["Config"]["Labels"]["com.docker.compose.service"] == service
            )
        )
        return 0
    if command == ["build"]:
        return 1 if os.environ.get("MOCK_BUILD_FAILURE") == "1" else 0
    spec = json.loads(spec_path.read_text())
    if command == ["config", "--services"]:
        print("\n".join(spec["services"]))
        return 0
    assert command == ["up", "-d", "--no-build", "--remove-orphans"]
    rollback = spec_path.name == "rollback.json"
    if rollback and os.environ.get("MOCK_ROLLBACK_UP_FAIL") == "1":
        return 1
    previous = list(containers.values()) or list(state["templates"].values())
    containers.clear()
    for service, entry in spec["services"].items():
        old = next(
            item
            for item in previous
            if item["Config"]["Labels"]["com.docker.compose.service"] == service
        )
        item = json.loads(json.dumps(old))
        item["Image"] = entry["image"]
        item["Config"]["Env"] = [
            value.replace("$$", "$") for value in entry["environment"]
        ]
        item["Config"]["Cmd"] = [value.replace("$$", "$") for value in entry["command"]]
        item["HostConfig"]["PortBindings"] = {
            f"{value['target']}/{value['protocol']}": [
                {"HostIp": value["host_ip"], "HostPort": value["published"]}
            ]
            for value in entry["ports"]
        }
        item["State"]["Health"]["Status"] = (
            "unhealthy"
            if (not rollback and os.environ.get("MOCK_CANDIDATE_UNHEALTHY") == "1")
            or (rollback and os.environ.get("MOCK_ROLLBACK_UNHEALTHY") == "1")
            else "healthy"
        )
        containers[("restored-" if rollback else "candidate-") + service] = item
    state_path.write_text(json.dumps(state))
    if not rollback and os.environ.get("MOCK_DEPLOY_UP_FAIL") == "1":
        return 1
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(newline="\n")
    sys.exit(main())
