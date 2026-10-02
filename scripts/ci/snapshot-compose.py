"""Build a pinned recovery Compose file from CQC Docker inspect JSON.

Read stdin; never log its contents (runtime credentials are included).
Networks and volumes refer to the existing Docker resources.
"""

from __future__ import annotations

import json
import sys


def literal(value):
    """Escape Compose interpolation, including passwords containing dollars."""
    if isinstance(value, str):
        return value.replace("$", "$$")
    if isinstance(value, list):
        return [literal(item) for item in value]
    if isinstance(value, dict):
        return {key: literal(item) for key, item in value.items()}
    return value


def snapshot(containers):
    result = {"services": {}, "networks": {}, "volumes": {}}
    for container in containers:
        config = container["Config"]
        host = container["HostConfig"]
        labels = config.get("Labels") or {}
        service = labels.get("com.docker.compose.service")
        if labels.get("com.docker.compose.oneoff", "False").lower() == "true":
            continue
        if not service or service in result["services"]:
            raise ValueError("Expected one Compose container per service")
        state = container["State"]
        if (
            not state.get("Running")
            or state.get("Health", {}).get("Status") != "healthy"
        ):
            raise ValueError(f"Previous service {service} must be running and healthy")
        if (
            host.get("Privileged")
            or host.get("Devices")
            or host.get("NetworkMode") in {"host", "none"}
        ):
            raise ValueError(f"Unsupported runtime configuration for {service}")

        entry = {
            "image": container["Image"],
            "environment": config.get("Env") or [],
            "command": config.get("Cmd") or [],
            "entrypoint": config.get("Entrypoint") or [],
            "working_dir": config.get("WorkingDir") or "/",
        }
        if config.get("User"):
            entry["user"] = config["User"]
        restart = host.get("RestartPolicy") or {}
        if restart.get("Name"):
            entry["restart"] = restart["Name"]
            if restart["Name"] == "on-failure" and restart.get("MaximumRetryCount"):
                entry["restart"] += f":{restart['MaximumRetryCount']}"
        if config.get("Healthcheck"):
            check = config["Healthcheck"]
            entry["healthcheck"] = {"test": check["Test"]}
            for source, target in (
                ("Interval", "interval"),
                ("Timeout", "timeout"),
                ("StartPeriod", "start_period"),
                ("StartInterval", "start_interval"),
            ):
                if check.get(source):
                    entry["healthcheck"][target] = f"{check[source]}ns"
            if check.get("Retries"):
                entry["healthcheck"]["retries"] = check["Retries"]
        ports = []
        for target, bindings in (host.get("PortBindings") or {}).items():
            port, protocol = target.split("/")
            for binding in bindings or []:
                ports.append(
                    {
                        "target": int(port),
                        "published": str(binding["HostPort"]),
                        "host_ip": binding.get("HostIp") or "0.0.0.0",
                        "protocol": protocol,
                    }
                )
        if ports:
            entry["ports"] = ports
        mounts = []
        for mount in container.get("Mounts", []):
            if mount["Type"] == "volume":
                source = mount["Name"]
                result["volumes"][source] = {"external": True, "name": source}
            elif mount["Type"] == "bind":
                source = mount["Source"]
            else:
                raise ValueError(f"Unsupported mount type for {service}")
            mounts.append(
                {
                    "type": mount["Type"],
                    "source": source,
                    "target": mount["Destination"],
                    "read_only": not mount["RW"],
                }
            )
        if mounts:
            entry["volumes"] = mounts
        networks = {}
        for name in container["NetworkSettings"]["Networks"]:
            result["networks"][name] = {"external": True, "name": name}
            networks[name] = {"aliases": [service]}
        if not networks:
            raise ValueError(f"Missing network for {service}")
        entry["networks"] = networks
        result["services"][service] = entry
    if not result["services"]:
        raise ValueError("No recoverable Compose services")
    return literal(result)


if __name__ == "__main__":
    try:
        json.dump(snapshot(json.load(sys.stdin)), sys.stdout)
    except (KeyError, TypeError, ValueError) as error:
        print(f"Cannot snapshot previous deployment: {error}", file=sys.stderr)
        sys.exit(1)
