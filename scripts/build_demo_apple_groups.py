"""Export demo-only apple bundles from conservatively unselected source frames."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import shutil
from pathlib import Path
from zipfile import ZipFile

from data.sampling.angle_balanced import select_angle_balanced_random_views
from src.data.multiview import load_groups, select_views


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def selection_exclusions(groups, configs):
    """Superset: apply recorded selectors to ALL groups and planned epochs."""
    signatures = set()
    for config in configs:
        sampling = config.get("sampling") or "fixed"
        if sampling not in {"fixed", "angle_balanced_random"}:
            raise ValueError(f"Unrecognized historical sampling: {sampling}")
        signatures.add((sampling, int(config["views"]), int(config["seed"]),
                        int(config["epochs"]) if sampling != "fixed" else 1))
    excluded = set()
    for group in groups:
        for sampling, views, seed, epochs in sorted(signatures):
            for epoch in range(1, epochs + 1):
                selected = (select_views(group.frames, views) if sampling == "fixed" else
                            select_angle_balanced_random_views(group.frames, views,
                                seed=seed, epoch=epoch, group_no=group.group_no))
                excluded.update(frame.sample_id for frame in selected.real_frames)
    return excluded, sorted(signatures)


def make_bundles(groups, excluded):
    bundles = []
    for group in groups:
        remaining = [frame for frame in group.frames if frame.sample_id not in excluded]
        index = 0
        while remaining:
            selected = select_angle_balanced_random_views(remaining, min(12, len(remaining)),
                seed=42, epoch=index, group_no=group.group_no).real_frames
            bundles.append((group, index, selected))
            ids = {frame.sample_id for frame in selected}
            remaining = [frame for frame in remaining if frame.sample_id not in ids]
            index += 1
    return bundles


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("data/processed/realtime-apple-arrival-demo"))
    parser.add_argument("--manifest", type=Path, default=Path("data/processed/manifest.csv"))
    parser.add_argument("--splits", type=Path, default=Path("configs/splits/seed-42.csv"))
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw"))
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
    digest = hashlib.sha256(args.manifest.read_bytes()).hexdigest()
    if digest.lower() != evidence["manifest_sha256"].lower():
        raise ValueError("Local and training-server manifests differ")
    groups = load_groups(args.manifest, args.splits)
    with args.manifest.open(encoding="utf-8-sig", newline="") as stream:
        rows = {row["sample_id"]: row for row in csv.DictReader(stream)}
    excluded, signatures = selection_exclusions(groups, evidence["configs"])
    # Identical bytes necessarily share CRC32 and length. Conservatively exclude
    # any collision too; no claim that CRC32 is a unique image identifier.
    blocked_content = {(rows[key]["image_crc32"], rows[key]["image_size_bytes"]) for key in excluded}
    excluded.update(key for key, row in rows.items()
                    if (row["image_crc32"], row["image_size_bytes"]) in blocked_content)
    bundles = make_bundles(groups, excluded)
    exported_ids = [frame.sample_id for _, _, frames in bundles for frame in frames]
    if len(exported_ids) != len(set(exported_ids)) or set(exported_ids) & excluded:
        raise ValueError("Repeated or excluded source frame in demo export")
    summary = {
        "purpose": "demo_stream_only_not_training_or_independent_evaluation",
        "same_physical_apples_as_original_dataset": True,
        "exclusion_policy": "all_recorded_selectors_on_all_groups_and_all_planned_epochs",
        "exact_per_batch_consumption_log_available": False,
        "manifest_sha256": digest,
        "training_configs_checked": len(evidence["configs"]),
        "selection_signatures": signatures,
        "total_original_images": len(rows), "excluded_images": len(excluded),
        "exported_images": len(exported_ids),
        "source_apples": len({group.group_no for group, _, _ in bundles}),
        "full_12_frame_bundles": sum(len(frames) == 12 for _, _, frames in bundles),
        "partial_bundles": sum(len(frames) < 12 for _, _, frames in bundles),
        "excluded_overlap": 0,
        "estimated_image_bytes": sum(int(rows[key]["image_size_bytes"]) for key in exported_ids),
    }
    print(json.dumps(summary), flush=True)
    if not args.execute:
        return
    if args.output.exists():
        raise FileExistsError(f"Existing destination is preserved: {args.output}")
    if shutil.disk_usage(args.output.parent).free < summary["estimated_image_bytes"] + 1024**3:
        raise OSError("Insufficient space for demo export")
    args.output.mkdir(parents=True)
    write_json(args.output / "source-training-configs.json", evidence)
    write_json(args.output / "excluded-sample-ids.json", sorted(excluded))
    archives = {}
    index = []
    try:
        for number, (group, bundle_index, frames) in enumerate(bundles, 1):
            demo_id = f"demo-{group.group_no}-{bundle_index:03d}"
            relative = Path("groups" if len(frames) == 12 else "partial_groups") / demo_id
            destination = args.output / relative
            destination.mkdir(parents=True)
            metadata, images, provenance = [], [], []
            for view_index, frame in enumerate(frames):
                archive_path = (args.raw_root / frame.image_archive).resolve()
                if args.raw_root.resolve() not in archive_path.parents:
                    raise ValueError("Archive outside raw root")
                if archive_path not in archives:
                    archives[archive_path] = ZipFile(archive_path)
                value = archives[archive_path].read(frame.image_member)
                name = f"frame_{view_index:02d}.png"
                with (destination / name).open("xb") as stream:
                    stream.write(value)
                images.append(name)
                metadata.append(dict(view_index=view_index, angle_direction=frame.angle_direction,
                    verticality_angle=frame.verticality_angle, horizontality_angle=frame.horizontality_angle))
                provenance.append(dict(file=name, sample_id=frame.sample_id,
                    source_archive=frame.image_archive, source_member=frame.image_member,
                    sha256=hashlib.sha256(value).hexdigest(), bytes=len(value)))
            write_json(destination / "request.json", dict(inspection_id=demo_id, images=images, metadata=metadata))
            write_json(destination / "provenance.json", dict(source_group_id=group.group_no,
                original_split=group.split, same_physical_apple=True, frames=provenance))
            write_json(destination / "expected.json", dict(cultivar=group.cultivar,
                quality_grade=group.quality_grade, send_to_model=False))
            index.append(dict(inspection_id=demo_id, path=relative.as_posix(),
                source_group_id=group.group_no, frame_count=len(frames), default_playback=len(frames)==12))
            if number % 50 == 0:
                print(f"exported_bundles={number}/{len(bundles)}", flush=True)
    finally:
        for archive in archives.values():
            archive.close()
    random.Random(42).shuffle(index)
    write_json(args.output / "index.json", index)
    write_json(args.output / "summary.json", summary)
    print(f"completed output={args.output}", flush=True)


if __name__ == "__main__":
    main()
