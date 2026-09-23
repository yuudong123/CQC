"""Check exported demo frame provenance, hashes, request metadata and exclusions."""
import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/processed/realtime-apple-arrival-demo"))
    parser.add_argument("--manifest", type=Path, default=Path("data/processed/manifest.csv"))
    args = parser.parse_args()
    read = lambda path: json.loads(path.read_text(encoding="utf-8"))
    summary = read(args.root / "summary.json")
    index = read(args.root / "index.json")
    excluded = set(read(args.root / "excluded-sample-ids.json"))
    with args.manifest.open(encoding="utf-8-sig", newline="") as stream:
        source = {row["sample_id"]: row for row in csv.DictReader(stream)}
    seen = set()
    hashes = Counter()
    total_bytes = 0
    for number, bundle in enumerate(index, 1):
        path = (args.root / bundle["path"]).resolve()
        assert args.root.resolve() in path.parents
        request = read(path / "request.json")
        provenance = read(path / "provenance.json")
        assert set(request) == {"inspection_id", "images", "metadata"}
        assert request["inspection_id"] == bundle["inspection_id"]
        assert len(request["images"]) == len(request["metadata"]) == len(provenance["frames"]) == bundle["frame_count"]
        for i, frame in enumerate(provenance["frames"]):
            key = frame["sample_id"]
            assert key not in excluded and key not in seen
            seen.add(key)
            row = source[key]
            assert row["source_group_id"] == provenance["source_group_id"] == bundle["source_group_id"]
            assert request["images"][i] == frame["file"]
            payload = (path / frame["file"]).read_bytes()
            digest = hashlib.sha256(payload).hexdigest()
            assert digest == frame["sha256"] and len(payload) == int(row["image_size_bytes"]) == frame["bytes"]
            assert payload.startswith(b"\x89PNG\r\n\x1a\n")
            hashes[digest] += 1
            total_bytes += len(payload)
            assert request["metadata"][i] == dict(view_index=i, angle_direction=row["angle_direction"],
                verticality_angle=int(row["verticality_angle"]), horizontality_angle=int(row["horizontality_angle"]))
        if number % 200 == 0:
            print(f"verified={number}/{len(index)}", flush=True)
    assert len(seen) == summary["exported_images"]
    assert total_bytes == summary["estimated_image_bytes"]
    report = dict(verified_images=len(seen), verified_bundles=len(index), excluded_overlap=0,
        repeated_source_sample_ids=0, repeated_content_hashes=sum(count-1 for count in hashes.values()),
        total_image_bytes=total_bytes, metadata_matches_source=True)
    (args.root / "verification.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
