"""Run MO restart acceptance checks against a guarded, disposable E2 project."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from run_mo09_acceptance import Result, git_sha, now, write_results
from run_mo09_e2_faults import gate, wait_for
from run_mo09_e2_recovery import PROBE


def docker(*args: str, timeout: int = 40) -> str:
    return subprocess.check_output(
        ["docker", *args], text=True, timeout=timeout
    ).strip()


def get(base: str, path: str) -> dict:
    with urllib.request.urlopen(base + path, timeout=20) as response:
        return json.load(response)


def put(base: str, state: dict) -> dict:
    data = json.dumps(state).encode()
    request = urllib.request.Request(
        base + "/v1/quality/simulator",
        data=data,
        headers={"Content-Type": "application/json"},
        method="PUT",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def state(base: str) -> dict:
    return get(base, "/v1/quality/snapshot")


def change(base: str, **settings) -> dict:
    return put(base, {"expectedRevision": state(base)["revision"], **settings})


def image_items(base: str, category: str | None = None) -> list[dict]:
    suffix = (
        "" if category is None else "?" + urllib.parse.urlencode({"category": category})
    )
    return get(base, "/v1/quality/fault-images" + suffix)["items"]


def preview_hash(base: str, path: str) -> str:
    with urllib.request.urlopen(
        base + path.replace("/api/quality", "/v1/quality"), timeout=20
    ) as response:
        if response.status != 200:
            raise AssertionError("preview did not return 200")
        return hashlib.sha256(response.read()).hexdigest()


def healthy(name: str) -> bool:
    data = json.loads(docker("inspect", name, timeout=15))[0]
    return data["State"]["Health"]["Status"] == "healthy"


def rows(project: str, sql: str) -> list[str]:
    name = f"{project}-mysql-1"
    raw = docker(
        "exec",
        name,
        "sh",
        "-c",
        'MYSQL_PWD="$MYSQL_PASSWORD" mysql -u"$MYSQL_USER" "$MYSQL_DATABASE" -N -e "$1"',
        "sh",
        sql,
        timeout=25,
    )
    return raw.splitlines() if raw else []


def run_case(evidence: dict, case: str, fn) -> None:
    item = {"time_kst": now()}
    evidence["cases"][case] = item
    try:
        item["detail"] = fn()
        item["status"] = "통과"
    except AssertionError as exc:
        item["status"] = "실패"
        item["error"] = f"{type(exc).__name__}: {exc}"
    except (
        subprocess.SubprocessError,
        OSError,
        ValueError,
        KeyError,
        TypeError,
        IndexError,
    ) as exc:
        item["status"] = "차단"
        item["error"] = f"{type(exc).__name__}: {exc}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--backend", default="http://127.0.0.1:18000")
    parser.add_argument("--provenance", type=Path, required=True)
    args = parser.parse_args()
    gate(args.project, args.backend)
    simulator = f"{args.project}-simulator-1"
    backend = f"{args.project}-backend-1"
    mysql = f"{args.project}-mysql-1"
    identities = {}
    for name in (simulator, backend, mysql, f"{args.project}-inference-1"):
        data = json.loads(docker("inspect", name, timeout=15))[0]
        if data["Config"]["Labels"]["com.docker.compose.project"] != args.project:
            raise AssertionError(f"project mismatch: {name}")
        identities[name] = {"image_id": data["Image"], "created_utc": data["Created"]}
    provenance = json.loads(args.provenance.read_text(encoding="utf-8"))
    if not provenance.get("verified"):
        raise AssertionError("verified deployment provenance required")
    expected_images = {
        item["service"]: item["image_id"] for item in provenance["services"]
    }
    for service in ("backend", "inference", "simulator"):
        if (
            identities[f"{args.project}-{service}-1"]["image_id"]
            != expected_images[service]
        ):
            raise AssertionError(f"{service} image differs from verified build")
    args.output.mkdir(parents=True, exist_ok=True)
    evidence = {
        "project": args.project,
        "started_kst": now(),
        "container_identities": identities,
        "deployed_source_sha": provenance["source_sha"],
        "jenkins_build": provenance["jenkins_build"],
        "script_head": git_sha(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "script_branch": subprocess.check_output(
            ["git", "branch", "--show-current"], text=True
        ).strip(),
        "working_tree_dirty": bool(
            subprocess.check_output(["git", "status", "--porcelain"])
        ),
        "cases": {},
    }

    def sim01() -> dict:
        first = state(args.backend)
        s = first["state"]
        component = first["components"]["Simulator"]["status"]
        started_at = json.loads(docker("inspect", simulator))[0]["State"]["StartedAt"]
        startup_age_seconds = (
            datetime.now(timezone.utc)
            - datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        ).total_seconds()
        if not 0 <= startup_age_seconds <= 60:
            raise AssertionError(
                f"startup observation outside first minute: {startup_age_seconds}s"
            )
        before = int(first["state"]["today"]["total"])
        if not (
            component == "healthy"
            and s["running"]
            and s["concurrency"] == 1
            and s["intervalMs"] == 2000
            and first["revision"] == 0
        ):
            raise AssertionError("startup settings/health mismatch")

        def increased():
            current = state(args.backend)["state"]["today"]["total"]
            return current if current > before else None

        later = wait_for(increased, 20)
        return {
            "initial_total": before,
            "later_total": later,
            "revision": 0,
            "component_status": component,
            "interval_ms": 2000,
            "startup_age_seconds": startup_age_seconds,
        }

    run_case(evidence, "QA-SIM-01", sim01)

    def dep05() -> dict:
        migration = docker("exec", backend, "alembic", "current")
        mappings = rows(
            args.project,
            "SELECT bin_code,cultivar,quality_grade,sweetness_band,is_reinspection,is_active FROM bin_mappings ORDER BY bin_code",
        )
        expected = []
        for cultivar in ("fuji", "yanggwang"):
            for grade in ("L", "M", "S"):
                for sweetness in ("less_sweet", "sweet"):
                    expected.append(
                        f"DEMO_BIN_{len(expected) + 1:02d}\t{cultivar}\t{grade}\t{sweetness}\t0\t1"
                    )
        expected.append("TEST_REINSPECTION_BIN\tNULL\tNULL\tNULL\t1\t1")
        if "20260929_02 (head)" not in migration or mappings != expected:
            raise AssertionError("migration or 13 seed mappings differ")
        return {"alembic_current": migration, "bin_mapping_rows": mappings}

    run_case(evidence, "QA-DEP-05", dep05)

    def seed_images() -> dict:
        for index in range(9):
            before = state(args.backend)
            known = {row["id"] for row in before["state"]["history"]}
            revision = before["revision"]
            put(
                args.backend,
                {
                    "expectedRevision": revision,
                    "faults": ["INFERENCE_ERROR"],
                    "scope": "NEXT",
                },
            )
            wait_for(
                lambda revision=revision: (
                    True if state(args.backend)["revision"] >= revision + 2 else None
                ),
                35,
            )

            def seen(known=known):
                for row in state(args.backend)["state"]["history"]:
                    if row["id"] not in known and "INFERENCE_ERROR" in row["faults"]:
                        return row["id"]
                return None

            wait_for(seen, 35)
        images = image_items(args.backend, "SYSTEM_ERROR")
        if len(images) != 100:
            raise AssertionError(f"expected 100 system error images, got {len(images)}")
        return {"system_error_count": len(images)}

    run_case(evidence, "QA-IMG-06-precondition", seed_images)

    def dep06_img07() -> dict:
        if evidence["cases"]["QA-IMG-06-precondition"]["status"] != "통과":
            raise AssertionError("100-image precondition failed")
        change(args.backend, running=False)
        time.sleep(4)
        before = get(args.backend, "/v1/quality/inspections?pageSize=50")
        saved_id = before["items"][0]["id"]
        total = before["total"]
        images = image_items(args.backend, "SYSTEM_ERROR")
        ids = {row["id"] for row in images}
        all_ids = {row["id"] for row in image_items(args.backend)}
        saved_history_ids = sorted(row["id"] for row in before["items"])
        sample = images[0]
        digest = preview_hash(args.backend, sample["previewUrl"])
        docker("restart", backend, mysql, timeout=90)
        wait_for(lambda: True if healthy(mysql) and healthy(backend) else None, 180)
        after = get(args.backend, "/v1/quality/inspections?pageSize=50")
        new_images = image_items(args.backend, "SYSTEM_ERROR")
        new_all_ids = {row["id"] for row in image_items(args.backend)}
        if (
            after["total"] != total
            or sorted(row["id"] for row in after["items"]) != saved_history_ids
        ):
            raise AssertionError("inspection history changed on restart")
        if {row["id"] for row in new_images} != ids:
            raise AssertionError("fault image IDs changed on restart")
        if new_all_ids != all_ids:
            raise AssertionError("full fault image ID set changed on restart")
        if preview_hash(args.backend, sample["previewUrl"]) != digest:
            raise AssertionError("preview bytes changed on restart")
        probe_id = "qa-mo09-restart-" + str(int(time.time() * 1000))
        raw = docker(
            "exec", "-w", "/app", simulator, "python", "-c", PROBE, probe_id, timeout=40
        )
        probe = json.loads(raw.splitlines()[-1])
        evidence["post_restart_probe"] = {
            "http_status": probe["http_status"],
            "body": probe["body"],
        }
        if (
            probe["http_status"] != 200
            or probe["body"].get("persistence_status") != "SUCCEEDED"
        ):
            raise AssertionError(
                f"new inspection status={probe['http_status']}, persistence={probe['body'].get('persistence_status')}"
            )
        if (
            probe["body"].get("decision_reason") != "NORMAL"
            or probe["body"].get("control_status") != "SUCCEEDED"
        ):
            raise AssertionError(
                "first new inspection after restart was not normal/control success"
            )
        change(args.backend, running=True)
        return {
            "history_total_before_after": [total, after["total"]],
            "saved_inspection_id": saved_id,
            "system_image_count": len(ids),
            "all_image_count": len(all_ids),
            "history_ids_before": saved_history_ids,
            "history_ids_after": sorted(row["id"] for row in after["items"]),
            "image_ids_before": sorted(all_ids),
            "image_ids_after": sorted(new_all_ids),
            "sample_image_id": sample["id"],
            "preview_sha256": digest,
            "new_inspection_id": probe_id,
            "new_persistence": "SUCCEEDED",
        }

    run_case(evidence, "QA-DEP-06+QA-IMG-07", dep06_img07)

    def sim08() -> dict:
        if not state(args.backend)["state"]["running"]:
            change(args.backend, running=True)
        configured = change(
            args.backend, faults=["CONTROL_FAILED"], scope="ALL", concurrency=2
        )
        if (
            configured["state"]["faults"] != ["CONTROL_FAILED"]
            or configured["state"]["concurrency"] != 2
        ):
            raise AssertionError("pre-restart fault/concurrency settings did not apply")
        time.sleep(6)
        old_ref = rows(
            args.project,
            "SELECT source_reference FROM inspections ORDER BY created_at DESC, inspection_id DESC LIMIT 1",
        )[0]
        position = json.loads(
            docker("exec", simulator, "cat", "/data/state/position.json")
        )["next_position"]
        index = json.loads(docker("exec", simulator, "cat", "/data/dataset/index.json"))
        order = [row["inspection_id"] for row in index if row.get("default_playback")]
        docker("restart", simulator, timeout=90)
        restarted = json.loads(docker("inspect", simulator))[0]
        boundary = datetime.fromisoformat(
            restarted["State"]["StartedAt"].replace("Z", "+00:00")
        ).strftime("%Y-%m-%d %H:%M:%S.%f")
        wait_for(lambda: True if healthy(simulator) else None, 90)

        def new_rows():
            result = rows(
                args.project,
                f"SELECT source_reference FROM inspections WHERE created_at > '{boundary}' ORDER BY created_at, inspection_id LIMIT 3",
            )
            return result if len(result) >= 3 else None

        first_three = wait_for(new_rows, 35)
        snap = state(args.backend)
        s = snap["state"]
        old_index = order.index(old_ref)
        expected = {order[(old_index + offset) % len(order)] for offset in (-1, 0, 1)}
        if first_three[0] not in expected:
            raise AssertionError("first bundle is not near preserved position")
        positions = [order.index(value) for value in first_three]
        if any((positions[i + 1] - positions[i]) % len(order) != 1 for i in range(2)):
            raise AssertionError("first three bundles are not sequential")
        if not (
            s["faults"] == []
            and s["concurrency"] == 1
            and s["intervalMs"] == 2000
            and s["running"]
            and snap["revision"] == 0
        ):
            raise AssertionError("simulator settings were not reset")
        return {
            "previous_source_reference": old_ref,
            "position_before_restart": position,
            "previous_dataset_index": old_index,
            "first_three_dataset_indexes": positions,
            "simulator_started_at_utc": restarted["State"]["StartedAt"],
            "first_three_source_references": first_three,
            "settings_after": {
                "faults": s["faults"],
                "concurrency": s["concurrency"],
                "intervalMs": s["intervalMs"],
                "running": s["running"],
                "revision": snap["revision"],
            },
        }

    run_case(evidence, "QA-SIM-08", sim08)
    evidence["finished_kst"] = now()
    (args.output / "restart-evidence.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    results = []
    model = (
        evidence.get("post_restart_probe", {})
        .get("body", {})
        .get("model_version", "unverified")
    )
    for case, item in evidence["cases"].items():
        if case == "QA-IMG-06-precondition":
            continue
        names = ("QA-DEP-06", "QA-IMG-07") if case == "QA-DEP-06+QA-IMG-07" else (case,)
        for name in names:
            results.append(
                Result(
                    name,
                    item["status"],
                    "MO QA",
                    item["time_kst"],
                    f"{provenance['source_sha']} / {model}",
                    f"E2 project={args.project}; evidence=restart-evidence.json; "
                    + item.get("error", "all expected checks passed"),
                    "E2",
                )
            )
    write_results(results, args.output)
    print(
        json.dumps(
            {case: item["status"] for case, item in evidence["cases"].items()},
            ensure_ascii=False,
        )
    )
    return (
        0 if all(item["status"] == "통과" for item in evidence["cases"].values()) else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
